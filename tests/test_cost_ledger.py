"""Cost layer: scripts/cost_ledger.py and scripts/cost_cfo.py on fixtures."""
import json
from datetime import date

import pytest

import cost_cfo as cfo
import cost_ledger as cl


def a(aid, lo, hi, unit="USD", conf="published", tech="", reverify="2027-12-31"):
    out = {"anchor_id": aid, "description": aid, "value_low": lo, "value_high": hi, "unit": unit,
           "source": "fixture", "source_date": "2026-01", "confidence": conf,
           "source_url": "https://example.org/" + aid, "reverify_by": reverify}
    if tech:
        out["technology"] = tech
    return out


def fixture_anchors(**over):
    rows = [
        a("capex_per_mw_solar", 1_000_000, 1_500_000, tech="solar"),
        a("capex_per_mw_wind", 1_800_000, 2_200_000, tech="wind"),
        a("capex_per_mw_battery_storage", 1_200_000, 1_600_000, tech="battery_storage"),
        a("construction_escalation", 0.02, 0.04),
        a("fixed_om_kw_year_solar", 20, 30, tech="solar"),
        a("fixed_om_kw_year_wind", 30, 45, tech="wind"),
        a("fixed_om_kw_year_battery_storage", 20, 30, tech="battery_storage"),
        a("project_life_years", 25, 30),
        a("capacity_factor_solar", 0.22, 0.26, tech="solar"),
        a("capacity_factor_wind", 0.33, 0.40, tech="wind"),
        a("ppa_price_mwh_solar", 50, 60, tech="solar"),
        a("ppa_price_mwh_wind", 60, 70, tech="wind"),
        a("capacity_price_kw_month_battery_storage", 8, 12, tech="battery_storage"),
        a("carrying_rate", 0.06, 0.09, conf="assumption"),
        a("predevelopment_share", 0.03, 0.08, conf="assumption"),
        a("credit_rate", 0.30, 0.40),
    ]
    for aid, change in over.items():
        rows = [{**r, **change} if r["anchor_id"] == aid else r for r in rows]
    return cl.validate_anchors(rows)


AS_OF = date(2026, 11, 5)


def project(**kw):
    base = {"id": "con_1", "project_name": "Fixture Solar", "state": "IA", "county": "Linn County",
            "county_fips": "19113", "technology": "solar", "outcome": "advanced_confirmed",
            "event_date_text": "2021", "resolution_date": "2023-06-15", "capacity_mw": "100",
            "facility_match": "", "facility_capacity_mw": "", "description": "", "long_description": ""}
    return {**base, **kw}


def qmatch(**kw):
    return {"id": "con_1", "match": "strong", "first_request_date": "2021-06-15", "queue_capacity_mw": "120",
            **kw}


def row(p=None, q="default", anchors=None, as_of=AS_OF):
    anchors = anchors or fixture_anchors()
    q = qmatch() if q == "default" else q
    return cl.ledger_row(p or project(), q, anchors, cl.stale_ids(anchors, as_of), as_of)


def test_decided_project_prices_request_to_decision():
    r = row()
    assert r["withheld_reason"] == ""
    assert r["span_kind"] == "request_to_decision"
    assert (r["start_source"], r["end_source"], r["mw_source"]) == ("queue_request", "resolution_date", "record")
    assert r["span_days"] == r["span_days_low"] == r["span_days_high"] == str((date(2023, 6, 15) - date(2021, 6, 15)).days)
    assert (r["capex_low"], r["capex_high"]) == ("100000000", "150000000")
    # Escalation, by hand: capex x rate x months / 12.
    months = 730 / cl.DAYS_PER_MONTH
    assert float(r["escalation_cost_low"]) == pytest.approx(100e6 * 0.02 * months / 12, abs=1)
    assert r["block_sunk_cost_low"] == ""
    total = float(r["escalation_cost_low"]) + float(r["deferral_npv_cost_low"])
    assert float(r["total_economic_cost_low"]) == pytest.approx(total, abs=2)


def test_blocked_project_carries_capital_at_risk_only():
    r = row(project(outcome="blocked_confirmed"))
    assert (r["block_sunk_cost_low"], r["block_sunk_cost_high"]) == ("3000000", "12000000")
    assert r["escalation_cost_low"] == r["deferral_npv_cost_low"] == r["deferred_revenue_exposure_low"] == ""
    assert r["total_economic_cost_low"] == "3000000"


