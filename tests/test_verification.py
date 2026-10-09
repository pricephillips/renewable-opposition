"""The evidence standard as a derived field (classify.verification), counted by
instrument in the headline metrics and printed in plain words by site
profiles. Synthetic rows only."""
import classify
import headline_metrics as hm
import site_profile as sp


def res(**kw):
    row = {"id": "res_x", "state": "KS", "technology": "wind", "description": "Synthetic county wind rules.",
           "source_url": "https://example.org/tracker", "jurisdiction": "Synthetic County",
           "jurisdiction_type": "County", "restriction_type": "setback", "severity_score": "2", **kw}
    return classify.stamp("restrictions", row)


def test_a_restriction_is_verified_only_against_an_instrument_that_was_read():
    assert res(primary_source_url="https://example.gov/ord.pdf", primary_source_access="opened",
               primary_source_verdict="confirmed")["verification"] == "verified"
    assert res(primary_source_url="https://example.gov/ord.pdf", primary_source_access="archived",
               primary_source_verdict="confirmed")["verification"] == "verified"
    assert res(primary_source_url="https://example.gov/ord.pdf",
               primary_source_access="snippet")["verification"] == "located"
    # A news article or tracker locates an instrument; it never verifies it.
    assert res()["verification"] == "unverified"
    assert res(moratorium_id="ks-x-2026")["verification"] == "unverified"


def proj(**kw):
    row = {"id": "con_x", "state": "KS", "project_name": "Synthetic Solar", "technology": "solar",
           "outcome": "blocked_unverified", "finality_evidence": "outcome_label_only", **kw}
    return classify.stamp("contested_projects", row)


def test_a_project_is_verified_by_a_news_article_or_court_record_that_was_read():
    assert proj()["verification"] == "unverified"
    assert proj(resolution_url="https://news.example.com/a", resolution_access="opened")["verification"] == "verified"
    assert proj(resolution_url="https://news.example.com/a", resolution_access="snippet")["verification"] == "unverified"
    assert proj(finality_evidence="court_ruling: X v. Y")["verification"] == "verified"
    assert proj(source_kind="news", source_access="opened")["verification"] == "verified"
    assert proj(source_kind="tracker", source_access="opened")["verification"] == "unverified"


def test_cases_need_a_court_record():
    assert classify.stamp("cases", {"id": "cas_x", "case_source_url": "https://court.example.gov/d"}
                          )["verification"] == "verified"
    assert classify.stamp("cases", {"id": "cas_y"})["verification"] == "unverified"


def test_headline_metrics_count_verification_by_instrument():
    rows = [res(id="a", moratorium_id="m1", technology="solar", scope="renewables_only"),
            res(id="b", moratorium_id="m1", technology="wind"),
            res(id="c", source_record_id="s1", primary_source_url="https://example.gov/o.pdf",
                primary_source_access="opened", primary_source_verdict="confirmed"),
            res(id="d", source_record_id="s2", primary_source_url="https://example.gov/o2.pdf",
                primary_source_access="snippet")]
    m = hm.compute({"restrictions": rows, "contested_projects": [proj()], "cases": []})
    ren = m["restrictions"]["by_scope"]["renewables_only"]
    assert ren["by_verification"] == {"located": 1, "unverified": 1, "verified": 1}
    assert m["contested_projects"]["by_verification"] == {"unverified": 1}
    text = hm.render(m)
    assert "| Verification: verified | 1 |" in text and "—" not in text


def synthetic_data(rows):
    d = sp.Data(local=False)
    d.restrictions, d.projects, d.cases, d.queue = rows, [], [], []
    d.held, d.gaps, d.candidates, d.quarantine = [], [], [], []
    return d


def placed(fips, **kw):
    r = res(county_fips_all=fips, **kw)
    return {k: "" if v is None else str(v) for k, v in r.items()}


def test_profiles_print_verification_and_verified_only_counts_what_it_left_out():
    here_ok = placed("20021", id="r1", moratorium_id="m1", primary_source_url="https://example.gov/o.pdf",
                     primary_source_access="opened", primary_source_verdict="confirmed")
    here_located = placed("20021", id="r2", moratorium_id="m2", primary_source_url="https://example.gov/p.pdf",
                          primary_source_access="snippet")
    next_door = placed("20037", id="r3", moratorium_id="m3")   # Crawford, KS borders Cherokee
    d = synthetic_data([here_ok, here_located, next_door])
    text = sp.render(sp.profile(d, "20021", "Cherokee", "KS"))
    assert "verified against the instrument or the minutes that adopted it" in text
    assert "instrument located but not yet read, so not verified" in text
    assert "not verified: no instrument or minutes read" in text
    p = sp.profile(d, "20021", "Cherokee", "KS", verified_only=True)
    assert [r["id"] for r in p["in_county"]["restrictions"]] == ["r1"]
    assert p["adjacent"] == {}
    assert p["left_out"] == {"located": 1, "unverified": 1}
    assert "Verified only: 2 restriction instrument(s)" in sp.render(p)
