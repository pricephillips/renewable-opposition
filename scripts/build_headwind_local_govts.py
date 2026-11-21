"""How many local governments each county holds, for the Renewable Headwind Model.

Source: data/census_governments_2024.csv (scripts/build_census_governments.py,
from the Census Bureau's 2024 Gazetteer files; public domain, cite "Source:
U.S. Census Bureau, Gazetteer Files"). It lists every functioning general
purpose government below the county: incorporated places and town or
township governments (FUNCSTAT A, B or C).

Writes data/reference/headwind_inputs/local_govts.csv, one row per county
(every county in data/reference/county_covariates.csv, 0 where none holds a
government, and any other county the source names):
places, township_govts and local_govts (their sum). A place is counted in the
county that holds its internal point. There is no year column, so the plug-in
input reads it as a static value: the governments of 2024 stand in for
earlier years, since few are created or dissolved in a decade. Any of these
governments can enact a local rule, and the county labels count a rule
enacted by any of them, so the count is part of a county's exposure. The data
center model reads the same measure (plg_gov_local_govts in data-centers).

Guards before anything is written: at least 3,000 counties hold a
government, and at least 30,000 governments are counted. A failure writes
nothing.

Usage: python scripts/build_headwind_local_govts.py [--selftest]
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, read_csv, write_csv  # noqa: E402

SOURCE_PATH = ROOT / "data" / "census_governments_2024.csv"
COVARIATES_PATH = ROOT / "data" / "reference" / "county_covariates.csv"
OUT_PATH = ROOT / "data" / "reference" / "headwind_inputs" / "local_govts.csv"
FIELDS = ["county_fips", "places", "township_govts", "local_govts"]
MIN_COUNTIES, MIN_GOVTS = 3000, 30000


def build(rows: list[dict], counties: list[str] = ()) -> list[dict]:
    """Counts per county; a county in `counties` with no government gets 0."""
    places, towns = Counter(), Counter()
    for r in rows:
        f = (r.get("county_fips") or "").strip()
        if len(f) != 5 or not f.isdigit() or r.get("funcstat") not in ("A", "B", "C"):
            continue
        (places if r.get("kind") == "place" else towns)[f] += 1
    return [{"county_fips": f, "places": places[f], "township_govts": towns[f],
             "local_govts": places[f] + towns[f]} for f in sorted(set(places) | set(towns) | set(counties))]


def guard(out: list[dict], min_counties: int = MIN_COUNTIES, min_govts: int = MIN_GOVTS) -> list[str]:
    bad = []
    if len(out) < min_counties:
        bad.append(f"{len(out)} counties with a government, fewer than {min_counties}")
    total = sum(r["local_govts"] for r in out)
    if total < min_govts:
        bad.append(f"{total} governments, fewer than {min_govts}")
    return bad


def _selftest() -> int:
    rows = [{"county_fips": "42001", "kind": "place", "funcstat": "A"},
            {"county_fips": "42001", "kind": "county_subdivision", "funcstat": "A"},
            {"county_fips": "42001", "kind": "county_subdivision", "funcstat": "C"},
            {"county_fips": "42001", "kind": "place", "funcstat": "S"},
            {"county_fips": "51107", "kind": "place", "funcstat": "B"},
            {"county_fips": "", "kind": "place", "funcstat": "A"}]
    by = {r["county_fips"]: r for r in build(rows)}
    assert set(by) == {"42001", "51107"}, by
    assert (by["42001"]["places"], by["42001"]["township_govts"], by["42001"]["local_govts"]) == (1, 2, 3)
    assert by["51107"]["township_govts"] == 0 and by["51107"]["local_govts"] == 1
    assert guard(build(rows), 2, 4) == [] and len(guard(build(rows), 3, 5)) == 2
    assert build(rows, ["09110"])[0] == {"county_fips": "09110", "places": 0, "township_govts": 0,
                                         "local_govts": 0}, "a county with no government is 0, not missing"
    print("build_headwind_local_govts selftest: ok")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    out = build(read_csv(SOURCE_PATH), [r["county_fips"] for r in read_csv(COVARIATES_PATH)])
    bad = guard([r for r in out if r["local_govts"]])
    if bad:
        print("Guard failed, nothing written:\n  " + "\n  ".join(bad), file=sys.stderr)
        return 1
    write_csv(OUT_PATH, out, FIELDS)
    print(f"build_headwind_local_govts: {len(out)} counties, {sum(r['local_govts'] for r in out)} governments "
          f"-> {OUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
