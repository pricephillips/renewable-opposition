"""Counting, scope, evidence and reviewer-resolution rules."""
import classify
import coverage_delta as cd
import headline_metrics as hm
import pytest
import resolutions
import verification_worklist as vw


def mn(tech, sectors, desc="Moratorium on battery storage systems.", **kw):
    return {"moratorium_id": "ks-x-2026", "technology": tech, "sectors": sectors,
            "description": desc, "state": "KS", "severity_score": 4, "status": "active", **kw}


def test_one_instrument_per_moratorium_whatever_its_technologies():
    rows = [classify.stamp("restrictions", mn(t, "battery_storage;solar")) for t in ("solar", "battery_storage")]
    m = hm.compute({"restrictions": rows})
    assert m["restrictions"]["rows"] == 2 and m["restrictions"]["instruments"] == 1
    assert m["restrictions"]["by_scope"]["renewables_only"]["by_technology"] == {"battery_storage": 1, "solar": 1}


def test_scope_uses_sectors_and_catches_data_center_only_text():
    assert classify.scope(mn("battery_storage", "battery_storage;data_center")) == "multi_sector_data_centers"
    assert classify.scope(mn("battery_storage", "battery_storage")) == "renewables_only"
    dc = mn("solar", "data_center;solar", desc="A proposed 600,000-sq-ft data center prompted a pause.")
    assert classify.scope(dc) == "data_center_only"
    # "window" is not wind
    assert classify.scope(mn("wind", "data_center;wind", desc="Data center window of review.")) == "data_center_only"
    # A Sabin row with no sectors column is renewables-only unless its text says otherwise
    assert classify.scope({"description": "Setbacks for wind turbines."}) == "renewables_only"


def test_multi_sector_is_reported_beside_the_headline_not_in_it():
    rows = [classify.stamp("restrictions", mn("solar", "solar")),
            classify.stamp("restrictions", {**mn("solar", "data_center;solar"), "moratorium_id": "ks-y"})]
    s = hm.compute({"restrictions": rows})["restrictions"]["by_scope"]
    assert s["renewables_only"]["instruments"] == 1 and s["multi_sector_data_centers"]["instruments"] == 1


def test_evidence_levels():
    assert classify.evidence_level("restrictions", mn("solar", "solar")) == "compiled_record"
    assert classify.evidence_level("restrictions", mn("solar", "solar", needs_verification="yes")) == "compiled_flagged"
    assert classify.evidence_level("restrictions", {"source_record_id": "REC-1"}) == "report_citation"
    confirmed = {"primary_source_url": "https://town.gov/o.pdf", "primary_source_verdict": "confirmed",
                 "primary_source_access": "opened"}
    assert classify.evidence_level("restrictions", confirmed) == "primary_source"
    assert classify.evidence_level("restrictions", {**confirmed, "primary_source_access": "archived"}) \
        == "primary_source"
    # Located, not yet read: no upgrade, and no access at all is no upgrade either.
    assert classify.evidence_level("restrictions", {**confirmed, "primary_source_access": "snippet"}) \
        == "report_citation"
    assert classify.evidence_level("restrictions", {**confirmed, "primary_source_access": ""}) \
        == "report_citation"
    assert classify.evidence_level("restrictions", {**confirmed, "primary_source_verdict": "contradicts"}) \
        == "report_citation"
    assert classify.evidence_level("contested_projects", {"outcome": "blocked_confirmed"}) == "confirmed"


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def test_outcome_resolution_confirms_and_rescores(tmp_path):
    rows = [{"source_record_id": "REC-5", "outcome": "pending", "has_litigation": "yes", "severity_score": 3}]
    f = _write(tmp_path / "r.csv", "source_record_id,outcome,evidence_url,evidence_date,access\n"
               "REC-5,blocked_confirmed,https://county.gov/denial.pdf,2024-05,opened\n")
    assert resolutions.apply_outcomes(rows, {"blocked_confirmed", "pending"}, f) == []
    assert rows[0]["outcome"] == "blocked_confirmed" and rows[0]["severity_score"] == 4
    assert rows[0]["finality_evidence"] == "resolution: https://county.gov/denial.pdf"
    assert rows[0]["resolution_access"] == "opened"


