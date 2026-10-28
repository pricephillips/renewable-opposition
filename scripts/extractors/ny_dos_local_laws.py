"""Extractor for New York local law filings (source_id ny_dos_local_laws).

Input: one raw JSON page of the New York Department of State's local laws
search, https://locallaws.static-assets.ny.gov/api/search (the API behind
https://dos.ny.gov/local-laws), as stored by fetch.py (gzipped). The query in
config/sources.yaml asks for the newest 100 local laws whose subject names
solar, photovoltaic, wind, battery, energy storage, BESS or renewable, newest
filing first. Every local law a New York county, city, town or village adopts
is filed with the Department of State (Municipal Home Rule Law section 27), and
the database holds the filed copy: the filing form and the law's own text, as a
PDF. Each item gives metadata.fields (municipalityType, municipalityName,
lawNumber, year, dateFiled, subject1, the law's title as filed), external_id
and filename.

The search stems its terms ("renewal" matches renewable, "windows" wind), so
the subject is read again here. A filing is kept when all of these hold:

  1. Its subject names a renewable technology as whole words, typos allowed
     (filed subjects carry many: BATERY, BATTREY, MORATRIUM, SYSEMS): solar,
     photovoltaic; wind followed by energy, farm, power, tower, turbine,
     generation, conversion, mill, facility, system or project, windmill,
     WECS; battery in any spelling, energy storage, BESS. "Renewable",
     "alternative" or "green" energy with no technology counts too, with
     technology left blank for the reviewer. Nothing else is read: a subject
     that names no technology is dropped even when the law's text does.
  2. It is not a tax law: a payment in lieu of taxes (PILOT), an exemption, or
     the Real Property Tax Law section 487 opt-out or opt-in is not siting.
  3. It is not about solar-powered devices (traffic signals, crosswalks).
  4. It does not only undo something: a repeal, rescission or termination
     that adopts nothing new (no replacement, new moratorium or new chapter)
     is dropped. The instrument it ends may already be on record; a status
     check, not a new restriction, is what that filing calls for.
  5. It is not about small, accessory, rooftop or residential systems only
     (a subject that also names commercial, utility, large, tier 2 or 3, or
     farm systems is kept).
  6. It is not a rezoning of one site (a planned development district, a tax
     map parcel): that is a decision on a project, not a rule for where
     facilities may go.

Every filing kept is a restriction lead: a filed local law is an instrument.
Filings of one law (the same government, year and law number, as when a
corrected copy is filed again) become one lead: the latest upload, the others
listed in reviewer_notes.

Fields. source_url is the filed copy itself,
https://itswebny.widen.net/content/{external_id}/pdf/{filename}, which answers
with the PDF (checked live on 2026-10-28: the Town of Hope's local law 2 of
2026, a filing form and the law's text). It is built from the API record
alone, so a filing keeps its URL from run to run. source_kind is
'official_copy': the Department of State's filed copy of the instrument
(classify.INSTRUMENT_KINDS). A reviewer who opens it reads the instrument, so
a lead promoted with access 'opened' is verified against its primary source,
as the evidence standard requires. access is 'snippet': a search record is not
a read document.

status, mechanisms, severity_score, adopted_date and end_date stay blank: the
subject is the law's title, not its terms. A moratorium's term, the date the
law was adopted and the date it took effect are in the PDF. Mechanism words in
the subject (moratorium, extension, prohibition, regulation) go in
reviewer_notes as hints, and so does the filing date. evidence_text is the
subject verbatim, whitespace collapsed, at most 1000 characters. description
quotes it after the government, law number and filing date.

Placement. state is NY. jurisdiction_type is the filing's municipalityType
(Town, Village, City or County) and municipality is "<Type> of <Name>" (blank
for a county). The county comes, in this order, from: the municipality itself
when it is a county; the county the Department of State adds in parentheses to
names shared by several towns ("CLINTON (CLINTON COUNTY)"); the one county
that data/census_governments_2024.csv (read only) gives a town, village or city
of that name in New York; or, when the census lists several, the one the
subject names ("TOWN OF SALEM WASHINGTON COUNTY"). A subject naming another
county than the census gives leaves county blank, and so does a name the
census does not list with no county in parentheses or the subject. Every
county is checked against data/county_fips_lookup.json (read only). A village
can extend into a neighboring county; the census places it by its internal
point, and reviewer_notes says so.

The response changed shape, and extract() raises ValueError (so parse.py
leaves the raw file unparsed and tries it again), when it has no items list,
when the search reports a query syntax error, when it matched nothing (the
query has matched thousands of filings since 2026), or when no item carries
the metadata fields read here.

Reads only: the raw file, data/census_governments_2024.csv and
data/county_fips_lookup.json. Writes nothing.
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from classify import lookup_county, place_key
from common import ROOT, read_csv, read_raw, strip_tracking

STATE, STATE_NAME = "NY", "new york"
GOVERNMENTS_PATH = ROOT / "data" / "census_governments_2024.csv"
LOOKUP_PATH = ROOT / "data" / "county_fips_lookup.json"
DOC_URL = "https://itswebny.widen.net/content/{external_id}/pdf/{filename}"
MAX_EVIDENCE = 1000
log = logging.getLogger(__name__)

# ── Reading the subject ──────────────────────────────────────────────────────

TECH = {
    "solar": re.compile(r"\bsolar\b|\bphotovoltaics?\b", re.I),
    "wind": re.compile(r"\bwinds?\s+(?:energy|farms?|power|towers?|turbines?|generat\w*|conversion|mills?|"
                       r"facilit\w*|systems?|projects?|driving)\b|\bwind\s*mills?\b|\bWECS\b|\bWEPS\b", re.I),
    # BATTERY, BATTERIES and the filed misspellings BATERY, BATTRY, BATTREY, BATTERT.
    "battery_storage": re.compile(r"\bbat{1,2}(?:e?r|re)[a-z]*\b|\benergy\s*,?\s+stor\w*\b|\bstorage\s+energy\b|"
                                  r"\bBESS\b", re.I),
}
GENERIC = re.compile(r"\b(?:renewable|alternative|green)\s+energy\b", re.I)
TAX = re.compile(r"\btax\w*|\bPILOT\b|\bpayments?\s+in\s+lieu\b|\bexemptions?\b|\bsection\s+487\b", re.I)
DEVICE = re.compile(r"\bsolar[- ]powered\b|\btraffic\s+(?:devices?|signals?|control)\b|\bcrosswalks?\b", re.I)
UNDO = re.compile(r"\brepeal\w*|\brescind\w*|\brescission\b|\bterminat\w*|\blift\w*|\bend(?:s|ing)?\s+the\s+moratori",
                  re.I)
ADOPTS_NEW = re.compile(r"\breplac\w*|\bestablish\w*|\bimpos\w*|\benact\w*\s+(?:a\s+)?new\b|"
                        r"\b(?:and|&)\s+(?:adopt|enact)\w*|\bwith\s+a\s+new\b|"
                        r"\bnew\s+(?:local\s+law|chapter|article|section|moratori\w*)\b", re.I)
# The size word must qualify the technology: "RESIDENTIAL SOLAR", "ACCESSORY
# SOLAR ENERGY", not "WITHIN RESIDENTIAL STRUCTURES AND BATTERY ENERGY SYSTEMS".
SMALL = re.compile(r"\b(?:accessory|rooftop|roof[- ]mounted|residential|small[- ]scale|small)\s+"
                   r"(?:(?!and\b|or\b)[\w-]+\s+)?(?:solar|wind|photovoltaic|batter\w*)", re.I)
LARGE = re.compile(r"\b(?:commercial|utility|large|industrial|major|community|farms?|facilit\w*|"
                   r"tier\s*(?:2|3|two|three|ii|iii))\b", re.I)
SITE = re.compile(r"\bplanned\s+development\s+district\b|\btax\s+maps?\b|\bparcels?\s+of\s+land\b", re.I)

# Mechanism words worth a reviewer's eye (never written to mechanisms). The
# moratorium pattern takes the filed misspellings (MORATRIUM, MORTORIUM,
# MORATROIUM, MORTAORIUM).
HINTS = [
    ("moratorium", r"\bmor[a-z]{0,3}t[a-z]{0,4}ium\b|\bmoratoria\b"),
    ("extension", r"\bextend\w*|\bextension\b|\bexending\b|\bentending\b|\badditional\b"),
    ("prohibition", r"\bprohibit\w*|\bbans?\b|\bbanning\b"),
    ("regulation", r"\bregulat\w*|\bzoning\b|\bsiting\b|\bstandards?\b|\brequirements?\b|\bpermits?\b"),
]
HINTS = [(label, re.compile(rx, re.I)) for label, rx in HINTS]
DATA_CENTER = re.compile(r"\bdata\s+(?:cent(?:er|re)s?|storage\s+facilit\w*|facilit\w*)\b", re.I)
EV_CHARGING = re.compile(r"\belectric\s+vehicles?\b|\bcharging\s+stations?\b", re.I)

_DASH = re.compile(r"[‒–—―−]+")


def clean(text: str | None) -> str:
    """Whitespace collapsed, em and en dashes made plain."""
    return " ".join(_DASH.sub("-", (text or "").replace(" ", " ")).split())


def cap(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rsplit(" ", 1)[0].rstrip(" ,;:") + "..."


def title_case(name: str) -> str:
    """'ST. ARMAND' -> 'St. Armand'; a name already in mixed case is kept."""
    name = clean(name)
    if name != name.upper():
        return name
    return re.sub(r"[A-Za-z]+(?:'[A-Za-z]+)?", lambda m: m.group(0).capitalize(), name.lower())


def technologies(subject: str) -> tuple[list[str], bool]:
    """(technology tokens in vocabulary order, whether renewable energy is named generally)."""
    return [t for t, rx in TECH.items() if rx.search(subject)], bool(GENERIC.search(subject))


def classify(subject: str) -> tuple[bool, str, dict]:
    """(keep, reason, details) for a filing's subject; the module docstring gives the rules."""
    techs, generic = technologies(subject)
    if not techs and not generic:
        return False, "no renewable facility technology named in the subject", {}
    m = TAX.search(subject)
    if m:
        return False, f"tax, exemption or payment in lieu of taxes ({clean(m.group(0)).lower()})", {}
    if DEVICE.search(subject):
        return False, "solar-powered devices, not facility siting", {}
    undo = [clean(w.group(0)).lower() for w in UNDO.finditer(subject)]
    if undo and not ADOPTS_NEW.search(subject):
        return False, f"undoes an earlier law ({', '.join(dict.fromkeys(undo))}) and adopts nothing new", {}
    if SMALL.search(subject) and not LARGE.search(subject):
        return False, "small-scale, accessory or residential systems only", {}
    if SITE.search(subject):
        return False, "a rezoning of one site, not a rule for where facilities may go", {}
    hints = [label for label, rx in HINTS if rx.search(subject)]
    return True, "a local law on " + (", ".join(t.replace("_", " ") for t in techs) or "renewable energy"), {
        "techs": techs, "generic": generic, "hints": hints, "undo": list(dict.fromkeys(undo))}


