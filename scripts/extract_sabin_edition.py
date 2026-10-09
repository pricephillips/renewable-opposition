"""Extract the Sabin Center's September 2026 edition into the 2025 record layout.

Reads the newest stored copies (data/raw/manifest.csv) of the files
scripts/fetch_sabin_edition.py downloads:

  restriction export    one row per restriction entry: ID, title, status,
                        year adopted, level (Local or State), state, county
                        FIPS, municipality, technology, rule lines, citations
  project export        one row per contested project
  web edition (HTML)    the full text of every entry, and the per-state totals
                        the Sabin Center publishes with it
  landing page (HTML)   the report's own headline totals

and writes data/renewable_opposition_records_2026-09.csv with exactly the
columns of data/renewable_opposition_records.csv (the June 2025 extraction),
one row per entry, state-level and local restrictions and every contested
project. Nothing is looked up or invented: each field is copied from the
export or the entry's text, or derived by the rules below.

  record_id             S26R-<export ID> for restrictions, S26P-<export Post
                        iD> for contested projects. The edition renumbers its
                        entries; scripts/sabin_crosswalk.py maps the 2025
                        REC- ids onto these.
  county                the export's county names (the FIPS codes' names from
                        data/county_fips_lookup.json when it lists none),
                        joined with "; " when there are several
  technology            the export's Type, lowercased and comma-joined
  policy_mechanism      one mechanism per rule line, in the
                        build_sabin_seeds.MECHANISM_TYPE vocabulary, with the
                        rule's own technology in parentheses ("setback
                        (wind)"; several joined with "+"). The edition's "Ban /
                        Moratorium" rule is split by the entry's text (the
                        sentences about the rule's technology, else the whole
                        text): a moratorium when it says moratorium and not
                        "permanent", a ban when it says ban or prohibit. When
                        it says neither, or the entry has no text, the
                        mechanism is "ban or moratorium": the
                        edition does not say which, and the build scores it
                        without choosing.
  status                restrictions: In effect -> in_force, Expired ->
                        expired. Projects: Pending -> pending, Canceled ->
                        cancelled, Operational -> operational, Unknown ->
                        unknown.
  adopted_or_event_date_text
                        restrictions: Year Adopted; projects: Date of Last
                        Event (both years)
  short_description     the first sentence of the entry's text; for an entry
                        the edition gives only as rule labels (no text), its
                        title and rule labels ("Uinta County: Setback
                        Restriction (wind)")
  long_description      the entry's full text, rule lines removed (blank for
                        a rule-only entry)
  notes                 the edition entry id, its rule lines, the last-event
                        year when it differs, the litigation venue, and any
                        disagreement between an entry's title and its county
                        columns

It also writes docs/sabin_2026_reconciliation.md: extracted counts against the
totals the Sabin Center prints, overall and per state, with every gap over 2%
listed.

Usage
  python scripts/extract_sabin_edition.py
"""
from __future__ import annotations

import csv
import html
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, STATE_NAMES, read_csv, write_csv  # noqa: E402

RAW_MANIFEST = ROOT / "data" / "raw" / "manifest.csv"
OUT_PATH = ROOT / "data" / "renewable_opposition_records_2026-09.csv"
RECONCILIATION_PATH = ROOT / "docs" / "sabin_2026_reconciliation.md"
FIPS_LOOKUP = ROOT / "data" / "county_fips_lookup.json"
RECORD_FIELDS_2025 = ROOT / "data" / "renewable_opposition_records.csv"

SOURCES = {
    "restrictions": "sabin_2026_09_restrictions_csv",
    "projects": "sabin_2026_09_projects_csv",
    "html": "sabin_2026_09_report_html",
    "landing": "sabin_2026_09_landing_html",
}
FIELDS = [
    "record_id", "state", "county", "municipality", "jurisdiction_level", "record_type",
    "project_or_policy_name", "technology", "policy_mechanism", "opposition_type",
    "adopted_or_event_date_text", "status", "project_capacity_mw", "project_area_acres",
    "has_litigation", "short_description", "long_description", "extraction_source_section", "notes",
]
# The headers the exports must have; anything else stops the extraction.
# The restriction export names two columns "County": the county names, then
# their FIPS codes. The second is read as "County FIPS".
RESTRICTION_HEADER = ["ID", "Title", "Report Year", "Status", "Year Adopted", "Date of Last Event", "Level",
                      "State", "County", "County", "Municipality", "Type", "Content", "Citations"]