def test_an_archived_copy_confirms_an_outcome_and_needs_its_url(tmp_path):
    rows = [{"source_record_id": "REC-5", "outcome": "blocked_unverified", "has_litigation": "no"}]
    f = _write(tmp_path / "r.csv", "source_record_id,outcome,evidence_url,access,archived_url\n"
               "REC-5,blocked_confirmed,https://news.example.org/a,archived,"
               "https://web.archive.org/web/2024/https://news.example.org/a\n")
    assert resolutions.apply_outcomes(rows, {"blocked_confirmed", "blocked_unverified"}, f) == []
    assert rows[0]["outcome"] == "blocked_confirmed"
    assert classify.stamp("contested_projects", rows[0])["evidence_level"] == "confirmed"
    bad = _write(tmp_path / "b.csv", "source_record_id,outcome,evidence_url,access\n"
                 "REC-5,blocked_confirmed,https://news.example.org/a,archived\n")
    assert "archived_url" in resolutions.apply_outcomes(rows, {"blocked_confirmed"}, bad)[0]


def test_a_snippet_resolution_is_a_lead_and_confirms_nothing(tmp_path):
    rows = [{"source_record_id": "REC-5", "outcome": "blocked_unverified", "has_litigation": "no",
             "severity_score": 4, "finality_evidence": "outcome_label_only"}]
    f = _write(tmp_path / "r.csv", "source_record_id,outcome,evidence_url,evidence_date,access\n"
               "REC-5,blocked_confirmed,https://news.example.org/a,2014-05,snippet\n")
    assert resolutions.apply_outcomes(rows, {"blocked_confirmed", "blocked_unverified"}, f) == []
    r = classify.stamp("contested_projects", rows[0])
    assert r["outcome"] == "blocked_unverified" and r["evidence_level"] == "report_citation"
    assert r["finality_evidence"] == "lead: https://news.example.org/a"
    assert (r["resolution_url"], r["resolution_access"]) == ("https://news.example.org/a", "snippet")
    assert not r.get("resolution_date")


def test_a_snippet_resolution_never_overwrites_a_court_ruling(tmp_path):
    rows = [{"source_record_id": "REC-5", "outcome": "advanced_confirmed",
             "finality_evidence": "court_ruling: A v. B"}]
    f = _write(tmp_path / "r.csv", "source_record_id,outcome,evidence_url,access\n"
               "REC-5,advanced_confirmed,https://news.example.org/a,snippet\n")
    assert resolutions.apply_outcomes(rows, {"advanced_confirmed"}, f) == []
    assert rows[0]["finality_evidence"] == "court_ruling: A v. B"


@pytest.mark.parametrize("access", ["", "seen", "Opened"])
def test_a_blank_or_unknown_access_stops_the_build(tmp_path, access):
    f = _write(tmp_path / "r.csv", "source_record_id,outcome,evidence_url,access\n"
               f"REC-5,blocked_confirmed,https://x.gov/a,{access}\n")
    rows = [{"source_record_id": "REC-5", "outcome": "pending"}]
    errors = resolutions.apply_outcomes(rows, {"blocked_confirmed", "pending"}, f)
    assert len(errors) == 1 and "access" in errors[0] and "snippet" in errors[0]
    assert rows[0]["outcome"] == "pending"
    s = _write(tmp_path / "s.csv", "instrument_id,primary_source_url,verdict,access\n"
               f"mn:ks-x-2026,https://ks-x.gov/o.pdf,confirmed,{access}\n")
    errors = resolutions.apply_restriction_sources([classify.stamp("restrictions", mn("solar", "solar"))], s)
    assert len(errors) == 1 and "access" in errors[0]


@pytest.mark.parametrize("line,msg", [
    ("REC-9,blocked_confirmed,https://x.gov/a,,opened", "no contested project"),
    ("REC-5,won,https://x.gov/a,,opened", "not in the vocabulary"),
    ("REC-5,blocked_confirmed,,,opened", "evidence_url is required"),
    ("REC-5,blocked_confirmed,https://x.gov/a,May 2024,opened", "not YYYY"),
])
def test_bad_outcome_resolutions_are_errors(tmp_path, line, msg):
    rows = [{"source_record_id": "REC-5", "outcome": "pending"}]
    f = _write(tmp_path / "r.csv", "source_record_id,outcome,evidence_url,evidence_date,access\n" + line + "\n")
    errors = resolutions.apply_outcomes(rows, {"blocked_confirmed", "pending"}, f)
    assert len(errors) == 1 and msg in errors[0] and rows[0]["outcome"] == "pending"