# ── Repository files (read only) ─────────────────────────────────────────────

@lru_cache(maxsize=4)
def load_lookup(path: str = str(LOOKUP_PATH)) -> dict[str, str]:
    """'<county name>|<state name>' -> county FIPS, without the '_' keys.
    Cached: callers must not change what it returns."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


@lru_cache(maxsize=4)
def county_names(path: str = str(LOOKUP_PATH)) -> dict[str, str]:
    """New York county FIPS -> '<Name> County'."""
    out = {}
    for key, fips in load_lookup(path).items():
        name, _, state = key.rpartition("|")
        if state == STATE_NAME and name.endswith(" county"):
            out[fips] = title_case(name.upper())
    return out


def name_key(name: str) -> str:
    """place_key without spaces: the census writes "De Witt" and "LaGrange"
    where filings write DEWITT and LA GRANGE."""
    return place_key(name).replace(" ", "")


@lru_cache(maxsize=4)
def load_governments(path: str = str(GOVERNMENTS_PATH)) -> dict[tuple[str, str], tuple[str, ...]]:
    """(kind, name_key(name)) -> the county FIPS of every New York government
    of that kind and name in the census list; kind is town, village or city."""
    out: dict[tuple[str, str], list[str]] = {}
    for r in read_csv(Path(path)):
        if r.get("state") != STATE:
            continue
        base, _, lsad = (r.get("name") or "").rpartition(" ")
        if lsad in ("town", "village", "city") and base:
            out.setdefault((lsad, name_key(base)), []).append(r.get("county_fips", ""))
    return {k: tuple(dict.fromkeys(v)) for k, v in out.items()}


# ── Placement ────────────────────────────────────────────────────────────────

PARENS = re.compile(r"^(.*?)\s*\(\s*([^)]*?)\s+COUNTY\s*\)?\s*$", re.I)
_WORD = r"[A-Z][A-Z.']*"
SUBJECT_COUNTY = re.compile(rf"\b({_WORD}(?:\s+{_WORD}){{0,2}})\s+COUNTY\b|\bCOUNTY\s+OF\s+({_WORD}(?:\s+{_WORD}){{0,2}})")


def _county(name: str, lookup: dict[str, str]) -> str | None:
    return lookup_county(name, STATE_NAME, lookup) if name else None


def subject_counties(subject: str, lookup: dict[str, str]) -> list[str]:
    """FIPS of the New York counties the subject names: the longest run of the
    words before "COUNTY" (or after "COUNTY OF") that is one."""
    out = []
    for m in SUBJECT_COUNTY.finditer(subject.upper()):
        words = (m.group(1) or m.group(2)).split()
        tries = [" ".join(words[i:]) for i in range(len(words))] if m.group(1) else \
                [" ".join(words[:j]) for j in range(len(words), 0, -1)]
        for t in tries:
            f = _county(t.title(), lookup)
            if f:
                if f not in out:
                    out.append(f)
                break
    return out


def placement(mtype: str, mname: str, subject: str) -> tuple[dict, str]:
    """Location fields for a filing and the note that says how they were set."""
    lookup, names, govs = load_lookup(), county_names(), load_governments()
    kind = mtype.strip().lower()
    name, paren = mname, ""
    m = PARENS.match(mname)
    if m:
        name, paren = m.group(1), m.group(2)
    display = title_case(name)
    fields = {"state": STATE, "county": "", "municipality": "",
              "jurisdiction_type": kind.capitalize() if kind else ""}
    named = subject_counties(subject, lookup)

    if kind == "county":
        f = _county(display, lookup)
        if not f:
            return fields, f"county left blank: {display} County is not a New York county in county_fips_lookup.json"
        fields["county"] = names.get(f, f"{display} County")
        return fields, "placed in the filing county"
    fields["municipality"] = f"{kind.capitalize()} of {display}" if kind else display

    if paren:
        f = _county(title_case(paren), lookup)
        if f:
            fields["county"] = names.get(f, f"{title_case(paren)} County")
            return fields, (f"placed in {fields['county']} from the county the Department of State gives in "
                            f"parentheses ({clean(mname)})")
    census = govs.get((kind, name_key(display)), ()) if kind in ("town", "village", "city") else ()
    village = " (a village can extend into a neighboring county; the census places it by its internal point)" \
        if kind == "village" else ""
    if len(census) == 1:
        f = census[0]
        others = [names.get(c, c) for c in named if c != f]
        if others:
            return fields, (f"county left blank: the census puts the {kind} of {display} in "
                            f"{names.get(f, f)}, but the subject names {', '.join(others)}")
        fields["county"] = names.get(f, "")
        return fields, f"placed in {fields['county']} by data/census_governments_2024.csv{village}"
    if len(census) > 1:
        chosen = [c for c in named if c in census]
        listed = ", ".join(names.get(c, c) for c in census)
        if len(chosen) == 1:
            fields["county"] = names.get(chosen[0], "")
            return fields, (f"the census lists a {kind} of {display} in {listed}; placed in {fields['county']}, "
                            f"the one the subject names")
        return fields, f"county left blank: the census lists a {kind} of {display} in {listed}"
    if len(named) == 1:
        fields["county"] = names.get(named[0], "")
        return fields, (f"placed in {fields['county']}, the county the subject names (the census lists no "
                        f"{kind} of {display})")
    return fields, f"county left blank: the census lists no {kind} of {display} in New York"


# ── Rows ─────────────────────────────────────────────────────────────────────

def _field(item: dict, key: str) -> str:
    v = ((item.get("metadata") or {}).get("fields") or {}).get(key) or []
    return clean(str(v[0])) if isinstance(v, list) and v else ""


def _date(value: str) -> str:
    return value[:10] if re.match(r"\d{4}-\d{2}-\d{2}", value or "") else ""


def filing(item: dict) -> dict:
    """The fields read from one search item."""
    return {
        "type": _field(item, "municipalityType"), "name": _field(item, "municipalityName"),
        "law": _field(item, "lawNumber"), "year": _field(item, "year"),
        "filed": _date(_field(item, "dateFiled")), "subject": _field(item, "subject1"),
        "key": _field(item, "subject"), "external_id": clean(item.get("external_id")),
        "filename": clean(item.get("filename")), "uploaded": clean(item.get("created_date")),
    }


def document_url(f: dict) -> str:
    return strip_tracking(DOC_URL.format(external_id=f["external_id"], filename=f["filename"]))


def lead(f: dict, reason: str, details: dict, merged: list[dict]) -> dict:
    loc, place_note = placement(f["type"], f["name"], f["subject"])
    who = loc["municipality"] or loc["county"] or title_case(f["name"])
    law = f"local law {f['law'] or '(no number)'} of {f['year'] or 'no year'}"
    notes = [f"NY DOS local law filing: {who}, {law}, filed {f['filed'] or 'no date'}"
             + (f" (DOS key {f['key']})" if f["key"] else ""),
             "source_url is the filed copy of the law: read it for the adoption date, the date it took effect, "
             "its terms and any end date before promoting",
             f"kept on {reason}", place_note]
    if not details["techs"]:
        notes.append("technology not named (renewable energy generally): read it from the law")
    if details["hints"]:
        notes.append("mechanism hints: " + ", ".join(details["hints"]))
    if details["undo"]:
        notes.append(f"also {', '.join(details['undo'])}: check what it replaced")
    if DATA_CENTER.search(f["subject"]):
        notes.append("also names data centers (multi-sector scope)")
    if EV_CHARGING.search(f["subject"]):
        notes.append("also names electric vehicle charging")
    if merged:
        notes.append("same law also filed as " + ", ".join(
            f"{o['filename']} (filed {o['filed'] or 'no date'}: \"{cap(o['subject'], 120)}\")" for o in merged))
    return {
        "entity_type": "restriction",
        **loc,
        "technology": ";".join(details["techs"]),
        "description": f"{who} {law}, filed with the New York Department of State on {f['filed'] or 'no date'}: "
                       f"\"{cap(f['subject'], 600)}\".",
        "source_url": document_url(f),
        "evidence_text": cap(f["subject"], MAX_EVIDENCE),
        "adopted_date": "",
        "end_date": "",
        "status": "",
        "mechanisms": "",
        "severity_score": "",
        "access": "snippet",
        "source_kind": "official_copy",
        "reviewer_notes": "; ".join(notes),
    }


def payload_items(payload) -> list[dict]:
    """The search items, after the checks the module docstring lists."""
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("no items list: the local laws search changed shape")
    if payload.get("query_syntax_ok") is False:
        raise ValueError(f"the local laws search refused the query: {str(payload.get('query'))[:200]}")
    items = [i for i in payload["items"] if isinstance(i, dict)]
    if not items and not payload.get("total_count"):
        raise ValueError("the local laws search matched nothing: the query or the API changed")
    if items and not any(_field(i, "subject1") and _field(i, "municipalityName") for i in items):
        raise ValueError("no item carries subject1 and municipalityName: the local laws search changed shape")
    return items


def extract(raw_path: Path, source: dict) -> list[dict]:
    payload = json.loads(read_raw(Path(raw_path)).decode("utf-8-sig"))
    groups: dict[tuple, list] = {}
    order: list[tuple] = []
    for item in payload_items(payload):
        f = filing(item)
        if not (f["subject"] and f["external_id"] and f["filename"]):
            log.warning("NY DOS item %s: no subject or no document, skipped", item.get("id"))
            continue
        keep, reason, details = classify(f["subject"])
        if not keep:
            log.info("NY DOS %s %s law %s/%s dropped: %s", f["type"], f["name"], f["law"], f["year"], reason)
            continue
        key = (f["type"].lower(), f["name"].lower(), f["year"], f["law"]) if f["law"] else (f["external_id"],)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((f, reason, details))
    out = []
    for key in order:
        items = sorted(groups[key], key=lambda it: (it[0]["filed"], it[0]["uploaded"]), reverse=True)
        f, reason, details = items[0]
        out.append(lead(f, reason, details, [it[0] for it in items[1:]]))
    return out


def explain(raw_path: Path) -> list[tuple[dict, bool, str]]:
    """(filing, kept, reason) for every item in a raw file: a triage aid for
    tuning the rules; extract() is what parse.py calls."""
    payload = json.loads(read_raw(Path(raw_path)).decode("utf-8-sig"))
    out = []
    for item in payload_items(payload):
        f = filing(item)
        keep, reason, _ = classify(f["subject"])
        out.append((f, keep, reason))
    return out
