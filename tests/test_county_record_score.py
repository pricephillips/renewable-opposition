"""County record score (scripts/county_record_score.py) on the committed rubric."""
import json

import pytest

import county_record_score as rs
from common import ROOT

CFG = json.loads((ROOT / "config" / "county_record_score.json").read_text(encoding="utf-8"))
NO_ZONING = {**CFG, "zoning_transition": {**CFG["zoning_transition"], "counties": []}}


def _r(iid, fips, sev=2, rtype="setback", currency="in_force", tech="solar", jtype="County", verified=True):
    return {"instrument_id": iid, "county_fips_all": fips, "severity_score": str(sev), "restriction_type": rtype,
            "currency": currency, "technology": tech, "jurisdiction_type": jtype, "jurisdiction": iid,
            "verification": "verified" if verified else "unverified"}


def _p(fips, outcome):
    return {"county_fips_all": fips, "outcome": outcome}


def _summary(*fips, coverage="record"):
    return [{"county_fips": f, "state": "KS", "county": f"C{f}", "coverage": coverage} for f in fips]


def _profile(scores):
    return [{"county_fips": f, rs.PROFILE_COLUMN: str(v)} for f, v in scores.items()]


def _build(restrictions=(), projects=(), summary=(), profile=None, cfg=NO_ZONING, as_of="2026-10-21"):
    summary = list(summary)
    profile = profile or {s["county_fips"]: 0.2 for s in summary}
    return {r["county_fips"]: r for r in rs.build(list(restrictions), list(projects), summary,
                                                   _profile(profile), cfg, as_of)}


def test_the_case_study_pattern_ranks_moratoria_above_approvals():
    """Nicholas-like (two moratoria and a 2,000-foot setback), Cherokee-like (a
    three-technology moratorium and a severe wind setback), Linn-like (a
    severity 2 ordinance and two confirmed approvals) and Harris-like (a
    severity 3 city rule, one blocked and two approved projects)."""
    restrictions = [
        _r("n1", "N", 4, "moratorium"), _r("n2", "N", 4, "moratorium", tech="wind"), _r("n3", "N", 3),
        *[_r("c1", "C", 4, "moratorium", tech=t) for t in ("solar", "wind", "battery_storage")],
        _r("c2", "C", 3, tech="wind"),
        _r("l1", "L", 2), _r("l1", "L", 2, tech="battery_storage"), _r("l2", "L", 2, currency="unknown", tech="wind"),
        _r("h1", "H", 3, tech="battery_storage", jtype="City"),
    ]
    projects = [_p("L", "advanced_confirmed"), _p("L", "advanced_confirmed"), _p("N", "pending"),
                _p("H", "blocked_unverified"), _p("H", "advanced_unverified"), _p("H", "advanced_unverified")]
    out = _build(restrictions, projects, _summary("N", "C", "L", "H"),
                 profile={"N": 0.05, "C": 0.13, "L": 0.40, "H": 0.36})
    assert min(out["C"]["combined"], out["N"]["combined"]) > out["H"]["combined"] > out["L"]["combined"]
    assert [out[f]["tier"] for f in "NCHL"] == ["closed", "closed", "restrictive", "regulated"]


def test_currency_jurisdiction_and_breadth_scale_an_instrument():
    out = _build([_r("a", "A", 3), _r("b", "B", 3, jtype="Township"), _r("c", "C", 3, currency="unknown"),
                  _r("d", "D", 3, currency="pending"), _r("e", "E", 3), _r("e", "E", 3, tech="wind")],
                 summary=_summary(*"ABCDE"))
    assert [out[f]["record_points"] for f in "ABCDE"] == [30, 15, 25.5, 9, 33]


def test_the_largest_instrument_counts_in_full_and_the_rest_at_a_quarter():
    out = _build([_r("a", "A", 3), _r("b", "A", 2), _r("c", "A", 2)], summary=_summary("A"))
    assert out["A"]["record_points"] == 30 + 0.25 * 24


