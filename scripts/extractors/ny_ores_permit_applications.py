"""Extractor for New York ORES permit applications (source_id ny_ores_permit_applications).

Input: the raw HTML of https://dps.ny.gov/ores-permit-applications as stored by
fetch.py (gzipped). The Office of Renewable Energy Siting and Electric
Transmission lists every major renewable facility application in one table per
section (h2 heading): Notices of Intent, Applications Pending Completeness
Determination, Incomplete Applications, Complete Applications Under Review,
Permitted Applications, Withdrawn Applications / Relinquished Permits, Denied
Applications, Request for Declaratory Ruling. Each row gives the case number
(linked to its documents.dps.ny.gov case page), the project name and a
description naming the capacity, towns and county.

Output: ``contested_project`` leads (state NY), only for
  - every row under Denied, and every row under Withdrawn / Relinquished, and
  - a row in any section whose project name matches a New York project in
    data/seed/contested_projects_seed.csv (read only): its ORES status may
    update that record's outcome.
Every other row is left out: an application is not opposition. The page never
shows opposition, so every lead says so in reviewer_notes and a reviewer must
find the record of opposition before setting it pending.

Seed matching follows scripts/facility_matches.py: names are compared on their
distinctive words (facility_matches.core: generic words such as solar, wind,
project, LLC dropped), and a match needs a shared technology too. The same
distinctive words match when the two share a county or either side names
none; one set containing the other (a shared word of four letters or more)
matches only within a shared county. So "Bliss Wind" (Wyoming County) never
matches the seed's "Bliss Solar 1 Project" (Schoharie County).

status is set only when the section states it outright and the mapping onto
build_sabin_seeds.OUTCOME is exact:
  Denied Applications                  rejected   (the README's "permit denied",
                                                   blocked_unverified); left
                                                   blank when the same project
                                                   is listed again in a live
                                                   section (refiled after a
                                                   denial without prejudice),
                                                   since the denial did not end it
  Permitted Applications               approved   (the row says the permit was
                                                   received)
  Pending Completeness, Incomplete,
  Complete Applications Under Review   pending
  Notices of Intent                    proposed   (notice of intent to apply)
  Withdrawn / Relinquished, Declaratory
  Ruling, any section not listed here  ''         A withdrawn application or a
                                                   relinquished permit is the
                                                   developer's act, and the page
                                                   never says the project was
                                                   cancelled (an applicant may
                                                   refile or build under another
                                                   permit), so 'cancelled'
                                                   (blocked_unverified) would
                                                   claim more than it says.
severity_score, mechanisms, opposition_type and first_event_date stay blank:
the row's effective date of a withdrawal is in description and evidence_text,
not an event date of opposition. jurisdiction_type is 'state': ORES, a state
office, decides these permits (Public Service Law Article VIII, formerly
Executive Law 94-c), not the towns.

source_kind is 'other'. source_url is the case's documents.dps.ny.gov case
page, a regulator's docket index: not the instrument, its minutes or an
official copy of either, and not a court record (classify.SOURCE_KINDS), and it
shows the application's status but no opposition. 'other' is not among
classify.EVENT_KINDS, so even a read copy of it can never verify a contested
project (promote_reviewed.evidence); a reviewer who reads the decision or the
filings that show opposition sets source_kind for what they read. A row with
no case link uses the page URL. access is 'snippet': a listing row is not a
read document.

Placement: the county comes from the row's "located in ..." clause, each
"<Name> County" checked against data/county_fips_lookup.json. When several
counties are named the first is used and all are listed, with their towns, in
reviewer_notes; municipality is the towns of that first county. Each town is
checked against data/place_county_index.json (Census place index), and a town
the index puts elsewhere is noted. A row with no "located in" clause, or a
county name the lookup does not know, gets county ''. Nothing is inferred.

Reads only: the raw file, the seed, the county lookup and the place index.
Writes nothing.
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from classify import lookup_county, place_key
from common import ROOT, SEED_DIR, normalize_url, read_csv, read_raw, strip_tracking, technology_tokens
from facility_matches import core

PAGE_URL = "https://dps.ny.gov/ores-permit-applications"
STATE, STATE_NAME = "NY", "new york"
SEED_PATH = SEED_DIR / "contested_projects_seed.csv"
LOOKUP_PATH = ROOT / "data" / "county_fips_lookup.json"
PLACES_PATH = ROOT / "data" / "place_county_index.json"
CASE_HOST = "documents.dps.ny.gov"
MAX_EVIDENCE = 1000
log = logging.getLogger(__name__)

# (key, heading pattern, status). Order matters: "Incomplete" and "Pending
# Completeness" both contain "complete".
SECTIONS = (
    ("notice_of_intent", r"notices? of intent", "proposed"),
    ("pending_completeness", r"pending completeness", "pending"),
    ("incomplete", r"\bincomplete\b", "pending"),
    ("under_review", r"under review", "pending"),
    ("permitted", r"\bpermitted\b", "approved"),
    ("withdrawn", r"withdrawn|relinquish", ""),
    ("denied", r"\bdenied\b", "rejected"),
    ("declaratory", r"declaratory", ""),
)
# Emitted whatever the seeds hold.
TERMINAL = {"withdrawn", "denied"}
# Sections where an application or permit is still alive.
LIVE = {"notice_of_intent", "pending_completeness", "incomplete", "under_review", "permitted"}

TECH_PATTERNS = (
    ("solar", r"\bsolar\b|\bphotovoltaic\b"),
    ("wind", r"\bwind(?:s|park|parks|farm|farms|mill|mills)?\b"),
    ("battery_storage", r"\bbatter(?:y|ies)\b|(?<!pumped )\bstorage\b"),
)
TECH_WORDS = {"solar": "solar", "wind": "wind", "battery_storage": "battery storage"}

CASE_NO = re.compile(r"\b\d{2}-\d{5}\b")
MW = re.compile(r"\b(up to (?:an? )?)?(\d[\d,]*(?:\.\d+)?)[\s-]*(?:megawatts?|mw)\b", re.I)
# The clause naming the place; ends at a sentence end that is not "St." or "Mt.".
LOCATED = re.compile(r"\blocated in (?:the )?(.+)", re.I)
CLAUSE_END = re.compile(r"\s+has been\b|(?<!\bst)(?<!\bmt)(?<!\bste)\.(?:\s|$)", re.I)
COUNTY_IN = re.compile(r"(?:^|,|\bin\b)\s*(?:and\s+)?(?:the\s+)?((?:st\.?\s+)?[a-z][a-z.'\- ]*?)\s+county\b", re.I)
PLACE_KIND = re.compile(r"\b(towns?|villages?|cities|city|hamlets?|boroughs?)\s+of\s+", re.I)
DENIED = re.compile(r"\bhas been (denied(?: without prejudice)?)", re.I)
WITHDRAWN = re.compile(r"\b(withdrawn|relinquished) effective ([A-Z][a-z]+\.? \d{1,2}, \d{4})", re.I)
DASHES = {"\u2014": ", ", "\u2013": "-", "\u2012": "-", "\u2015": ", ", "\u00a0": " "}
QUOTES = str.maketrans({"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"'})


def clean(text: str) -> str:
    """Whitespace collapsed, no em-dash or en-dash, no stray space before a comma."""
    for k, v in DASHES.items():
        text = (text or "").replace(k, v)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+,", ",", re.sub(r",\s*,", ",", text))


def plain(text: str) -> str:
    """clean(), with typographic quotes made plain (for names and summaries)."""
    return clean(text).translate(QUOTES)


def title_case(name: str) -> str:
    """'ST. LAWRENCE' -> 'St. Lawrence'; a name already in mixed case is kept."""
    name = clean(name)
    if name != name.upper():
        return name
    return re.sub(r"[A-Za-z]+(?:'[A-Za-z]+)?", lambda m: m.group(0).capitalize(), name.lower())


# ── HTML ───────────────────────────────────────────────────────────────────────

class _Tables(HTMLParser):
    """Every table row on the page with the h2 heading above it: rows are
    (table number, heading, [cell]), cell = {text, links [(href, text)], header}."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[int, str, list[dict]]] = []
        self.heading = ""
        self._h: list[str] | None = None
        self._table = 0
        self._row: list[dict] | None = None
        self._cell: dict | None = None
        self._link: list | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "h2":
            self._h = []
        elif tag == "table":
            self._table += 1
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = {"text": [], "links": [], "header": tag == "th"}
        elif tag == "a" and self._cell is not None:
            self._link = [dict(attrs).get("href") or "", []]
        elif tag in ("br", "p", "li") and self._cell is not None:
            self._cell["text"].append(" ")

    def handle_endtag(self, tag):
        if tag == "h2" and self._h is not None:
            self.heading = clean("".join(self._h))
            self._h = None
        elif tag == "a" and self._link is not None and self._cell is not None:
            self._cell["links"].append((self._link[0].strip(), clean("".join(self._link[1]))))
            self._link = None
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append({**self._cell, "text": clean("".join(self._cell["text"]))})
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append((self._table, self.heading, self._row))
            self._row = None

    def handle_data(self, data):
        if self._h is not None:
            self._h.append(data)
        if self._cell is not None:
            self._cell["text"].append(data)
        if self._link is not None:
            self._link[1].append(data)


