"""County house price growth by year for the Renewable Headwind Model.

Source: Federal Housing Finance Agency, House Price Index for counties
(all-transactions, annual, developmental),
https://www.fhfa.gov/hpi/download/annual/hpi_at_county.csv. No key. The file
is an Excel workbook despite its name. FHFA's data are a federal agency's own
work and public domain; cite "Source: Federal Housing Finance Agency, House
Price Index."

Writes data/reference/headwind_inputs/fhfa_hpi.csv, one row per county and
year from 2000: the index (base 100 in the county's first year, so its level
cannot be compared across counties) and its change over the five years before
(hpi_growth_5y, a share: 0.25 is 25 percent). config/headwind_inputs.json reads
hpi_growth_5y as the plug-in input hpi_growth_5y, lagged a year. Rising land
and house values change what a lease is worth to an owner and what neighbours
fear to lose, which the model had no measure of.

Guards before anything is written: the header row has the columns read, and
every year 2008 to 2022 covers at least 2,500 counties (FHFA leaves out
counties with too few sales). A failure writes nothing.

Usage: python scripts/fetch_headwind_fhfa_hpi.py [--selftest | --dry-run]
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, write_csv  # noqa: E402

URL = "https://www.fhfa.gov/hpi/download/annual/hpi_at_county.csv"
OUT_PATH = ROOT / "data" / "reference" / "headwind_inputs" / "fhfa_hpi.csv"
FIRST_YEAR, GUARD_YEARS, MIN_COUNTIES = 2000, range(2008, 2023), 2500
FIELDS = ["county_fips", "year", "hpi", "hpi_growth_5y"]
HEADER = ("FIPS code", "Year", "HPI")
USER_AGENT = ("renewable-opposition-pipeline/0.1 "
              "(research; contact: github.com/pricephillips/renewable-opposition)")


def build(sheet_rows) -> list[dict]:
    """Rows of the workbook's one sheet, as tuples, to county-year rows."""
    it = iter(sheet_rows)
    for head in it:
        if head and all(h in head for h in HEADER):
            break
    else:
        raise ValueError(f"no header row with {HEADER}")
    i_f, i_y, i_h = (head.index(h) for h in HEADER)
    series: dict[str, dict[int, float]] = {}
    for r in it:
        try:
            fips = str(int(r[i_f])).zfill(5) if not isinstance(r[i_f], str) else r[i_f].strip().zfill(5)
            series.setdefault(fips, {})[int(r[i_y])] = float(r[i_h])
        except (TypeError, ValueError, IndexError):
            continue  # FHFA marks a missing value with "."
    rows = []
    for fips in sorted(series):
        s = series[fips]
        for y in sorted(s):
            if y < FIRST_YEAR:
                continue
            g = (s[y] / s[y - 5] - 1.0) if s.get(y - 5) else None
            rows.append({"county_fips": fips, "year": y, "hpi": s[y],
                         "hpi_growth_5y": "" if g is None else round(g, 5)})
    return rows


def guard(rows: list[dict], min_counties: int = MIN_COUNTIES) -> list[str]:
    out = []
    for y in GUARD_YEARS:
        n = sum(1 for r in rows if r["year"] == y and r["hpi_growth_5y"] != "")
        if n < min_counties:
            out.append(f"{y}: {n} counties with a five-year change, fewer than {min_counties}")
    return out


def download():
    import openpyxl
    import requests
    resp = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=300)
    resp.raise_for_status()
    wb = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
    return list(wb.worksheets[0].iter_rows(values_only=True))


def _selftest() -> int:
    sheet = [("HPI for Counties", None, None, None, None, None), (None,) * 6,
             ("State", "County", "FIPS code", "Year", "Annual Change (%)", "HPI")]
    sheet += [("AL", "Autauga", "01001", y, 1.0, 100.0 + 10 * (y - 1995)) for y in range(1995, 2011)]
    sheet += [("ID", "Jefferson", 16051, 2004, None, 120.0), ("ID", "Jefferson", 16051, 2009, None, "."),
              ("ID", "Jefferson", 16051, 2010, None, 150.0)]
    rows = build(sheet)
    by = {(r["county_fips"], r["year"]): r for r in rows}
    assert by[("01001", 2005)]["hpi_growth_5y"] == round(200 / 150 - 1, 5)
    assert ("01001", 1999) not in by, "nothing before the first year kept"
    assert ("16051", 2009) not in by, "a '.' value is skipped"
    assert by[("16051", 2010)]["hpi_growth_5y"] == "", "no growth without the year five before"
    assert "16051" in {r["county_fips"] for r in rows}, "a numeric FIPS is zero-padded"
    try:
        build([("no", "header")])
        raise AssertionError("a sheet with no header must fail")
    except ValueError:
        pass
    print("fetch_headwind_fhfa_hpi selftest: ok")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    if "--dry-run" in sys.argv:
        print(f"[dry-run] {URL} -> {OUT_PATH.relative_to(ROOT)}")
        return 0
    try:
        sheet = download()
    except Exception as exc:  # noqa: BLE001 - any download failure writes nothing
        print(f"Download failed, nothing written: {exc}", file=sys.stderr)
        return 1
    rows = build(sheet)
    bad = guard(rows)
    if bad:
        print("Guard failed, nothing written:\n  " + "\n  ".join(bad), file=sys.stderr)
        return 1
    write_csv(OUT_PATH, rows, FIELDS)
    print(f"fetch_headwind_fhfa_hpi: {len(rows)} county-years, {len({r['county_fips'] for r in rows})} counties "
          f"-> {OUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
