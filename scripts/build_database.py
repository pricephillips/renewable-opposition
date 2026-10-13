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
  python scripts/build_database.py              build data/db/renewable_opposition.duckdb
  python scripts/build_database.py --publish    also write the published files: one Parquet file per
                                                table and view in data/db/parquet/, and
                                                data/db/state_summary.json and county_summary.json,
                                                and one detail file per state in data/db/state/
  python scripts/build_database.py --out /tmp/ro.duckdb   build somewhere else

The Build dashboard data workflow runs it with --publish and commits the
Parquet and the summaries, so GitHub Pages serves them; the .duckdb file is
never committed.
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
import geoid_match  # noqa: E402
import group_registry  # noqa: E402
import negative_checks  # noqa: E402
import site_profile  # noqa: E402
from common import (PROCESSED_DIR, REVIEW_DIR, ROOT, STATE_NAMES, jurisdiction_key, jurisdiction_kind,  # noqa: E402
                    read_csv, write_csv)

DB_DIR = ROOT / "db"
DEFAULT_OUT = ROOT / "data" / "db" / "renewable_opposition.duckdb"
# Published with --publish and committed by the Build dashboard data workflow,
# so GitHub Pages serves them to the dashboard. The .duckdb file is not.
PARQUET_DIR = ROOT / "data" / "db" / "parquet"
STATE_SUMMARY = ROOT / "data" / "db" / "state_summary.json"
COUNTY_SUMMARY = ROOT / "data" / "db" / "county_summary.json"
# One detail file per state: what the dashboard's state and county views
# list. Written from the same database, so they count the way it does.
STATE_DIR = ROOT / "data" / "db" / "state"
# Which record lives in which state file, for the dashboard's record pages.
RECORD_INDEX = ROOT / "data" / "db" / "record_index.json"
# How long each review worklist is: sizes only, never rows (README, "Closing
# the gaps"; docs/national_database_design.md, decision 3).
WORKLISTS_JSON = ROOT / "data" / "db" / "worklists.json"
# Every published Parquet file with its row count and size, for the
# dashboard's data page.
MANIFEST_JSON = ROOT / "data" / "db" / "manifest.json"
# Restrictions by year and dating basis (v_restrictions_by_year), for the
# national timeline.
TIMELINE_JSON = ROOT / "data" / "db" / "timeline.json"
# The headline figures as each build published them (headline_history.py).
HISTORY_JSON = ROOT / "data" / "db" / "history.json"
# build_info keys that change on every run. Left out of the Parquet so an
# unchanged build rewrites identical bytes and commits nothing.
VOLATILE_INFO = ("built_at", "git_commit")
METRICS = PROCESSED_DIR / "headline_metrics.json"
# Every functioning local government with its Census GEOID
# (scripts/build_census_governments.py), for geoid_match.
CENSUS_GOVERNMENTS = ROOT / "data" / "census_governments_2024.csv"
# Jurisdictions no single Census government fits, for a reviewer. Written on
# every --publish run; never published as data.
GEOID_WORKLIST = REVIEW_DIR / "geoid_worklist.csv"
EXAMINATION_WORKLIST = REVIEW_DIR / "examination_worklist.csv"
EXAMINATION_WORKLIST_FIELDS = [
    "rank", "state", "county_fips", "county", "reason", "next_step", "state_remaining", "state_counties",
    "who_decides", "census_local_governments", "neighbors_with_restrictions", "neighbor_projects",
    "last_negative_check", "negative_check_grade", "drafted_by"]
