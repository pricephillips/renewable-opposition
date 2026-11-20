"""County income and population by year for the Renewable Headwind Model.

Source: Bureau of Economic Analysis, Regional Economic Accounts, table CAINC1
(county personal income summary), https://apps.bea.gov/regional/zip/CAINC1.zip.
No key. BEA's statistics are public domain; cite "Source: U.S. Bureau of
Economic Analysis, CAINC1."

Writes data/reference/headwind_inputs/bea_cainc1.csv, one row per county and
year from 2000: per capita personal income (dollars, nominal), population, and
the population change over the five years before (pop_growth_5y, a share: 0.05
is five percent). config/headwind_inputs.json reads two of its columns as
plug-in inputs (income_pc and pop_growth_5y), each lagged a year, so a request
made in year Y reads year Y - 1. Being yearly, both fix the main weakness of
the census covariates, which are 2020 to 2024 values for requests made from
2010.

BEA folds 23 Virginia independent cities into a neighbouring county (codes
51901 to 51958, for example "Albemarle + Charlottesville"). Each such row is
written under every county FIPS it names, matched by name against
data/reference/county_covariates.csv. Connecticut stays on its eight old
counties, as in BEA's file.

Guards before anything is written: the file has the columns read, and every
year 2008 to 2022 covers at least 3,000 counties. A failure writes nothing.

Usage: python scripts/fetch_headwind_bea_income.py [--selftest | --dry-run]
"""
from __future__ import annotations

import csv
import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, read_csv, write_csv  # noqa: E402

URL = "https://apps.bea.gov/regional/zip/CAINC1.zip"
MEMBER = "CAINC1__ALL_AREAS_"
OUT_PATH = ROOT / "data" / "reference" / "headwind_inputs" / "bea_cainc1.csv"
COVARIATES_PATH = ROOT / "data" / "reference" / "county_covariates.csv"
FIXTURE = ROOT / "tests" / "fixtures" / "headwind_inputs" / "cainc1_sample.csv"
FIRST_YEAR, GUARD_YEARS, MIN_COUNTIES = 2000, range(2008, 2023), 3000
FIELDS = ["county_fips", "year", "income_pc", "population", "pop_growth_5y"]
USER_AGENT = ("renewable-opposition-pipeline/0.1 "
              "(research; contact: github.com/pricephillips/renewable-opposition)")


def _clean(v: str) -> str:
    return (v or "").strip().strip('"').strip()


def virginia_names(cov_rows: list[dict]) -> dict[str, list[str]]:
    """Name to FIPS for Virginia, counties first, then independent cities."""
    out: dict[str, list[str]] = {}
    for r in sorted((r for r in cov_rows if r["county_fips"].startswith("51")), key=lambda r: r["county_fips"]):
        out.setdefault(r["county"].lower(), []).append(r["county_fips"])
    return out


def components(name: str, va: dict[str, list[str]]) -> list[str]:
    """FIPS codes named by a BEA combination, e.g. 'Fairfax, Fairfax City + Falls Church, VA*'.
    The first name is a county (FIPS below 51500), the rest are cities."""
    parts = [p.strip() for p in name.split(",")[:-1] if p.strip()]
    names = [n.strip() for p in parts for n in p.split("+") if n.strip()]
    out = []
    for i, n in enumerate(names):
        key = n.lower().removesuffix(" city").strip()
        codes = va.get(key, [])
        county = [c for c in codes if c < "51500"]
        city = [c for c in codes if c >= "51500"]
        pick = (county or city) if i == 0 else (city or county)
        if pick:
            out.append(pick[0])
    return out


