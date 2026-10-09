#!/usr/bin/env python3
"""
build_database.py

Builds the national database: one DuckDB file holding every published table
in data/processed/, normalized around the instrument and the county, plus the
geography, coverage and reference tables the dashboard needs. Design:
docs/national_database_design.md.

The database is derived. It is rebuilt from scratch on every run from files
the pipeline already publishes, so the CSVs in data/processed/ stay the
source of truth and nothing in the database is ever edited by hand.

  db/schema.sql   table definitions
  db/load.sql     fills them from staging tables this script creates
  db/views.sql    headline, county, state and timeline views

Parity. Before it writes anything, the script recomputes the headline
numbers from the database (db/views.sql) and compares them with
data/processed/headline_metrics.json. Any difference stops the build: the
database must never quote a number the published metrics do not.

Usage
  python scripts/build_database.py                       build data/db/renewable_opposition.duckdb
  python scripts/build_database.py --parquet data/db/parquet   also export every table and view as Parquet
  python scripts/build_database.py --out /tmp/ro.duckdb  build somewhere else
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))

import geo  # noqa: E402
import group_registry  # noqa: E402
from common import PROCESSED_DIR, REVIEW_DIR, ROOT, STATE_NAMES, jurisdiction_key, jurisdiction_kind, read_csv  # noqa: E402

DB_DIR = ROOT / "db"
DEFAULT_OUT = ROOT / "data" / "db" / "renewable_opposition.duckdb"
METRICS = PROCESSED_DIR / "headline_metrics.json"

# Every input, as staging table -> file. Read with every column VARCHAR;
# db/load.sql does the typing.
STAGING = {
    "stg_restrictions": PROCESSED_DIR / "restrictions.csv",
    "stg_contested_projects": PROCESSED_DIR / "contested_projects.csv",
    "stg_cases": PROCESSED_DIR / "cases.csv",
    "stg_siting_standards": PROCESSED_DIR / "siting_standards.csv",
    "stg_state_policies": PROCESSED_DIR / "state_policies.csv",
    "stg_sources": PROCESSED_DIR / "sources.csv",
    "stg_group_registry": PROCESSED_DIR / "group_registry.csv",
    "stg_negative_checks": REVIEW_DIR / "negative_checks.csv",
    "stg_data_center_events": ROOT / "data" / "reference" / "data_center_events.csv",
}

# 2-digit state FIPS for the 50 states, DC and Puerto Rico (the 2024 county
# file includes Puerto Rico; headline_metrics leaves it out of coverage).
STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09", "DE": "10",
    "DC": "11", "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19",
    "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24", "MA": "25", "MI": "26", "MN": "27",
    "MS": "28", "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34", "NM": "35",
    "NY": "36", "NC": "37", "ND": "38", "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
    "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53",
    "WV": "54", "WI": "55", "WY": "56", "PR": "72",
}
EXTRA_STATE_NAMES = {"DC": "District of Columbia", "PR": "Puerto Rico"}

TABLES = ("state", "county", "county_adjacency", "jurisdiction", "restriction_instrument", "restriction",
          "contested_project", "legal_case", "case_project", "siting_standard", "state_policy",
          "record_county", "source_document", "evidence_link", "opposition_group", "project_group",
          "negative_check", "data_center_event", "build_info")
VIEWS = ("v_headline_restrictions", "v_headline_by_source", "v_county_coverage_totals", "v_county_summary",
         "v_state_summary", "v_restrictions_by_month")


def _sql(name: str) -> str:
    return (DB_DIR / name).read_text(encoding="utf-8")


def _stage_csv(con: duckdb.DuckDBPyConnection, table: str, path: Path) -> None:
    con.execute(
        f"CREATE TEMP TABLE {table} AS SELECT * FROM read_csv(?, header = true, all_varchar = true, "
        "delim = ',', quote = '\"', escape = '\"', null_padding = true)",
        [str(path)],
    )


def _stage_rows(con: duckdb.DuckDBPyConnection, table: str, columns: list[str], rows: list[tuple]) -> None:
    cols = ", ".join(f"{c} VARCHAR" for c in columns)
    con.execute(f"CREATE TEMP TABLE {table} ({cols})")
    if rows:
        marks = ", ".join("?" for _ in columns)
        con.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)


def _stage_python(con: duckdb.DuckDBPyConnection) -> None:
    """Staging tables computed with the pipeline's own helpers, so the
    database places, keys and links records exactly as the build does."""
    states = []
    for code, fips in STATE_FIPS.items():
        states.append((code, EXTRA_STATE_NAMES.get(code) or STATE_NAMES.get(code, code), fips))
    _stage_rows(con, "stg_state", ["state_code", "state_name", "state_fips"], states)

    counties = geo.all_counties()
    _stage_rows(con, "stg_county", ["county_fips", "county_name"], [(f, geo.name(f)) for f in counties])
    _stage_rows(con, "stg_county_adjacency", ["county_fips", "neighbor_fips"],
                [(f, n) for f in counties for n in geo.neighbors(f)])

    combos = set()
    for path in (STAGING["stg_restrictions"], STAGING["stg_siting_standards"]):
        for r in read_csv(path):
            if (r.get("jurisdiction") or "").strip():
                combos.add((r.get("state") or "", r.get("jurisdiction_type") or "", r["jurisdiction"]))
    keys = []
    for state, jtype, name in sorted(combos):
        kind = jurisdiction_kind(jtype)
        keys.append((state, jtype, name, jurisdiction_key(state, kind, name), kind))
    _stage_rows(con, "stg_jurisdiction_key",
                ["state", "jurisdiction_type", "jurisdiction", "jurisdiction_key", "kind"], keys)

    links = []
    for p in read_csv(STAGING["stg_contested_projects"]):
        for name in group_registry.split(p.get("opposition_groups")):
            links.append((p["instrument_id"], group_registry.canonical_id(group_registry.key(name))))
    _stage_rows(con, "stg_project_group", ["project_id", "group_id"], links)


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def build(con: duckdb.DuckDBPyConnection) -> None:
    for table, path in STAGING.items():
        _stage_csv(con, table, path)
    _stage_python(con)
    con.execute(_sql("schema.sql"))
    con.execute(_sql("load.sql"))
    con.execute(_sql("views.sql"))
    info = {
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git_commit(),
        "headline_metrics_json": METRICS.read_text(encoding="utf-8"),
    }
    for table, path in STAGING.items():
        info[f"input:{table}"] = str(path.relative_to(ROOT))
    con.executemany("INSERT INTO build_info VALUES (?, ?)", sorted(info.items()))


def _counts(con, sql: str) -> dict[str, int]:
    return {k or "": v for k, v in con.execute(sql).fetchall()}


def _nonzero(d: dict) -> dict:
    return {k: v for k, v in d.items() if v}


def parity(con: duckdb.DuckDBPyConnection, metrics: dict) -> list[str]:
    """Every difference between the database and headline_metrics.json."""
    problems: list[str] = []

    def check(label, got, want):
        if got != want:
            problems.append(f"{label}: database {got!r}, headline_metrics.json {want!r}")

    r = metrics["restrictions"]
    check("restrictions.rows", con.execute("SELECT count(*) FROM restriction").fetchone()[0], r["rows"])
    check("restrictions.instruments",
          con.execute("SELECT count(*) FROM restriction_instrument").fetchone()[0], r["instruments"])
    for scope, want in r["by_scope"].items():
        row = con.execute("SELECT instruments, severe_instruments, states FROM v_headline_restrictions "
                          "WHERE scope = ?", [scope]).fetchone() or (0, 0, 0)
        check(f"restrictions.{scope}.instruments", row[0], want["instruments"])
        check(f"restrictions.{scope}.severe_instruments", row[1], want["severe_instruments"])
        check(f"restrictions.{scope}.states", row[2], want["states"])
        for field in ("status", "evidence_level", "verification"):
            got = _counts(con, f"SELECT coalesce({field}, ''), count(*) FROM restriction_instrument "
                               f"WHERE scope = '{scope}' GROUP BY 1")
            check(f"restrictions.{scope}.by_{field}", got, want[f"by_{field}"])
        got = _counts(con, "SELECT t, count(*) FROM (SELECT unnest(technologies) AS t FROM "
                           f"restriction_instrument WHERE scope = '{scope}') GROUP BY t")
        check(f"restrictions.{scope}.by_technology", got, want["by_technology"])

    for entity, section in (("restrictions", r), ("contested_projects", metrics["contested_projects"])):
        for src, want in section["by_source"].items():
            row = con.execute("SELECT instruments, severe_instruments, verified, located, unverified "
                              "FROM v_headline_by_source WHERE entity = ? AND source_family = ?",
                              [entity, src]).fetchone() or (0, 0, 0, 0, 0)
            check(f"{entity}.by_source[{src}].instruments", row[0], want["instruments"])
            check(f"{entity}.by_source[{src}].severe_instruments", row[1], want["severe_instruments"])
            got = _nonzero({"verified": row[2], "located": row[3], "unverified": row[4]})
            check(f"{entity}.by_source[{src}].by_verification", got, want["by_verification"])

    p = metrics["contested_projects"]
    check("contested_projects.projects", con.execute("SELECT count(*) FROM contested_project").fetchone()[0],
          p["projects"])
    check("contested_projects.confirmed_outcomes",
          con.execute("SELECT count(*) FROM contested_project WHERE outcome_confirmed").fetchone()[0],
          p["confirmed_outcomes"])
    for field in ("outcome", "evidence_level", "verification"):
        got = _counts(con, f"SELECT {field}, count(*) FROM contested_project GROUP BY 1")
        check(f"contested_projects.by_{field}", got, p[f"by_{field}"])

    k = metrics["cases"]
    check("cases.rows", con.execute("SELECT count(*) FROM case_project").fetchone()[0], k["rows"])
    check("cases.cases", con.execute("SELECT count(*) FROM legal_case").fetchone()[0], k["cases"])
    check("cases.by_case_status", _counts(con, "SELECT case_status, count(*) FROM legal_case GROUP BY 1"),
          k["by_case_status"])
    check("cases.by_verification", _counts(con, "SELECT verification, count(*) FROM legal_case GROUP BY 1"),
          k["by_verification"])

    s = metrics["siting_standards"]
    check("siting_standards.rows", con.execute("SELECT count(*) FROM siting_standard").fetchone()[0], s["rows"])
    check("siting_standards.restricting_rows",
          con.execute("SELECT count(*) FROM siting_standard WHERE restricting").fetchone()[0],
          s["restricting_rows"])
    check("siting_standards.by_verification",
          _counts(con, "SELECT verification, count(*) FROM siting_standard GROUP BY 1"), s["by_verification"])

    check("state_policies.rows", con.execute("SELECT count(*) FROM state_policy").fetchone()[0],
          metrics["state_policies"]["rows"])

    if "county_coverage" in metrics:
        cur = con.execute("SELECT * FROM v_county_coverage_totals")
        got = dict(zip([d[0] for d in cur.description], cur.fetchone()))
        want = metrics["county_coverage"]
        for key in want:
            if key in got:
                check(f"county_coverage.{key}", got[key], want[key])
    return problems


def export_parquet(con: duckdb.DuckDBPyConnection, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name in TABLES + VIEWS:
        path = out_dir / f"{name}.parquet"
        con.execute(f"COPY (SELECT * FROM {name}) TO '{path.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="DuckDB file to write")
    ap.add_argument("--parquet", type=Path, help="also export every table and view as Parquet here")
    args = ap.parse_args(argv)

    # Build in a temporary file and move it into place only once parity
    # holds, so a failed build never leaves a database that disagrees with
    # the published metrics.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.out.parent) as tmp:
        tmp_db = Path(tmp) / args.out.name
        con = duckdb.connect(str(tmp_db))
        try:
            build(con)
            problems = parity(con, json.loads(METRICS.read_text(encoding="utf-8")))
            if problems:
                print("build_database: the database disagrees with headline_metrics.json:", file=sys.stderr)
                for p in problems:
                    print(f"  - {p}", file=sys.stderr)
                return 1
            if args.parquet:
                export_parquet(con, args.parquet)
            counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}
        finally:
            con.close()
        tmp_db.replace(args.out)

    print(f"build_database: wrote {args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out}")
    for t, n in counts.items():
        print(f"  {t:<24} {n:>7}")
    if args.parquet:
        print(f"  parquet: {len(TABLES) + len(VIEWS)} files in {args.parquet}")
    print("  parity with headline_metrics.json: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
