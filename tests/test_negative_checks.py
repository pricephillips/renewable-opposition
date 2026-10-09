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
    out = nc.worklist(requests, checks, {"19113"}, lambda f: f"name {f}", lambda f: "ST")
    assert [(r["county_fips"], r["last_requested"], r["requests"]) for r in out] == [
        ("20021", "2026-10-03", 2), ("21181", "2026-10-02", 1)]


def synthetic(checks):
    d = sp.Data(local=False)
    d.restrictions, d.projects, d.cases, d.queue = [], [], [], []
    d.held, d.gaps, d.candidates, d.quarantine = [], [], [], []
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
