"""Match a named jurisdiction to its Census GEOID. Pure functions: no I/O.

scripts/build_database.py calls match() once per distinct (state,
jurisdiction type, jurisdiction name) that a restriction or an NREL siting
standard names, with the counties those records are placed in.

The rule refuses to guess. A jurisdiction gets a GEOID only when exactly one
government fits:
  - its name (normalized: case, punctuation, "St."/"Saint", "Mt."/"Mount",
    "Ft."/"Fort"), and
  - its kind of government (city, town, village, township, borough, ...),
    when the record says which ("Binghamton City", "Town of Cutler", or a
    jurisdiction_type of Town), and
  - its county, when the record is placed in one or more counties.
More than one fit is "ambiguous"; none is "no_match"; a single fit whose
county disagrees with the record's is "county_differs". All three are left
without a GEOID for a reviewer.

Counties match the county table by name within the state, and states their
own FIPS code.

Methods (how a GEOID was found)
  name_type_county  name, kind of government and county all agree
  name_type         name and kind agree; the record has no county
  name_county       name and county agree; the record does not say its kind
  name              the only government of that name in the state, and the
                    record names neither kind nor county
  name_county_other_type  the only government of that name in the record's
                    counties, though the record calls it another kind
                    ("Tipton City", a Census town)
  name_type_adjacent_county  (or name_adjacent_county when the record names
                    no kind) a place of that name and kind whose Census
                    county is next to the record's: places straddle county
                    lines, and the Census gives each the county of its
                    internal point only (Bethlehem, PA)
  county            a county jurisdiction, by its name
  state             a state jurisdiction
"""
from __future__ import annotations

import re

# Census legal descriptions that end a place or county subdivision name, longest
# first so "charter township" wins over "township".
TYPES = ("city and borough", "charter township", "plantation", "township", "borough", "village", "city",
         "town", "municipality", "unified government", "metro government", "consolidated government")
# A record's own word for the kind of government, and what it means here.
RECORD_TYPES = {"city": "city", "town": "town", "village": "village", "township": "township",
                "charter township": "township", "borough": "borough", "plantation": "plantation",
                "municipality": None}  # a jurisdiction_type of Municipality says nothing about the kind
_EQUIVALENT = {"charter township": "township"}

_PAREN = re.compile(r"\(([^)]*)\)")
_PREFIX = re.compile(r"^(?:the\s+)?(charter township|township|town|city|village|borough|plantation)\s+of\s+", re.I)
_SUFFIX = re.compile(r"\s+(charter township|township|town|city|village|borough|plantation|municipality)$", re.I)
COUNTY_SUFFIX = re.compile(r"\s+(county|parish|borough|census area|city and borough|municipality)$", re.I)


