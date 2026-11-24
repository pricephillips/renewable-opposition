"""County briefs: plain-English summaries of one county's renewables record.

A brief is 3 to 5 bullets for the top of a county page and one or two
sentences that open each page section, the way the Key Takeaways open a
Hawthorn case study. Its format and the check it must pass are shared with
data-centers (scripts/brief_core.py, pinned by config/brief_format.lock);
config/county_brief.json says which sections a renewables brief has, which
terms it may not use, and the house wording.

How a brief is made (docs/VERIFICATION_ROUTINE.md, county briefs):

  1. `facts --fips F` builds the county's fact sheet from the published
     tables only: each local instrument (restrictions.csv, once per
     instrument), the state's siting law (state_policies.csv), contested
     projects (contested_projects.csv) and cases (cases.csv), each with its
     record id and source URL, and the state's township rule
     (config/county_zoning_authority.json). Severity and the county scores
     are never in it: clients do not see them.
  2. `worklist` lists the counties to draft this run: those in
     county_brief.json's worklist.first, then any with a published brief
     whose fact sheet has changed, at most worklist.per_run.
  3. `card --fips F` prints what the brief-drafter agent is given: the fact
     sheet, its digest, the house wording and the township sentence.
  4. The drafter writes the brief; the brief-reviewer agent, given the card
     and the brief's text but not the drafter's notes, checks each sentence
     against the facts it cites; the session runs the humanizer pass and
     appends the brief to data/review/county_briefs.jsonl.
  5. `publish` (run by the build) checks every brief against the county's
     current fact sheet and writes the ones that pass, newest per county, to
     data/processed/county_briefs.json and .csv (one row per bullet or
     line, which the client builder reads). A brief whose records have changed
     since it was drafted fails as stale and is not shown until redrafted.

Usage
  python scripts/county_briefs.py facts --fips 21181
  python scripts/county_briefs.py worklist
  python scripts/county_briefs.py card --fips 21181
  python scripts/county_briefs.py blind --draft .packets/RUN/brief/21181.draft.json
  python scripts/county_briefs.py accept --draft ...draft.json --review ...review.json
  python scripts/county_briefs.py check
  python scripts/county_briefs.py publish
  python scripts/county_briefs.py compare-lock --lock SIBLING.lock
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import brief_core  # noqa: E402
import geo  # noqa: E402
import site_profile  # noqa: E402
import state_policies  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "county_brief.json"
ZONING = ROOT / "config" / "county_zoning_authority.json"
DRAFTS = ROOT / "data" / "review" / "county_briefs.jsonl"
PUBLISHED = ROOT / "data" / "processed" / "county_briefs.json"
# One row per bullet or section line, for the datapackage and the client
# builder (data-centers scripts/build_client_db.py reads it at the pinned commit).
PUBLISHED_CSV = PUBLISHED.with_suffix(".csv")
CSV_FIELDS = ["brief_row_id", "county_fips", "product", "part", "position", "text", "facts", "facts_digest",
              "drafter", "reviewer", "drafted_on", "reviewed_on"]
LOCK = ROOT / "config" / "brief_format.lock"
CORE = ROOT / "scripts" / "brief_core.py"

# Fields a fact carries, by table. Anything that changes with the calendar
# (months_in_force) is left out, so a sheet changes only when a record does.
RESTRICTION_VALUES = ["jurisdiction", "jurisdiction_type", "restriction_type", "status", "currency",
                      "date_enacted_iso",
                      "date_text", "ends_on", "extensions", "last_extended_on", "scope", "verification"]
POLICY_VALUES = ["policy_type", "who_decides", "state_body", "threshold_mw", "statute_citation", "verification"]
PROJECT_VALUES = ["project_name", "outcome", "status", "event_date_text", "capacity_mw", "area_acres",
                  "municipality", "resolution_date", "facility_status", "verification"]
CASE_VALUES = ["case_name", "court", "court_level", "docket_number", "case_status", "project_name", "verification"]


def load_config(path: Path = CONFIG) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def township_rule(state: str, zoning: dict | None = None) -> dict:
    """The state's township rule: {} where config/county_zoning_authority.json
    records none (no townships, or not yet read)."""
    zoning = zoning if zoning is not None else json.loads(ZONING.read_text(encoding="utf-8"))
    t = (zoning.get("states", {}).get(state) or {}).get("township_land_use") or {}
    return {k: t[k] for k in ("role", "basis", "confidence") if t.get(k)}


def _values(r: dict, fields: list[str]) -> dict:
    return {k: r[k] for k in fields if r.get(k)}


def _techs(rows: list[dict]) -> str:
    return ", ".join(sorted({t for r in rows for t in str(r.get("technology", "")).split(";") if t}))


def _url(r: dict) -> str:
    return r.get("primary_source_url") or r.get("statute_url") or r.get("case_source_url") or r.get("source_url", "")


def facts(d: site_profile.Data, fips: str, cfg: dict | None = None, zoning: dict | None = None) -> dict:
    """The county's fact sheet in the shared format (brief_core.FACTS_FORMAT)."""
    cfg = cfg or load_config()
    fips = fips.zfill(5)
    st = site_profile.state_of(d, fips)
    here = [r for r in d.restrictions if fips in site_profile.fips_set(r)]
    projects = [r for r in d.projects if fips in site_profile.fips_set(r)]
    linked = {r.get("source_record_id") for r in here + projects if r.get("source_record_id")}
    cases = list({(c.get("case_name"), c.get("court"), c.get("docket_number")): c
                  for c in d.cases if c.get("source_record_id") in linked}.values())
    by_kind = {
        "restrictions": [
            {"id": g[0].get("instrument_id") or g[0]["id"], "text": g[0].get("description", ""),
             "values": {**_values(g[0], RESTRICTION_VALUES), "technology": _techs(g)}, "source_url": _url(g[0])}
            for g in site_profile._instruments(here)],
        "state_policies": [
            {"id": r["id"], "text": r.get("summary", ""), "values": {**_values(r, POLICY_VALUES),
                                                                      "technology": _techs([r])},
             "source_url": _url(r)}
            for r in state_policies.framework(d.policies, st)],
        "contested_projects": [
            {"id": r["id"], "text": r.get("description", ""),
             "values": {**_values(r, PROJECT_VALUES), "technology": _techs([r])}, "source_url": _url(r)}
            for r in projects],
        "cases": [
            {"id": c.get("case_id") or c["id"], "text": c.get("description", ""),
             "values": _values(c, CASE_VALUES), "source_url": _url(c)}
            for c in cases],
    }
    for rows in by_kind.values():
        rows.sort(key=lambda f: f["id"])
    sheet = {"format": brief_core.FACTS_FORMAT, "format_version": brief_core.FORMAT_VERSION,
             "product": cfg["product"], "fips": fips, "county": geo.name(fips), "state": st,
             "as_of": d.as_of,
             "sections": {s["id"]: {"title": s["title"], "facts": by_kind.get(s["facts"], [])}
                          for s in cfg["sections"]},
             "rules": {"township": township_rule(st, zoning)}}
    sheet["made_by"] = {"script": "scripts/county_briefs.py", "config_version": cfg.get("version"),
                        "commit": _commit()}
    sheet["digest"] = brief_core.facts_digest(sheet)
    return sheet


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def card(sheet: dict, cfg: dict | None = None) -> dict:
    """What the drafter (and, without the draft's notes, the reviewer) reads."""
    cfg = cfg or load_config()
    rule = sheet["rules"].get("township") or {}
    wording = cfg["township"].get(rule.get("role", ""), "")
    return {"fips": sheet["fips"], "county": sheet["county"], "state": sheet["state"],
            "facts_digest": sheet["digest"], "style": cfg["style"], "refused": cfg["refused"],
            "township_sentence": wording.format(state=site_profile.STATE_NAMES.get(sheet["state"], sheet["state"])),
            "limits": {"headline": [brief_core.HEADLINE_MIN, brief_core.HEADLINE_MAX],
                       "section_sentences": brief_core.SECTION_MAX_SENTENCES, "words": brief_core.MAX_WORDS},
            "sheet": sheet}