def section_of(heading: str) -> tuple[str, str]:
    """(section key, status) for a heading; ('other', '') when unknown."""
    for key, pattern, status in SECTIONS:
        if re.search(pattern, heading, re.I):
            return key, status
    return "other", ""


def _columns(header: list[dict]) -> dict[str, int]:
    cols: dict[str, int] = {}
    for i, c in enumerate(header):
        t = c["text"].lower()
        if "number" in t or "case" in t:
            cols.setdefault("case", i)
        elif "name" in t:
            cols.setdefault("name", i)
        elif "description" in t:
            cols.setdefault("desc", i)
    return cols if {"case", "name", "desc"} <= set(cols) else {"case": 0, "name": 1, "desc": 2}


def _links(cells: list[dict], page_url: str) -> list[str]:
    """The cells' absolute http(s) links, in order, each once."""
    found = []
    for c in cells:
        for href, _text in c["links"]:
            url = urljoin(page_url, href)
            if urlsplit(url).scheme in ("http", "https") and url not in found:
                found.append(url)
    return found


def _case_page(url: str) -> bool:
    parts = urlsplit(url)
    return parts.netloc.lower() == CASE_HOST and "casemaster" in parts.path.lower()


def applications(html: str, page_url: str = PAGE_URL) -> list[dict]:
    """One dict per application row: section, status, heading, case, name,
    desc, links (absolute http(s) URLs, in order), case_link (the case's own
    documents.dps.ny.gov link: the case cell's, else a case page linked
    anywhere in the row, else ''), row_text."""
    parser = _Tables()
    parser.feed(html)
    parser.close()
    out, cols = [], {}
    for table, heading, cells in parser.rows:
        if all(c["header"] for c in cells) or any(c["text"].lower() == "project name" for c in cells):
            cols[table] = _columns(cells)
            continue
        col = cols.get(table, {"case": 0, "name": 1, "desc": 2})
        if len(cells) <= max(col.values()):
            continue
        case_text = cells[col["case"]]["text"]
        case = CASE_NO.search(case_text) or CASE_NO.search(" ".join(c["text"] for c in cells))
        in_cell = [u for u in _links([cells[col["case"]]], page_url) if urlsplit(u).netloc.lower() == CASE_HOST]
        links = _links(cells, page_url)
        case_link = (in_cell or [u for u in links if _case_page(u)] or [""])[0]
        key, status = section_of(heading)
        out.append({
            "section": key, "status": status, "heading": heading,
            "case": case.group(0) if case else case_text,
            "name": cells[col["name"]]["text"], "desc": cells[col["desc"]]["text"],
            "links": links, "case_link": case_link,
            "row_text": " | ".join(c["text"] for c in cells),
        })
    return out