PROJECT_HEADER = ["Post iD", "Title", "Report Year", "Status", "Year Cancelled", "Date of Last Event",
                  "Litigation", "Litigation Venue", "State", "County", "County ID", "Municipality", "Type",
                  "Capacity", "Area", "Content", "Citations"]

RESTRICTION_STATUS = {"In effect": "in_force", "Expired": "expired"}
PROJECT_STATUS = {"Pending": "pending", "Canceled": "cancelled", "Operational": "operational",
                  "Unknown": "unknown"}
TYPE_TECH = {"wind": "wind", "solar": "solar", "storage": "storage", "transmission": "transmission"}

# The edition's rule labels -> the build_sabin_seeds.MECHANISM_TYPE vocabulary.
# "Ban / Moratorium" is split by the entry's text (ban_or_moratorium).
RULE_MECHANISM = {
    "setback restriction": "setback",
    "height restriction": "height limit",
    "noise restriction": "noise limit",
    "shadow flicker restriction": "shadow_flicker_limit",
    "size cap": "cap on project size",
    "capacity cap": "cap on capacity",
    "size and capacity cap": "cap on project size",
    "capacity and size cap": "cap on project size",
    "size cap and capacity cap": "cap on project size",
    "density cap": "cap on project size",
    "number cap": "cap on project size",
    "use restriction": "zoning restriction",
    "viewshed restriction": "visual_impact_rule",
}
BAN_OR_MORATORIUM = {"ban / moratorium", "ban/moratorium"}
UNSTATED = "ban or moratorium"
_RULE = re.compile(r"^\s*Rules?\s+[\w\s,&.-]*?:\s*(.+?)\s*$")


class SchemaError(SystemExit):
    """An export whose columns changed: stop rather than misread it."""


# ── Raw files ────────────────────────────────────────────────────────────────

def newest(source_id: str, manifest: list[dict] | None = None) -> Path:
    """The newest stored copy of source_id per data/raw/manifest.csv."""
    rows = manifest if manifest is not None else read_csv(RAW_MANIFEST)
    stored = [r for r in rows if r.get("source_id") == source_id and not r.get("error")
              and r.get("local_path") not in ("", "unchanged")]
    if not stored:
        raise SystemExit(f"No stored copy of {source_id}; run scripts/fetch_sabin_edition.py")
    return ROOT / stored[-1]["local_path"]


def read_export(text: str, header: list[str]) -> list[dict]:
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
    if not rows or rows[0] != header:
        raise SchemaError(f"export columns changed: expected {header}, got {rows[0] if rows else []}")
    names = list(header)
    if names.count("County") == 2:
        names[len(names) - 1 - names[::-1].index("County")] = "County FIPS"
    return [dict(zip(names, r)) for r in rows[1:] if any(c.strip() for c in r)]


# ── Text helpers ─────────────────────────────────────────────────────────────

def strip_tags(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>|</p>\s*<p[^>]*>", "\n", fragment)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def split_rules(content: str) -> tuple[list[str], str]:
    """(rule labels, body text) from an entry's Content or HTML text. A rule
    line may hold several rules separated by '|'."""
    rules, body = [], []
    for line in strip_tags(content).splitlines():
        if line.lstrip().lower().startswith("rule"):
            for part in line.split("|"):
                m = _RULE.match(part)
                if m:
                    rules.append(m.group(1))
            continue
        body.append(line)
    return rules, " ".join(body).strip()


_ABBREV = re.compile(r"\b(?:St|Mt|Ft|No|Nos|Co|Twp|Inc|Jr|Dr|Mr|Ms|Gov|Sen|Rep|Ave|Ord|Res|approx|U\.S|"
                     r"[A-Z])\.$")


def first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"“])", text)
    out = ""
    for p in parts:
        out = f"{out} {p}".strip()
        if not _ABBREV.search(out):
            return out
    return out


TECH_WORDS = {
    "wind": r"\b(wind|turbines?|WECS)\b",
    "solar": r"\b(solar|photovoltaic|PV)\b",
    "storage": r"\b(battery|batteries|storage|BESS)\b",
    "transmission": r"\btransmission\b",
}


def about(text: str, techs: list[str]) -> str:
    """The sentences that name one of techs; the whole text when none does."""
    sentences = re.split(r"(?<=[.;])\s+", text)
    own = [s for s in sentences if any(re.search(TECH_WORDS.get(t, t), s, re.I) for t in techs)]
    return " ".join(own) or text


