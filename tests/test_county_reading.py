"""The county report's readings, after pricephillips/data-center-map's way of
reading a county without its model: reference groups (county_benchmarks.py),
the adjacency ladder (adjacency_scan.py), comparable decided projects and
activity nearby (site_screener.py). Synthetic data in a temporary tree; only
the 2024 county geometry is real."""
import csv
import json
from datetime import date

import adjacency_worklist
import county_summary
import headline_metrics as hm
import pytest
import site_profile as sp

HOME, NEXT, FAR = "20001", "20011", "20021"   # Allen KS; Bourbon KS borders it; Cherokee KS does not
LOOKUP = {"allen county|kansas": HOME, "allen|kansas": HOME, "bourbon county|kansas": NEXT,
          "bourbon|kansas": NEXT, "cherokee county|kansas": FAR, "cherokee|kansas": FAR}
TODAY = date.today()


def iso(months_ago: int) -> str:
    return sp.months_before(TODAY, months_ago).isoformat()


def restriction(id_, fips, **kw):
    r = {"id": id_, "instrument_id": f"syn:{id_}", "state": "KS", "technology": "wind", "jurisdiction": "Synthetic",
         "jurisdiction_type": "County", "restriction_type": "setback", "severity_score": "3",
         "severity_basis": "wind setback 3000 ft", "status": "active", "description": "Synthetic.",
         "evidence_level": "primary_source", "verification": "verified", "scope": "renewables_only",
         "source_url": "https://example.gov/o.pdf", "county_fips_all": fips, "county_fips_method": "name",
         "date_enacted_iso": "", "state_limits_local": "no"}
    r.update(kw)
    return r


def project(id_, fips, outcome, **kw):
    r = {"id": id_, "instrument_id": f"syn:{id_}", "source_record_id": id_, "state": "KS", "project_name": id_,
         "technology": "solar", "county": "Bourbon", "outcome": outcome, "severity_score": "4",
         "has_litigation": "no", "finality_evidence": "outcome_label_only", "evidence_level": "report_citation",
         "verification": "unverified", "description": "Synthetic.", "source_url": "https://report.example.org/r.pdf",
         "county_fips_all": fips, "county_fips_method": "name", "event_date_text": "2024", "resolution_date": "",
         "opposition_type": "local_residents", "concerns": "noise"}
    r.update(kw)
    return r


def _write(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def summary_rows():
    base = {k: 0 for k in county_summary.FIELDS}
    return [{**base, "county_fips": HOME, "state": "KS", "county": "Allen", "coverage": "record",
             "restrictions_renewables": 1, "restrictions_renewables_severe": 1, "restrictions_renewables_verified": 1},
            {**base, "county_fips": NEXT, "state": "KS", "county": "Bourbon", "coverage": "record",
             "restrictions_renewables": 1, "contested_projects": 2},
            {**base, "county_fips": FAR, "state": "KS", "county": "Cherokee", "coverage": "none"},
            {**base, "county_fips": "29097", "state": "MO", "county": "Jasper", "coverage": "negative_check"}]


@pytest.fixture
def tree(tmp_path):
    data = tmp_path / "data"
    _write(data / "processed" / "restrictions.csv", [
        restriction("r_home", HOME),
        restriction("r_next_new", NEXT, date_enacted_iso=iso(3)),            # enacted within the window
        restriction("r_far_old", FAR, date_enacted_iso="2019-05-01"),        # not adjacent
        restriction("r_shared", f"{HOME};{NEXT}", id="r_shared"),            # shared: never diffusion
    ])
    _write(data / "processed" / "contested_projects.csv", [
        project("p_home_pending", HOME, "pending"),
        project("p_next_blocked", NEXT, "blocked_confirmed", finality_evidence="court_ruling: x",
                verification="verified", evidence_level="confirmed", resolution_date="2024-03-01"),
        project("p_far_advanced", FAR, "advanced_unverified", event_date_text="2023"),
        project("p_far_fresh", FAR, "blocked_unverified", event_date_text=TODAY.isoformat()),
        project("p_tx_blocked", "48201", "blocked_confirmed", state="TX", county="Harris"),  # another state, far away
        project("p_home_decided", HOME, "advanced_confirmed", event_date_text="2022"),
    ])
    _write(data / "processed" / "cases.csv", [], ["id", "state", "source_record_id"])
    _write(data / "processed" / "county_summary.csv", summary_rows(), county_summary.FIELDS)
    _write(data / "review" / "adjacency_worklist.csv", [{
        "county_fips": HOME, "state": "KS", "county": "Allen", "trigger_instrument_id": "syn:r_next_new",
        "trigger_jurisdiction": "Synthetic", "trigger_state": "KS", "trigger_type": "setback",
        "trigger_status": "active", "trigger_date": iso(3), "trigger_technologies": "wind",
        "suggested_query": '"Allen County" Kansas wind ordinance'}], adjacency_worklist.FIELDS)
    (data / "county_fips_lookup.json").write_text(json.dumps(LOOKUP), encoding="utf-8")
    return tmp_path


def run(tree, fips=HOME, **kw):
    d = sp.Data(local=False, root=tree)
    f, name, st = sp.resolve(d, fips=fips)
    return sp.profile(d, f, name, st, **kw)


def section(text, heading):
    return text.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]