def test_pending_project_accrues_to_the_run_date():
    r = row(project(outcome="pending", resolution_date=""))
    assert r["span_kind"] == "accrued_to_date"
    assert (r["end_date"], r["end_source"]) == ("2026-11-05", "run_date")
    assert "still pending" in r["note"]


def test_month_precision_widens_the_span_in_the_right_direction():
    # A month-precision start can only shorten the span; a month-precision end can only lengthen it.
    r = row(q=qmatch(first_request_date="2021-06"),
            p=project(resolution_date="2023-02"))
    span = (date(2023, 2, 1) - date(2021, 6, 1)).days
    assert r["span_days"] == str(span)
    assert int(r["span_days_low"]) == span - 29
    assert int(r["span_days_high"]) == span + 27
    assert cl.span_range(date(2026, 3, 1), "month", date(2026, 3, 10), "day") == (1, 9)


def test_start_falls_back_to_a_dated_event_and_withholds_a_year():
    r = row(project(event_date_text="2022-03-04"), q=None)
    assert (r["start_source"], r["start_date"]) == ("event_date", "2022-03-04")
    assert row(project(event_date_text="2022"), q=None)["withheld_reason"] == "start_year_precision"
    assert row(project(event_date_text=""), q=None)["withheld_reason"] == "no_start_date"
    assert row(q=qmatch(match="possible"))["withheld_reason"] == "start_from_possible_queue_match"
    conflict = "outcome pending, but every matched queue request was withdrawn"
    assert row(project(outcome="pending"), q=qmatch(conflict=conflict))["withheld_reason"] == "queue_match_conflict"


@pytest.mark.parametrize("kw,reason", [
    ({"technology": "transmission"}, "technology_not_priced"),
    ({"technology": "solar;transmission"}, "technology_not_priced"),
    ({"technology": "wind", "description": "A proposed offshore wind farm"}, "technology_not_priced"),
    ({"outcome": "needs_review"}, "outcome_needs_review"),
    ({"outcome": "blocked_unverified"}, "outcome_unverified"),
    ({"resolution_date": ""}, "no_end_date"),
    ({"resolution_date": "2023"}, "no_end_date"),
    ({"resolution_date": "2020-01-01"}, "nonpositive_span"),
])
def test_withheld_reasons(kw, reason):
    r = row(project(**kw))
    assert r["withheld_reason"] == reason
    assert all(r[c] == "" for c in cl.DOLLAR_COLS)
    assert reason in cl.WITHHELD_REASONS


def test_mw_comes_from_a_stated_source_and_is_never_imputed():
    assert row(project(capacity_mw=""))["mw_source"] == "queue_request"
    r = row(project(capacity_mw="", facility_match="strong", facility_capacity_mw="80"))
    assert (r["capacity_mw"], r["mw_source"]) == ("80", "federal_plant_inventory")
    r = row(project(capacity_mw="", area_acres="900"), q=qmatch(queue_capacity_mw=""))
    assert r["withheld_reason"] == "no_capacity_mw"
    # A possible queue match does not supply MW either.
    assert cl.capacity(project(capacity_mw=""), qmatch(match="possible")) == (None, "")


def test_hybrid_is_priced_on_its_first_technology_and_flagged():
    r = row(project(technology="solar;battery_storage"))
    assert r["priced_technology"] == "solar"
    assert "hybrid_priced_on_primary" in r["review_flags"]
    assert "offshore_wind" in row(project(technology="wind", project_name="Big Offshore Wind"))["review_flags"]


def test_storage_revenue_is_a_capacity_payment():
    anchors = fixture_anchors()
    assert cl.annual_revenue(anchors, "battery_storage", 10) == (10 * 1000 * 8 * 12, 10 * 1000 * 12 * 12)
    lo, hi = cl.annual_revenue(anchors, "solar", 10)
    assert lo == pytest.approx(10 * 0.22 * 8760 * 50)
    assert hi == pytest.approx(10 * 0.26 * 8760 * 60)