# ── Reading the row ────────────────────────────────────────────────────────────

def technologies(text: str) -> list[str]:
    return [t for t, pat in TECH_PATTERNS if re.search(pat, text or "", re.I)]


def _join(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def places(desc: str, lookup: dict[str, str]) -> list[dict]:
    """[{county (as written), fips (or None), towns [(kind, name)]}] from the
    row's 'located in' clause, in the order named. [] when there is none."""
    m = LOCATED.search(desc or "")
    if not m:
        return []
    clause = CLAUSE_END.split(m.group(1), maxsplit=1)[0]
    out, start = [], 0
    for cm in COUNTY_IN.finditer(clause):
        name = title_case(cm.group(1))
        segment = clause[start:cm.start()]
        start = cm.end()
        out.append({"county": f"{name} County", "fips": lookup_county(name, STATE_NAME, lookup),
                    "towns": _towns(segment)})
    return out


def _towns(segment: str) -> list[tuple[str, str]]:
    """'the Towns of BELLMONT, BURKE, AND CHATEAUGAY' -> [('Town', 'Bellmont'), ...]."""
    seg = re.sub(r"^[\s,]*(?:and\s+)?(?:the\s+)?", "", segment, flags=re.I).strip(" ,")
    parts = PLACE_KIND.split(seg)
    pairs = []
    if parts[0].strip(" ,") and len(parts) == 1:
        parts = ["", "", parts[0]]
    for i in range(1, len(parts) - 1, 2):
        kind = parts[i].lower()
        kind = {"cities": "City", "towns": "Town", "villages": "Village", "hamlets": "Hamlet",
                "boroughs": "Borough"}.get(kind, kind.capitalize())
        names_text = re.sub(r"\s+and\s*$", "", parts[i + 1].strip(" ,"), flags=re.I)
        names = re.split(r",\s*(?:and\s+)?|\s+and\s+", names_text, flags=re.I)
        for n in names:
            n = re.sub(r"^(?:and|the)\s+", "", n.strip(" ,"), flags=re.I)
            if n:
                pairs.append((kind, title_case(n)))
    return pairs


def municipality(towns: list[tuple[str, str]]) -> str:
    """[('Town', 'Root'), ('Town', 'Canajoharie')] -> 'Towns of Root and Canajoharie'."""
    groups: dict[str, list[str]] = {}
    for kind, name in towns:
        groups.setdefault(kind, []).append(name)
    phrases = []
    for kind, names in groups.items():
        if not kind:
            phrases.append(_join(names))
        else:
            phrases.append(f"{kind}{'s' if len(names) > 1 else ''} of {_join(names)}")
    return " and ".join(phrases)


def capacity(desc: str) -> tuple[str, str, list[str]]:
    """(MW as written, 'up to ' or '', the technologies of the facility the
    figure sizes: named between it and the next "facility")."""
    m = MW.search(desc or "")
    if not m:
        return "", "", []
    noun = re.match(r".{0,80}?\bfacilit(?:y|ies)\b", desc[m.end():], re.I | re.S)
    return (m.group(2).replace(",", ""), "up to " if m.group(1) else "",
            technologies(noun.group(0) if noun else desc[m.end():m.end() + 40]))


def summary(app: dict, techs: list[str], conflict: bool, located: list[dict], action: str) -> str:
    """One plain sentence from the row's own words."""
    mw, upto, primary = capacity(app["desc"])
    if conflict:
        primary, rest = [], []
    else:
        primary = [t for t in primary if t in techs]
        rest = [t for t in techs if t not in primary]
    words = [TECH_WORDS[t] for t in (primary or rest)]
    noun = f"{_join(words)} facility" if words else "facility"
    if primary and rest:
        noun += f" with {_join([TECH_WORDS[t] for t in rest])}"
    if mw and upto:
        cap = f"a {noun} of up to {mw} MW"
    elif mw:
        article = "an" if mw.startswith("8") or re.fullmatch(r"1[18](?:\.\d+)?", mw) else "a"
        cap = f"{article} {mw} MW {noun}"
    else:
        cap = f"{'an' if noun[0] in 'aeiou' else 'a'} {noun}"
    spots = [f"{'the ' + municipality(p['towns']) + ', ' if p['towns'] else ''}{p['county']}" for p in located]
    where = f" in {_join(spots)}" if spots else ""
    text = f"{plain(app['name'])}, {cap}{where}, is listed by ORES under {app['heading']}, case {app['case']}"
    return plain(text + (f" ({action})" if action else "") + ".")


# ── Repository files (read only) ───────────────────────────────────────────────

@lru_cache(maxsize=8)
def _json(path: Path) -> dict:
    """A JSON reference file without its '_' keys; {} when it is absent. Cached:
    callers must not change what it returns."""
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {k: v for k, v in data.items() if not k.startswith("_")}


def load_lookup(path: Path | None = None) -> dict[str, str]:
    """'<county name>|<state name>' -> county FIPS (data/county_fips_lookup.json)."""
    return _json(Path(path or LOOKUP_PATH))


def load_places(path: Path | None = None) -> dict[str, list[str]]:
    """'<place>|<ST>' -> the counties a place sits in (data/place_county_index.json)."""
    return _json(Path(path or PLACES_PATH))


def _seed_fips(county: str, lookup: dict[str, str]) -> set[str]:
    out = set()
    for part in re.split(r",|;|&|\band\b", county or "", flags=re.I):
        part = re.sub(r"\b(?:county|counties)\b", "", part, flags=re.I).strip()
        f = lookup_county(part, STATE_NAME, lookup) if part else None
        if f:
            out.add(f)
    return out


def load_seeds(path: Path | None = None, lookup: dict[str, str] | None = None) -> list[dict]:
    """New York contested projects with their name core, technologies and counties."""
    lookup = load_lookup() if lookup is None else lookup
    out = []
    for r in read_csv(Path(path or SEED_PATH)):
        if (r.get("state") or "").strip().upper() != STATE:
            continue
        try:
            techs = set(technology_tokens(r.get("technology", "")))
        except ValueError:
            techs = set()
        out.append({"id": r.get("pinned_id") or r.get("source_record_id") or r.get("id") or "",
                    "name": r.get("project_name", ""), "outcome": r.get("outcome", ""),
                    "core": core(r.get("project_name", "")), "techs": techs,
                    "fips": _seed_fips(r.get("county", ""), lookup)})
    return out


def seed_matches(name: str, techs: set[str], fips: set[str], seeds: list[dict]) -> list[tuple[dict, str]]:
    """[(seed, how)] for the seeds this application is (facility_matches' rule,
    without capacity): same distinctive words, a shared technology, and a
    shared county or none named on one side; or one name inside the other
    within a shared county."""
    rcore = core(name)
    if not rcore or not techs:
        return []
    out = []
    for s in seeds:
        if not (techs & s["techs"]) or not s["core"]:
            continue
        shared = bool(fips & s["fips"])
        if s["core"] == rcore and (shared or not fips or not s["fips"]):
            out.append((s, "name, technology and county" if shared else "name and technology (county not compared)"))
        elif (s["core"] < rcore or rcore < s["core"]) and shared \
                and any(len(w) >= 4 for w in s["core"] & rcore):
            out.append((s, "part of the name, technology and county"))
    return out


# ── Extract ────────────────────────────────────────────────────────────────────

def _same_project(a: dict, b: dict) -> bool:
    """Two rows of the page name one project: the same distinctive words and
    no technology that sets them apart."""
    ta = set(technologies(a["name"] + " " + a["desc"]))
    tb = set(technologies(b["name"] + " " + b["desc"]))
    return bool(core(a["name"])) and core(a["name"]) == core(b["name"]) and (not ta or not tb or bool(ta & tb))


def _status(a: dict, others: list[dict]) -> tuple[str, str, list[str]]:
    """(status, the row's own decision words, notes) for one row; the module
    docstring gives the rule."""
    if a["section"] == "denied":
        m = DENIED.search(a["desc"])
        action = m.group(1).lower() if m else ""
        live = [o for o in others if o["section"] in LIVE]
        if live:
            return "", action, [f"status left blank: the project is listed again under {live[0]['heading']} "
                                f"(case {live[0]['case']}), so the denial did not end it"]
        if "without prejudice" in action:
            return a["status"], action, ["status rejected: denied without prejudice, so the applicant may refile"]
        return a["status"], action, []
    if a["section"] == "withdrawn":
        m = WITHDRAWN.search(a["desc"])
        action = f"{m.group(1).lower()} effective {m.group(2)}" if m else ""
        return "", action, ["status left blank: a withdrawn application or relinquished permit "
                            "is not a stated cancellation"]
    if a["section"] == "other":
        return "", "", [f"section {a['heading']!r} is not one this extractor knows: status left blank"]
    return a["status"], "", []


def _placement(located: list[dict], place_index: dict[str, list[str]]) -> tuple[dict | None, list[str]]:
    """(the county used, or None; notes on how it was found)."""
    if not located:
        return None, ["no 'located in' clause in the row: county left blank"]
    valid = [p for p in located if p["fips"]]
    first = valid[0] if valid else None
    notes = []
    bad = [p["county"] for p in located if not p["fips"]]
    if bad:
        notes.append(f"{_join(bad)} not a New York county in county_fips_lookup.json")
    if len(located) > 1:
        listed = "; ".join(f"{p['county']} ({municipality(p['towns']) or 'no town named'})" for p in located)
        notes.append(f"counties named: {listed}; county set to the first valid one")
    if first and first["towns"] and place_index:
        elsewhere = [t for _k, t in first["towns"]
                     if first["fips"] not in place_index.get(f"{place_key(t)}|{STATE}", [])]
        notes.append(f"placed from the row's own words; {_join(elsewhere)} not in {first['county']} "
                     "per the Census place index" if elsewhere else
                     "placed from the row's own words; towns confirmed in that county by the Census place index")
    elif first:
        notes.append("placed from the row's own words")
    return first, notes


def extract(raw_path: Path, source: dict) -> list[dict]:
    html = read_raw(Path(raw_path)).decode("utf-8", errors="replace")
    page_url = (source or {}).get("url") or PAGE_URL
    apps = applications(html, page_url)
    if not apps:
        raise ValueError("no application rows found: the ORES page changed shape")
    lookup, place_index, seeds = load_lookup(), load_places(), load_seeds()

    out, seen = [], set()
    for a in apps:
        name_techs, desc_techs = technologies(a["name"]), technologies(a["desc"])
        techs = [t for t in ("solar", "wind", "battery_storage") if t in name_techs + desc_techs]
        conflict = bool(name_techs and desc_techs and not set(name_techs) & set(desc_techs))
        located = places(a["desc"], lookup)
        matches = seed_matches(a["name"], set(techs), {p["fips"] for p in located if p["fips"]}, seeds)
        if a["section"] not in TERMINAL and not matches:
            continue

        url = strip_tracking(a["case_link"] or page_url)
        key = normalize_url(url)
        if key in seen:
            log.warning("ORES case %s (%s): same source_url as an earlier row, left out", a["case"], a["name"])
            continue
        seen.add(key)

        notes = [f"ORES {a['heading']}, case {a['case']}; opposition is not shown on this page: "
                 "find the record of it before promoting"]
        notes += [f"matches seed {s['id']} ({plain(s['name'])}, outcome {s['outcome'] or 'blank'}) "
                  f"on {how}: its ORES status may update that outcome" for s, how in matches]
        others = [o for o in apps if o is not a and _same_project(a, o)]
        status, action, status_notes = _status(a, others)
        notes += status_notes
        notes += [f"also listed under {o['heading']}, case {o['case']}" for o in others
                  if not any(f"case {o['case']}" in n for n in status_notes)]
        first, place_notes = _placement(located, place_index)
        notes += place_notes
        if conflict:
            notes.append(f"technology conflict: the name says {_join(name_techs)}, "
                         f"the description says {_join(desc_techs)}")
        if not techs:
            notes.append("no technology named in the row")
        if not a["case_link"]:
            notes.append("the row links no case page: source_url is the ORES page")
        extra = [strip_tracking(u) for u in a["links"] if normalize_url(strip_tracking(u)) != key]
        if extra:
            notes.append("row also links " + ", ".join(extra))

        out.append({
            "entity_type": "contested_project",
            "state": STATE,
            "county": first["county"] if first else "",
            "municipality": municipality(first["towns"]) if first else "",
            "jurisdiction_type": "state",
            "project_name": plain(a["name"]),
            "technology": ";".join(techs),
            "description": summary(a, techs, conflict, located, action),
            "source_url": url,
            "status": status,
            "evidence_text": clean(a["row_text"])[:MAX_EVIDENCE],
            "access": "snippet",
            "source_kind": "other",
            "reviewer_notes": clean("; ".join(notes)),
        })
    return out