def test_restriction_source_reaches_every_row_of_the_instrument(tmp_path):
    rows = [classify.stamp("restrictions", mn(t, "solar;wind")) for t in ("solar", "wind")]
    f = _write(tmp_path / "s.csv", "instrument_id,primary_source_url,verdict,access\n"
               "mn:ks-x-2026,https://ks-x.gov/ordinance.pdf,confirmed,opened\n")
    assert resolutions.apply_restriction_sources(rows, f) == []
    assert all(classify.stamp("restrictions", r)["evidence_level"] == "primary_source" for r in rows)
    bad = _write(tmp_path / "b.csv", "instrument_id,primary_source_url,verdict,access\n"
                 "mn:ks-x-2026,https://a.gov/x,maybe,opened\n")
    assert "verdict" in resolutions.apply_restriction_sources(rows, bad)[0]


def test_a_snippet_primary_source_is_attached_but_upgrades_nothing(tmp_path):
    rows = [classify.stamp("restrictions", mn(t, "solar;wind")) for t in ("solar", "wind")]
    f = _write(tmp_path / "s.csv", "instrument_id,primary_source_url,verdict,access\n"
               "mn:ks-x-2026,https://ks-x.gov/ordinance.pdf,confirmed,snippet\n")
    assert resolutions.apply_restriction_sources(rows, f) == []
    for r in rows:
        classify.stamp("restrictions", r)
        assert r["evidence_level"] == "compiled_record"
        assert (r["primary_source_url"], r["primary_source_access"]) == ("https://ks-x.gov/ordinance.pdf", "snippet")


def test_a_snippet_contradiction_is_reported_not_quarantined():
    import qc_gate
    row = {"state": "KS", "status": "active", "source_url": "https://x.org",
           "primary_source_url": "https://town.gov/o.pdf", "primary_source_verdict": "contradicts"}
    (issue,) = qc_gate.check_record("restrictions", {**row, "primary_source_access": "snippet"})
    assert issue.code == "PRIMARY_SOURCE_CONTRADICTS" and issue.severity == "MEDIUM"
    (issue,) = qc_gate.check_record("restrictions", {**row, "primary_source_access": "opened"})
    assert issue.severity == "HIGH"


@pytest.mark.parametrize("name", ["restriction_sources", "outcome_resolutions", "place_overrides", "queue"])
def test_every_committed_review_row_says_how_its_evidence_was_seen(name):
    from common import REVIEW_DIR, read_csv
    for r in read_csv(REVIEW_DIR / f"{name}.csv"):
        assert resolutions.access_error(r) == "", (name, r.get("access"))


def test_snippet_leads_stay_on_the_worklists():
    read, leads = vw.split_by_access([
        {"instrument_id": "a", "primary_source_url": "https://a.gov", "access": "opened"},
        {"instrument_id": "b", "primary_source_url": "https://b.gov", "access": "snippet"}],
        "instrument_id", "primary_source_url")
    assert read == {"a"} and leads == {"b": "https://b.gov"}
    rows = [classify.stamp("restrictions", {"source_record_id": "REC-1", "state": "KS", "technology": "wind"})]
    (out,) = vw.restriction_rows(rows, checked=read, located={"sabin:REC-1": "https://b.gov"})
    assert out["located_url"] == "https://b.gov"


def test_missing_resolution_files_are_fine(tmp_path):
    assert resolutions.apply_outcomes([], set(), tmp_path / "none.csv") == []
    assert resolutions.apply_restriction_sources([], tmp_path / "none.csv") == []


def test_outcome_worklist_ranks_blocked_claims_first_and_drops_resolved():
    projects = [
        {"source_record_id": "A", "outcome": "pending", "event_date_text": "2019", "state": "OH"},
        {"source_record_id": "B", "outcome": "blocked_unverified", "event_date_text": "2021", "state": "OH",
         "project_name": "Birch Solar", "technology": "solar", "county": "Allen County"},
        {"source_record_id": "C", "outcome": "blocked_confirmed", "state": "OH"},
        {"source_record_id": "D", "outcome": "advanced_unverified", "state": "OH"},
    ]
    rows = vw.outcome_rows(projects, resolved={"D"})
    assert [r["source_record_id"] for r in rows] == ["B", "A"]
    assert rows[0]["priority"] == 1 and rows[0]["search_query"] == '"Birch Solar" solar Allen County Ohio'