def test_deferral_npv_bounds_cover_every_cost_of_capital_corner():
    anchors = fixture_anchors()
    lo, hi = cl.deferral_npv(anchors, "wind", 100, (12, 12))
    assert 0 < lo < hi
    # Higher net revenue and a longer delay cost more.
    assert cl.deferral_npv(anchors, "wind", 100, (24, 24))[1] > hi
    # By hand at one corner: r = 6%, life 30, low O&M, high revenue.
    net = 100 * 0.40 * 8760 * 70 - 100 * 1000 * 30
    value = net * (1 - 1.06 ** -30) / 0.06
    assert hi >= value * (1 - 1.06 ** -1) - 1


def test_stale_anchor_is_flagged_not_fatal():
    anchors = fixture_anchors(capex_per_mw_solar={"reverify_by": "2026-01-01"})
    r = row(anchors=anchors)
    assert r["stale_anchors"] == "capex_per_mw_solar"
    assert "(stale)" in cl.methodology(anchors, [r], {"capex_per_mw_solar"}, AS_OF)


@pytest.mark.parametrize("change,msg", [
    ({"source_url": ""}, "needs a source_url"),
    ({"value_low": 5, "value_high": 1}, "value_low <= value_high"),
    ({"source_date": "2026"}, "YYYY-MM"),
    ({"technology": "nuclear"}, "technology must be"),
])
def test_anchor_validation(change, msg):
    with pytest.raises(cl.AnchorError, match=msg):
        fixture_anchors(capex_per_mw_solar=change)


def test_an_assumption_needs_no_url_but_a_missing_anchor_fails():
    fixture_anchors(carrying_rate={"source_url": ""})
    rows = [x for x in fixture_anchors().values() if x["anchor_id"] != "capacity_factor_wind"]
    with pytest.raises(cl.AnchorError, match="capacity_factor_wind"):
        cl.validate_anchors(rows)


def test_banned_wording_is_caught():
    assert cl.banned_hits({"x": "the projected loss of revenue"})
    assert cl.banned_hits({"x": "a cost attributable to opposition"})
    assert not cl.banned_hits({"x": "deferred revenue exposure, an upper bound"})


def test_rate_card_and_scenarios_scale_with_mw(tmp_path):
    anchors = fixture_anchors()
    one = cfo.slip_costs(anchors, "solar", 1, 6)
    hundred = cfo.slip_costs(anchors, "solar", 100, 6)
    assert hundred["escalation"][0] == pytest.approx(100 * one["escalation"][0])
    assert hundred["deferral"][1] == pytest.approx(100 * one["deferral"][1])
    rate = cfo.rate_card(anchors, set())
    assert [r["technology"] for r in rate] == list(cl.TECHNOLOGIES)
    scen = cfo.scenarios(anchors)
    assert len(scen) == len(cl.TECHNOLOGIES) * len(cfo.SCENARIO_MONTHS)
    sens = cfo.sensitivity(anchors)
    solar = [s for s in sens if s["technology"] == "solar"]
    assert [float(s["swing"]) for s in solar] == sorted((float(s["swing"]) for s in solar), reverse=True)


def test_brief_has_no_banned_wording_and_states_it_is_internal(tmp_path):
    anchors = fixture_anchors()
    deadlines = [{"deadline_id": "d1", "technologies": ["solar", "wind"], "rule": "placed in service by",
                  "date": "2027-12-31", "source": "fixture", "source_url": "https://example.org/d1",
                  "reverify_by": "2027-06-30"}]
    path = tmp_path / "anchors.json"
    path.write_text(json.dumps({"anchors": list(anchors.values()), "credit_deadlines": deadlines}))
    assert cfo.load_deadlines(path) == deadlines
    rate = cfo.rate_card(anchors, set(), cfo.credit_techs(deadlines))
    assert rate[0]["credit_at_deadline_per_mw_low"] == "300000"
    assert rate[2].get("credit_at_deadline_per_mw_low", "") == ""
    text = cfo.brief(anchors, rate, cfo.scenarios(anchors),
                     cfo.sensitivity(anchors), deadlines, [], set(), AS_OF)
    assert "Internal, not for client delivery" in text
    assert not cl.banned_hits({"brief": text})
    bad = [{**deadlines[0], "source_url": ""}]
    path.write_text(json.dumps({"anchors": [], "credit_deadlines": bad}))
    with pytest.raises(cl.AnchorError, match="missing source_url"):
        cfo.load_deadlines(path)
