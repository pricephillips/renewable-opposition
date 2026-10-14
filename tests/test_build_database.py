import json
from types import SimpleNamespace

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


# Every path --publish writes, as bdb constant -> name under a publish dir.
PUBLISH_PATHS = {
    "PARQUET_DIR": "parquet", "STATE_SUMMARY": "state_summary.json", "COUNTY_SUMMARY": "county_summary.json",
    "STATE_DIR": "state", "RECORD_INDEX": "record_index.json", "WORKLISTS_JSON": "worklists.json",
    "MANIFEST_JSON": "manifest.json", "GEOID_WORKLIST": "geoid_worklist.csv", "TIMELINE_JSON": "timeline.json",
    "HISTORY_JSON": "history.json", "EXAMINATION_WORKLIST": "examination_worklist.csv",
}


def _publish_to(mp, root):
    for name, rel in PUBLISH_PATHS.items():
        mp.setattr(bdb, name, root / rel)


@pytest.fixture
def publish_dirs(monkeypatch, tmp_path):
    _publish_to(monkeypatch, tmp_path)
    return tmp_path


def _publish(con, root):
    """Every published file written from con (export_parquet through
    write_manifest), as {file name: bytes} of everything under root."""
    parquet = bdb.export_parquet(con)
    bdb.write_summaries(con)
    bdb.write_state_files(con)
    bdb.write_record_index(con)
    bdb.write_worklists(con)
    bdb.write_timeline(con)
    bdb.write_history(con)
    bdb.write_manifest(con, parquet)
    return {p.name: p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.fixture(scope="module")
def published(con, tmp_path_factory):
    """One publish from con into a temp dir, made once for the module (about
    10 s, most of it the state files). test_publish_is_byte_for_byte_repeatable
    compares it with a second; the state-file and record-index tests only
    read it."""
    root = tmp_path_factory.mktemp("published")
    with pytest.MonkeyPatch.context() as mp:
        _publish_to(mp, root)
        files = _publish(con, root)
    return SimpleNamespace(root=root, files=files)


@pytest.fixture
def published_dirs(published, monkeypatch):
    """bdb's publish paths pointed at the shared publish, for tests that only
    read what it wrote."""
    _publish_to(monkeypatch, published.root)
    return published.root


def test_main_publishes_parquet_and_summaries(publish_dirs):
    out = publish_dirs / "ro.duckdb"
    (publish_dirs / "parquet").mkdir()
    (publish_dirs / "parquet" / "dropped_table.parquet").write_bytes(b"old")
    assert bdb.main(["--out", str(out), "--publish"]) == 0
    assert out.exists()
    names = {p.stem for p in (publish_dirs / "parquet").glob("*.parquet")}
    assert names == set(bdb.TABLES) | set(bdb.VIEWS)
    assert {p.stem for p in (publish_dirs / "state").glob("*.json")} == set(bdb.STATE_FIPS)


def test_publish_is_byte_for_byte_repeatable(con, published, publish_dirs):
    # The first publish from con is the module's (published); the second is made here.
    assert published.files == _publish(con, publish_dirs)
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


def test_every_record_is_in_its_own_state_file(con, published_dirs):
    # bdb.write_state_files(con) ran in the module's publish (published).
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


def test_record_index_names_the_state_file_of_every_record(con, published_dirs):
    # bdb.write_state_files(con) and bdb.write_record_index(con) ran in the module's publish (published).
    idx = json.loads(bdb.RECORD_INDEX.read_text())
    rows = rowsof(idx)
    key = {"restriction": "restrictions", "project": "projects", "case": "cases"}
    files = {p.stem: json.loads(p.read_text()) for p in bdb.STATE_DIR.glob("*.json")}
    for r in rows:
        ids = {x["instrument_id"] for x in files[r["state_code"]][key[r["entity"]]]}
        assert r["instrument_id"] in ids, r
    m = _metrics()
    counts = {e: sum(1 for r in rows if r["entity"] == e) for e in key}
    assert counts == {"restriction": m["restrictions"]["instruments"],
                      "project": m["contested_projects"]["projects"], "case": m["cases"]["cases"]}


def test_state_file_records_carry_their_technology_rows(con):
    detail = bdb.state_detail(con, "NY")
    n = sum(len(r["rows"]) for r in detail["restrictions"] if r["state_code"] == "NY")
    want = con.execute("SELECT count(*) FROM restriction JOIN restriction_instrument USING (instrument_id) "
                       "WHERE state_code = 'NY'").fetchone()[0]
    assert n == want


def test_worklists_publish_sizes_only(con, publish_dirs):
    bdb.write_worklists(con)
    w = json.loads(bdb.WORKLISTS_JSON.read_text())
    assert w["columns"] == ["worklist", "description", "rows"]
    assert {r[0] for r in w["rows"]} == set(bdb.WORKLISTS) | {"geoid_worklist", "examination_worklist"}
    path, only, _ = bdb.WORKLISTS["queue"]
    from common import read_csv
    assert dict((r[0], r[2]) for r in w["rows"])["queue"] == \
        sum(1 for r in read_csv(path) if r.get(only[0]) in only[1])


def test_manifest_lists_every_parquet_file(con, publish_dirs):
    parquet = bdb.export_parquet(con)
    bdb.write_manifest(con, parquet)
    rows = rowsof(json.loads(bdb.MANIFEST_JSON.read_text()))
    assert {r["name"] for r in rows} == set(bdb.TABLES) | set(bdb.VIEWS)
    for r in rows:
        assert (publish_dirs / r["file"]).stat().st_size == r["bytes"]


def rowsof(t):
    return [dict(zip(t["columns"], r)) for r in t["rows"]]


def test_every_named_jurisdiction_is_matched_or_listed(con):
    total, matched = con.execute("SELECT count(*), count(geoid) FROM jurisdiction_match").fetchone()
    listed = con.execute("SELECT count(*) FROM stg_geoid_worklist").fetchone()[0]
    assert total == matched + listed
    assert matched / total > 0.9
    # Matched ones carry their GEOID to the records.
    orphans = con.execute("""SELECT count(*) FROM restriction_instrument ri
                             JOIN restriction r USING (instrument_id)
                             JOIN stg_restrictions s ON s.id = r.id
                             JOIN jurisdiction_match m ON m.state_code = upper(s.state)
                              AND m.jurisdiction = s.jurisdiction AND m.jurisdiction_type = s.jurisdiction_type
                              AND m.counties = coalesce(nullif(s.county_fips_all, ''), nullif(s.county_fips, ''), '')
                             WHERE m.geoid IS NOT NULL AND ri.geoid IS NULL""").fetchone()[0]
    assert orphans == 0


def test_two_governments_sharing_a_match_key_get_two_geoids(con):
    rows = con.execute("""SELECT jurisdiction_key, count(DISTINCT s.geoid) FROM siting_standard s
                          WHERE s.geoid IS NOT NULL
                          GROUP BY jurisdiction_key HAVING count(DISTINCT jurisdiction) > 1""").fetchall()
    if not rows:
        pytest.skip("no shared match key in the current data")
    assert all(n > 1 for _, n in rows), rows


def test_geoid_worklist_is_written_on_publish(con, publish_dirs):
    bdb.write_geoid_worklist(con)
    from common import read_csv
    rows = read_csv(publish_dirs / "geoid_worklist.csv")
    assert len(rows) == con.execute("SELECT count(*) FROM jurisdiction_match WHERE geoid IS NULL").fetchone()[0]
    assert all(r["method"] in {"ambiguous", "no_match", "county_differs"} for r in rows)


def test_timeline_counts_every_instrument_once(con, publish_dirs):
    bdb.write_timeline(con)
    rows = rowsof(json.loads(bdb.TIMELINE_JSON.read_text()))
    m = _metrics()["restrictions"]["by_scope"]
    for scope in ("renewables_only", "multi_sector_data_centers"):
        assert sum(r["instruments"] for r in rows if r["scope"] == scope) == m[scope]["instruments"]
    assert {r["basis"] for r in rows} <= {"enacted", "year_reported", "ordinance_year", "undated"}
    assert all((r["year"] is None) == (r["basis"] == "undated") for r in rows)


def test_examination_worklist_lists_every_unexamined_county_nearest_states_first(con, publish_dirs):
    bdb.write_examination_worklist(con)
    from common import read_csv
    rows = read_csv(publish_dirs / "examination_worklist.csv")
    todo = {f for (f,) in con.execute("SELECT county_fips FROM v_county_summary "
                                      "WHERE in_coverage_universe AND coverage_status = 'not_examined'").fetchall()}
    assert {r["county_fips"] for r in rows if r["reason"] in ("not_examined", "check_held")} == todo
    assert [int(r["rank"]) for r in rows] == list(range(1, len(rows) + 1))
    remaining = [int(r["state_remaining"]) for r in rows]
    assert remaining == sorted(remaining)
    assert not any(r["county_fips"].startswith("72") for r in rows), "Puerto Rico is outside the coverage universe"
    size = con.execute("SELECT rows FROM worklist_size WHERE worklist = 'examination_worklist'").fetchone()[0]
    assert size == len(rows)


def test_a_drafted_check_counts_only_once_reviewed(con, monkeypatch, tmp_path):
    import negative_checks as nc
    from common import write_csv
    # Two counties nobody has examined: one gets the drafted check, the other
    # the same check reviewed. One build holds both; each is asserted on its own.
    (fips, st), (reviewed_fips, reviewed_st) = con.execute(
        "SELECT county_fips, state_code FROM v_county_summary WHERE in_coverage_universe "
        "AND coverage_status = 'not_examined' ORDER BY county_fips LIMIT 2").fetchall()
    draft = {"county_fips": fips, "state": st, "county": "x", "scope": "restrictions",
             "governments_checked": "the county", "checked_on": nc.PROTOCOL_START, "result": "none_found",
             "sources_checked": "code: zoning code (https://example.org); minutes: board 2023 to 2026; "
                                "news search: solar moratorium",
             "drafted_by": "agent:checker-1", "reviewer": ""}
    reviewed_check = {**draft, "county_fips": reviewed_fips, "state": reviewed_st, "reviewer": "agent:reviewer-1"}

    def build_with(*checks):
        path = tmp_path / "negative_checks.csv"
        write_csv(path, nc.load() + list(checks), nc.CHECK_FIELDS)
        monkeypatch.setattr(nc, "CHECKS_PATH", path)
        c = duckdb.connect()
        bdb.build(c)
        return c

    held = reviewed = build_with(draft, reviewed_check)
    assert held.execute("SELECT coverage_status FROM v_county_summary WHERE county_fips = ?", [fips]).fetchone() \
        == ("not_examined",)
    assert held.execute("SELECT reason, drafted_by FROM examination_worklist WHERE county_fips = ?",
                        [fips]).fetchone() == ("check_held", "agent:checker-1")
    assert reviewed.execute("SELECT coverage_status, negative_check_grade FROM v_county_summary "
                            "WHERE county_fips = ?", [reviewed_fips]).fetchone() == ("checked_none", "A")
    assert reviewed.execute("SELECT count(*) FROM examination_worklist WHERE county_fips = ?",
                            [reviewed_fips]).fetchone() == (0,)
