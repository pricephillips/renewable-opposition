import json

import duckdb
import pytest

import build_database as bdb


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect()
    bdb.build(c)
    yield c
    c.close()


def _metrics():
    return json.loads(bdb.METRICS.read_text(encoding="utf-8"))


def test_database_matches_headline_metrics(con):
    assert bdb.parity(con, _metrics()) == []


def test_parity_reports_a_number_the_metrics_do_not_quote(con):
    m = _metrics()
    m["restrictions"]["by_scope"]["renewables_only"]["instruments"] += 1
    m["contested_projects"]["by_outcome"]["blocked_confirmed"] += 1
    problems = bdb.parity(con, m)
    assert any(p.startswith("restrictions.renewables_only.instruments") for p in problems)
    assert any(p.startswith("contested_projects.by_outcome") for p in problems)


def test_one_instrument_counts_once_however_many_technology_rows(con):
    rows, instruments = con.execute(
        "SELECT (SELECT count(*) FROM restriction), (SELECT count(*) FROM restriction_instrument)").fetchone()
    assert rows > instruments
    multi = con.execute("SELECT count(*) FROM restriction_instrument WHERE len(technologies) > 1").fetchone()[0]
    assert multi > 0
    assert con.execute("SELECT sum(n_rows) FROM restriction_instrument").fetchone()[0] == rows


def test_county_summary_never_paints_an_unexamined_county_as_empty(con):
    statuses = dict(con.execute(
        "SELECT coverage_status, count(*) FROM v_county_summary WHERE in_coverage_universe GROUP BY 1").fetchall())
    cov = _metrics()["county_coverage"]
    assert statuses.get("has_records", 0) == cov["with_any_record"]
    assert statuses.get("not_examined", 0) == cov["with_neither"]
    assert statuses.get("checked_none", 0) == cov["with_negative_check_and_no_record"]


def test_data_center_events_never_enter_renewable_counts(con):
    # The summary keeps them in their own column; restriction counts come from
    # restriction_instrument alone.
    total = con.execute("SELECT sum(restrictions) FROM v_state_summary").fetchone()[0]
    renewables = _metrics()["restrictions"]["by_scope"]["renewables_only"]["instruments"]
    assert total == renewables


def test_every_case_links_to_a_published_project(con):
    assert con.execute("SELECT count(*) FROM case_project WHERE project_id IS NULL").fetchone()[0] == 0


def test_main_writes_database_and_parquet(tmp_path):
    out = tmp_path / "ro.duckdb"
    assert bdb.main(["--out", str(out), "--parquet", str(tmp_path / "parquet")]) == 0
    assert out.exists()
    names = {p.stem for p in (tmp_path / "parquet").glob("*.parquet")}
    assert names == set(bdb.TABLES) | set(bdb.VIEWS)