def test_approvals_take_off_at_most_half_and_never_undercut_a_moratorium():
    out = _build([_r("a", "A", 2), _r("b", "B", 4, "moratorium")],
                 [_p("A", "advanced_confirmed")] * 3 + [_p("B", "advanced_confirmed")] * 3,
                 summary=_summary("A", "B"))
    assert out["A"]["record_points"] == 6 and out["A"]["approval_credit"] == 6
    assert out["B"]["record_points"] == 40 and out["B"]["approval_credit"] == 0


def test_blocked_projects_alone_put_a_county_on_the_scale():
    out = _build(projects=[_p("A", "blocked_confirmed"), _p("A", "blocked_unverified")], summary=_summary("A"))
    assert out["A"]["record_points"] == 15 and out["A"]["tier"] == "restrictive"


def test_a_kansas_county_moving_to_zoning_counts_as_a_severe_instrument():
    entry = {"county_fips": "Z", "state": "KS", "county": "Zed", "status": "drafting_first_code",
             "adopted_on": "", "technologies": ["solar", "wind"]}
    cfg = {**CFG, "zoning_transition": {**CFG["zoning_transition"], "counties": [entry]}}
    out = _build(summary=_summary("Z"), cfg=cfg)
    assert out["Z"]["zoning_points"] == 33 and out["Z"]["tier"] == "severe"
    adopted = {**entry, "adopted_on": "2022-03-01"}
    cfg["zoning_transition"]["counties"] = [adopted]
    assert _build(summary=_summary("Z"), cfg=cfg, as_of="2025-03-01")["Z"]["zoning_points"] == 33
    assert _build(summary=_summary("Z"), cfg=cfg, as_of="2025-03-02")["Z"]["basis"] == "profile_only"
    cfg["zoning_transition"]["counties"] = [{**entry, "state": "IL"}]
    with pytest.raises(ValueError):
        _build(summary=_summary("Z"), cfg=cfg)


def test_a_zoning_transition_counts_as_verified_only_after_a_confirmed_second_reading():
    entry = {"county_fips": "Z", "state": "KS", "county": "Zed", "status": "drafting_first_code",
             "adopted_on": "", "technologies": ["wind"]}
    def weight(e):
        cfg = {**CFG, "zoning_transition": {**CFG["zoning_transition"], "counties": [e]}}
        return _build(summary=_summary("Z"), cfg=cfg)["Z"]["evidence_weight"]
    assert weight(entry) == CFG["evidence_weight"]["unverified_record"]
    assert weight({**entry, "second_reading": {"verdict": "contradicts"}}) == CFG["evidence_weight"]["unverified_record"]
    assert weight({**entry, "second_reading": {"verdict": "confirmed"}}) == CFG["evidence_weight"]["verified_record"]


def test_a_county_with_no_record_takes_its_resemblance_decile_prior():
    fips = [f"{i:02d}" for i in range(20)]
    restrictions = [_r("a", "19", 4, "moratorium")]
    out = _build(restrictions, summary=_summary(*fips[:19], coverage="none") + _summary("19"),
                 profile={f: i / 100 for i, f in enumerate(fips)})
    # 18 and 19 share the top decile; 19's 40 points average to 20 over the two.
    assert out["18"]["basis"] == "profile_only" and out["18"]["tier"] == "no_record"
    assert out["18"]["combined"] == 20 and out["00"]["combined"] == 0
    assert out["19"]["combined"] == 40


def test_unverified_records_lean_on_the_prior():
    out = _build([_r("a", "A", 3, verified=False), _r("b", "B", 3)], summary=_summary("A", "B"),
                 profile={"A": 0.5, "B": 0.5})
    # Both in one decile with a mean of 30: A = 0.75 x 30 + 0.25 x 30.
    assert out["A"]["evidence_weight"] == 0.75 and out["B"]["evidence_weight"] == 1.0
    assert out["A"]["combined"] == out["B"]["combined"] == 30


def test_the_rubric_is_complete():
    assert set(CFG["instruments"]["severity_points"]) == {"1", "2", "3", "4"}
    assert [t["min"] for t in CFG["tiers"]] == sorted((t["min"] for t in CFG["tiers"]), reverse=True)
    for c in CFG["zoning_transition"]["counties"]:
        assert c["state"] in CFG["zoning_transition"]["states"] and c["sources"]


