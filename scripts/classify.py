"""Derived fields that decide what a record counts as. Pure functions: no I/O.

build_seed_outputs.py stamps these onto every processed row; qc_gate.py and
headline_metrics.py read them. They are derived, never stored in a seed, so a
rule change here reaches every record on the next build.

instrument_id   What one count means. A seed row is one technology of one
                instrument, so a moratorium covering solar, wind and battery
                storage is three rows but one instrument:
                  restrictions        mn:<moratorium_id> or sabin:<source_record_id>
                  contested_projects  sabin:<source_record_id>
                  cases               case:<case_id>
                A row with none of those keys is its own instrument (its id).

scope           restrictions only. Whether the instrument is aimed at
                renewables or bundles them with data centers:
                  renewables_only            sectors (or text) name no data centers
                  multi_sector_data_centers  Moratorium Nation's sectors include
                                             data_center, or the text names data
                                             centers alongside a renewable technology
                  data_center_only           the text names data centers and no
                                             renewable technology at all: the
                                             sector tag is not supported by the
                                             record, so qc_gate holds it for review
                Moratorium Nation's `sectors` is authoritative when present; the
                text test is the fallback (Sabin rows) and the contradiction check.

evidence_level  How far the record is from a primary source, best first:
                  primary_source     a reviewer confirmed the record against a
                                     primary_source_url (the ordinance, minutes,
                                     permit decision): resolutions.py
                  confirmed          contested project whose outcome is *_confirmed
                  court_record       case with a court or docket URL
                  compiled_record    Moratorium Nation row with no [VERIFY] tag;
                                     cites its legal basis but links the inventory
                  compiled_flagged   Moratorium Nation row with [VERIFY] tags
                  report_citation    cites the Sabin report as a whole

county_fips     contested_projects, and restrictions whose jurisdiction_type is
                County, Parish or Borough: the 5-digit county FIPS of the state
                plus the county name (a restriction's jurisdiction), looked up
                exactly in data/county_fips_lookup.json (copied from
                pricephillips/data-center-map, passoff B4). No fuzzy matching:
                a name the lookup does not hold, a field naming several
                counties, or a code that is not a 2024 county (NOT_2024_COUNTY)
                is a miss with a reason, never a guess. build_seed_outputs.py
                lists the misses in data/review/fips_misses.csv. Other entities
                and municipal restrictions have no county to look up.

county_fips_all Every 2024 county a record touches, for finding records by
                place (scripts/site_profile.py), never for painting the map.
                county_fips_method says how they were found, in the order tried:
                  name         the county named in the record; also a
                               jurisdiction typed as a municipality whose name
                               ends in County or Parish, and a consolidated
                               city-county (CITY_COUNTIES)
                  names        a multi-county name split into its parts
                  point        the record's coordinates inside a county polygon
                  place        a town name that sits in one county of its state
                               in the Census place index
                  place_text   a town name shared by several counties, where
                               the record's own text names exactly one of them
                               as "<Name> County"
                  place_ambiguous  shared by several counties and the text
                               does not settle it: left unplaced
                  override     a reviewer's county with an evidence URL, from
                               data/review/place_overrides.csv, applied last by
                               resolutions.apply_place_overrides
"""
from __future__ import annotations

import re

RENEWABLE_TEXT = re.compile(
    r"solar|photovolt|\bpv\b|\bwind(?:s|farms?|mills?|power)?\b|turbine|batter|energy storage|\bbess\b|renewable", re.I)
DATA_CENTER_TEXT = re.compile(
    r"data[ -]?cent(?:er|re)s?|data processing facilit|crypto|bitcoin|hyperscale", re.I)
TEXT_FIELDS = ("description", "long_description", "notes", "legal_basis")

EVIDENCE_ORDER = ("primary_source", "confirmed", "court_record", "compiled_record",
                  "compiled_flagged", "report_citation")
SCOPES = ("renewables_only", "multi_sector_data_centers", "data_center_only")

