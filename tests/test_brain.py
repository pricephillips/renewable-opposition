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
    reviewed = {"description": "Setbacks for wind turbines.",
                "notes": "Reviewer: the board also adopted a separate data center moratorium."}
    assert classify.scope(reviewed) == "renewables_only"


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


def test_a_verdict_on_a_lifted_queue_instrument_stays_without_a_row(tmp_path):
    """promote_reviewed.py takes a repealed queue instrument out of the seed;
    the verdict that found the repeal is still checked, and lays on nothing."""
    q = _write(tmp_path / "queue.csv", "queue_id,entity_type,review_status,status\n"
               "q_1,restriction,promoted,lifted\nq_2,restriction,promoted,active\n"
               "q_3,restriction,confirmed,expired\nq_4,contested_project,promoted,expired\n")
    assert resolutions.retired_instruments(q) == {"queue:q_1"}
    f = _write(tmp_path / "s.csv", "instrument_id,primary_source_url,verdict,access\n"
               "queue:q_1,https://city.gov/o.pdf,contradicts,opened\n")
    assert resolutions.apply_restriction_sources([], f, retired={"queue:q_1"}) == []
    assert "no restriction has instrument_id" in resolutions.apply_restriction_sources([], f)[0]
    bad = _write(tmp_path / "b.csv", "instrument_id,primary_source_url,verdict,access\n"
                 "queue:q_1,https://city.gov/o.pdf,contradicts,seen\n")
    assert "access" in resolutions.apply_restriction_sources([], bad, retired={"queue:q_1"})[0]


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


# Currency: an instrument's own dates, not its status word, say whether it is in force.
T = __import__("datetime").date(2026, 10, 13)


def test_currency_follows_the_end_date_not_the_status_word():
    assert classify.currency(mn("solar", "solar", current_end_date_iso="2027-01-01"), T) == "in_force"
    assert classify.currency(mn("solar", "solar"), T) == "in_force"
    assert classify.currency(mn("solar", "solar", current_end_date_iso="2026-10-01"), T) == "lapsed_unconfirmed"
    assert classify.currency(mn("solar", "solar", status="extended", current_end_date_iso="2026-09"), T) \
        == "lapsed_unconfirmed"
    assert classify.currency(mn("solar", "solar", status="pending", current_end_date_iso="2026-10-01"), T) == "pending"
    assert classify.currency({"status": "unknown"}, T) == "unknown"
    assert classify.currency({"status": ""}, T) == "unknown"
    # A month-precision end date that is this month has not passed.
    assert classify.currency(mn("solar", "solar", current_end_date_iso="2026-10"), T) == "in_force"


def test_a_reviewer_who_confirmed_the_instrument_after_its_end_date_keeps_it_in_force():
    row = mn("solar", "solar", current_end_date_iso="2026-10-01", primary_source_url="https://x.gov/o.pdf",
             primary_source_verdict="confirmed", primary_source_checked_on="2026-10-05")
    assert classify.currency(row, T) == "in_force"
    assert classify.currency({**row, "primary_source_checked_on": "2026-09-20"}, T) == "lapsed_unconfirmed"
    assert classify.currency({**row, "primary_source_verdict": "contradicts"}, T) == "lapsed_unconfirmed"


def test_status_as_of_is_the_latest_date_the_status_is_known_to_hold():
    assert classify.status_as_of(mn("solar", "solar", desc="Pending as of 2026-09-23; vote set for later.")) \
        == "2026-09-23"
    assert classify.status_as_of(mn("solar", "solar", date_enacted_iso="2026-01-13",
                                    primary_source_checked_on="2026-03-01")) == "2026-03-01"
    assert classify.status_as_of(mn("solar", "solar")) == ""


def test_stamp_carries_currency_and_the_headline_counts_it_apart():
    rows = [classify.stamp("restrictions", mn(t, "solar;wind", current_end_date_iso="2026-10-01"), T)
            for t in ("solar", "wind")]
    assert all(r["currency"] == "lapsed_unconfirmed" for r in rows)
    rows.append(classify.stamp("restrictions", {**mn("solar", "solar"), "moratorium_id": "ks-y"}, T))
    s = hm.compute({"restrictions": rows})["restrictions"]["by_scope"]["renewables_only"]
    assert s["instruments"] == 2 and s["by_currency"] == {"in_force": 1, "lapsed_unconfirmed": 1}
    assert "lapsed_unconfirmed | 1 |" in hm.render(hm.compute({"restrictions": rows}))