def test_the_zoning_rules_follow_the_county_zoning_survey():
    survey = json.loads((ROOT / "config" / "county_zoning_authority.json").read_text(encoding="utf-8"))["states"]
    assert len(survey) == 50
    assert set(CFG["zoning_transition"]["states"]) == {s for s, e in survey.items() if e["zoning_transition"]}
    for s in CFG["zoning_transition"]["states"]:
        assert survey[s]["may_counties_remain_unzoned"] is True and survey[s]["county_zoning_power"] == "optional"
    for s in CFG["no_county_zoning"]["states"]:
        assert survey[s]["county_zoning_power"] in {"limited", "none"}
    for e in survey.values():
        assert e["citations"] and (e["zoning_transition"] or e["zoning_transition_excluded_because"])


def _plant(fips, year, mw=50, tech="solar", status="operating", source="eia860m"):
    return {"county_fips": fips, "year": str(year), "capacity_mw": str(mw), "technology": tech,
            "status": status, "source": source}


def test_plants_built_after_the_latest_rule_count_as_uncontested_approvals():
    restrictions = [{**_r("a", "A", 2), "date_enacted_iso": "2022-05-01"}]
    facilities = [_plant("A", 2021), _plant("A", 2023), _plant("A", 2024, tech="battery_storage;solar"),
                  _plant("A", 2025, mw=5), _plant("A", 2025, source="uspvdb"), _plant("A", 2026, tech="geothermal")]
    out = {r["county_fips"]: r for r in rs.build(restrictions, [], _summary("A"), _profile({"A": 0.2}), NO_ZONING,
                                                  "2026-10-21", facilities)}
    # Two plants qualify (2023, 2024): 6 points, capped at half of 12.
    assert out["A"]["plants_built"] == 2 and out["A"]["record_points"] == 6


def test_contested_approvals_are_assumed_to_be_among_the_plants():
    facilities = [_plant("A", 2024), _plant("A", 2025)]
    out = {r["county_fips"]: r for r in rs.build([_r("a", "A", 3)], [_p("A", "advanced_confirmed")], _summary("A"),
                                                  _profile({"A": 0.2}), NO_ZONING, "2026-10-21", facilities)}
    assert out["A"]["plants_built"] == 1 and out["A"]["approval_credit"] == 13


def test_build_out_alone_puts_a_county_on_evidence():
    fips = [f"{i:02d}" for i in range(20)]
    profile = {f: i / 100 for i, f in enumerate(fips)}
    out = {r["county_fips"]: r for r in rs.build([_r("m", "19", 4, "moratorium")], [],
                                                  _summary(*fips[:19], coverage="none") + _summary("19"),
                                                  _profile(profile), NO_ZONING, "2026-10-21",
                                                  [_plant("18", 2024)])}
    # 18 and 19 share the top decile, with a mean of 20 points; build-out
    # weighs 18's own record (0 points) at 0.6 against that prior.
    assert out["18"]["basis"] == "build_out" and out["18"]["combined"] == 8
    assert out["17"]["basis"] == "profile_only"


def test_a_county_that_cannot_zone_is_not_scored_on_its_profile_alone():
    fips = [f"{i:02d}" for i in range(20)]
    summary = [{"county_fips": f, "state": "TX" if f == "18" else "OK", "county": f, "coverage": "none"} for f in fips]
    summary[19]["coverage"] = "record"
    out = {r["county_fips"]: r for r in rs.build([_r("m", "19", 4, "moratorium")], [], summary,
                                                  _profile({f: i / 100 for i, f in enumerate(fips)}), NO_ZONING,
                                                  "2026-10-21")}
    assert out["18"]["basis"] == "no_county_zoning" and out["18"]["combined"] == 8
    assert out["17"]["basis"] == "profile_only"
    # A county of such a state that zones by local act is scored as anywhere else.
    cfg = {**NO_ZONING, "no_county_zoning": {**CFG["no_county_zoning"], "except_counties": {"18": "local act"}}}
    out = {r["county_fips"]: r for r in rs.build([_r("m", "19", 4, "moratorium")], [], summary,
                                                  _profile({f: i / 100 for i, f in enumerate(fips)}), cfg,
                                                  "2026-10-21")}
    assert out["18"]["basis"] == "profile_only"