def drafts(path: Path = DRAFTS) -> dict[str, dict]:
    """The newest brief per county in the review file (later lines win)."""
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            b = json.loads(line)
            out[b["fips"]] = b
    return out


def checked(d: site_profile.Data, cfg: dict, briefs: dict[str, dict]) -> dict[str, list[str]]:
    zoning = json.loads(ZONING.read_text(encoding="utf-8"))
    return {f: brief_core.check(b, facts(d, f, cfg, zoning), refused=cfg["refused"])
            for f, b in sorted(briefs.items())}


def worklist(d: site_profile.Data, cfg: dict, briefs: dict[str, dict]) -> list[str]:
    zoning = json.loads(ZONING.read_text(encoding="utf-8"))
    out = []
    first = [f.zfill(5) for f in cfg["worklist"]["first"]]
    for f in first + sorted(set(briefs) - set(first)):
        b = briefs.get(f)
        if b is None or b.get("facts_digest") != facts(d, f, cfg, zoning)["digest"]:
            out.append(f)
    return out[: cfg["worklist"]["per_run"]]


def publish(d: site_profile.Data, cfg: dict, briefs: dict[str, dict], path: Path = PUBLISHED) -> dict:
    problems = checked(d, cfg, briefs)
    ok = {f: briefs[f] for f, p in problems.items() if not p}
    doc = {"_comment": "Written by scripts/county_briefs.py publish; do not edit. Briefs that pass "
                       "brief_core.check against the county's current fact sheet, one per county.",
           "format": brief_core.BRIEF_FORMAT, "format_version": brief_core.FORMAT_VERSION,
           "product": cfg["product"], "as_of": d.as_of,
           "sections": [s["id"] for s in cfg["sections"]],
           "briefs": [ok[f] for f in sorted(ok)],
           "held": {f: p for f, p in problems.items() if p}}
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    rows = []
    for b in doc["briefs"]:
        m = b["made_by"]
        items = [("headline", i, x) for i, x in enumerate(b["headline"], 1)]
        items += [(k, 1, v) for k, v in b["sections"].items()]
        for part, pos, x in items:
            rows.append({"brief_row_id": f"{b['fips']}:{part}:{pos}", "county_fips": b["fips"], "product": b["product"],
                         "part": part, "position": pos, "text": x["text"], "facts": ";".join(x["facts"]),
                         "facts_digest": b["facts_digest"], "drafter": m["drafter"], "reviewer": m["reviewer"],
                         "drafted_on": m.get("drafted_on", ""), "reviewed_on": m.get("reviewed_on", "")})
    with open(path.with_suffix(".csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    if path == PUBLISHED:  # the data dictionary counts this file's rows
        import datapackage
        (path.parent / "datapackage.json").write_text(
            json.dumps(datapackage.build(path.parent), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def blind(draft: dict, sheet: dict, cfg: dict | None = None) -> dict:
    """The reviewer's card: the facts and each drafted item's text and cited
    facts, never the drafter's note or signature."""
    return {"packet": "blind", "queue": "brief", "key": sheet["fips"], "card": card(sheet, cfg),
            "claims": [{"where": f"headline {i}", "text": b["text"], "facts": b["facts"]}
                       for i, b in enumerate(draft.get("headline") or [], 1)]
            + [{"where": f"section {k}", "text": v["text"], "facts": v["facts"]}
               for k, v in (draft.get("sections") or {}).items()],
            "expect": {"packet": "review", "queue": "brief", "key": sheet["fips"], "facts_digest": sheet["digest"],
                       "agent": "", "date": "", "verdict": "confirmed | contradicts",
                       "items": [{"where": "headline 1", "supported": True, "problem": ""}], "note": ""}}


def accept(draft: dict, review: dict, sheet: dict, cfg: dict) -> tuple[dict, list[str]]:
    """The brief a confirmed draft and review make, and every reason it may
    not be appended to data/review/county_briefs.jsonl."""
    import review_packets
    problems = []
    for p in (draft, review):
        errs, _ = review_packets.check_packet(p)
        problems += [f"{p.get('packet')}: {e}" for e in errs]
    if draft.get("key") != sheet["fips"] or review.get("key") != sheet["fips"]:
        problems.append("the draft and review must both be for this county")
    if review.get("verdict") != "confirmed":
        problems.append("the review does not confirm the draft")
    if draft.get("facts_digest") != review.get("facts_digest"):
        problems.append("the draft and review were made from different cards")
    brief = {"format": brief_core.BRIEF_FORMAT, "format_version": brief_core.FORMAT_VERSION,
             "product": cfg["product"], "fips": sheet["fips"], "facts_digest": draft.get("facts_digest"),
             "as_of": sheet.get("as_of"),
             "made_by": {"drafter": draft.get("agent"), "reviewer": review.get("agent"),
                         "drafted_on": draft.get("date"), "reviewed_on": review.get("date"),
                         "config_version": cfg.get("version"), "commit": sheet["made_by"]["commit"]},
             "headline": [{"text": b["text"], "facts": list(b["facts"])} for b in draft.get("headline") or []],
             "sections": {k: {"text": v["text"], "facts": list(v["facts"])}
                          for k, v in (draft.get("sections") or {}).items()}}
    problems += brief_core.check(brief, sheet, refused=cfg["refused"])
    return brief, problems


def compare_lock(other: Path, lock: Path = LOCK, core: Path = CORE) -> list[str]:
    """Every way this repository's brief format differs from its lock or from
    the sibling repository's lock (brief-format.yml)."""
    import hashlib
    mine = json.loads(lock.read_text(encoding="utf-8"))
    theirs = json.loads(other.read_text(encoding="utf-8"))
    out = []
    if hashlib.sha256(core.read_bytes()).hexdigest() != mine["core_sha256"]:
        out.append(f"{core.name} differs from {lock.name}: bump the lock here and in data-centers")
    if mine["format_version"] != brief_core.FORMAT_VERSION:
        out.append("format_version in the lock differs from brief_core.FORMAT_VERSION")
    for k in ("format_version", "core_sha256"):
        if mine.get(k) != theirs.get(k):
            out.append(f"{k} differs from the sibling's lock")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["facts", "card", "blind", "accept", "worklist", "check", "publish",
                                        "compare-lock"])
    ap.add_argument("--fips")
    ap.add_argument("--draft", type=Path, help="blind, accept: the brief-drafter's packet")
    ap.add_argument("--review", type=Path, help="accept: the blind-reviewer's packet")
    ap.add_argument("--lock", type=Path, help="compare-lock: the sibling repository's brief_format.lock")
    a = ap.parse_args(argv)
    if a.command == "compare-lock":
        problems = compare_lock(a.lock or LOCK)
        print("\n".join(problems) or "brief format: lock matches")
        return 1 if problems else 0
    cfg = load_config()
    d = site_profile.Data(local=False)
    if a.command in ("facts", "card"):
        if not a.fips:
            ap.error("--fips is required")
        sheet = facts(d, a.fips, cfg)
        print(json.dumps(sheet if a.command == "facts" else card(sheet, cfg), indent=1, ensure_ascii=False))
        return 0
    if a.command in ("blind", "accept"):
        if not a.draft or (a.command == "accept" and not a.review):
            ap.error("--draft (and, for accept, --review) is required")
        draft = json.loads(a.draft.read_text(encoding="utf-8"))
        sheet = facts(d, draft["key"], cfg)
        if a.command == "blind":
            out = a.draft.with_name(a.draft.name.replace(".draft.json", "") + ".blind.json")
            out.write_text(json.dumps(blind(draft, sheet, cfg), indent=1, ensure_ascii=False) + "\n",
                           encoding="utf-8")
            print(out)
            return 0
        brief, problems = accept(draft, json.loads(a.review.read_text(encoding="utf-8")), sheet, cfg)
        if problems:
            print("\n".join(problems))
            return 1
        with open(DRAFTS, "a", encoding="utf-8") as f:
            f.write(json.dumps(brief, ensure_ascii=False, sort_keys=True) + "\n")
        print(f"{sheet['fips']}: appended to {DRAFTS.relative_to(ROOT)}")
        return 0
    briefs = drafts()
    if a.command == "worklist":
        print("\n".join(worklist(d, cfg, briefs)))
        return 0
    if a.command == "check":
        bad = 0
        for f, p in checked(d, cfg, briefs).items():
            print(f"{f}: {'ok' if not p else '; '.join(p)}")
            bad += bool(p)
        return 1 if bad else 0
    doc = publish(d, cfg, briefs)
    print(f"county briefs: {len(doc['briefs'])} published, {len(doc['held'])} held ({date.today()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