def test_a_lapsed_instrument_is_reported_by_qc_never_quarantined():
    import qc_gate
    row = classify.stamp("restrictions", {**mn("solar", "solar", current_end_date_iso="2026-10-01"),
                                          "source_url": "https://x.org/a"}, T)
    issues = qc_gate.check_record("restrictions", row, T)
    assert [i.code for i in issues] == ["END_DATE_PASSED"] and not qc_gate.blocks(issues)
    assert all(code in {c[0] for c in qc_gate.CHECKS} for code, *_ in qc_gate.CHECKS)
    held = [{"entity": "restrictions", "id": "res_1", "state": "KS", "jurisdiction": "Example County",
             "qc_issues": [{"code": "SCOPE_DATA_CENTER_ONLY", "severity": "HIGH"},
                           {"code": "DATE_UNPARSEABLE", "severity": "LOW"}]}]
    report = qc_gate.render_report([], {"restrictions": 1}, held)
    assert "| restrictions | res_1 | KS | Example County | SCOPE_DATA_CENTER_ONLY | if the instrument" in report
    assert "DATE_UNPARSEABLE | nothing" not in report      # only the blocking code names a release action


def test_every_qc_code_the_selftest_emits_is_in_the_checks_table():
    import qc_gate
    listed = {code: sev for code, sev, *_ in qc_gate.CHECKS}
    assert all(release for *_, release in qc_gate.CHECKS)
    rows = [
        ("restrictions", {"state": "PA", "latitude": 32.5, "longitude": -91.6, "status": "enacted", "source_url": "x",
                          "date_enacted_iso": "2099-01", "current_end_date_iso": "March", "severity_score": 4,
                          "primary_source_url": "https://t.gov/o", "primary_source_verdict": "contradicts",
                          "scope": "data_center_only"}),
        ("restrictions", {"state": "PA", "status": "pending", "severity_score": 4, "source_url": "https://x.org"}),
        ("restrictions", {"state": "PA", "status": "active", "current_end_date_iso": "2020-01-01",
                          "source_url": "https://x.org"}),
        ("contested_projects", {"state": "PA", "outcome": "blocked_confirmed", "source_url": "https://x.org"}),
    ]
    seen = set()
    for entity, row in rows:
        for i in qc_gate.check_record(entity, row, T):
            seen.add(i.code)
            assert i.severity in listed[i.code].split(" or "), i.code
    # The one cross-entity check runs on the datasets, not a row.
    for f in qc_gate.check_links({"cases": [{"id": "c", "source_record_id": "REC-none"}]}):
        for i in f["issues"]:
            seen.add(i["code"])
            assert i["severity"] in listed[i["code"]].split(" or "), i["code"]
    assert seen == set(listed)


def test_lapsed_instruments_lead_the_restriction_worklist_even_when_checked_before():
    lapsed = classify.stamp("restrictions", mn("solar", "solar", current_end_date_iso="2026-10-01",
                                               primary_source_url="https://x.gov/o.pdf",
                                               primary_source_verdict="confirmed", primary_source_access="opened",
                                               primary_source_checked_on="2026-05-01"), T)
    assert lapsed["evidence_level"] == "primary_source"       # verified, and still lapsed
    other = classify.stamp("restrictions", {"source_record_id": "REC-1", "state": "KS", "technology": "wind",
                                            "status": "active", "severity_score": 4}, T)
    out = vw.restriction_rows([other, lapsed], checked={"mn:ks-x-2026"}, today=T)
    assert [r["instrument_id"] for r in out] == ["mn:ks-x-2026", "sabin:REC-1"]
    assert out[0]["currency"] == "lapsed_unconfirmed" and "end date 2026-10-01 passed" in out[0]["flags"]
    assert out[1]["flags"] == ""