def ban_or_moratorium(text: str) -> str:
    """'moratorium', 'ban/prohibition' or UNSTATED, from what the text says."""
    t = text.lower()
    if re.search(r"moratori", t) and not re.search(r"\bpermanent", t):
        return "moratorium"
    if re.search(r"\bban(?:s|ned|ning)?\b|prohibit", t):
        return "ban/prohibition"
    if re.search(r"moratori", t):
        return "moratorium"
    return UNSTATED


def rule_techs(label: str, row_techs: list[str]) -> list[str]:
    m = re.search(r"\(([^)]*)\)\s*$", label)
    if not m:
        return row_techs
    return [TYPE_TECH[t.strip().lower()] for t in m.group(1).split(",") if t.strip().lower() in TYPE_TECH]


def mechanisms(rules: list[str], body: str, row_techs: list[str]) -> list[str]:
    out: list[str] = []
    for label in rules:
        name = re.sub(r"\s*\([^)]*\)\s*$", "", label).strip().lower()
        techs = rule_techs(label, row_techs)
        if name in BAN_OR_MORATORIUM:
            # The sentences about the rule's own technology first; the whole
            # text when they name neither.
            mech = ban_or_moratorium(about(body, techs))
            if mech == UNSTATED:
                mech = ban_or_moratorium(body)
        elif name in RULE_MECHANISM:
            mech = RULE_MECHANISM[name]
        else:
            raise SchemaError(f"unknown Sabin rule label {label!r}; map it in RULE_MECHANISM")
        item = f"{mech} ({'+'.join(techs)})" if techs else mech
        if item not in out:
            out.append(item)
    return out


def techs_of(type_field: str) -> list[str]:
    out = []
    for t in type_field.split("|"):
        t = t.strip().lower()
        if not t:
            continue
        if t not in TYPE_TECH:
            raise SchemaError(f"unknown technology {t!r} in the export's Type column")
        out.append(TYPE_TECH[t])
    return out


# ── County names ─────────────────────────────────────────────────────────────

def county_names(lookup_path: Path = FIPS_LOOKUP) -> dict[str, str]:
    """FIPS -> the county's name with its suffix ('Etowah County', 'Caddo
    Parish'), from the longest lookup key for the code."""
    data = json.loads(lookup_path.read_text(encoding="utf-8"))
    best: dict[str, str] = {}
    for k, v in data.items():
        if k.startswith("_"):
            continue
        name = k.rpartition("|")[0]
        if len(name) > len(best.get(v, "")):
            best[v] = name
    return {v: " ".join(w if w in ("and", "of", "the") else w[:1].upper() + w[1:] for w in n.split())
            for v, n in best.items()}


_TRAILING_PLACE = re.compile(r"\s*\(([^()]*(?:County|Counties|Parish|Parishes|Borough|Area)[^()]*)\)\s*$")


def title_counties(title: str) -> str:
    m = _TRAILING_PLACE.search(title)
    return m.group(1) if m else ""


def strip_place(title: str) -> str:
    return _TRAILING_PLACE.sub("", title).strip()


# ── Web edition ──────────────────────────────────────────────────────────────

def html_items(page: str) -> list[dict]:
    """Every entry of the web edition: state, section, status, kind, title, text."""
    out = []
    states = re.split(r'<h2 id="([A-Z]{2})-report">', page)
    for i in range(1, len(states), 2):
        st, body = states[i], states[i + 1]
        parts = re.split(r'<h3 id="[A-Z]{2}-([a-z-]+)">', body)
        for j in range(1, len(parts), 2):
            section, sbody = parts[j], parts[j + 1]
            status = ""
            for m in re.finditer(r'<h4>Restrictions with Status <em>([^<]+)</em></h4>'
                                 r'|<li class="record ([a-z-]+)">(.*?)</li>', sbody, re.S):
                if m.group(1):
                    status = m.group(1).strip()
                    continue
                li = m.group(3)
                title = re.search(r'<span class="record-title">(.*?)</span>', li, re.S)
                text = re.search(r'<div class="record-text">(.*?)</div>\s*<div class="record-citation">', li, re.S)
                if not title or "data.restrictions" in li:
                    continue  # the page's client-side template, not an entry
                out.append({"state": st, "section": section, "status": status, "kind": m.group(2),
                            "title": strip_tags(title.group(1)), "text": text.group(1) if text else ""})
    return out


