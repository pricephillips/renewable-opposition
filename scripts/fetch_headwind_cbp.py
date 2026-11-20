"""County business patterns by year for the Renewable Headwind Model.

Source: Census Bureau, County Business Patterns, the complete county files,
one zip per year, https://www2.census.gov/programs-surveys/cbp/datasets/<year>/cbp<yy>co.zip.
No key. Public domain; cite "Source: U.S. Census Bureau, County Business
Patterns."

Writes data/reference/headwind_inputs/cbp.csv, one row per county and year
from 2007: total employment (mid-March), total establishments, and the share
of establishments in construction (NAICS 23), utilities (NAICS 22) and
agriculture support (NAICS 11). Employment by sector is often suppressed in
small counties, so the sector measures use establishment counts, which are
never suppressed.

Guards before anything is written: every year 2008 to 2021 has at least 3,000
counties with establishments. A failure writes nothing. Each zip is about 15
MB, so a full run downloads about 250 MB.

Usage: python scripts/fetch_headwind_cbp.py [--selftest | --dry-run]
"""
from __future__ import annotations

import csv
import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, write_csv  # noqa: E402

URL = "https://www2.census.gov/programs-surveys/cbp/datasets/{y}/cbp{yy}co.zip"
YEARS = range(2007, 2023)
OUT_PATH = ROOT / "data" / "reference" / "headwind_inputs" / "cbp.csv"
FIXTURE = ROOT / "tests" / "fixtures" / "headwind_inputs" / "cbp_sample.txt"
GUARD_YEARS, MIN_COUNTIES = range(2008, 2022), 3000
SECTORS = {"23----": "construction_est_share", "22----": "utilities_est_share", "11----": "ag_support_est_share"}
FIELDS = ["county_fips", "year", "employment", "establishments", *SECTORS.values()]
USER_AGENT = ("renewable-opposition-pipeline/0.1 "
              "(research; contact: github.com/pricephillips/renewable-opposition)")


def parse(text: str, year: int) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    reader.fieldnames = [f.strip().lower() for f in reader.fieldnames]
    by: dict[str, dict] = {}
    for r in reader:
        naics = (r.get("naics") or "").strip()
        if naics != "------" and naics not in SECTORS:
            continue
        fips = r["fipstate"].strip().zfill(2) + r["fipscty"].strip().zfill(3)
        if fips.endswith("999"):  # statewide, no county
            continue
        try:
            est = int(r["est"])
        except (TypeError, ValueError):
            continue
        d = by.setdefault(fips, {"county_fips": fips, "year": year})
        if naics == "------":
            d["establishments"] = est
            try:
                d["employment"] = int(r["emp"])
            except (TypeError, ValueError):
                d["employment"] = ""
        else:
            d["_" + SECTORS[naics]] = est
    rows = []
    for d in by.values():
        total = d.get("establishments")
        if not total:
            continue
        for col in SECTORS.values():
            d[col] = round(d.pop("_" + col, 0) / total, 5)
        rows.append(d)
    return rows


def guard(rows: list[dict], years=GUARD_YEARS, min_counties: int = MIN_COUNTIES) -> list[str]:
    out = []
    for y in years:
        n = sum(1 for r in rows if r["year"] == y)
        if n < min_counties:
            out.append(f"{y}: {n} counties, fewer than {min_counties}")
    return out


def _selftest() -> int:
    rows = parse(FIXTURE.read_text(encoding="utf-8"), 2012)
    by = {r["county_fips"]: r for r in rows}
    assert set(by) == {"01001", "01003"}, by
    a = by["01001"]
    assert a["establishments"] == 817 and a["employment"] == 9908, a
    assert 0 < a["construction_est_share"] < 1 and a["ag_support_est_share"] == round(6 / 817, 5), a
    assert guard(rows, [2012], 2) == [] and guard(rows, [2012], 3)
    print("fetch_headwind_cbp selftest: ok")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    if "--dry-run" in sys.argv:
        print(f"[dry-run] {URL.format(y=YEARS[0], yy=str(YEARS[0])[2:])} ... -> {OUT_PATH.relative_to(ROOT)}")
        return 0
    import requests
    rows = []
    try:
        for y in YEARS:
            resp = requests.get(URL.format(y=y, yy=str(y)[2:]), headers={"User-Agent": USER_AGENT}, timeout=300)
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                name = next(n for n in z.namelist() if n.lower().endswith(".txt"))
                rows += parse(z.read(name).decode("latin-1"), y)
    except Exception as exc:  # noqa: BLE001 - any download failure writes nothing
        print(f"Download failed, nothing written: {exc}", file=sys.stderr)
        return 1
    bad = guard(rows)
    if bad:
        print("Guard failed, nothing written:\n  " + "\n  ".join(bad), file=sys.stderr)
        return 1
    rows.sort(key=lambda r: (r["county_fips"], r["year"]))
    write_csv(OUT_PATH, rows, FIELDS)
    print(f"fetch_headwind_cbp: {len(rows)} county-years -> {OUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