def test_the_window_matches_the_neighbor_watch():
    assert sp.ADJACENCY_WINDOW_MONTHS == adjacency_worklist.WINDOW_MONTHS
    assert sp.months_before(date(2026, 3, 31), 1) == adjacency_worklist.months_before(date(2026, 3, 31), 1)


def test_reference_groups_count_counties_never_rates(tree):
    p = run(tree)
    c = p["readings"]["comparison"]
    assert c["national"] == {"counties": 4, "any_instrument": 2, "severe": 1, "verified": 1, "projects": 1,
                             "examined": 3}
    assert c["state"]["counties"] == 3 and c["state"]["examined"] == 2
    text = sp.render(p)
    body = section(text, "How this county compares")
    assert "| All counties | 4 | 2 | 1 | 1 | 1 | 3 |" in body
    assert "| KS counties | 3 | 2 | 1 | 1 | 1 | 2 |" in body
    assert "| This county | 1 | yes | yes | yes | no | yes |" in body
    assert "as do 1 of 3 counties in KS and 1 of 4 nationally (counties, not rates)" in body
    assert "%" not in body
    unexamined = sp.render(run(tree, fips=FAR))
    assert "unexamined, which is an inference from silence, not a finding" in section(unexamined, "How this county compares")


def test_diffusion_tier_one_needs_a_recent_neighbor_and_something_unresolved(tree):
    p = run(tree)
    g = p["readings"]["diffusion"]
    # Bourbon has one instrument of its own, enacted recently; the one shared with Allen is not counted.
    assert [r["fips"] for r in g["neighbors"]] == [NEXT]
    assert g["neighbors"][0]["instruments"] == 1 and g["neighbors"][0]["within_window"]
    assert g["recent"] == 1 and g["tier"] == 3 and not g["unresolved_here"]   # nothing unresolved at home
    assert g["worklist"][0]["suggested_query"].startswith('"Allen County"')
    text = sp.render(p)
    body = section(text, "Diffusion from adjacent counties")
    assert "| Bourbon, KS (20011) | 1 |" in body and "| yes |" in body
    assert "Tier 3: a neighbor enacted within the window and this county has nothing unresolved" in body
    assert "This county is on the neighbor watch" in body and "Suggested search:" in body
    assert "Diffusion reading: tier 3," in section(text, "Summary")