# The counties still to examine (docs/COUNTY_CHECK.md), ranked: states nearest
# to finished first, then within a state the counties next to the most
# restricted ones. A temporary view, so it is never exported to Parquet: the
# public site shows the worklist's size only (decision 3).
EXAMINATION_SQL = """
CREATE TEMP VIEW examination_worklist AS
WITH cs AS (
    SELECT * FROM v_county_summary WHERE in_coverage_universe
), held AS (
    SELECT county_fips, min(drafted_by) AS drafted_by FROM negative_check WHERE held GROUP BY county_fips
), todo AS (
    SELECT cs.*, h.drafted_by,
           CASE WHEN h.county_fips IS NOT NULL AND cs.coverage_status = 'not_examined' THEN 'check_held'
                WHEN cs.coverage_status = 'not_examined' THEN 'not_examined'
                ELSE 'recheck' END AS reason
    FROM cs LEFT JOIN held h USING (county_fips)
    WHERE cs.coverage_status = 'not_examined'
       OR (cs.coverage_status = 'checked_none' AND cs.negative_check_grade <> 'A')
), st AS (
    SELECT state_code, count(*) AS state_counties,
           count(*) FILTER (WHERE coverage_status = 'not_examined') AS state_remaining
    FROM cs GROUP BY state_code
), sp AS (
    SELECT state_code, string_agg(DISTINCT who_decides, '; ' ORDER BY who_decides) AS who_decides
    FROM state_policy WHERE policy_type = 'siting_authority' GROUP BY state_code
), nb AS (
    SELECT a.county_fips, count(*) FILTER (WHERE n.restrictions > 0) AS neighbors_with_restrictions,
           sum(n.contested_projects) AS neighbor_projects
    FROM county_adjacency a JOIN v_county_summary n ON n.county_fips = a.neighbor_fips
    GROUP BY a.county_fips
)
SELECT row_number() OVER (ORDER BY st.state_remaining, t.state_code,
                                   CASE t.reason WHEN 'check_held' THEN 0 WHEN 'not_examined' THEN 1 ELSE 2 END,
                                   coalesce(nb.neighbors_with_restrictions, 0) DESC, t.county_fips) AS rank,
       t.state_code AS state, t.county_fips, t.county_name AS county, t.reason,
       CASE t.reason
           WHEN 'check_held' THEN 'review the drafted negative check (docs/COUNTY_CHECK.md, section 4)'
           WHEN 'not_examined' THEN 'run the county check (docs/COUNTY_CHECK.md)'
           ELSE 'check again: the last check is grade ' || t.negative_check_grade
       END AS next_step,
       st.state_remaining, st.state_counties, sp.who_decides,
       coalesce(CAST(lg.n AS INTEGER), 0) AS census_local_governments,
       coalesce(nb.neighbors_with_restrictions, 0) AS neighbors_with_restrictions,
       coalesce(nb.neighbor_projects, 0) AS neighbor_projects,
       t.last_negative_check, t.negative_check_grade, t.drafted_by
FROM todo t
JOIN st USING (state_code)
LEFT JOIN sp USING (state_code)
LEFT JOIN nb USING (county_fips)
LEFT JOIN stg_local_governments lg USING (county_fips)
"""
GEOID_WORKLIST_FIELDS = ["state", "jurisdiction_type", "jurisdiction", "counties", "method", "candidates",
                         "candidate_names", "records"]

# name -> (file, the rows that count, what the list is for). The files are
# written by the Build dashboard data workflow's steps before this one.
WORKLISTS = {
    "restriction_worklist": (REVIEW_DIR / "restriction_worklist.csv", None,
                             "Restrictions whose instrument or adopting minutes nobody has read yet"),
    "outcome_worklist": (REVIEW_DIR / "outcome_worklist.csv", None,
                         "Contested-project outcomes not yet confirmed by a source someone read"),
    "adjacency_worklist": (REVIEW_DIR / "adjacency_worklist.csv", None,
                           "Counties next to a recent restriction that nobody has checked"),
    "negative_check_worklist": (REVIEW_DIR / "negative_check_worklist.csv", None,
                                "Profiled counties with no restriction and no documented check"),
    "cases_candidates": (REVIEW_DIR / "cases_candidates.csv", ("review_status", {"lead", "needs_docket_research"}),
                         "Litigated projects waiting for a court record"),
    "queue": (REVIEW_DIR / "queue.csv", ("review_status", {"pending"}),
              "Candidate records waiting for a reviewer"),
    "group_review": (REVIEW_DIR / "group_review.csv", None,
                     "Opposition groups held back until a source names them"),
    "coverage_gaps": (REVIEW_DIR / "coverage_gaps.csv", None,
                      "Moratoria found in only one of the two compiled sources"),
}

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
    "stg_data_center_events": ROOT / "data" / "reference" / "data_center_events.csv",
    "stg_headline_history": ROOT / "data" / "snapshots" / "headline_history.csv",
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