def build(text: str, cov_rows: list[dict]) -> list[dict]:
    reader = csv.reader(io.StringIO(text))
    header = [_clean(h) for h in next(reader)]
    for col in ("GeoFIPS", "GeoName", "LineCode"):
        if col not in header:
            raise ValueError(f"CAINC1 has no {col} column")
    years = [(i, int(h)) for i, h in enumerate(header) if h.isdigit() and int(h) >= FIRST_YEAR - 5]
    va = virginia_names(cov_rows)
    pop: dict[str, dict[int, float]] = {}
    inc: dict[str, dict[int, float]] = {}
    for r in reader:
        if len(r) < len(header):
            continue
        fips, line = _clean(r[0]), _clean(r[header.index("LineCode")])
        if len(fips) != 5 or not fips.isdigit() or fips.endswith("000") or line not in ("2", "3"):
            continue
        if "51900" <= fips <= "51999":
            targets = components(_clean(r[header.index("GeoName")]), va)
        else:
            targets = [fips]
        for t in targets:
            series = (pop if line == "2" else inc).setdefault(t, {})
            for i, y in years:
                try:
                    series[y] = float(_clean(r[i]))
                except ValueError:
                    pass
    rows = []
    for fips in sorted(set(pop) | set(inc)):
        p, m = pop.get(fips, {}), inc.get(fips, {})
        for y in sorted(set(p) | set(m)):
            if y < FIRST_YEAR:
                continue
            growth = (p[y] / p[y - 5] - 1.0) if y in p and p.get(y - 5) else None
            rows.append({"county_fips": fips, "year": y, "income_pc": m.get(y, ""), "population": p.get(y, ""),
                         "pop_growth_5y": "" if growth is None else round(growth, 5)})
    return rows


def guard(rows: list[dict], min_counties: int = MIN_COUNTIES) -> list[str]:
    out = []
    for y in GUARD_YEARS:
        n = sum(1 for r in rows if r["year"] == y and r["income_pc"] != "")
        if n < min_counties:
            out.append(f"{y}: {n} counties with income, fewer than {min_counties}")
    return out


def download() -> str:
    import requests
    resp = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=300)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        name = next(n for n in z.namelist() if n.startswith(MEMBER))
        return z.read(name).decode("latin-1")


def _selftest() -> int:
    cov = [{"county_fips": "51003", "county": "Albemarle"}, {"county_fips": "51540", "county": "Charlottesville"},
           {"county_fips": "51059", "county": "Fairfax"}, {"county_fips": "51600", "county": "Fairfax"},
           {"county_fips": "51610", "county": "Falls Church"}]
    va = virginia_names(cov)
    assert components("Fairfax, Fairfax City + Falls Church, VA*", va) == ["51059", "51600", "51610"]
    rows = build(FIXTURE.read_text(encoding="utf-8"), cov)
    by = {(r["county_fips"], r["year"]): r for r in rows}
    a = by[("01001", 2015)]
    assert a["income_pc"] and a["population"] and a["pop_growth_5y"] != "", a
    assert by[("51003", 2015)]["income_pc"] == by[("51540", 2015)]["income_pc"], "a combination fills each member"
    assert not any(r["county_fips"].endswith("000") for r in rows), "no state or national rows"
    assert min(r["year"] for r in rows) == FIRST_YEAR
    assert guard(rows, 4) == [] and guard(rows, 5), "the guard counts counties per year"
    print("fetch_headwind_bea_income selftest: ok")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    if "--dry-run" in sys.argv:
        print(f"[dry-run] {URL} -> {OUT_PATH.relative_to(ROOT)}")
        return 0
    try:
        text = download()
    except Exception as exc:  # noqa: BLE001 - any download failure writes nothing
        print(f"Download failed, nothing written: {exc}", file=sys.stderr)
        return 1
    rows = build(text, read_csv(COVARIATES_PATH))
    bad = guard(rows)
    if bad:
        print("Guard failed, nothing written:\n  " + "\n  ".join(bad), file=sys.stderr)
        return 1
    write_csv(OUT_PATH, rows, FIELDS)
    print(f"fetch_headwind_bea_income: {len(rows)} county-years, {len({r['county_fips'] for r in rows})} counties "
          f"-> {OUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
