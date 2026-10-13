"""'Checked, nothing found' results: validated by the build, printed by site
profiles in place of silence, and a worklist of profiled counties still to
check. Synthetic rows only."""
from datetime import date, timedelta

import geo
import negative_checks as nc
import site_profile as sp

GOOD = {"county_fips": "20021", "state": "KS", "county": "Cherokee", "scope": "both",
        "sources_checked": "county code library; commission minutes 2023 to 2026; news search for solar, "
                           "wind and battery storage",
        "checked_on": "2026-10-01", "result": "none_found", "note": "", "reviewer": "test"}


def errors(**kw):
    return nc.validate([{**GOOD, **kw}], geo.known, {"20021": "KS"}.get)


def test_a_complete_check_passes_and_each_rule_is_enforced():
    assert errors() == []
    assert "not a 2024 county" in errors(county_fips="99999")[0]
    assert "does not match county" in errors(state="MO")[0]
    assert "scope" in errors(scope="everything")[0]
    assert "at least one source" in errors(sources_checked=" ; ")[0]
    assert "YYYY-MM-DD" in errors(checked_on="Oct 2026")[0]
    assert "in the future" in errors(checked_on=(date.today() + timedelta(days=3)).isoformat())[0]
    assert "none_found" in errors(result="found")[0]


def test_the_worklist_lists_unchecked_unrestricted_counties_newest_first():
    requests = [{"county_fips": "20021", "date": "2026-09-01"}, {"county_fips": "21181", "date": "2026-10-02"},
                {"county_fips": "19113", "date": "2026-10-05"}, {"county_fips": "20037", "date": "2026-08-01"},
                {"county_fips": "20021", "date": "2026-10-03"}]
    checks = [{**GOOD, "county_fips": "20037", "scope": "restrictions"},
              {**GOOD, "county_fips": "21181", "scope": "projects"}]   # projects only: still to check
    today = date(2026, 10, 13)
    out = nc.worklist(requests, checks, {"19113"}, lambda f: f"name {f}", lambda f: "ST", today)
    assert [(r["county_fips"], r["last_requested"], r["requests"]) for r in out] == [
        ("20021", "2026-10-03", 2), ("21181", "2026-10-02", 1)]
    assert {r["reason"] for r in out} == {"no check on record"} and list(out[0]) == nc.WORKLIST_FIELDS
    # A stale check puts the county back on the list, saying so; a fresh one keeps it off.
    stale = [{**GOOD, "county_fips": "20021", "scope": "both", "checked_on": "2025-01-01"}]
    (row,) = nc.worklist(requests[:1], stale, set(), lambda f: "", lambda f: "KS", today)
    assert row["reason"] == f"check of 2025-01-01 is stale (more than {nc.STALE_DAYS} days old)"
    assert nc.worklist(requests[:1], [{**GOOD, "county_fips": "20021", "scope": "both"}], set(),
                       lambda f: "", lambda f: "KS", today) == []


def synthetic(checks):
    d = sp.Data(local=False)
    d.restrictions, d.projects, d.cases, d.queue = [], [], [], []
    d.held, d.gaps, d.candidates, d.quarantine, d.dc_events = [], [], [], [], []
    d.checks = checks
    return d


def test_an_empty_county_prints_what_was_checked_and_flags_a_stale_check():
    fresh = {**GOOD, "checked_on": date.today().isoformat()}
    text = sp.render(sp.profile(synthetic({"20021": [fresh]}), "20021", "Cherokee", "KS"))
    assert f"- Restrictions: Checked county code library; commission minutes 2023 to 2026; news search " \
           f"for solar, wind and battery storage on {fresh['checked_on']}: none found" in text
    assert "- Projects: Checked" in text and "Nothing published for this county" not in text
    old = {**GOOD, "checked_on": "2024-01-01", "scope": "restrictions"}
    p = sp.profile(synthetic({"20021": [old]}), "20021", "Cherokee", "KS")
    text = sp.render(p)
    assert "on 2024-01-01: none found (stale: more than 12 months old)" in text
    assert "- Projects:" not in text and any("stale" in f for f in p["flags"])
    neighbor = sp.render(sp.profile(synthetic({"20037": [fresh]}), "20021", "Cherokee", "KS"))
    assert "Crawford (20037), nothing published: Checked" in neighbor
    assert "Nothing published for this county." in sp.render(sp.profile(synthetic({}), "20021", "Cherokee", "KS"))