def reported_totals(page: str) -> dict[str, dict[str, int]]:
    """Per state: local restrictions in effect (res_loc), state-level ones in
    effect (res_sta) and contested projects, as the web edition's map prints them."""
    m = re.search(r"AmCharts\.wpChartData = (\{.*?\});", page, re.S)
    if not m:
        raise SchemaError("the web edition no longer carries its per-state totals (AmCharts.wpChartData)")
    data = json.loads(m.group(1))
    return {s["id"].removeprefix("US-"): {"res_loc": s.get("res_loc") or 0, "res_sta": s.get("res_sta") or 0,
                                          "projects": s.get("projects") or 0} for s in data["states"]}


def headline_totals(page: str) -> dict[str, int]:
    text = re.sub(r"\s+", " ", strip_tags(page))
    m = re.search(r"at least ([\d,]+) state and local restrictions.*?at least ([\d,]+) projects"
                  r".*?across (\d+) states", text)
    if not m:
        raise SchemaError("the landing page no longer states the report's totals")
    return {"restrictions": int(m.group(1).replace(",", "")), "projects": int(m.group(2).replace(",", "")),
            "states": int(m.group(3))}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def attach_text(rows: list[dict], items: list[dict], section_of, status_of) -> list[str]:
    """Give each export row the full text of its web-edition entry, matched on
    state, section, status and title; several entries with one title are told
    apart by their rule line and opening words. Returns the ids left unmatched."""
    pool: dict[tuple, list[dict]] = {}
    for it in items:
        pool.setdefault((it["state"], it["section"], it["status"], _norm(it["title"])), []).append(it)
    missing = []
    for r in rows:
        key = (r["State"], section_of(r), status_of(r), _norm(r["Title"]))
        cands = pool.get(key, [])
        if len(cands) > 1:
            rules, body = split_rules(r["Content"])
            sig = _norm(" ".join(rules) + " " + body[:120])
            scored = sorted(cands, key=lambda it: -_overlap(sig, _norm(" ".join(split_rules(it["text"])[0])
                                                                         + " " + split_rules(it["text"])[1][:120])))
            best = scored[0]
            first = _overlap(sig, _norm(" ".join(split_rules(best["text"])[0]) + " " + split_rules(best["text"])[1][:120]))
            second = _overlap(sig, _norm(" ".join(split_rules(scored[1]["text"])[0]) + " "
                                         + split_rules(scored[1]["text"])[1][:120]))
            cands = [best] if first > second else []
        if len(cands) == 1:
            r["_html"] = cands[0]["text"]
            pool[key].remove(cands[0])
        else:
            missing.append(r.get("ID") or r.get("Post iD"))
    return missing


def _overlap(a: str, b: str) -> float:
    x, y = set(a.split()), set(b.split())
    return len(x & y) / len(x | y) if x | y else 0.0


# ── Mapping ──────────────────────────────────────────────────────────────────

def map_restriction(r: dict, names: dict[str, str]) -> dict:
    rules, body = split_rules(r.get("_html") or r["Content"])
    if not body:
        body = split_rules(r["Content"])[1]
    techs = techs_of(r["Type"])
    codes = [c for c in r["County FIPS"].split("|") if c]
    listed = [c.strip() for c in r["County"].split("|") if c.strip()]
    county = "; ".join(listed) or "; ".join(names[c.zfill(5)] for c in codes if names.get(c.zfill(5)))
    level = r["Level"].strip().lower()
    notes = [f"Sabin 2026 entry {r['ID']}"]
    if rules:
        notes.append("rules: " + " | ".join(rules))
    if r["Date of Last Event"] and r["Date of Last Event"] != r["Year Adopted"]:
        notes.append(f"last event {r['Date of Last Event']}")
    if codes:
        notes.append(f"county FIPS {', '.join(codes)}")
    return {
        "record_id": f"S26R-{r['ID']}",
        "state": r["State"].strip(),
        "county": county if level == "local" else "",
        "municipality": r["Municipality"].strip(),
        "jurisdiction_level": "state" if level == "state" else "local",
        "record_type": "state_restriction" if level == "state" else "local_restriction",
        "project_or_policy_name": r["Title"].strip() if level == "state" else "",
        "technology": ", ".join(techs),
        "policy_mechanism": ", ".join(mechanisms(rules, body, techs)),
        "opposition_type": "",
        "adopted_or_event_date_text": r["Year Adopted"].strip(),
        "status": RESTRICTION_STATUS[r["Status"].strip()],
        "project_capacity_mw": "", "project_area_acres": "", "has_litigation": "",
        # An entry the edition gives only as its rule labels is described by them.
        "short_description": first_sentence(body) or f"{r['Title'].strip()}: {' | '.join(rules)}",
        "long_description": body,
        "extraction_source_section": "state_level_restrictions" if level == "state" else "local_restrictions",
        "notes": "; ".join(notes),
    }