def test_deciles_split_counties_evenly_despite_tied_scores():
    # 40 counties with no record in two resemblance deciles share two combined
    # scores; the resemblance score breaks the ties, so each decile holds four.
    fips = [f"{i:02d}" for i in range(40)]
    restrictions = [_r("a", "39", 4, "moratorium")]
    out = _build(restrictions, summary=_summary(*fips[:39], coverage="none") + _summary("39"),
                 profile={f: i / 100 for i, f in enumerate(fips)})
    assert len({r["combined"] for r in out.values()}) < 5
    counts = [sum(1 for r in out.values() if r["combined_decile"] == d) for d in range(1, 11)]
    assert counts == [4] * 10
    assert out["00"]["combined_decile"] == 1 and out["39"]["combined_decile"] == 10
    # Within a tie, the higher resemblance score ranks higher.
    assert out["01"]["combined"] == out["00"]["combined"]
    assert out["01"]["combined_normal"] > out["00"]["combined_normal"]


def test_the_normal_score_is_centred_and_symmetric():
    fips = [f"{i:02d}" for i in range(21)]
    out = _build(summary=_summary(*fips, coverage="none"), profile={f: i / 100 for i, f in enumerate(fips)})
    z = sorted(r["combined_normal"] for r in out.values())
    assert z[10] == 0 and z[0] == -z[-1] and z[-1] > 1.5


# ── State preemption ────────────────────────────────────────────────────────

def _in(state, *fips, coverage="record"):
    return [{"county_fips": f, "state": state, "county": f"C{f}", "coverage": coverage} for f in fips]


def test_illinois_caps_county_rules_but_not_city_rules():
    """55 ILCS 5/5-12020 binds counties only: a county moratorium counts at
    severity 2, a city ban keeps its own severity."""
    out = _build([_r("m", "A", 4, "moratorium"), _r("m", "A", 4, "moratorium", tech="wind"),
                  _r("b", "B", 4, "ban", jtype="City")], summary=_in("IL", "A", "B"), as_of="2026-10-30")
    a, b = out["A"], out["B"]
    assert a["record_points"] == 13.2 and a["local_points"] == 44 and a["preemption_points"] == 30.8
    assert a["preemption_rules"] == "IL-local_preemption-1;IL-local_preemption-3"
    assert "severity 2 capped from 4" in a["top_instrument"]
    assert a["tier"] == "restrictive" and a["tier_local"] == "closed"
    assert b["record_points"] == b["local_points"] == 20 and b["preemption_rules"] == ""


def test_a_rule_counts_only_from_its_effective_date():
    """Illinois' storage limits took effect 2026-06-01."""
    before = _build([_r("s", "A", 4, "moratorium", tech="battery_storage")], summary=_in("IL", "A"),
                    as_of="2026-05-31")["A"]
    after = _build([_r("s", "A", 4, "moratorium", tech="battery_storage")], summary=_in("IL", "A"),
                   as_of="2026-06-01")["A"]
    assert before["record_points"] == 40 and after["record_points"] == 12


def test_ohio_counties_keep_their_sb52_veto():
    """The Power Siting Board preempts township and city rules, but county
    commissioners may bar projects under SB 52."""
    out = _build([_r("c", "A", 4, "ban"), _r("t", "B", 4, "moratorium", tech="wind", jtype="Township")],
                 summary=_in("OH", "A", "B"), as_of="2026-10-30")
    assert out["A"]["record_points"] == 40 and out["A"]["preemption_points"] == 0
    assert out["B"]["record_points"] == 4 * 0.5 and out["B"]["preemption_rules"] == "OH-local_preemption-1"