COUNTY_JURISDICTION_TYPES = {"county", "parish", "borough"}
# Lookup values with no polygon in the Census 2024 county boundaries: the eight
# Connecticut counties that planning regions (09110 to 09190) replaced in 2022,
# and Alaska's state election districts (029xx), which are not counties. A
# record naming one of them is a miss, since picking a successor is a guess.
NOT_2024_COUNTY_PREFIXES = ("029",)
NOT_2024_COUNTY = {"09001", "09003", "09005", "09007", "09009", "09011", "09013", "09015"}
SEVERAL_COUNTIES = re.compile(r",|;|&|\(|\band\b", re.I)
# A parenthetical that names no county is a qualifier on the one county named,
# "Huron County (solar and battery storage)"; one that does is a second county.
QUALIFIER = re.compile(r"\s*\((?![^)]*\b(?:count|parish|borough))[^)]*\)", re.I)


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def _text(row: dict) -> str:
    return " ".join(_s(row.get(f)) for f in TEXT_FIELDS)


def instrument_id(entity: str, row: dict) -> str:
    if entity == "restrictions":
        if _s(row.get("moratorium_id")):
            return f"mn:{_s(row['moratorium_id'])}"
        if _s(row.get("source_record_id")):
            return f"sabin:{_s(row['source_record_id'])}"
    elif entity == "contested_projects" and _s(row.get("source_record_id")):
        return f"sabin:{_s(row['source_record_id'])}"
    elif entity == "cases" and _s(row.get("case_id")):
        return f"case:{_s(row['case_id'])}"
    return _s(row.get("id"))


def scope(row: dict) -> str:
    text = _text(row)
    names_renewable = bool(RENEWABLE_TEXT.search(text))
    names_data_center = bool(DATA_CENTER_TEXT.search(text))
    if names_data_center and not names_renewable:
        return "data_center_only"
    sectors = {s for s in _s(row.get("sectors")).split(";") if s}
    if "data_center" in sectors or names_data_center:
        return "multi_sector_data_centers"
    return "renewables_only"


def evidence_level(entity: str, row: dict) -> str:
    if _s(row.get("primary_source_url")) and _s(row.get("primary_source_verdict")) != "contradicts":
        return "primary_source"
    if entity == "contested_projects":
        return "confirmed" if _s(row.get("outcome")).endswith("_confirmed") else "report_citation"
    if entity == "cases":
        return "court_record" if _s(row.get("case_source_url")) or _s(row.get("source_url")) \
            else "report_citation"
    if _s(row.get("moratorium_id")):
        return "compiled_flagged" if _s(row.get("needs_verification")) == "yes" else "compiled_record"
    return "report_citation"


def county_name(entity: str, row: dict) -> str | None:
    """The county name to look up, "" when one is expected but blank, or None
    when the record is not tied to a county at all."""
    if entity == "contested_projects":
        return _s(row.get("county"))
    if entity == "restrictions" and _s(row.get("jurisdiction_type")).lower() in COUNTY_JURISDICTION_TYPES:
        return _s(row.get("jurisdiction"))
    return None


# Text-extraction damage in Sabin county names: a lost "ti" or "ft" ligature.
# Exact strings only; anything else stays a miss.
EXTRACTION_FIXES = {"bal>more": "baltimore", "granon": "grafton"}
_SPLIT = re.compile(r",|;|&|\(|\)|\band\b", re.I)
_COUNTY_WORD = re.compile(r"\b(?:counties|county|various)\b", re.I)


def _squash(name: str) -> str:
    """Spacing and punctuation-insensitive key: 'DeWitt' and 'De Witt' match,
    as do 'St. Clair' and 'Saint Clair'. Spelling must still be exact."""
    n = name.lower().replace("saint ", "st ").replace("ste. ", "ste ")
    return re.sub(r"[^a-z0-9]", "", n)


def lookup_county(name: str, state: str, lookup: dict[str, str]) -> str | None:
    key = " ".join(name.lower().split())
    key = EXTRACTION_FIXES.get(key, key)
    for k in (key, f"{key} county"):
        hit = lookup.get(f"{k}|{state}")
        if hit is not None:
            return hit
    want = _squash(key)
    for k, v in lookup.items():
        n, _, st = k.rpartition("|")
        if st == state and _squash(n) == want:
            return v
    return None