TABLES = ("state", "county", "county_adjacency", "jurisdiction", "government", "jurisdiction_match",
          "restriction_instrument", "restriction",
          "contested_project", "legal_case", "case_project", "siting_standard", "state_policy",
          "record_county", "source_document", "evidence_link", "opposition_group", "project_group",
          "negative_check", "county_pending_review", "worklist_size", "data_center_event", "headline_history",
          "build_info")
VIEWS = ("v_headline_restrictions", "v_headline_by_source", "v_county_coverage_totals", "v_county_summary",
         "v_state_summary", "v_restrictions_by_month", "v_geoid_coverage", "v_restrictions_by_year")


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


NEGATIVE_CHECK_FIELDS = negative_checks.CHECK_FIELDS + ["grade", "classes", "recheck_by", "held"]


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

    combos: dict[tuple, set[str]] = {}
    records: dict[tuple, int] = {}
    for path in (STAGING["stg_restrictions"], STAGING["stg_siting_standards"]):
        for r in read_csv(path):
            if (r.get("jurisdiction") or "").strip():
                # The counties are part of the key: Pennsylvania has many
                # Washington Townships, and each row names one of them.
                fips = r.get("county_fips_all") or r.get("county_fips") or ""
                k = (r.get("state") or "", r.get("jurisdiction_type") or "", r["jurisdiction"], fips)
                combos.setdefault(k, set()).update(f for f in fips.split(";") if f)
                records[k] = records.get(k, 0) + 1
    keys = []
    for state, jtype, name in sorted({k[:3] for k in combos}):
        kind = jurisdiction_kind(jtype)
        keys.append((state, jtype, name, jurisdiction_key(state, kind, name), kind))
    _stage_rows(con, "stg_jurisdiction_key",
                ["state", "jurisdiction_type", "jurisdiction", "jurisdiction_key", "kind"], keys)
    _stage_geoids(con, combos, records, counties)

    # Negative checks with what the pipeline derives from them: the evidence
    # grade, the re-check date, and whether the check is held for review
    # (drafted, not reviewed, so not counted).
    checks = []
    for c in negative_checks.load():
        checks.append(tuple(c.get(f) or "" for f in NEGATIVE_CHECK_FIELDS[:-4]) + (
            negative_checks.grade(c), ";".join(negative_checks.independence_classes(c)),
            negative_checks.recheck_by(c), "true" if negative_checks.held(c) else "false"))
    _stage_rows(con, "stg_negative_checks", NEGATIVE_CHECK_FIELDS, checks)

    # Census local governments per county (places by their internal point),
    # for the examination worklist: how many governments a check may need to
    # cover. Not every one zones.
    local: dict[str, int] = {}
    for g in read_csv(CENSUS_GOVERNMENTS):
        if g.get("county_fips"):
            local[g["county_fips"]] = local.get(g["county_fips"], 0) + 1
    _stage_rows(con, "stg_local_governments", ["county_fips", "n"], sorted((f, str(n)) for f, n in local.items()))

    links = []
    for p in read_csv(STAGING["stg_contested_projects"]):
        for name in group_registry.split(p.get("opposition_groups")):
            links.append((p["instrument_id"], group_registry.canonical_id(group_registry.key(name))))
    _stage_rows(con, "stg_project_group", ["project_id", "group_id"], links)

    # Pending review-queue candidates per county, matched the way site
    # profiles match them. Only the count is kept; local knowledge is never
    # read (local=False).
    profile_data = site_profile.Data(local=False)
    pending = []
    if profile_data.queue:
        for f in counties:
            st = next((c for c, sf in STATE_FIPS.items() if sf == f[:2]), "")
            n = len(site_profile.pending_for(profile_data, f, geo.name(f), st))
            if n:
                pending.append((f, str(n)))
    _stage_rows(con, "stg_county_pending", ["county_fips", "candidates"], pending)

    sizes = []
    for name, (path, only, description) in WORKLISTS.items():
        rows = read_csv(path) if path.exists() else []
        if only:
            rows = [r for r in rows if (r.get(only[0]) or "") in only[1]]
        sizes.append((name, description, str(len(rows))))
    sizes.append(("geoid_worklist", "Named jurisdictions no single Census government fits",
                  str(con.execute("SELECT count(*) FROM stg_geoid_worklist").fetchone()[0])))
    _stage_rows(con, "stg_worklist_size", ["worklist", "description", "rows"], sizes)