def test_a_size_threshold_is_read_against_the_states_own_plants():
    """Florida's siting board reaches solar of 75 MW or more. With no plant
    data the score falls back to a 100 MW project and the board caps a county
    moratorium at 1; with Florida's plants, sized just under 75 MW, the board
    does not reach the typical project, and only the agricultural-district
    statute, which applies at any size, caps it at 2."""
    restrictions = [_r("m", "A", 4, "moratorium")]
    summary = [{"county_fips": "A", "state": "FL", "county": "CA", "coverage": "record"}]
    fallback = rs.build(restrictions, [], summary, _profile({"A": 0.2}), NO_ZONING, "2026-10-30")[0]
    assert fallback["record_points"] == 4 and "FL-local_preemption-1" in fallback["preemption_rules"]
    plants = [{**_plant("B", 2023, mw=74.9), "state": "FL"} for _ in range(6)]
    assert rs.reference_sizes(plants, CFG) == {("FL", "solar"): 74.9}
    sized = rs.build(restrictions, [], summary, _profile({"A": 0.2}), NO_ZONING, "2026-10-30", plants)[0]
    assert sized["record_points"] == 12 and sized["preemption_rules"] == "FL-local_preemption-2"


def test_too_few_plants_fall_back_to_the_reference_size():
    plants = [{**_plant("B", 2023, mw=74.9), "state": "FL"} for _ in range(4)]
    assert rs.reference_sizes(plants, CFG) == {}


def test_an_instrument_a_rule_reaches_in_part_is_capped_only_there():
    """ORES caps a New York moratorium on solar and wind but does not site
    stand-alone storage: storage counts in full at severity 4, and solar and
    wind add their breadth at the capped severity 2 (12 points each)."""
    out = _build([_r("m", "A", 4, "moratorium", tech=t) for t in ("solar", "wind", "battery_storage")],
                 summary=_in("NY", "A"), as_of="2026-10-30")["A"]
    assert out["local_points"] == 48
    assert out["record_points"] == 40 + 0.1 * (12 + 12)


def test_a_capped_instrument_never_outscores_itself_uncapped():
    """A city moratorium below the county's top instrument: capping part of
    it must not add points (an earlier split of instruments did)."""
    out = _build([_r("c", "A", 4, "moratorium"),
                  *[_r("p", "A", 4, "moratorium", tech=t, jtype="Town") for t in ("solar", "wind",
                                                                                  "battery_storage")]],
                 summary=_in("NY", "A"), as_of="2026-10-30")["A"]
    assert out["record_points"] <= out["local_points"]


def test_iowa_wind_is_left_to_the_county():
    out = _build([_r("w", "A", 4, "moratorium", tech="wind"), _r("s", "B", 4, "moratorium")],
                 summary=_in("IA", "A", "B"), as_of="2026-10-30")
    assert out["A"]["record_points"] == 40 and out["B"]["record_points"] == 12


def test_a_preempted_moratorium_no_longer_outweighs_approvals():
    """Approvals never undercut a county-wide moratorium in force, but once
    state law caps it the ordinary half-the-points limit applies."""
    out = _build([_r("m", "A", 4, "moratorium")], [_p("A", "advanced_confirmed")] * 3,
                 summary=_in("MN", "A"), as_of="2026-10-30")
    assert out["A"]["local_points"] == 40 and out["A"]["record_points"] == 2


def test_preemption_only_lowers_scores_and_only_where_a_rule_applies():
    restrictions = [_r("a", "A", 4, "moratorium"), _r("b", "B", 4, "moratorium"), _r("c", "C", 3)]
    summary = _in("IL", "A") + _in("KS", "B") + _in("MN", "C")
    out = _build(restrictions, summary=summary, as_of="2026-10-30")
    assert out["B"]["combined"] == out["B"]["combined_local"] and out["B"]["profile_cap"] == ""
    for r in out.values():
        assert r["combined"] <= r["combined_local"] and r["record_points"] <= r["local_points"]


def test_the_prior_is_capped_where_county_rules_are_capped_on_every_technology():
    """An Illinois county with no record cannot be expected to restrict more
    than one county-wide severity 2 instrument on all three technologies; a
    Kansas county takes the full prior."""
    fips = [f"{i:02d}" for i in range(20)]
    summary = _in("KS", *fips[:18], coverage="none") + _in("IL", "18", coverage="none") + _in("KS", "19")
    out = _build([_r("m", "19", 4, "moratorium")], summary=summary,
                 profile={f: i / 100 for i, f in enumerate(fips)}, as_of="2026-10-30")
    # 18 and 19 share the top decile, with a mean of 20 points.
    assert out["18"]["profile_cap"] == 14.4 and out["18"]["profile_points"] == 14.4
    assert out["19"]["profile_cap"] == "" and out["19"]["profile_points"] == 20