def _usable(fips: str | None) -> bool:
    return bool(fips) and fips not in NOT_2024_COUNTY and not fips.startswith(NOT_2024_COUNTY_PREFIXES)


# Legal/statistical area descriptions the Census Gazetteer appends to a place
# name, and the "Village of" style prefixes local records use.
_LSAD = re.compile(
    r"\s+(?:charter township|township|town|city and borough|consolidated government"
    r"|unified government|metropolitan government|metro government|urban county"
    r"|city|village|borough|municipality|plantation|grant|purchase|location|gore"
    r"|reservation|cdp|comunidad|zona urbana|precinct|district|unorganized territory)"
    r"(?:\s+\(balance\))?$",
    re.I,
)
_PLACE_PREFIX = re.compile(r"^(?:city|town|township|village|borough|municipality)\s+of\s+", re.I)


def place_key(name: str) -> str:
    """'Shawnee township' -> 'shawnee'; 'Village of Teutopolis' -> 'teutopolis';
    'St. Clair' -> 'st clair'. Used to build and to read data/place_county_index.json."""
    n = _PLACE_PREFIX.sub("", _s(name))
    n = _LSAD.sub("", n)
    n = n.lower().replace("saint ", "st ").replace(".", "").replace("'", "")
    return " ".join(n.split())


# A city and county under one government, where the city has the county's
# name. Listed outright because a record often says only "City Council"
# (the Sabin entry for Honolulu does). Other consolidated governments
# (Nashville-Davidson, Louisville-Jefferson) have a different county name and
# are not matched here.
CITY_COUNTIES = {
    "honolulu|HI": "15003",       # City and County of Honolulu
    "san francisco|CA": "06075",  # City and County of San Francisco
    "denver|CO": "08031",         # City and County of Denver
    "broomfield|CO": "08014",     # City and County of Broomfield
    "philadelphia|PA": "42101",   # City and County of Philadelphia
}
_MISTYPED_COUNTY = re.compile(r"\b(?:county|parish)\s*$", re.I)


def _mistyped_county(entity: str, row: dict) -> str:
    """A jurisdiction typed as a municipality whose name is plainly a county,
    "Atlantic County". county_fips leaves it alone (the map paints only
    County-typed rows); county_fips_all looks it up."""
    if entity != "restrictions" or county_name(entity, row) is not None:
        return ""
    j = _s(row.get("jurisdiction"))
    return j if _MISTYPED_COUNTY.search(j) else ""


def _words(name: str) -> str:
    """A regex for a name, any run of whitespace between its words."""
    return r"\s+".join(map(re.escape, name.split()))


def _city_county(row: dict, town: str, state: str, lookup: dict[str, str],
                 places: dict[str, list[str]] | None) -> str | None:
    """The county of a consolidated city-county: listed in CITY_COUNTIES, or
    a city whose record calls it "City and County of <Name>" (or "<Name> City
    and County") and whose Census place sits in the county of that name."""
    key, st = place_key(town), _s(row.get("state")).upper()
    if f"{key}|{st}" in CITY_COUNTIES:
        return CITY_COUNTIES[f"{key}|{st}"]
    name = _words(key)
    said = re.compile(rf"\bcity\s+and\s+county\s+of\s+{name}\b|\b{name}\s+city\s+and\s+county\b", re.I)
    if not said.search(f"{town} {_text(row)}"):
        return None
    fips = lookup_county(key, state, lookup)
    if _usable(fips) and fips in (places or {}).get(f"{key}|{st}", []):
        return fips
    return None


def _county_names(fips: str, state: str, lookup: dict[str, str]) -> set[str]:
    """Every lookup spelling of a county's name without its County/Parish word."""
    out = set()
    for k, v in lookup.items():
        n, _, st = k.rpartition("|")
        if v == fips and st == state:
            out.add(re.sub(r"\s+(?:county|parish)$", "", n))
    return out