def _stage_geoids(con: duckdb.DuckDBPyConnection, combos: dict[tuple, set[str]], records: dict[tuple, int],
                  counties: list[str]) -> None:
    """Match every named jurisdiction, with the counties its rows are placed
    in, to a Census GEOID (geoid_match) and
    stage the matches, the governments matched, and the worklist of the
    rest (stg_geoid_worklist, for write_geoid_worklist)."""
    census = read_csv(CENSUS_GOVERNMENTS) if CENSUS_GOVERNMENTS.exists() else []
    idx = geoid_match.index(census)
    by_geoid = {g["geoid"]: g for g in census}
    code_of = {fips: code for code, fips in STATE_FIPS.items()}
    county_names: dict[str, dict[str, str]] = {}
    for f in counties:
        county_names.setdefault(code_of.get(f[:2], ""), {})[f] = geo.name(f)
    neighbors = {f: set(geo.neighbors(f)) for f in counties}
    matches, governments, worklist = [], {}, []
    for (state, jtype, name, fips), placed in sorted(combos.items()):
        st = state.upper()
        m = geoid_match.match(idx, st, jtype, name, placed, county_names.get(st, {}), STATE_FIPS.get(st, ""),
                              neighbors)
        matches.append((state, jtype, name, fips, m["geoid"], m["kind"], m["method"], str(m["candidates"])))
        g = m["geoid"]
        if g and g not in governments:
            if m["kind"] == "state":
                governments[g] = (g, "state", st, "", STATE_NAMES.get(st, st), "")
            elif m["kind"] == "county":
                governments[g] = (g, "county", st, g, geo.name(g), "")
            else:
                c = by_geoid[g]
                governments[g] = (g, c["kind"], st, c["county_fips"], c["name"], c["funcstat"])
        if not g:
            base, kind, _ = geoid_match.record_split(name, jtype)
            near = idx.get(st, {}).get(base, [])
            worklist.append({"state": st, "jurisdiction_type": jtype, "jurisdiction": name,
                             "counties": ";".join(sorted(placed)), "method": m["method"],
                             "candidates": m["candidates"],
                             "candidate_names": "; ".join(sorted(f"{c['name']} ({c['geoid']}, county {c['county_fips'] or 'unknown'})"
                                                                  for c in near)),
                             "records": records.get((state, jtype, name, fips), 0)})
    _stage_rows(con, "stg_jurisdiction_match", ["state", "jurisdiction_type", "jurisdiction", "counties", "geoid",
                                                "geoid_kind", "method", "candidates"], matches)
    _stage_rows(con, "stg_government", ["geoid", "kind", "state_code", "county_fips", "census_name", "funcstat"],
                sorted(governments.values()))
    _stage_rows(con, "stg_geoid_worklist", GEOID_WORKLIST_FIELDS,
                [tuple(str(r[f]) for f in GEOID_WORKLIST_FIELDS) for r in worklist])


def write_examination_worklist(con: duckdb.DuckDBPyConnection) -> None:
    """data/review/examination_worklist.csv (EXAMINATION_SQL)."""
    cur = con.execute("SELECT * FROM examination_worklist ORDER BY rank")
    cols = [d[0] for d in cur.description]
    write_csv(EXAMINATION_WORKLIST, [dict(zip(cols, r)) for r in cur.fetchall()], EXAMINATION_WORKLIST_FIELDS)


