#!/usr/bin/env python3
"""Build data/census_governments_2024.csv: every functioning local government
below the county (incorporated places and county subdivisions with an active
government), with its Census GEOID, from the Census 2024 Gazetteer files.

Why: restrictions and NREL siting standards name local governments as text
("Binghamton City", "Town of Cutler", "Porter Township"). The pipeline's
match key (common.jurisdiction_key) folds "<Name> City" and "<Name> Town"
together, so two governments can share one key. A GEOID is the Census's own
identifier for each government and keeps them apart; scripts/build_database.py
matches every named jurisdiction to one (docs/national_database_design.md,
phase 5).

Sources (public domain, U.S. Census Bureau), the same files
scripts/build_place_index.py reads:
  2024_Gaz_place_national.zip    incorporated places (and CDPs, left out)
  2024_Gaz_cousubs_national.zip  county subdivisions: towns, townships,
                                 boroughs and the rest

Kept: FUNCSTAT A (active government), B (active, partly consolidated) and C
(active, consolidated with another government). Statistical areas (CDPs,
CCDs, FUNCSTAT S), fictitious (F), nonfunctioning (N), inactive (I) and
unorganized (G) entities are not governments and are left out.

Columns
  geoid        7-digit place GEOID or 10-digit county subdivision GEOID
  kind         place | county_subdivision
  state        USPS code
  county_fips  the county: a county subdivision's own first five digits; a
               place's is the 2024 county containing its internal point
  name         the Census name, legal description included ("Binghamton city")
  funcstat     A | B | C

Usage
  python scripts/build_census_governments.py                       download, then build
  python scripts/build_census_governments.py --cousub F --place F  build from local zips or .txt files
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import geo  # noqa: E402
from build_place_index import COUSUB_URL, PLACE_URL, _read  # noqa: E402

OUT = ROOT / "data" / "census_governments_2024.csv"
FIELDS = ["geoid", "kind", "state", "county_fips", "name", "funcstat"]
GOVERNMENT = {"A", "B", "C"}


def build(cousub_rows: list[dict], place_rows: list[dict]) -> list[dict]:
    out = []
    for r in place_rows:
        if r.get("FUNCSTAT") not in GOVERNMENT:
            continue
        try:
            lat, lon = float(r["INTPTLAT"]), float(r["INTPTLONG"])
        except (KeyError, ValueError):
            continue
        out.append({"geoid": r["GEOID"], "kind": "place", "state": r["USPS"],
                    "county_fips": geo.county_at(lat, lon), "name": r["NAME"], "funcstat": r["FUNCSTAT"]})
    for r in cousub_rows:
        if r.get("FUNCSTAT") not in GOVERNMENT or len(r.get("GEOID", "")) != 10:
            continue
        out.append({"geoid": r["GEOID"], "kind": "county_subdivision", "state": r["USPS"],
                    "county_fips": r["GEOID"][:5], "name": r["NAME"], "funcstat": r["FUNCSTAT"]})
    return sorted(out, key=lambda r: (r["state"], r["kind"], r["geoid"]))


def write(rows: list[dict], path: Path = OUT) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--cousub", default=COUSUB_URL)
    a.add_argument("--place", default=PLACE_URL)
    x = a.parse_args()
    cousubs, h1 = _read(x.cousub)
    places, h2 = _read(x.place)
    rows = build(cousubs, places)
    if len(rows) < 30000:
        print(f"Only {len(rows)} governments; refusing to write a thin list.", file=sys.stderr)
        return 1
    write(rows, OUT)
    kinds = {k: sum(1 for r in rows if r["kind"] == k) for k in ("place", "county_subdivision")}
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(rows)} governments ({kinds['place']} places, "
          f"{kinds['county_subdivision']} county subdivisions); sha256 cousubs {h1[:16]}, places {h2[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