def test_diffusion_tiers_move_with_the_evidence(tree):
    d = sp.Data(local=False, root=tree)
    d.restrictions[0]["verification"] = "located"            # the home instrument is not yet read
    p = sp.profile(d, HOME, "Allen", "KS")
    assert p["readings"]["diffusion"]["tier"] == 1
    next(r for r in d.restrictions if r["id"] == "r_next_new")["date_enacted_iso"] = "2015-01-01"   # no recent trigger
    assert sp.profile(d, HOME, "Allen", "KS")["readings"]["diffusion"]["tier"] == 4
    d.restrictions = [r for r in d.restrictions if HOME in sp.fips_set(r)]
    g = sp.profile(d, HOME, "Allen", "KS")["readings"]["diffusion"]
    assert g["tier"] == 0 and g["reading"].startswith("no adjacent county")
    # three restricting neighbours make a cluster whatever their dates
    d = sp.Data(local=False, root=tree)
    import geo
    d.restrictions = [restriction(f"r_{nb}", nb, date_enacted_iso="2015-01-01") for nb in geo.neighbors(HOME)[:3]]
    assert sp.profile(d, HOME, "Allen", "KS")["readings"]["diffusion"]["tier"] == 2


def test_comparables_are_decided_in_state_or_nearby_and_never_the_countys_own(tree):
    p = run(tree)
    c = p["readings"]["comparables"]
    ids = [r["id"] for r in c["projects"]]
    assert "p_next_blocked" in ids and "p_far_advanced" in ids and "p_far_fresh" in ids
    assert "p_home_decided" not in ids and "p_home_pending" not in ids       # the county's own; not decided
    assert "p_tx_blocked" not in ids                                         # another state, too far
    assert ids[0] == "p_next_blocked"                                        # nearest first
    assert c["found"] == 3
    rate = c["state_rate"]
    assert rate["guard_days"] == hm.YOUNG_DAYS and rate["young_excluded"] == 1   # p_far_fresh is younger than the guard
    assert rate["all"] == {"projects": 3, "blocked": 1, "blocked_share": 0.333}
    assert rate["confirmed_only"] == {"projects": 2, "blocked": 1, "blocked_share": 0.5}
    text = sp.render(p)
    body = section(text, "Comparable decided projects")
    assert "| p_next_blocked | Bourbon, KS | solar | blocked_confirmed; finality court_ruling | local_residents | noise |" in body
    assert "Decided projects recorded in KS" in body and "3, of which 1 were blocked (33%)" in body
    assert "1 younger decision(s) left out" in body
    assert "Comparable decided projects within 100 miles or in KS: 3." in section(text, "Summary")


def test_recent_activity_counts_by_window_and_places_records_at_the_centroid(tree):
    p = run(tree)
    a = p["readings"]["recent_activity"]
    assert a["available"] and a["radius_mi"] == 25 and a["context_radius_mi"] == 50
    windows = {w["label"]: (w["restrictions"], w["projects"]) for w in a["windows"]}
    # Allen (distance zero): two undated instruments, projects dated 2024 and 2022. Bourbon's centroid is
    # 24.8 miles away: one instrument enacted three months ago and a project decided 2024-03-01.
    assert windows["undated"] == (2, 0) and windows["the last 12 months"] == (1, 0)
    assert windows["12 to 24 months ago"] == (0, 1) and windows["older"] == (0, 2)
    assert a["within_radius"] == 6 and a["within_context"] >= 6
    assert a["newest"][0]["label"] == "Synthetic" and a["newest"][0]["kind"] == "restriction"
    text = sp.render(p)
    body = section(text, "Activity nearby in the last two years")
    assert "| Total within 25 miles | 3 | 3 |" in body and "Newest dated records within the radius:" in body
    assert "weighted" in body and "centroid" in body


def test_the_readings_define_their_terms_and_the_sources_carry_the_limits(tree):
    text = sp.render(run(tree))
    cfg = sp.load_report_config()
    for key in ("reference_group", "diffusion_reading", "comparable_decided_project"):
        assert text.count(f"({cfg['terms'][key]['definition']})") == 1, key
    tail = section(text, "Sources and method")
    assert "Standing limits." in tail and cfg["notices"]["selection"] in tail and cfg["notices"]["limits"] in tail
    assert "state limits local rules: no" in section(text, "Restrictions on record")
    assert "—" not in text and "%" not in section(text, "Summary")