def write_geoid_worklist(con: duckdb.DuckDBPyConnection) -> None:
    """data/review/geoid_worklist.csv: every jurisdiction with no single
    Census match, most records first, with the governments of that name."""
    cur = con.execute("SELECT * FROM stg_geoid_worklist ORDER BY CAST(records AS INTEGER) DESC, state, "
                      "jurisdiction, jurisdiction_type")
    cols = [d[0] for d in cur.description]
    write_csv(GEOID_WORKLIST, [dict(zip(cols, r)) for r in cur.fetchall()], GEOID_WORKLIST_FIELDS)


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
    con.execute(EXAMINATION_SQL)
    con.execute("INSERT INTO worklist_size SELECT 'examination_worklist', "
                "'Counties to examine, check again, or whose drafted check awaits review', count(*) "
                "FROM examination_worklist")
    info = {
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git_commit(),
        "headline_metrics_json": METRICS.read_text(encoding="utf-8"),
    }
    for table, path in STAGING.items():
        info[f"input:{table}"] = str(path.relative_to(ROOT))
    info["input:census_governments"] = str(CENSUS_GOVERNMENTS.relative_to(ROOT))
    checks = negative_checks.CHECKS_PATH
    info["input:negative_checks"] = str(checks.relative_to(ROOT) if checks.is_relative_to(ROOT) else checks)
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


