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
    assert [out[f]["record_points"] for f in "ABCDE"] == [30, 15, 15, 9, 33]


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
    cfg["zoning_transition"]["counties"] = [{**entry, "state": "IA"}]
    with pytest.raises(ValueError):
        _build(summary=_summary("Z"), cfg=cfg)


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
