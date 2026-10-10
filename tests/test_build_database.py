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


@pytest.fixture
def publish_dirs(monkeypatch, tmp_path):
    monkeypatch.setattr(bdb, "PARQUET_DIR", tmp_path / "parquet")
    monkeypatch.setattr(bdb, "STATE_SUMMARY", tmp_path / "state_summary.json")
    monkeypatch.setattr(bdb, "COUNTY_SUMMARY", tmp_path / "county_summary.json")
    monkeypatch.setattr(bdb, "STATE_DIR", tmp_path / "state")
    return tmp_path


def test_main_publishes_parquet_and_summaries(publish_dirs):
    out = publish_dirs / "ro.duckdb"
    (publish_dirs / "parquet").mkdir()
    (publish_dirs / "parquet" / "dropped_table.parquet").write_bytes(b"old")
    assert bdb.main(["--out", str(out), "--publish"]) == 0
    assert out.exists()
    names = {p.stem for p in (publish_dirs / "parquet").glob("*.parquet")}
    assert names == set(bdb.TABLES) | set(bdb.VIEWS)
    assert {p.stem for p in (publish_dirs / "state").glob("*.json")} == set(bdb.STATE_FIPS)


def test_publish_is_byte_for_byte_repeatable(con, publish_dirs):
    def snapshot():
        bdb.export_parquet(con)
        bdb.write_summaries(con)
        bdb.write_state_files(con)
        return {p.name: p.read_bytes() for p in publish_dirs.rglob("*") if p.is_file()}
    assert snapshot() == snapshot()
    keys = {k for (k,) in duckdb.sql(
        f"SELECT key FROM '{(publish_dirs / 'parquet' / 'build_info.parquet').as_posix()}'").fetchall()}
    assert not keys & set(bdb.VOLATILE_INFO)


def test_summaries_agree_with_headline_metrics(con, publish_dirs):
    bdb.write_summaries(con)
    states = json.loads(bdb.STATE_SUMMARY.read_text())
    counties = json.loads(bdb.COUNTY_SUMMARY.read_text())
    m = _metrics()
    col = {c: i for i, c in enumerate(states["columns"])}
    assert sum(r[col["restrictions"]] for r in states["rows"]) == \
        m["restrictions"]["by_scope"]["renewables_only"]["instruments"]
    col = {c: i for i, c in enumerate(counties["columns"])}
    universe = [r for r in counties["rows"] if r[col["in_coverage_universe"]]]
    assert len(universe) == m["county_coverage"]["counties"]
    assert sum(r[col["coverage_status"]] == "not_examined" for r in universe) == \
        m["county_coverage"]["with_neither"]


def test_every_record_is_in_its_own_state_file(con, publish_dirs):
    bdb.write_state_files(con)
    files = {p.stem: json.loads(p.read_text()) for p in bdb.STATE_DIR.glob("*.json")}
    for entity, table in (("restrictions", "restriction_instrument"), ("projects", "contested_project")):
        expected = dict(con.execute(f"SELECT instrument_id, state_code FROM {table}").fetchall())
        for iid, st in expected.items():
            assert iid in {r["instrument_id"] for r in files[st][entity]}, (entity, iid, st)
    standards = sum(s["features"] for f in files.values() for s in f["siting_standards"])
    assert standards == _metrics()["siting_standards"]["rows"]


def test_siting_standards_keep_same_key_governments_apart(con):
    # common.jurisdiction_key folds "<Name> City" and "<Name> Town" together;
    # the state files list each government on its own.
    rows = con.execute("""SELECT jurisdiction_key FROM siting_standard
                          GROUP BY jurisdiction_key, technology
                          HAVING count(DISTINCT jurisdiction) > 1""").fetchall()
    if not rows:
        pytest.skip("no shared match key in the current data")
    key = rows[0][0]
    st = key.split("::")[0]
    detail = bdb.state_detail(con, st)
    names = {s["jurisdiction"] for s in detail["siting_standards"] if s["jurisdiction_key"] == key}
    assert len(names) > 1


def test_pending_review_is_a_count_that_matches_site_profiles(con):
    import site_profile
    d = site_profile.Data(local=False)
    for fips, n in con.execute("SELECT county_fips, candidates FROM county_pending_review").fetchall():
        st, name = con.execute("SELECT state_code, county_name FROM county WHERE county_fips = ?",
                               [fips]).fetchone()
        assert n == len(site_profile.pending_for(d, fips, name, st))
    detail_keys = set(bdb.state_detail(con, "IA"))
    assert not any("pending" in k or "queue" in k for k in detail_keys)
