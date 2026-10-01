#!/usr/bin/env python3
"""Build data/place_county_index.json: town, city, village and township names
to the county they sit in, from the Census 2024 Gazetteer files.

Why: about a hundred Sabin restrictions are town-level instruments with no
coordinates, so neither the county-name lookup nor the point-in-polygon test
can place them, and a county search silently misses them. This index lets
classify.county_fips_all place them by name.

Sources (public domain, U.S. Census Bureau):
  2024_Gaz_cousubs_national.zip  county subdivisions (townships, towns,
                                 MCDs); the GEOID's first five digits are the
                                 county FIPS, so no geometry is needed.
  2024_Gaz_place_national.zip    incorporated places and CDPs; the county is
                                 the 2024 county polygon containing the
                                 place's internal point (scripts/geo.py).

Output keys are '<normalized name>|<ST>' and values the sorted list of every
county a place of that name sits in, so a name shared by several places in a
state (Pennsylvania has many Washington Townships) keeps all of them and the
consumer can refuse to guess. A place that straddles counties is listed under
the county holding its internal point only.

Usage
  python scripts/build_place_index.py                       download, then build
  python scripts/build_place_index.py --cousub F --place F  build from local zips or .txt files
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import classify  # noqa: E402
import geo  # noqa: E402

OUT = ROOT / "data" / "place_county_index.json"
BASE = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/"
COUSUB_URL = BASE + "2024_Gaz_cousubs_national.zip"
PLACE_URL = BASE + "2024_Gaz_place_national.zip"

place_key = classify.place_key


def _read(source: str) -> tuple[list[dict], str]:
    if source.startswith("http"):
        with urllib.request.urlopen(source, timeout=120) as r:  # noqa: S310 (fixed Census URL)
            blob = r.read()
    else:
        blob = Path(source).read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    if blob[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            txt = z.read(next(n for n in z.namelist() if n.endswith(".txt")))
    else:
        txt = blob
    text = txt.decode("utf-8-sig", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text), delimiter="\t"))
    return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in rows], digest


def build(cousub_rows: list[dict], place_rows: list[dict]) -> dict[str, list[str]]:
    index: dict[str, set[str]] = {}
    for r in cousub_rows:
        geoid, st, nm = r.get("GEOID", ""), r.get("USPS", ""), r.get("NAME", "")
        if len(geoid) < 5 or not st or not nm or nm.lower().startswith("county subdivisions not defined"):
            continue
        index.setdefault(f"{place_key(nm)}|{st}", set()).add(geoid[:5])
    for r in place_rows:
        st, nm = r.get("USPS", ""), r.get("NAME", "")
        try:
            lat, lon = float(r["INTPTLAT"]), float(r["INTPTLONG"])
        except (KeyError, ValueError):
            continue
        fips = geo.county_at(lat, lon)
        if st and nm and fips:
            index.setdefault(f"{place_key(nm)}|{st}", set()).add(fips)
    return {k: sorted(v) for k, v in sorted(index.items())}


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--cousub", default=COUSUB_URL)
    a.add_argument("--place", default=PLACE_URL)
    x = a.parse_args()
    cousubs, h1 = _read(x.cousub)
    places, h2 = _read(x.place)
    index = build(cousubs, places)
    if len(index) < 10000:
        print(f"Only {len(index)} names; refusing to write a thin index.", file=sys.stderr)
        return 1
    out = {"_comment": (f"Built {date.today().isoformat()} by scripts/build_place_index.py from the Census "
                        f"2024 Gazetteer: {Path(x.cousub).name} (sha256 {h1[:16]}), "
                        f"{Path(x.place).name} (sha256 {h2[:16]}). Keys '<name>|<ST>'; values every "
                        "county a place of that name sits in.")}
    out.update(index)
    OUT.write_text(json.dumps(out, indent=0, sort_keys=False) + "\n", encoding="utf-8")
    ambiguous = sum(1 for v in index.values() if len(v) > 1)
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(index)} names, {ambiguous} in more than one county")
    return 0


if __name__ == "__main__":
    sys.exit(main())