def test_an_old_pending_restriction_is_flagged_stale():
    row = classify.stamp("restrictions", mn("solar", "solar", status="pending", severity_score=2,
                                            desc="Pending as of 2026-04-01; a vote was expected in May."), T)
    (out,) = vw.restriction_rows([row], checked=set(), today=T)
    assert out["status_as_of"] == "2026-04-01" and "pending 195 days (since 2026-04-01), past 120" in out["flags"]
    fresh = classify.stamp("restrictions", mn("solar", "solar", status="pending", severity_score=2,
                                              desc="Pending as of 2026-09-23."), T)
    assert vw.restriction_rows([fresh], checked=set(), today=T)[0]["flags"] == ""


def test_outcome_worklist_measures_age_and_flags_overdue_pending_projects():
    projects = [
        {"source_record_id": "A", "outcome": "pending", "event_date_text": "2023", "state": "OH",
         "description": "The county is considering the application."},
        {"source_record_id": "B", "outcome": "pending", "event_date_text": "2026-09", "state": "OH"},
        {"source_record_id": "C", "outcome": "needs_review", "event_date_text": "January 2015, June 2023", "state": "OH"},
    ]
    rows = {r["source_record_id"]: r for r in vw.outcome_rows(projects, resolved=set(), today=T)}
    assert rows["A"]["age_days"] == (T - __import__("datetime").date(2023, 12, 31)).days
    assert rows["A"]["recheck"].startswith("overdue: pending 1017 days")
    assert rows["B"]["recheck"] == "" and rows["B"]["age_days"] == 13
    assert rows["C"]["recheck"] == "" and rows["C"]["age_days"] == (T - __import__("datetime").date(2023, 6, 30)).days


def test_decision_language_is_a_lead_only_when_nothing_says_the_step_was_not_final():
    assert vw.decision_language("In 2023 the board denied the permit and the developer withdrew.") == "denied; withdrew"
    assert vw.decision_language("The board approved the permit; residents have appealed.") == ""
    assert vw.decision_language("A hearing on the proposed project is set for June.") == ""
    assert vw.decision_language("Residents packed the meeting.") == ""
    projects = [
        {"source_record_id": "A", "outcome": "pending", "event_date_text": "2024", "state": "OH",
         "description": "Residents object to the project."},
        {"source_record_id": "B", "outcome": "pending", "event_date_text": "2024", "state": "OH",
         "description": "Commissioners rejected the rezoning in May 2024."},
        {"source_record_id": "C", "outcome": "blocked_unverified", "event_date_text": "2024", "state": "OH",
         "description": "Commissioners rejected the rezoning in May 2024."},
    ]
    rows = vw.outcome_rows(projects, resolved=set(), today=T)
    # Inside the pending tier the row whose text already states the decision comes first.
    assert [r["source_record_id"] for r in rows] == ["C", "B", "A"]
    assert rows[1]["decision_language"] == "rejected" and rows[0]["decision_language"] == ""


def test_county_impact_names_the_instruments_whose_check_would_move_a_county():
    def r(iid, fips, sev, scope="renewables_only"):
        return {"instrument_id": iid, "county_fips_all": fips, "severity_score": sev, "scope": scope,
                "state": "KS", "technology": "wind", "status": "active", "evidence_level": "report_citation"}
    rows = [r("a", "20001", 4), r("b", "20001", 2), r("c", "20003", 4), r("d", "20003", 4),
            r("e", "20005", 2), r("f", "20007", 4, scope="multi_sector_data_centers")]
    assert vw.county_impacts(rows) == {"a": "sole_severe", "b": "", "c": "", "d": "", "e": "sole_record"}
    out = vw.restriction_rows(rows, checked=set(), today=T)
    # Within the tier: renewables-only first, then the instruments whose check moves a county.
    assert [x["instrument_id"] for x in out] == ["a", "e", "c", "d", "b", "f"]
    assert out[0]["county_impact"] == "sole_severe" and out[1]["county_impact"] == "sole_record"


POLICIES_OH = [
    {"id": "OH-siting_authority-1", "state": "OH", "technology": "solar;wind", "policy_type": "siting_authority",
     "who_decides": "state_board", "threshold_mw": "solar:50;wind:5"},
    {"id": "OH-local_opt_out-1", "state": "OH", "technology": "solar;wind", "policy_type": "local_opt_out",
     "who_decides": "", "threshold_mw": ""},
]
POLICIES_AL = [{"id": "AL-siting_authority-1", "state": "AL", "technology": "solar;wind",
                "policy_type": "siting_authority", "who_decides": "local_government", "threshold_mw": ""}]