def test_profiles_record_the_county_and_date_only(monkeypatch, tmp_path):
    path = tmp_path / "profile_requests.csv"
    monkeypatch.setattr(sp, "PROFILE_REQUESTS", path)
    sp.record_request("20021", today="2026-10-09")
    sp.record_request("20021", today="2026-10-09")      # once per county per day
    sp.record_request("21181", today="2026-10-09")
    assert path.read_text(encoding="utf-8") == "county_fips,date\n20021,2026-10-09\n21181,2026-10-09\n"
    assert sp.main(["--fips", "19113", "--no-local"]) == 0
    assert path.read_text(encoding="utf-8").splitlines()[-1] == f"19113,{date.today().isoformat()}"


def test_the_committed_files_have_their_columns():
    from common import read_csv
    header = nc.CHECKS_PATH.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header == nc.CHECK_FIELDS
    assert nc.validate(read_csv(nc.CHECKS_PATH), geo.known) == []
    assert nc.REQUESTS_PATH.read_text(encoding="utf-8").splitlines()[0] == "county_fips,date"


def test_a_check_is_graded_by_independence_classes_not_by_source_count():
    today = date(2026, 10, 13)
    assert nc.independence_classes(GOOD) == ["primary_law", "proceeding", "secondary"]
    assert nc.grade(GOOD, today) == "A"
    # Three news searches are one class: they can all be wrong together.
    news = {**GOOD, "sources_checked": "Google News search; local newspaper archive; Moratorium Nation tracker"}
    assert nc.independence_classes(news) == ["secondary"] and nc.grade(news, today) == "B"
    assert nc.grade({**news, "checked_on": "2025-01-01"}, today) == "C"
    assert nc.grade({**GOOD, "checked_on": "2025-01-01"}, today) == "B"
    assert nc.grade({**GOOD, "sources_checked": ""}, today) == "U"
    assert nc.family_of("county code library") == "primary_law"
    assert nc.family_of("commission minutes 2023 to 2026") == "proceeding"
    assert nc.family_of("state PSC dockets") == "proceeding"
    assert nc.family_of("news search for solar") == "secondary"
    assert all(g in nc.GRADE_MEANING for g in nc.GRADES)


def test_the_county_summary_and_profile_carry_the_grade():
    import county_summary
    rows = county_summary.build({}, [], [GOOD], ["20021", "20023"], lambda f: "X", lambda f: "KS")
    by = {r["county_fips"]: r for r in rows}
    assert by["20021"]["coverage"] == "negative_check" and by["20021"]["negative_check_grade"] == "A"
    assert by["20023"]["negative_check_grade"] == "" and list(rows[0]) == county_summary.FIELDS
    assert "Evidence grade A (primary_law, proceeding, secondary)" in sp.checked_line(GOOD)


def test_a_source_s_kind_decides_its_class_and_a_web_search_is_never_law():
    assert nc.family_of("code: Alton Zoning Ordinance searched for solar (https://example.org)") == "primary_law"
    assert nc.family_of("minutes: board of commissioners 2023 to 2026") == "proceeding"
    assert nc.family_of("docket: Siting Council, Fairfield") == "proceeding"
    # The words of the query do not make a search the instrument.
    assert nc.family_of("web search: Nicholas County ordinance moratorium minutes") == "secondary"
    assert nc.family_of("news search: solar moratorium") == "secondary"


def test_a_drafted_check_is_held_until_someone_else_reviews_it():
    new = {**GOOD, "checked_on": nc.PROTOCOL_START, "governments_checked": "Cherokee County",
           "drafted_by": "agent:checker-1", "reviewer": ""}
    assert errors(**{k: new[k] for k in ("checked_on", "governments_checked", "drafted_by", "reviewer")}) == []
    assert nc.held(new) and nc.counted([new]) == []
    reviewed = {**new, "reviewer": "agent:reviewer-1"}
    assert not nc.held(reviewed) and nc.counted([reviewed]) == [reviewed]
    # Rows from before the protocol have no drafter and count as they did.
    assert nc.counted([GOOD]) == [GOOD]
    assert "reviewer is the drafter" in errors(checked_on=nc.PROTOCOL_START, governments_checked="x",
                                               drafted_by="agent:checker-1", reviewer="Agent:Checker-1")[0]
    missing = errors(checked_on=nc.PROTOCOL_START, reviewer="agent:reviewer-1")
    assert any("drafted_by is required" in e for e in missing)
    assert any("governments_checked is required" in e for e in missing)


def test_a_check_is_due_again_a_year_after_it_ran():
    assert nc.recheck_by({"checked_on": "2026-10-13"}) == "2027-10-13"
    assert nc.recheck_by({"checked_on": "soon"}) == ""
