"""County covariates for the county restriction model (predictive foundation, step 1).

One row per 2024 county in the 50 states and DC (3,144 counties; Connecticut
as its nine planning regions), in data/reference/county_covariates.csv:

  demographic  ACS 5-year estimates from the Census Bureau's table-based
               summary files (www2.census.gov, no API key): population
               (B01003), median household income (B19013) and the share of
               adults 25 and over with a bachelor's degree or more (B15003).
               Land area from the 2024 Census Gazetteer, and density from the
               two.
  political    MIT Election Data and Science Lab, County Presidential Election
               Returns 2000-2024 (Harvard Dataverse, doi:10.7910/DVN/VOQCHQ,
               CC0): two-party Democratic share and the D minus R margin for
               2016, 2020 and 2024, and the change in two-party share between
               cycles. Alaska (reported by state house district) and
               Connecticut (reported by its eight retired counties in every
               year, 2024 included) do not map onto the county frame and carry
               statewide values, with geo_basis_<year> = state.

Every variable is an attribute of the county, not of any project or
opposition record, so every column is leakage class "none"
(docs/predictive_foundation_design.md, section 3). The variables that come
from this repo's own records (plant exposure, neighbouring restrictions, state
siting law, data center events) are computed by the model's feature builder,
not here.

The MEDSL file cannot be downloaded anonymously: Dataverse asks for a
guestbook response first. data/reference/medsl/countypres_2000-2024.csv is
the copy pricephillips/data-center-map keeps (data/raw/medsl/), downloaded by
a person. Each run reads Dataverse's metadata, which needs no guestbook, and
refuses the copy when its md5 differs from the one Dataverse publishes (a new
MEDSL release), so a stale copy fails loudly with the steps to replace it.

The ACS and Gazetteer files are not committed (about 130 MB);
data/reference/county_covariates_manifest.csv records each one's URL,
release, SHA-256 and the rows read and kept. data/reference/
county_covariates_catalog.json describes every column: its source, vintage,
unit and leakage class.

Guards, before anything is written: every file must have the columns this
script reads, the ACS must cover at least 3,140 frame counties with a national
population between 300 and 360 million, and MEDSL must give a county-basis
2024 result for at least 3,000 counties. A failure writes nothing.

Usage
  python scripts/fetch_county_covariates.py              fetch and write
  python scripts/fetch_county_covariates.py --dry-run    print the plan
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geo  # noqa: E402
from common import ROOT, read_csv, write_csv  # noqa: E402

REFERENCE_DIR = ROOT / "data" / "reference"
COVARIATES_PATH = REFERENCE_DIR / "county_covariates.csv"
MANIFEST_PATH = REFERENCE_DIR / "county_covariates_manifest.csv"
CATALOG_PATH = REFERENCE_DIR / "county_covariates_catalog.json"
MEDSL_PATH = REFERENCE_DIR / "medsl" / "countypres_2000-2024.csv"

ACS_YEAR = 2024
ACS_RELEASE = f"ACS 5-year {ACS_YEAR - 4}-{ACS_YEAR}"
ACS_BASE = (f"https://www2.census.gov/programs-surveys/acs/summary_file/{ACS_YEAR}/"
            f"table-based-SF/data/5YRData/")
ACS_TABLES = {"b01003": ["B01003_E001"],
              "b19013": ["B19013_E001"],
              "b15003": ["B15003_E001", "B15003_E022", "B15003_E023", "B15003_E024", "B15003_E025"]}
GAZETTEER_URL = ("https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/"
                 "2024_Gaz_counties_national.zip")
DATAVERSE = "https://dataverse.harvard.edu"
MEDSL_DOI = "doi:10.7910/DVN/VOQCHQ"
MEDSL_FILE = "countypres_2000-2024"
MEDSL_REQUIRED = ["year", "state_po", "county_fips", "office", "party", "candidatevotes",
                  "totalvotes", "mode"]
YEARS = [2016, 2020, 2024]
STATE_FALLBACK = {"AK", "CT"}
# Places MEDSL reports apart from (or under an old code for) a frame county,
# as in data-center-map's fetch_county_features.py.
MEDSL_FOLD = {"2938000": "29095",      # Kansas City MO, reported apart from Jackson County
              "46113": "46102",        # Shannon County SD, renamed Oglala Lakota (2015)
              "51515": "51019"}        # Bedford city VA, merged into Bedford County (2013)
ACS_SENTINELS = {-666666666.0, -999999999.0, -888888888.0, -222222222.0, -333333333.0, -555555555.0}

MIN_FRAME_COUNTIES = 3140
POPULATION_RANGE = (300e6, 360e6)
MIN_MEDSL_2024_COUNTIES = 3000

USER_AGENT = ("renewable-opposition-pipeline/0.1 "
              "(research; contact: github.com/pricephillips/renewable-opposition)")

FIELDS = (["county_fips", "state", "county", "population", "land_sqmi", "pop_density_sqmi",
           "median_hh_income", "pct_bachelors_plus"]
          + [f"{c}_{y}" for y in YEARS for c in ("dem_share_2p", "margin_dr", "geo_basis")]
          + [f"dem_share_2p_chg_{a}_{b}" for a, b in zip(YEARS, YEARS[1:])])
MANIFEST_FIELDS = ["source", "release", "url", "file_name", "sha256", "bytes", "fetched_at",
                   "rows_read", "rows_kept", "license"]

COLUMNS = {
    "county_fips": ("2024 county FIPS code (Connecticut planning regions 09110 to 09190)", "frame", ""),
    "state": ("Two-letter state code", "frame", ""),
    "county": ("County name, from the 2024 boundary file", "frame", ""),
    "population": ("Total population (B01003_001)", "acs", "people"),
    "land_sqmi": ("Land area (ALAND_SQMI)", "gazetteer", "square miles"),
    "pop_density_sqmi": ("population / land_sqmi", "acs+gazetteer", "people per square mile"),
    "median_hh_income": ("Median household income in the past 12 months (B19013_001)", "acs",
                         f"{ACS_YEAR} inflation-adjusted dollars"),
    "pct_bachelors_plus": ("Share of people 25 and over with a bachelor's, master's, professional or "
                           "doctoral degree (B15003_022 to _025 over B15003_001)", "acs", "percent"),
}
for _y in YEARS:
    COLUMNS[f"dem_share_2p_{_y}"] = (f"Democratic share of the two-party presidential vote, {_y}",
                                     "medsl", "share 0 to 1")
    COLUMNS[f"margin_dr_{_y}"] = (f"(Democratic - Republican) / total presidential votes, {_y}; the "
                                  "sign convention of data-center-map's county_votes.json", "medsl",
                                  "share -1 to 1")
    COLUMNS[f"geo_basis_{_y}"] = (f"county: the county's own {_y} returns; state: statewide values "
                                  "(Alaska and Connecticut); blank: no returns", "medsl", "")
for _a, _b in zip(YEARS, YEARS[1:]):
    COLUMNS[f"dem_share_2p_chg_{_a}_{_b}"] = (f"dem_share_2p_{_b} - dem_share_2p_{_a}", "medsl",
                                              "share points")


class SchemaError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _num(v) -> float | None:
    try:
        f = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return None if f in ACS_SENTINELS or f < 0 else f


def rnd(v: float | None, places: int = 4):
    return "" if v is None else round(v, places)


# ── Frame ───────────────────────────────────────────────────────────────────

def frame() -> dict[str, dict]:
    """fips -> {state, county} for every 2024 county in the 50 states and DC."""
    by_fips = {}
    for f in geo.all_counties():
        if f[:2] == "72" or int(f[:2]) > 56:
            continue
        by_fips[f] = {"state": STATE_BY_FIPS.get(f[:2], ""), "county": geo.name(f)}
    return by_fips


STATE_BY_FIPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE",
    "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA",
    "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM",
    "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY",
}


# ── ACS and Gazetteer ───────────────────────────────────────────────────────

def read_acs_table(data: bytes, columns: list[str]) -> tuple[dict[str, dict], int]:
    """(fips -> {column: value}, rows read) for the county rows (GEO_ID
    0500000USsscc) of one pipe-delimited table-based summary file."""
    text = data.decode("utf-8-sig", errors="replace")
    lines = iter(text.splitlines())
    header = next(lines, "").split("|")
    lacks = [c for c in ["GEO_ID", *columns] if c not in header]
    if lacks:
        raise SchemaError(f"ACS table lacks column(s) {lacks}")
    ix = {c: i for i, c in enumerate(header)}
    out, read = {}, 0
    for line in lines:
        read += 1
        if not line.startswith("0500000US"):
            continue
        cells = line.split("|")
        out[cells[ix["GEO_ID"]][-5:]] = {c: _num(cells[ix[c]]) for c in columns}
    return out, read


def read_gazetteer(data: bytes) -> dict[str, float]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise SchemaError("Gazetteer: not a zip file") from exc
    names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
    if len(names) != 1:
        raise SchemaError(f"Gazetteer: expected one .txt in the zip, found {names}")
    reader = csv.DictReader(io.StringIO(zf.read(names[0]).decode("utf-8-sig", errors="replace")),
                            delimiter="\t")
    reader.fieldnames = [f.strip() for f in reader.fieldnames or []]
    if "GEOID" not in reader.fieldnames or "ALAND_SQMI" not in reader.fieldnames:
        raise SchemaError(f"Gazetteer: missing GEOID or ALAND_SQMI in {reader.fieldnames}")
    out = {}
    for row in reader:
        v = _num(row["ALAND_SQMI"])
        if v:
            out[row["GEOID"].strip().zfill(5)] = v
    return out


def demographic(tables: dict[str, dict[str, dict]], land: dict[str, float],
                counties: dict[str, dict]) -> dict[str, dict]:
    out = {}
    for f in counties:
        pop = (tables["b01003"].get(f) or {}).get("B01003_E001")
        income = (tables["b19013"].get(f) or {}).get("B19013_E001")
        ed = tables["b15003"].get(f) or {}
        total = ed.get("B15003_E001")
        ba = sum(ed.get(c) or 0.0 for c in ("B15003_E022", "B15003_E023", "B15003_E024", "B15003_E025"))
        sqmi = land.get(f)
        out[f] = {"population": int(pop) if pop is not None else "",
                  "land_sqmi": rnd(sqmi, 3),
                  "pop_density_sqmi": rnd(pop / sqmi, 2) if pop is not None and sqmi else "",
                  "median_hh_income": int(income) if income is not None else "",
                  "pct_bachelors_plus": rnd(100.0 * ba / total, 2) if total else ""}
    return out


def check_demographic(rows: dict[str, dict]) -> None:
    with_pop = [r["population"] for r in rows.values() if r["population"] != ""]
    if len(with_pop) < MIN_FRAME_COUNTIES:
        raise SchemaError(f"ACS covers {len(with_pop)} frame counties; at least {MIN_FRAME_COUNTIES} expected")
    total = sum(with_pop)
    if not POPULATION_RANGE[0] <= total <= POPULATION_RANGE[1]:
        raise SchemaError(f"ACS national population {total:,} is outside {POPULATION_RANGE}")


# ── MEDSL ───────────────────────────────────────────────────────────────────

def medsl_fips(v) -> str:
    s = str(v or "").strip().split(".")[0]
    if s in MEDSL_FOLD:
        return MEDSL_FOLD[s]
    f = s.zfill(5) if s.isdigit() else s
    return MEDSL_FOLD.get(f, f)


def read_medsl(data: bytes) -> list[dict]:
    text = data.decode("utf-8-sig", errors="replace")
    head = text.split("\n", 1)[0]
    rows = list(csv.DictReader(io.StringIO(text), delimiter="\t" if head.count("\t") > head.count(",") else ","))
    if not rows:
        raise SchemaError("MEDSL: no rows")
    lacks = [c for c in MEDSL_REQUIRED if c not in rows[0]]
    if lacks:
        raise SchemaError(f"MEDSL: missing column(s) {lacks}")
    return rows


def medsl_votes(recs: list[dict]):
    """(votes[(year, raw_fips)] = {D, R}, totals[(year, raw_fips)], state_of[raw_fips]).
    Per county and year: the TOTAL-mode rows when the county has any,
    otherwise the sum of every mode. MEDSL repeats the county total on each
    row, so the total is the largest totalvotes."""
    has_total = {(str(r["year"]).strip(), str(r["county_fips"]).strip())
                 for r in recs if str(r.get("mode", "")).strip().upper() == "TOTAL"}
    votes = defaultdict(lambda: {"D": 0.0, "R": 0.0})
    totals: dict[tuple, float] = defaultdict(float)
    state_of = {}
    for r in recs:
        try:
            y = int(str(r["year"]).strip())
        except ValueError:
            continue
        if y not in YEARS or "PRESIDENT" not in str(r.get("office", "")).upper():
            continue
        raw = str(r.get("county_fips", "")).strip()
        if (str(y), raw) in has_total and str(r.get("mode", "")).strip().upper() != "TOTAL":
            continue
        party = str(r.get("party", "")).strip().upper()
        n = _num(r.get("candidatevotes")) or 0.0
        if party == "DEMOCRAT":
            votes[(y, raw)]["D"] += n
        elif party == "REPUBLICAN":
            votes[(y, raw)]["R"] += n
        totals[(y, raw)] = max(totals[(y, raw)], _num(r.get("totalvotes")) or 0.0)
        state_of[raw] = str(r.get("state_po", "")).strip().upper()
    return votes, totals, state_of


def political(recs: list[dict], counties: dict[str, dict]) -> dict[str, dict]:
    """fips -> political columns. A state in STATE_FALLBACK whose frame
    counties are not all matched in a year gets statewide values on every
    county (geo_basis state); elsewhere an unmatched county stays blank."""
    votes, totals, state_of = medsl_votes(recs)
    by_county = defaultdict(lambda: {"D": 0.0, "R": 0.0, "T": 0.0})
    by_state = defaultdict(lambda: {"D": 0.0, "R": 0.0, "T": 0.0})
    for (y, raw), v in votes.items():
        f = medsl_fips(raw)
        buckets = ([by_county[(y, f)]] if f in counties else []) + [by_state[(y, state_of[raw])]]
        for b in buckets:
            b["D"] += v["D"]
            b["R"] += v["R"]
            b["T"] += totals[(y, raw)]
    in_state = defaultdict(list)
    for f, meta in counties.items():
        in_state[meta["state"]].append(f)
    basis = {}
    for y in YEARS:
        for st, fs in in_state.items():
            full = all((y, f) in by_county for f in fs)
            use_state = not full and st in STATE_FALLBACK and (y, st) in by_state
            for f in fs:
                basis[(y, f)] = "state" if use_state else ("county" if (y, f) in by_county else "")
    out = {}
    for f, meta in counties.items():
        row, share = {}, {}
        for y in YEARS:
            b = basis[(y, f)]
            v = by_county[(y, f)] if b == "county" else by_state[(y, meta["state"])] if b == "state" else None
            two = (v["D"] + v["R"]) if v else 0.0
            share[y] = v["D"] / two if v and two > 0 else None
            margin = (v["D"] - v["R"]) / v["T"] if v and v["T"] > 0 else None
            row.update({f"dem_share_2p_{y}": rnd(share[y]), f"margin_dr_{y}": rnd(margin),
                        f"geo_basis_{y}": b})
        for a, b in zip(YEARS, YEARS[1:]):
            row[f"dem_share_2p_chg_{a}_{b}"] = rnd(share[b] - share[a]
                                                   if share[a] is not None and share[b] is not None else None)
        out[f] = row
    return out


def check_political(rows: dict[str, dict]) -> None:
    n = sum(1 for r in rows.values() if r["geo_basis_2024"] == "county")
    if n < MIN_MEDSL_2024_COUNTIES:
        raise SchemaError(f"MEDSL gives 2024 county returns for {n} frame counties; "
                          f"at least {MIN_MEDSL_2024_COUNTIES} expected")


def dataverse_metadata(session: requests.Session) -> dict:
    """The MEDSL file's md5, dataset version and license, from the dataset
    metadata Dataverse serves without a guestbook."""
    r = session.get(f"{DATAVERSE}/api/datasets/:persistentId/", params={"persistentId": MEDSL_DOI}, timeout=60)
    r.raise_for_status()
    ver = r.json()["data"]["latestVersion"]
    for f in ver.get("files", []):
        df = f.get("dataFile", {})
        if MEDSL_FILE in f"{df.get('filename', '')} {df.get('originalFileName', '')}".lower():
            lic = ver.get("license")
            return {"md5": df.get("md5") or (df.get("checksum") or {}).get("value", ""),
                    "version": f"{ver.get('versionNumber', '')}.{ver.get('versionMinorNumber', '')}",
                    "license": lic.get("name", "") if isinstance(lic, dict) else str(lic or ""),
                    "file_name": df.get("originalFileName") or df.get("filename", "")}
    raise SchemaError(f"no file matching {MEDSL_FILE!r} in {MEDSL_DOI}")


def check_medsl_copy(data: bytes, meta: dict) -> None:
    got = hashlib.md5(data).hexdigest()
    if meta["md5"] and meta["md5"] != got:
        raise SchemaError(
            f"{MEDSL_PATH.relative_to(ROOT)} (md5 {got}) is not the file Dataverse publishes "
            f"(md5 {meta['md5']}, version {meta['version']}): MEDSL has released a new version. "
            f"Open https://doi.org/{MEDSL_DOI.removeprefix('doi:')}, fill in the guestbook, download "
            f"{meta['file_name']} in its original CSV format, and replace the file unedited.")


# ── Assembly ────────────────────────────────────────────────────────────────

def build(acs: dict[str, tuple[str, bytes]], gazetteer: tuple[str, bytes], medsl: bytes,
          medsl_meta: dict, counties: dict[str, dict] | None = None) -> tuple[list[dict], list[dict], dict]:
    """(covariate rows, manifest rows, catalog). Raises SchemaError on any
    changed layout or implausible total."""
    counties = counties if counties is not None else frame()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest, tables = [], {}
    for table, (url, data) in acs.items():
        tables[table], read = read_acs_table(data, ACS_TABLES[table])
        manifest.append({"source": f"acs_{table}", "release": ACS_RELEASE, "url": url,
                         "file_name": url.rsplit("/", 1)[-1], "sha256": sha256(data), "bytes": len(data),
                         "fetched_at": now, "rows_read": read,
                         "rows_kept": sum(1 for f in tables[table] if f in counties),
                         "license": "U.S. government work (public domain)"})
    gurl, gdata = gazetteer
    land = read_gazetteer(gdata)
    manifest.append({"source": "gazetteer", "release": "2024 Gazetteer, counties", "url": gurl,
                     "file_name": gurl.rsplit("/", 1)[-1], "sha256": sha256(gdata), "bytes": len(gdata),
                     "fetched_at": now, "rows_read": len(land),
                     "rows_kept": sum(1 for f in land if f in counties),
                     "license": "U.S. government work (public domain)"})
    demo = demographic(tables, land, counties)
    check_demographic(demo)
    check_medsl_copy(medsl, medsl_meta)
    recs = read_medsl(medsl)
    pol = political(recs, counties)
    check_political(pol)
    manifest.append({"source": "medsl", "release": f"MEDSL countypres 2000-2024, Dataverse version "
                     f"{medsl_meta['version']}", "url": f"https://doi.org/{MEDSL_DOI.removeprefix('doi:')}",
                     "file_name": str(MEDSL_PATH.relative_to(ROOT)), "sha256": sha256(medsl),
                     "bytes": len(medsl), "fetched_at": now, "rows_read": len(recs),
                     "rows_kept": sum(1 for r in pol.values() if r["geo_basis_2024"]),
                     "license": medsl_meta["license"] or "not stated"})
    rows = [{"county_fips": f, "state": meta["state"], "county": meta["county"], **demo[f], **pol[f]}
            for f, meta in sorted(counties.items())]
    catalog = {
        "_comment": "Written by scripts/fetch_county_covariates.py. Do not edit by hand.",
        "sources": {
            "frame": "2024 county boundaries (data/geo/counties_2024.topojson), 50 states and DC",
            "acs": f"U.S. Census Bureau, American Community Survey {ACS_RELEASE}, table-based summary files",
            "gazetteer": "U.S. Census Bureau, 2024 Gazetteer Files, counties",
            "medsl": f"MIT Election Data and Science Lab, County Presidential Election Returns 2000-2024, "
                     f"Harvard Dataverse {MEDSL_DOI}, version {medsl_meta['version']} "
                     f"({medsl_meta['license'] or 'license not stated'})",
        },
        "columns": {c: {"description": d, "source": s, "unit": u,
                        "leakage_class": "none"} for c, (d, s, u) in COLUMNS.items()},
    }
    return rows, manifest, catalog


def download(session: requests.Session) -> tuple[dict[str, tuple[str, bytes]], tuple[str, bytes]]:
    acs = {}
    for table in ACS_TABLES:
        url = f"{ACS_BASE}acsdt5y{ACS_YEAR}-{table}.dat"
        r = session.get(url, timeout=600)
        r.raise_for_status()
        acs[table] = (url, r.content)
    r = session.get(GAZETTEER_URL, timeout=300)
    r.raise_for_status()
    return acs, (GAZETTEER_URL, r.content)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.dry_run:
        for table in ACS_TABLES:
            print(f"[dry-run] ACS: {ACS_BASE}acsdt5y{ACS_YEAR}-{table}.dat")
        print(f"[dry-run] Gazetteer: {GAZETTEER_URL}")
        print(f"[dry-run] MEDSL: {MEDSL_PATH.relative_to(ROOT)}, md5 checked against {MEDSL_DOI}")
        print(f"[dry-run] would write {COVARIATES_PATH.relative_to(ROOT)}, "
              f"{MANIFEST_PATH.relative_to(ROOT)} and {CATALOG_PATH.relative_to(ROOT)}")
        return 0
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    try:
        acs, gazetteer = download(session)
        meta = dataverse_metadata(session)
        medsl = MEDSL_PATH.read_bytes()
        rows, manifest, catalog = build(acs, gazetteer, medsl, meta)
    except (requests.RequestException, OSError) as exc:
        print(f"Download failed, nothing written: {exc}", file=sys.stderr)
        return 1
    except SchemaError as exc:
        print(f"Refused by the schema guard, nothing written: {exc}", file=sys.stderr)
        return 1
    for m in manifest:
        print(f"{m['source']}: {m['release']}, {m['rows_read']} rows read, {m['rows_kept']} kept "
              f"({m['sha256'][:12]})")
    filled = {c: sum(1 for r in rows if r[c] != "") for c in FIELDS[3:]}
    print("Filled: " + ", ".join(f"{c} {n}" for c, n in filled.items()))
    if unchanged(manifest):
        print("Unchanged inputs (every file's SHA-256 matches the manifest); nothing rewritten")
        return 0
    write_csv(COVARIATES_PATH, rows, FIELDS)
    write_csv(MANIFEST_PATH, manifest, MANIFEST_FIELDS)
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {COVARIATES_PATH.relative_to(ROOT)} ({len(rows)} counties)")
    return 0


def unchanged(manifest: list[dict]) -> bool:
    """Whether every input file is the one the last run read, so the outputs
    would come out the same and only the fetch times would differ."""
    if not (MANIFEST_PATH.exists() and COVARIATES_PATH.exists() and CATALOG_PATH.exists()):
        return False
    before = {(m["source"], m["sha256"]) for m in read_csv(MANIFEST_PATH)}
    return before == {(m["source"], m["sha256"]) for m in manifest}


if __name__ == "__main__":
    sys.exit(main())