POLICIES_MD = [{"id": "MD-siting_authority-1", "state": "MD", "technology": "solar;wind;battery_storage",
                "policy_type": "siting_authority", "who_decides": "hybrid", "threshold_mw": ""},
               {"id": "MD-local_preemption-1", "state": "MD", "technology": "solar",
                "policy_type": "local_preemption", "who_decides": "local_government", "threshold_mw": ""}]


def test_state_context_reads_the_verified_policy_rows_and_never_infers():
    county = {"state": "OH", "technology": "wind", "jurisdiction_type": "County"}
    assert classify.state_context(county, POLICIES_OH) == {
        "state_siting_authority": "state_board", "state_threshold_mw": "5", "state_preemption_ids": "",
        "state_limits_local": "yes"}
    assert classify.state_context({**county, "technology": "solar"}, POLICIES_OH)["state_threshold_mw"] == "50"
    # No verified row for the technology: unknown, with every other field blank.
    assert classify.state_context({**county, "technology": "battery_storage"}, POLICIES_OH) == {
        "state_siting_authority": "", "state_threshold_mw": "", "state_preemption_ids": "",
        "state_limits_local": "unknown"}
    assert classify.state_context({**county, "state": "AL"}, POLICIES_AL)["state_limits_local"] == "no"
    md = classify.state_context({**county, "state": "MD", "technology": "solar"}, POLICIES_MD)
    assert (md["state_limits_local"], md["state_preemption_ids"], md["state_siting_authority"]) == \
        ("yes", "MD-local_preemption-1", "hybrid")
    # Hybrid with no threshold and no preemption rule for the technology: unknown, not a guess.
    assert classify.state_context({**county, "state": "MD"}, POLICIES_MD)["state_limits_local"] == "unknown"
    # A state-level row, or one with no technology, carries nothing.
    assert classify.state_context({**county, "jurisdiction_type": "State"}, POLICIES_OH)["state_limits_local"] == ""
    assert classify.state_context({**county}, [])["state_limits_local"] == "unknown"
    assert classify.threshold_for("solar:50;wind:5", "wind") == "5" and classify.threshold_for("", "wind") == ""


def test_headline_reports_severe_instruments_in_limiting_states_beside_the_count():
    rows = [classify.stamp("restrictions", {**mn("wind", "wind", moratorium_id=f"oh-{i}"), "state": "OH",
                                            "state_limits_local": lim}, T)
            for i, lim in enumerate(["yes", "no", "yes"])]
    rows[2]["severity_score"] = 2
    ren = hm.compute({"restrictions": rows})["restrictions"]["by_scope"]["renewables_only"]
    assert ren["severe_instruments"] == 2 and ren["severe_where_state_limits_local"] == 1
    assert "sit in a state whose verified siting law limits" in hm.render(hm.compute({"restrictions": rows}))


def test_a_verified_sibling_instrument_lends_its_primary_source_as_a_lead():
    verified = classify.stamp("restrictions", {
        "source_record_id": "REC-7", "state": "KS", "jurisdiction": "Cherokee County", "jurisdiction_type": "County",
        "technology": "wind", "status": "active", "severity_score": 3, "primary_source_url": "https://ck.gov/o.pdf",
        "primary_source_verdict": "confirmed", "primary_source_access": "opened"}, T)
    unverified = classify.stamp("restrictions", mn("wind", "wind", jurisdiction="Cherokee", jurisdiction_type="County",
                                                   state="KS"), T)
    other = classify.stamp("restrictions", mn("solar", "solar", moratorium_id="ks-y", jurisdiction="Cherokee",
                                              jurisdiction_type="County", state="KS"), T)
    assert vw.sibling_sources([verified, unverified, other]) == {"mn:ks-x-2026": ("sabin:REC-7", "https://ck.gov/o.pdf")}
    out = {r["instrument_id"]: r for r in vw.restriction_rows([verified, unverified, other], checked=set(), today=T)}
    assert out["mn:ks-x-2026"]["located_url"] == "https://ck.gov/o.pdf"
    assert "primary source held by sabin:REC-7" in out["mn:ks-x-2026"]["flags"]
    assert out["mn:ks-y"]["located_url"] == "" and "sabin:REC-7" not in out["mn:ks-y"]["flags"]