def _named_in_text(row: dict, fips: str, state: str, lookup: dict[str, str]) -> bool:
    """Whether the record's text says "<Name> County" (or Parish) for this county."""
    text = _text(row)
    return any(re.search(rf"\b{_words(n)}\s+(?:County|Parish)\b", text, re.I)
               for n in _county_names(fips, state, lookup))


def place_name(entity: str, row: dict) -> str:
    """The town, city or township a record names, when it names one."""
    if entity == "restrictions":
        if _s(row.get("jurisdiction_type")).lower() in COUNTY_JURISDICTION_TYPES | {"state", ""}:
            return ""
        return _s(row.get("jurisdiction"))
    if entity == "contested_projects":
        return _s(row.get("municipality"))
    return ""


def county_fips_all(entity: str, row: dict, lookup: dict[str, str], state_names: dict[str, str],
                    locate=None, places: dict[str, list[str]] | None = None) -> tuple[list[str], str]:
    """Every 2024 county a record touches, and how they were found (the
    methods are listed in the module docstring). ``locate(lat, lon) -> fips``
    is injected so this stays free of I/O. Unlike ``county_fips``, this is for
    finding records by place, not for painting a county on the map: a town's
    moratorium touches its county but does not cover it. Reviewer overrides
    are not applied here; resolutions.apply_place_overrides lays them over
    the result."""
    fips, _ = county_fips(entity, row, lookup, state_names)
    if fips:
        return [fips], "name"
    state = state_names.get(_s(row.get("state")).upper(), "").lower()
    mistyped = _mistyped_county(entity, row)
    if mistyped:
        f = lookup_county(QUALIFIER.sub("", mistyped).strip(), state, lookup)
        if _usable(f):
            return [f], "name"
    town = place_name(entity, row)
    if town and not mistyped:
        f = _city_county(row, town, state, lookup, places)
        if f:
            return [f], "name"
    name = county_name(entity, row) or mistyped
    if name:
        # "Various (Clark, Lyon, Nye)": the parenthetical is the list, not a qualifier.
        listed = name if re.match(r"\s*various\b", name, re.I) else QUALIFIER.sub("", name)
        parts = [_COUNTY_WORD.sub("", p).strip() for p in _SPLIT.split(listed)]
        found = []
        for part in filter(None, parts):
            f = lookup_county(part, state, lookup)
            if _usable(f) and f not in found:
                found.append(f)
        if found:
            return found, "names"
    lat, lon = row.get("latitude"), row.get("longitude")
    if locate and lat not in (None, "") and lon not in (None, ""):
        f = locate(float(lat), float(lon))
        if f:
            return [f], "point"
    if places and town and not mistyped:
        hits = places.get(f"{place_key(town)}|{_s(row.get('state')).upper()}", [])
        if len(hits) == 1:
            return list(hits), "place"
        if len(hits) > 1:
            named = [f for f in hits if _named_in_text(row, f, state, lookup)]
            if len(named) == 1:
                return named, "place_text"
            return [], "place_ambiguous"
    return [], ""


def county_fips(entity: str, row: dict, lookup: dict[str, str], state_names: dict[str, str]) -> tuple[str, str]:
    """(fips, "") on a hit, ("", reason) on a miss, ("", "") when the record
    has no county. lookup keys are '<county>|<state name>', lowercase;
    state_names maps a two-letter code to its name."""
    name = county_name(entity, row)
    if name is None:
        return "", ""
    if not name:
        return "", "blank_county"
    name = QUALIFIER.sub("", name).strip()
    if SEVERAL_COUNTIES.search(name):
        return "", "several_counties"
    state = state_names.get(_s(row.get("state")).upper(), "").lower()
    fips = lookup_county(name, state, lookup)
    if fips is None:
        return "", "not_in_lookup"
    if fips in NOT_2024_COUNTY or fips.startswith(NOT_2024_COUNTY_PREFIXES):
        return "", "not_a_2024_county"
    return fips, ""


def stamp(entity: str, row: dict) -> dict:
    """Add the derived fields to row in place and return it."""
    row["instrument_id"] = instrument_id(entity, row)
    if entity == "restrictions":
        row["scope"] = scope(row)
    row["evidence_level"] = evidence_level(entity, row)
    return row