def map_project(r: dict) -> dict:
    body = split_rules(r.get("_html") or r["Content"])[1] or split_rules(r["Content"])[1]
    counties = [c.strip() for c in r["County"].split("|") if c.strip()]
    notes = [f"Sabin 2026 entry {r['Post iD']}"]
    if r["Litigation Venue"].strip():
        notes.append(f"litigation venue: {r['Litigation Venue'].strip().replace('|', ', ')}")
    if r["Year Cancelled"].strip():
        notes.append(f"cancelled {r['Year Cancelled'].strip()}")
    said = title_counties(r["Title"])
    if said and counties:
        words = {w for w in _norm(said).split() if w not in ("county", "counties", "and", "parish")}
        have = {w for c in counties for w in _norm(c).split() if w not in ("county", "parish")}
        if words - have:
            notes.append(f"title names {said}, county columns name {', '.join(counties)}")
    status = r["Status"].strip()
    if status not in PROJECT_STATUS:
        raise SchemaError(f"unknown project status {status!r}")
    lit = r["Litigation"].strip().lower()
    return {
        "record_id": f"S26P-{r['Post iD']}",
        "state": r["State"].strip(),
        "county": "; ".join(counties),
        "municipality": r["Municipality"].strip(),
        "jurisdiction_level": "contested_project",
        "record_type": "contested_project",
        "project_or_policy_name": strip_place(r["Title"]),
        "technology": ", ".join(techs_of(r["Type"])),
        "policy_mechanism": "",
        "opposition_type": "litigation" if lit == "yes" else "",
        "adopted_or_event_date_text": r["Date of Last Event"].strip(),
        "status": PROJECT_STATUS[status],
        "project_capacity_mw": r["Capacity"].strip(),
        "project_area_acres": r["Area"].strip(),
        "has_litigation": {"yes": "yes", "no": "no"}.get(lit, ""),
        "short_description": first_sentence(body),
        "long_description": body,
        "extraction_source_section": "contested_projects",
        "notes": "; ".join(notes),
    }


def extract(restrictions: list[dict], projects: list[dict], page: str,
            names: dict[str, str]) -> tuple[list[dict], list[str]]:
    items = html_items(page)
    unmatched = attach_text(restrictions, items,
                            lambda r: "state-restrictions" if r["Level"] == "State" else "local-restrictions",
                            lambda r: r["Status"].strip())
    unmatched += attach_text(projects, items, lambda r: "contested-projects", lambda r: "")
    records = [map_restriction(r, names) for r in restrictions] + [map_project(r) for r in projects]
    records.sort(key=lambda x: (x["extraction_source_section"], x["state"], x["record_id"]))
    return records, unmatched


# ── Reconciliation ───────────────────────────────────────────────────────────

def reconcile(records: list[dict], per_state: dict[str, dict[str, int]], headline: dict[str, int]) -> dict:
    def count(section: str, status: str | None = None) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in records:
            if r["extraction_source_section"] == section and (status is None or r["status"] == status):
                out[r["state"]] = out.get(r["state"], 0) + 1
        return out

    loc, sta, proj = count("local_restrictions", "in_force"), count("state_level_restrictions", "in_force"), \
        count("contested_projects")
    loc_exp = count("local_restrictions", "expired")
    sta_exp = count("state_level_restrictions", "expired")
    rows, gaps = [], []
    for st in sorted(set(per_state) | set(loc) | set(sta) | set(proj)):
        rep = per_state.get(st, {"res_loc": 0, "res_sta": 0, "projects": 0})
        row = {"state": st, "local_x": loc.get(st, 0), "local_r": rep["res_loc"], "state_x": sta.get(st, 0),
               "state_r": rep["res_sta"], "proj_x": proj.get(st, 0), "proj_r": rep["projects"],
               "expired": loc_exp.get(st, 0) + sta_exp.get(st, 0)}
        rows.append(row)
        for what, x, r in (("local restrictions in effect", row["local_x"], row["local_r"]),
                           ("state restrictions in effect", row["state_x"], row["state_r"]),
                           ("contested projects", row["proj_x"], row["proj_r"])):
            if x != r and (r == 0 or abs(x - r) / r > 0.02):
                gaps.append(f"{st} {what}: extracted {x}, reported {r}")
    restrictions = sum(1 for r in records if r["extraction_source_section"] != "contested_projects")
    projects = sum(1 for r in records if r["extraction_source_section"] == "contested_projects")
    states = len({r["state"] for r in records if r["extraction_source_section"] == "contested_projects"})
    return {"rows": rows, "gaps": gaps, "restrictions": restrictions, "projects": projects, "states": states,
            "headline": headline}