def test_concerns_come_from_the_text_by_a_fixed_table_with_word_boundaries():
    assert classify.concerns({"description": "Neighbors cited prime farmland, property values and shadow flicker."}) \
        == "farmland;property_value;shadow_flicker"
    # "fired" is not fire_safety and "in view of" is not viewshed; a bare "water" is not a water concern.
    assert classify.concerns({"description": "The board fired its consultant in view of the water treatment plan."}) == ""
    assert classify.concerns({"description": "A thermal runaway fire at the battery site; groundwater wells nearby."}) \
        == "fire_safety;water"
    assert classify.concerns({"description": ""}) == ""
    row = classify.stamp("contested_projects", {"outcome": "pending", "description": "Bats and eagles."})
    assert row["concerns"] == "wildlife"
    assert [n for n, _ in classify.CONCERNS] == sorted({n for n, _ in classify.CONCERNS}, key=[n for n, _ in classify.CONCERNS].index)


def test_co_located_lists_severe_instruments_for_the_same_technology_in_any_county_touched():
    restrictions = [
        {"instrument_id": "mn:a", "county_fips_all": "20001", "technology": "wind", "severity_score": "4",
         "scope": "renewables_only"},
        {"instrument_id": "mn:b", "county_fips_all": "20001", "technology": "solar", "severity_score": "4",
         "scope": "renewables_only"},
        {"instrument_id": "mn:c", "county_fips_all": "20003;20005", "technology": "wind", "severity_score": "2",
         "scope": "renewables_only"},
        {"instrument_id": "mn:d", "county_fips_all": "20005", "technology": "wind", "severity_score": "4",
         "scope": "multi_sector_data_centers"},
        {"instrument_id": "sabin:e", "county_fips_all": "20005", "technology": "wind", "severity_score": "3",
         "scope": "renewables_only"},
    ]
    index = classify.severe_index(restrictions)
    assert classify.co_located({"county_fips_all": "20001;20005", "technology": "wind"}, index) == "mn:a;sabin:e"
    assert classify.co_located({"county_fips_all": "20003", "technology": "wind"}, index) == ""   # severity 2 only
    assert classify.co_located({"county_fips_all": "20005", "technology": "solar"}, index) == ""  # other technology
    assert classify.co_located({"county_fips_all": "", "technology": "wind"}, index) == ""


def test_decided_rate_excludes_young_records_and_reports_confirmed_only_apart():
    def proj(rid, outcome, when, tech="solar", concerns=""):
        return classify.stamp("contested_projects", {"source_record_id": rid, "outcome": outcome,
                                                     "event_date_text": when, "technology": tech,
                                                     "description": concerns})
    rows = [proj("A", "blocked_confirmed", "2024"), proj("B", "blocked_unverified", "2025-03"),
            proj("C", "advanced_confirmed", "2023", "wind"), proj("D", "advanced_unverified", "September 2026"),
            proj("E", "pending", "2024"), proj("F", "needs_review", "2024"),
            proj("G", "blocked_unverified", "2026-10-01", concerns="Noise and farmland.")]
    rows[0]["county_severe_restriction_ids"] = "mn:a"
    c = hm.compute({"contested_projects": rows}, today=T)["contested_projects"]
    d = c["decided"]
    assert d["young_excluded"] == 2 and d["guard_days"] == 90          # D (2026-09-30) and G are younger than 90 days
    assert d["all"] == {"projects": 3, "blocked": 2, "blocked_share": 0.667}
    assert d["confirmed_only"] == {"projects": 2, "blocked": 1, "blocked_share": 0.5}
    assert d["by_technology"]["wind"] == {"projects": 1, "blocked": 0, "blocked_share": 0.0}
    assert c["by_concern"] == {"farmland": 1, "noise": 1} and c["with_no_concern_named"] == 6
    assert c["in_county_with_severe_restriction"] == 1
    text = hm.render(hm.compute({"contested_projects": rows}, today=T))
    assert "| All decided | 3 | 2 | 67% |" in text and "| Confirmed outcomes only | 2 | 1 | 50% |" in text
    assert "absent by construction" in text and "| farmland | 1 |" in text
    empty = hm.compute({"contested_projects": []}, today=T)["contested_projects"]["decided"]
    assert empty["all"]["blocked_share"] is None
