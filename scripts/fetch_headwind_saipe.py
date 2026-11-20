"""County poverty and median household income by year for the Renewable Headwind Model.

Source: Census Bureau, Small Area Income and Poverty Estimates (SAIPE), the
state and county text files, one per year,
https://www2.census.gov/programs-surveys/saipe/datasets/<year>/<year>-state-and-county/est<yy>all.txt.
No key. Public domain; cite "Source: U.S. Census Bureau, Small Area Income
and Poverty Estimates."

Writes data/reference/headwind_inputs/saipe.csv, one row per county and year
from 2005: the poverty rate, all ages (percent) and the median household income
(dollars, nominal). Unlike the 2020 to 2024 census values in the model, these
can be read as of the year before each request.

Each county line holds whitespace-separated fields: state and county FIPS,
then seven estimates with their 90 percent bounds (poverty count and percent,
all ages, under 18, ages 5 to 17 in families) and median household income,
then the county name. The poverty percent is the 6th field and the median
income the 21st. State lines (county 000) are skipped.

Guards before anything is written: every year 2008 to 2022 has at least 3,000
counties, and each year's median of median household income lies between
20,000 and 150,000 dollars. A failure writes nothing.

Usage: python scripts/fetch_headwind_saipe.py [--selftest | --dry-run]
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, write_csv  # noqa: E402

URL = "https://www2.census.gov/programs-surveys/saipe/datasets/{y}/{y}-state-and-county/est{yy}all.txt"
YEARS = range(2005, 2024)
OUT_PATH = ROOT / "data" / "reference" / "headwind_inputs" / "saipe.csv"
FIXTURE = ROOT / "tests" / "fixtures" / "headwind_inputs" / "saipe_sample.txt"
GUARD_YEARS, MIN_COUNTIES = range(2008, 2023), 3000
FIELDS = ["county_fips", "year", "poverty_pct", "median_hh_income"]
USER_AGENT = ("renewable-opposition-pipeline/0.1 "
              "(research; contact: github.com/pricephillips/renewable-opposition)")


def parse(text: str, year: int) -> list[dict]:
    rows = []
    for line in text.splitlines():
        tok = line.split()
        if len(tok) < 22 or not (tok[0].isdigit() and tok[1].isdigit()) or int(tok[1]) == 0:
            continue
        try:
            pct, inc = float(tok[5]), float(tok[20])
        except ValueError:
            continue
        rows.append({"county_fips": tok[0].zfill(2) + tok[1].zfill(3), "year": year,
                     "poverty_pct": pct, "median_hh_income": inc})
    return rows


def guard(rows: list[dict], years=GUARD_YEARS, min_counties: int = MIN_COUNTIES) -> list[str]:
    out = []
    for y in years:
        inc = [r["median_hh_income"] for r in rows if r["year"] == y]
        if len(inc) < min_counties:
            out.append(f"{y}: {len(inc)} counties, fewer than {min_counties}")
        elif not 20000 <= statistics.median(inc) <= 150000:
            out.append(f"{y}: median income {statistics.median(inc)} out of range (layout changed?)")
    return out


def _selftest() -> int:
    rows = parse(FIXTURE.read_text(encoding="utf-8"), 2015)
    assert [r["county_fips"] for r in rows] == ["01001", "01003"], rows
    assert 0 < rows[0]["poverty_pct"] < 100 and 20000 < rows[0]["median_hh_income"] < 150000, rows[0]
    assert guard(rows, [2015], 2) == [] and guard(rows, [2015], 3), "the guard counts counties per year"
    print("fetch_headwind_saipe selftest: ok")
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
            resp = requests.get(URL.format(y=y, yy=str(y)[2:]), headers={"User-Agent": USER_AGENT}, timeout=120)
            resp.raise_for_status()
            rows += parse(resp.content.decode("latin-1"), y)
    except Exception as exc:  # noqa: BLE001 - any download failure writes nothing
        print(f"Download failed, nothing written: {exc}", file=sys.stderr)
        return 1
    bad = guard(rows)
    if bad:
        print("Guard failed, nothing written:\n  " + "\n  ".join(bad), file=sys.stderr)
        return 1
    rows.sort(key=lambda r: (r["county_fips"], r["year"]))
    write_csv(OUT_PATH, rows, FIELDS)
    print(f"fetch_headwind_saipe: {len(rows)} county-years -> {OUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