def test_every_verified_preemption_row_is_ruled_on():
    """Each local_preemption and local_opt_out row in state_policies.csv is a
    rule or is listed as read and not applied, and every rule matches its
    row's technologies and MW thresholds."""
    import classify
    from common import read_csv
    sp = CFG["state_preemption"]
    policies = {r["id"]: r for r in read_csv(ROOT / "data" / "processed" / "state_policies.csv")}
    ruled = {r["policy_id"] for r in sp["rules"]}
    skipped = {k for k in sp["not_applied"] if not k.startswith("_")}
    assert not ruled & skipped
    for pid, p in policies.items():
        if p["policy_type"] in ("local_preemption", "local_opt_out"):
            assert pid in ruled | skipped, f"{pid} is neither a rule nor read and not applied"
    ruled_states = {r["policy_id"].split("-")[0] for r in sp["rules"]}
    siting = {k for k in sp["siting_without_preemption"] if not k.startswith("_")}
    for pid, p in policies.items():
        if p["policy_type"] == "siting_authority" and p["who_decides"] in ("state_board", "hybrid") \
                and p["state"] not in ruled_states:
            assert pid in siting, f"{pid}: a state siting row with no rule and no reason"
    assert siting <= set(policies)
    for rule in sp["rules"]:
        p = policies[rule["policy_id"]]
        assert rule["mechanism"] in sp["ceilings"] and 1 <= sp["ceilings"][rule["mechanism"]] <= 4
        assert rule["binds"] in ("county", "non_county", "all_local") and rule["note"]
        for tech, least in rule["technologies"].items():
            assert tech in p["technology"].split(";"), (rule["policy_id"], tech)
            stated = classify.threshold_for(p["threshold_mw"], tech)
            if isinstance(least, (int, float)) and stated:
                assert float(stated) == least, (rule["policy_id"], tech)


def test_a_bounded_governments_rules_count_as_one():
    """The most an Illinois county may impose is the statute's own standards,
    so its rules count together as one instrument at the ceiling; a city's
    rules are another government's and stay apart."""
    out = _build([_r("m", "A", 4, "moratorium"), _r("s", "A", 3, tech="wind"),
                  _r("b", "A", 2, tech="battery_storage"), _r("c", "A", 4, "ban", tech="wind", jtype="City")],
                 summary=_in("IL", "A"), as_of="2026-10-30")["A"]
    # One county instrument at severity 2 on three technologies (14.4) under
    # the city ban (20): 20 + 0.25 x 14.4.
    assert out["record_points"] == 23.6
    assert out["local_points"] == 40 + 0.25 * (30 + 20 + 12)


def test_a_discretionary_override_does_not_merge_rules():
    """Under New York's override each local rule binds unless ORES sets it
    aside, so two capped rules still add up."""
    out = _build([_r("a", "A", 4, "moratorium"), _r("b", "A", 4, "ban", tech="wind")],
                 summary=_in("NY", "A"), as_of="2026-10-30")["A"]
    assert out["record_points"] == 12 + 0.25 * 12


def test_a_rule_with_an_unbounded_technology_stays_apart():
    """Maryland bounds solar and storage but not wind: the solar and storage
    rules merge, the wind moratorium counts in full beside them."""
    out = _build([_r("s", "A", 4, "moratorium"), _r("t", "A", 3, tech="battery_storage"),
                  _r("w", "A", 4, "moratorium", tech="wind")], summary=_in("MD", "A"), as_of="2026-10-30")["A"]
    assert out["record_points"] == 40 + 0.25 * 13.2


def test_the_prior_is_capped_only_where_the_rulebook_is_bounded():
    """Washington's override is discretionary, so its prior is not capped."""
    rules = rs.preemption_rules(CFG, "WA", "2026-10-30")
    assert rules and rs.prior_cap(rules, CFG) is None
    assert rs.prior_cap(rs.preemption_rules(CFG, "MN", "2026-10-30"), CFG) == 4 * 1.2