def render_reconciliation(rec: dict, unmatched: list[str]) -> str:
    h = rec["headline"]

    def pct(x: int, r: int) -> str:
        return f"{(x - r) / r * 100:+.1f}%" if r else "n/a"

    lines = [
        "# Sabin Center September 2026 edition: extracted against reported",
        "",
        "Written by `scripts/extract_sabin_edition.py`. Source: the Sabin Center's own export of the",
        "edition's entries and its web edition at oppositionreport.org (stored under `data/raw/`). The",
        "report PDF could not be downloaded from this session (see `data/raw/manifest.csv`), so the",
        "per-state counts below are checked against the totals the web edition publishes beside the",
        "report, and the headline totals against the edition's landing page.",
        "",
        "## Totals",
        "",
        "| | Extracted | Reported | Gap |",
        "|---|---:|---:|---:|",
        f"| State and local restrictions (in effect and expired) | {rec['restrictions']} | "
        f"at least {h['restrictions']} | {pct(rec['restrictions'], h['restrictions'])} |",
        f"| Contested projects | {rec['projects']} | at least {h['projects']} | "
        f"{pct(rec['projects'], h['projects'])} |",
        f"| States with a contested project | {rec['states']} | {h['states']} | |",
        f"| States with any entry | {len(rec['rows'])} | | |",
        "",
        "## Per state",
        "",
        "Reported: the per-state figures the web edition's map prints (local and state-level",
        "restrictions in effect, contested projects). The map does not count expired restrictions, so",
        "they are listed on their own.",
        "",
        "| State | Local in effect, extracted | Reported | State-level in effect, extracted | Reported | "
        "Projects, extracted | Reported | Expired (not on the map) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rec["rows"]:
        lines.append(f"| {r['state']} {STATE_NAMES.get(r['state'], '')} | {r['local_x']} | {r['local_r']} | "
                     f"{r['state_x']} | {r['state_r']} | {r['proj_x']} | {r['proj_r']} | {r['expired']} |")
    lines += ["", "## Gaps over 2%", ""]
    lines += [f"- {g}" for g in rec["gaps"]] or ["- None: every per-state count matches the reported figure."]
    lines += ["", "## Entries without web-edition text", ""]
    lines += [f"- export id {u}: text taken from the export's Content column" for u in unmatched] or [
        "- None: every export row was matched to its web-edition entry."]
    return "\n".join(lines) + "\n"


def main() -> int:
    manifest = read_csv(RAW_MANIFEST)
    restrictions = read_export(newest(SOURCES["restrictions"], manifest).read_text(encoding="utf-8-sig"),
                               RESTRICTION_HEADER)
    projects = read_export(newest(SOURCES["projects"], manifest).read_text(encoding="utf-8-sig"), PROJECT_HEADER)
    page = newest(SOURCES["html"], manifest).read_text(encoding="utf-8")
    landing = newest(SOURCES["landing"], manifest).read_text(encoding="utf-8")
    header_2025 = list(read_csv(RECORD_FIELDS_2025)[0].keys())
    if header_2025 != FIELDS:
        raise SchemaError(f"data/renewable_opposition_records.csv columns are {header_2025}; FIELDS must match")
    records, unmatched = extract(restrictions, projects, page, county_names())
    write_csv(OUT_PATH, records, FIELDS)
    rec = reconcile(records, reported_totals(page), headline_totals(landing))
    RECONCILIATION_PATH.write_text(render_reconciliation(rec, unmatched), encoding="utf-8")
    print(f"Wrote {OUT_PATH.relative_to(ROOT)}: {rec['restrictions']} restrictions, {rec['projects']} projects, "
          f"{rec['states']} states; {len(rec['gaps'])} per-state gap(s) over 2%; "
          f"{len(unmatched)} entr(ies) without web-edition text")
    print(f"Wrote {RECONCILIATION_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