def test_restriction_worklist_is_per_instrument_weakest_evidence_first():
    rows = [classify.stamp("restrictions", r) for r in (
        {"source_record_id": "REC-1", "jurisdiction": "A", "state": "OH", "technology": "wind", "severity_score": 4},
        mn("solar", "solar", needs_verification="yes", jurisdiction="B"),
        mn("wind", "solar;wind", needs_verification="yes", jurisdiction="B"),
    )]
    out = vw.restriction_rows(rows, checked=set())
    assert [r["instrument_id"] for r in out] == ["mn:ks-x-2026", "sabin:REC-1"]
    assert out[0]["technologies"] == "solar;wind"
    assert vw.restriction_rows(rows, checked={"mn:ks-x-2026"})[0]["instrument_id"] == "sabin:REC-1"


def test_coverage_gate_fails_a_collapsed_column_only():
    before = cd.profile("id,county,notes\n" + "".join(f"r{i},C{i},{'n' if i < 3 else ''}\n" for i in range(40)))
    fewer_rows = cd.profile("id,county,notes\n" + "".join(f"r{i},C{i},\n" for i in range(30)))
    assert cd.compare(before, fewer_rows) == []  # rows removed on purpose, fill rate intact; notes too sparse to judge
    blanked = cd.profile("id,county,notes\n" + "".join(f"r{i},,\n" for i in range(40)))
    assert [d["column"] for d in cd.compare(before, blanked)] == ["county"]
    renamed = cd.profile("id,county_name,notes\n" + "".join(f"r{i},C{i},\n" for i in range(40)))
    fails = cd.compare(before, renamed)
    assert fails[0]["column"] == "county" and fails[0]["missing"]


def test_a_declared_drop_clears_only_its_exact_count():
    drop = [{"column": "municipality", "before": 22, "after": 17}]
    exc = {"contested_projects.csv": {"municipality": {"expect_after": 17, "reason": "moved"}}}
    assert cd.split_declared("contested_projects.csv", drop, exc)[0] == []
    worse = [{"column": "municipality", "before": 22, "after": 3}]
    assert cd.split_declared("contested_projects.csv", worse, exc)[0] == worse
    assert cd.split_declared("cases.csv", drop, exc)[0] == drop


def test_a_new_column_is_held_to_its_declared_floor():
    exp = {"contested_projects.csv": {"county_fips": {"min_filled": 3, "reason": "r"}}}
    ok = cd.profile("id,county_fips\na,01001\nb,01003\nc,01005\nd,\n")
    assert cd.below_floor("contested_projects.csv", ok, exp) == []
    thin = cd.profile("id,county_fips\na,01001\nb,\nc,\n")
    assert [(d["column"], d["after"]) for d in cd.below_floor("contested_projects.csv", thin, exp)] == [("county_fips", 1)]
    gone = cd.profile("id,county\na,x\n")
    assert cd.below_floor("contested_projects.csv", gone, exp)[0]["missing"] is True
    assert cd.below_floor("cases.csv", thin, exp) == []


LOOKUP = {"autauga county|alabama": "01001", "autauga|alabama": "01001",
          "fairfield|connecticut": "09001", "district 1|alaska": "02901",
          "huron county|michigan": "26063"}
NAMES = {"AL": "Alabama", "CT": "Connecticut", "AK": "Alaska", "MI": "Michigan"}


@pytest.mark.parametrize("entity,row,expected", [
    ("contested_projects", {"state": "AL", "county": "Autauga County"}, ("01001", "")),
    ("contested_projects", {"state": "AL", "county": " autauga "}, ("01001", "")),
    ("contested_projects", {"state": "AL", "county": ""}, ("", "blank_county")),
    ("contested_projects", {"state": "AL", "county": "Autauga and Elmore Counties"}, ("", "several_counties")),
    ("contested_projects", {"state": "AL", "county": "Autauga County (Elmore County)"}, ("", "several_counties")),
    ("contested_projects", {"state": "AL", "county": "Autaugaa County"}, ("", "not_in_lookup")),
    ("contested_projects", {"state": "CT", "county": "Fairfield"}, ("", "not_a_2024_county")),
    ("contested_projects", {"state": "AK", "county": "District 1"}, ("", "not_a_2024_county")),
    ("restrictions", {"state": "MI", "jurisdiction": "Huron County (solar and battery storage)",
                      "jurisdiction_type": "County"}, ("26063", "")),
    ("restrictions", {"state": "AL", "jurisdiction": "Autauga", "jurisdiction_type": "Town"}, ("", "")),
    ("cases", {"state": "AL", "county": "Autauga County"}, ("", "")),
])
def test_county_fips_is_an_exact_lookup_or_a_named_miss(entity, row, expected):
    assert classify.county_fips(entity, row, LOOKUP, NAMES) == expected