def _write_bytes(dest: Path, data: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def export_parquet(con: duckdb.DuckDBPyConnection) -> list[Path]:
    """One Parquet file per table and view in PARQUET_DIR. Rows are sorted and
    build_info leaves out VOLATILE_INFO, so the same inputs give the same
    bytes. A file for a table that no longer exists is removed."""
    written = []
    with tempfile.TemporaryDirectory() as tmp:
        for name in TABLES + VIEWS:
            where = ""
            if name == "build_info":
                where = "WHERE key NOT IN (" + ", ".join(f"'{k}'" for k in VOLATILE_INFO) + ")"
            staged = Path(tmp) / f"{name}.parquet"
            con.execute(f"COPY (SELECT * FROM {name} {where} ORDER BY ALL) TO '{staged.as_posix()}' "
                        "(FORMAT parquet, COMPRESSION zstd)")
            _write_bytes(PARQUET_DIR / f"{name}.parquet", staged.read_bytes())
            written.append(PARQUET_DIR / f"{name}.parquet")
    for stale in set(PARQUET_DIR.glob("*.parquet")) - set(written):
        stale.unlink()
    return written


def _query_json(con: duckdb.DuckDBPyConnection, sql: str) -> str:
    """A query as {"columns": [...], "rows": [[...], ...]}, one row per line:
    a third the size of an array of objects, and readable diffs."""
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = [[_plain(v) for v in r] for r in cur.fetchall()]
    dump = lambda v: json.dumps(v, ensure_ascii=False, separators=(",", ":"))  # noqa: E731
    return ('{"columns":' + dump(cols) + ',"rows":[\n' + ",\n".join(dump(r) for r in rows) + "\n]}\n")


def _summary(con: duckdb.DuckDBPyConnection, view: str, key: str) -> str:
    """A view as columns and rows, sorted by key."""
    return _query_json(con, f"SELECT * FROM {view} ORDER BY {key}")


def write_summaries(con: duckdb.DuckDBPyConnection) -> None:
    """state_summary.json and county_summary.json: what the dashboard's first
    paint draws before the in-browser database has loaded."""
    _write_bytes(STATE_SUMMARY, _summary(con, "v_state_summary", "state_code").encode("utf-8"))
    _write_bytes(COUNTY_SUMMARY, _summary(con, "v_county_summary", "county_fips").encode("utf-8"))


# The per-state detail queries. Each takes the state code and its 2-digit FIPS
# and must return the same rows in the same order on every run (no
# any_value over values that differ), so an unchanged build rewrites
# identical bytes. Siting standards group by the jurisdiction's own name, not
# only its match key: the key folds "Binghamton City" and "Binghamton Town"
# together, and they are two governments with two ordinances. A record
# belongs to a state's file when its state is that state or it is placed in
# one of the state's counties.
STATE_QUERIES = {
    "policies": """
        SELECT * EXCLUDE (state_code) FROM state_policy WHERE state_code = $st ORDER BY id""",
    "counties": """
        SELECT c.county_fips, c.county_name,
               coalesce(list(a.neighbor_fips ORDER BY a.neighbor_fips)
                        FILTER (WHERE a.neighbor_fips IS NOT NULL), []) AS neighbors
        FROM county c LEFT JOIN county_adjacency a USING (county_fips)
        WHERE c.state_code = $st GROUP BY ALL ORDER BY c.county_fips""",
    "negative_checks": """
        SELECT county_fips, scope, checked_on, governments_checked, sources_checked, grade, recheck_by, held,
               drafted_by, reviewer, note FROM negative_check
        WHERE substr(county_fips, 1, 2) = $sf ORDER BY county_fips, checked_on""",
    "restrictions": """
        SELECT ri.instrument_id, ri.state_code, ri.jurisdiction_name, ri.jurisdiction_type, ri.scope,
               ri.status, ri.severity_score, ri.technologies, ri.restriction_types, ri.evidence_level,
               ri.verification, ri.source_family, ri.date_enacted_iso, ri.date_text, ri.current_end_date,
               (SELECT first(r.description ORDER BY r.id) FROM restriction r
                 WHERE r.instrument_id = ri.instrument_id) AS description,
               (SELECT first(r.severity_basis ORDER BY r.id) FROM restriction r
                 WHERE r.instrument_id = ri.instrument_id) AS severity_basis,
               (SELECT first(r.long_description ORDER BY r.id) FILTER (WHERE r.long_description IS NOT NULL)
                 FROM restriction r WHERE r.instrument_id = ri.instrument_id) AS long_description,
               ri.sabin_edition, ri.edition_status, ri.primary_source_access, ri.geoid,
               (SELECT g.census_name FROM government g WHERE g.geoid = ri.geoid) AS census_name,
               (SELECT list({'technology': r.technology, 'restriction_type': r.restriction_type,
                             'severity_score': r.severity_score, 'severity_basis': r.severity_basis,
                             'mechanisms': r.mechanisms, 'legal_basis': r.legal_basis, 'sectors': r.sectors,
                             'nrel_id': r.nrel_id, 'conflicts_with': r.conflicts_with}
                            ORDER BY r.technology, r.id)
                 FROM restriction r WHERE r.instrument_id = ri.instrument_id) AS rows,
               coalesce((SELECT list({'county_fips': rc.county_fips, 'method': rc.method,
                                     'is_primary': rc.is_primary} ORDER BY rc.county_fips) FROM record_county rc
                 WHERE rc.entity = 'restriction' AND rc.record_id = ri.instrument_id), []) AS placements,
               coalesce((SELECT list(rc.county_fips ORDER BY rc.county_fips) FROM record_county rc
                 WHERE rc.entity = 'restriction' AND rc.record_id = ri.instrument_id), []) AS counties,
               coalesce((SELECT list({'role': e.role, 'url': e.url, 'access': e.access}
                                     ORDER BY e.role, e.url) FROM evidence_link e
                 WHERE e.entity = 'restriction' AND e.record_id = ri.instrument_id), []) AS evidence
        FROM restriction_instrument ri
        WHERE ri.state_code = $st OR ri.instrument_id IN (
            SELECT record_id FROM record_county
            WHERE entity = 'restriction' AND substr(county_fips, 1, 2) = $sf)
        ORDER BY ri.instrument_id""",
    "projects": """
        SELECT cp.instrument_id, cp.state_code, cp.project_name, cp.technologies, cp.outcome,
               cp.outcome_class, cp.outcome_confirmed, cp.finality_evidence, cp.status, cp.severity_score,
               cp.has_litigation, cp.municipality, cp.event_date_text, cp.capacity_mw_text, cp.description,
               cp.source_family, cp.evidence_level, cp.verification,
               cp.long_description, cp.opposition_type, cp.area_acres_text, cp.sabin_edition,
               cp.edition_status,
               coalesce((SELECT list({'county_fips': rc.county_fips, 'method': rc.method,
                                     'is_primary': rc.is_primary} ORDER BY rc.county_fips) FROM record_county rc
                 WHERE rc.entity = 'contested_project' AND rc.record_id = cp.instrument_id), []) AS placements,
               coalesce((SELECT list(rc.county_fips ORDER BY rc.county_fips) FROM record_county rc
                 WHERE rc.entity = 'contested_project' AND rc.record_id = cp.instrument_id), []) AS counties,
               coalesce((SELECT list(g.canonical_name ORDER BY g.canonical_name) FROM project_group pg
                 JOIN opposition_group g USING (group_id) WHERE pg.project_id = cp.instrument_id), [])
                 AS groups,
               coalesce((SELECT list(k.case_id ORDER BY k.case_id) FROM case_project k
                 WHERE k.project_id = cp.instrument_id), []) AS cases,
               coalesce((SELECT list({'role': e.role, 'url': e.url, 'access': e.access}
                                     ORDER BY e.role, e.url) FROM evidence_link e
                 WHERE e.entity = 'contested_project' AND e.record_id = cp.instrument_id), []) AS evidence
        FROM contested_project cp
        WHERE cp.state_code = $st OR cp.instrument_id IN (
            SELECT record_id FROM record_county
            WHERE entity = 'contested_project' AND substr(county_fips, 1, 2) = $sf)
        ORDER BY cp.instrument_id""",
    "cases": """
        SELECT lc.instrument_id, lc.state_code, lc.case_name, lc.court, lc.court_level, lc.docket_number,
               lc.case_status, lc.technologies, lc.case_source_url, lc.evidence_level, lc.verification,
               coalesce(list(k.project_id ORDER BY k.project_id)
                        FILTER (WHERE k.project_id IS NOT NULL), []) AS projects,
               coalesce((SELECT list({'role': e.role, 'url': e.url, 'access': e.access}
                                     ORDER BY e.role, e.url) FROM evidence_link e
                 WHERE e.entity = 'legal_case' AND e.record_id = lc.instrument_id), []) AS evidence
        FROM legal_case lc LEFT JOIN case_project k ON k.case_id = lc.instrument_id
        WHERE lc.state_code = $st GROUP BY ALL ORDER BY lc.instrument_id""",
    "siting_standards": """
        SELECT s.jurisdiction_key, s.jurisdiction, s.jurisdiction_type, s.technology,
               min(s.geoid) AS geoid, min(g.census_name) AS census_name,
               coalesce(list(DISTINCT rc.county_fips ORDER BY rc.county_fips)
                        FILTER (WHERE rc.county_fips IS NOT NULL), []) AS counties,
               max(s.ordinance_year) AS ordinance_year, min(s.ordinance_url) AS ordinance_url,
               count(DISTINCT s.id) AS features,
               count(DISTINCT s.id) FILTER (WHERE s.restricting) AS restricting_features,
               count(DISTINCT s.id) FILTER (WHERE s.verification = 'verified') AS verified_features,
               list(DISTINCT {'feature': s.feature, 'value': s.value, 'units': s.units}
                    ORDER BY {'feature': s.feature, 'value': s.value, 'units': s.units})
                    FILTER (WHERE s.restricting) AS restricting
        FROM siting_standard s
        LEFT JOIN government g ON g.geoid = s.geoid
        LEFT JOIN record_county rc ON rc.entity = 'siting_standard' AND rc.record_id = s.id
        WHERE s.state_code = $st
        GROUP BY s.jurisdiction_key, s.jurisdiction, s.jurisdiction_type, s.technology
        ORDER BY s.jurisdiction_key, s.jurisdiction, s.jurisdiction_type, s.technology""",
    "data_center_events": """
        SELECT county_fips, event_date, event_type, status, summary, source_urls[1] AS source_url,
               opposition_groups
        FROM data_center_event WHERE state_code = $st
        ORDER BY county_fips, event_date, dc_row_ref""",
}


def _plain(v):
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if isinstance(v, dict):  # a nested struct: its null fields are left out
        return {k: _plain(x) for k, x in v.items() if x is not None}
    return v


def state_detail(con: duckdb.DuckDBPyConnection, code: str) -> dict:
    out: dict = {"state_code": code}
    params = {"st": code, "sf": STATE_FIPS[code]}
    for key, sql in STATE_QUERIES.items():
        cur = con.execute(sql, {k: v for k, v in params.items() if f"${k}" in sql})
        cols = [d[0] for d in cur.description]
        out[key] = [{c: _plain(v) for c, v in zip(cols, row)} for row in cur.fetchall()]
    return out


def _detail_json(detail: dict) -> str:
    """One record per line, so a rebuilt file diffs by record."""
    dump = lambda v: json.dumps(v, ensure_ascii=False, separators=(",", ":"))  # noqa: E731
    parts = []
    for key, value in detail.items():
        if isinstance(value, list) and value:
            parts.append(f"{dump(key)}:[\n" + ",\n".join(dump(v) for v in value) + "\n]")
        else:
            parts.append(f"{dump(key)}:{dump(value)}")
    return "{" + ",\n".join(parts) + "}\n"


def write_state_files(con: duckdb.DuckDBPyConnection) -> list[Path]:
    """data/db/state/<ST>.json for every state, DC and Puerto Rico. A file
    for a state no longer in the table is removed."""
    written = []
    for (code,) in con.execute("SELECT state_code FROM state ORDER BY state_code").fetchall():
        _write_bytes(STATE_DIR / f"{code}.json", _detail_json(state_detail(con, code)).encode("utf-8"))
        written.append(STATE_DIR / f"{code}.json")
    for stale in set(STATE_DIR.glob("*.json")) - set(written):
        stale.unlink()
    return written


def write_record_index(con: duckdb.DuckDBPyConnection) -> None:
    """Which state file holds each record: restriction, project and case
    instrument_ids with their entity and state."""
    _write_bytes(RECORD_INDEX, _query_json(con, """
        SELECT instrument_id, 'restriction' AS entity, state_code FROM restriction_instrument
        UNION ALL SELECT instrument_id, 'project', state_code FROM contested_project
        UNION ALL SELECT instrument_id, 'case', state_code FROM legal_case
        ORDER BY entity, instrument_id""").encode("utf-8"))


def write_timeline(con: duckdb.DuckDBPyConnection) -> None:
    _write_bytes(TIMELINE_JSON, _query_json(con, "SELECT * FROM v_restrictions_by_year "
                                                 "ORDER BY scope, year NULLS LAST, basis").encode("utf-8"))


def write_history(con: duckdb.DuckDBPyConnection) -> None:
    _write_bytes(HISTORY_JSON, _query_json(con, "SELECT * FROM headline_history ORDER BY date").encode("utf-8"))


def write_worklists(con: duckdb.DuckDBPyConnection) -> None:
    _write_bytes(WORKLISTS_JSON, _query_json(con, "SELECT * FROM worklist_size ORDER BY worklist").encode("utf-8"))


def write_manifest(con: duckdb.DuckDBPyConnection, parquet: list[Path]) -> None:
    """Every published Parquet file with its kind, rows and bytes."""
    rows = []
    for path in sorted(parquet):
        name = path.stem
        n = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        kind = "view" if name in VIEWS else "table"
        rows.append((f"parquet/{path.name}", name, kind, n, path.stat().st_size))
    con.execute("CREATE OR REPLACE TEMP TABLE _manifest (file VARCHAR, name VARCHAR, kind VARCHAR, "
                "rows BIGINT, bytes BIGINT)")
    con.executemany("INSERT INTO _manifest VALUES (?, ?, ?, ?, ?)", rows)
    _write_bytes(MANIFEST_JSON, _query_json(con, "SELECT * FROM _manifest ORDER BY file").encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="DuckDB file to write")
    ap.add_argument("--publish", action="store_true",
                    help="also write the published files: Parquet in data/db/parquet/ and the state and "
                         "county summaries in data/db/")
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
            if args.publish:
                parquet = export_parquet(con)
                write_summaries(con)
                write_state_files(con)
                write_record_index(con)
                write_worklists(con)
                write_timeline(con)
                write_history(con)
                write_manifest(con, parquet)
                write_geoid_worklist(con)
                write_examination_worklist(con)
            counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}
        finally:
            con.close()
        tmp_db.replace(args.out)

    def rel(path: Path) -> Path:
        return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path

    print(f"build_database: wrote {rel(args.out)}")
    for t, n in counts.items():
        print(f"  {t:<24} {n:>7}")
    if args.publish:
        print(f"  published: {len(TABLES) + len(VIEWS)} Parquet files in {rel(PARQUET_DIR)}, "
              f"{STATE_SUMMARY.name}, {COUNTY_SUMMARY.name}, {len(STATE_FIPS)} state files in {rel(STATE_DIR)}")
    print("  parity with headline_metrics.json: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