def norm(name: str) -> str:
    s = (name or "").lower().replace("&", " and ")
    s = re.sub(r"\bst\b\.?", "saint", s)
    s = re.sub(r"\bmt\b\.?", "mount", s)
    s = re.sub(r"\bft\b\.?", "fort", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def census_split(name: str) -> tuple[str, str | None]:
    """'Binghamton city' -> ('binghamton', 'city'); a name with no legal
    description keeps its type as None."""
    low = (name or "").strip()
    low = _PAREN.sub(" ", low).strip()
    for t in TYPES:
        if low.lower().endswith(" " + t):
            base = low[: -len(t)].strip()
            return norm(base), _EQUIVALENT.get(t, t)
    return norm(low), None


def record_split(name: str, jurisdiction_type: str = "") -> tuple[str, str | None, str]:
    """(normalized base name, kind of government or None, county named in a
    parenthetical or '') for a record's jurisdiction name."""
    raw = (name or "").strip()
    county_hint = ""
    for m in _PAREN.finditer(raw):
        if re.search(r"\b(county|parish)\b", m.group(1), re.I):
            county_hint = m.group(1).strip()
    raw = _PAREN.sub(" ", raw).strip()
    kind = None
    m = _PREFIX.match(raw)
    if m:
        kind, raw = m.group(1).lower(), raw[m.end():]
    else:
        m = _SUFFIX.search(raw)
        if m:
            kind, raw = m.group(1).lower(), raw[: m.start()]
            # "Monroeville Municipality" names the kind; a jurisdiction_type
            # of Municipality (below) is only the source's generic label.
            if kind == "municipality":
                return norm(raw), "municipality", county_hint
    if kind is None:
        kind = (jurisdiction_type or "").strip().lower() or None
    kind = RECORD_TYPES.get(kind) if kind in RECORD_TYPES else None
    return norm(raw), kind, county_hint


def index(governments: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """state -> normalized base name -> governments, from
    data/census_governments_2024.csv rows."""
    out: dict[str, dict[str, list[dict]]] = {}
    for g in governments:
        base, kind = census_split(g["name"])
        out.setdefault(g["state"], {}).setdefault(base, []).append({**g, "type": kind})
    return out


def match(idx: dict, state: str, jurisdiction_type: str, name: str, counties: set[str],
          county_names: dict[str, str] | None = None, state_fips: str = "",
          neighbors: dict[str, set[str]] | None = None) -> dict:
    """{'geoid', 'kind', 'method', 'candidates'}; geoid is '' when no single
    government fits. county_names: county FIPS -> county name for the
    state's counties (for county jurisdictions and parenthetical hints).
    neighbors: county FIPS -> adjacent counties, for places that straddle a
    county line (the Census gives a place the county of its internal point
    only)."""
    county_names = county_names or {}
    neighbors = neighbors or {}
    jt = (jurisdiction_type or "").strip().lower()
    if jt == "state":
        return {"geoid": state_fips, "kind": "state", "method": "state" if state_fips else "no_match",
                "candidates": 1 if state_fips else 0}
    # A municipality named "<X> County" is the county ("Atlantic County", NJ;
    # README, "Placement"); "Borough" alone stays a borough.
    if jt in ("county", "parish", "borough", "multi-county") or re.search(r"\s(county|parish)$", name or "", re.I):
        want = norm(COUNTY_SUFFIX.sub("", _PAREN.sub(" ", name or "").strip()))
        hits = sorted(f for f, n in county_names.items() if norm(COUNTY_SUFFIX.sub("", n)) == want)
        if len(hits) > 1 and counties:
            hits = [f for f in hits if f in counties] or hits
        if len(hits) == 1:
            return {"geoid": hits[0], "kind": "county", "method": "county", "candidates": 1}
        return {"geoid": "", "kind": "county", "method": "ambiguous" if hits else "no_match", "candidates": len(hits)}

    base, kind, hint = record_split(name, jurisdiction_type)
    if hint:
        hinted = {f for f, n in county_names.items() if norm(COUNTY_SUFFIX.sub("", n)) == norm(COUNTY_SUFFIX.sub("", hint))}
        counties = (counties & hinted) or hinted or counties
    by_name = list(idx.get(state, {}).get(base, []))
    cands = [c for c in by_name if c["type"] == kind] if kind else by_name
    if not cands and kind:
        # "Ponca City" is Census "Ponca City city": the word is part of the
        # name. Tried before another kind of the shorter name, so "Rogers
        # City" is Rogers City city, not Rogers township.
        whole = list(idx.get(state, {}).get(norm(_PAREN.sub(" ", name or "").strip()), []))
        if whole:
            by_name = whole
            cands = [c for c in by_name if c["type"] == kind]
    suffix = ""
    if not cands and kind and counties:
        # The record's kind disagrees with the Census's ("Tipton City", a
        # Census town): accept only the one government of that name in the
        # record's counties.
        cands = [c for c in by_name if c["county_fips"] in counties]
        if len(cands) == 1:
            c = cands[0]
            return {"geoid": c["geoid"], "kind": c["kind"], "method": "name_county_other_type", "candidates": 1}
        cands = []
    if not cands:
        return {"geoid": "", "kind": "", "method": "no_match", "candidates": 0}
    if counties:
        # A place whose Census internal point falls in water has no county;
        # it may be the one, and the uniqueness check below still applies.
        here = [c for c in cands if c["county_fips"] in counties or not c["county_fips"]]
        if not here:
            near = set().union(*(neighbors.get(f, set()) for f in counties))
            here = [c for c in cands if c["kind"] == "place" and c["county_fips"] in near]
            if len(here) != 1:
                return {"geoid": "", "kind": "", "method": "county_differs", "candidates": len(cands)}
            suffix = "_adjacent_county"
        cands = here
    # A place and a county subdivision of the same name, kind and county are
    # one government recorded twice (an independent city); keep the place.
    seen: dict[tuple, dict] = {}
    for c in sorted(cands, key=lambda c: (c["kind"] != "place", c["geoid"])):
        seen.setdefault((c["type"], c["county_fips"]), c)
    cands = list(seen.values())
    if len(cands) > 1:
        return {"geoid": "", "kind": "", "method": "ambiguous", "candidates": len(cands)}
    c = cands[0]
    method = ("name" + ("_type" if kind else "") + ("_county" if counties else "")) if not suffix \
        else "name" + ("_type" if kind else "") + suffix
    return {"geoid": c["geoid"], "kind": c["kind"], "method": method, "candidates": 1}
