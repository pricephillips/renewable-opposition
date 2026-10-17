import county_typology as ct


def _summary(fips, state="KY", **kw):
    row = {"county_fips": fips, "state": state, "county": f"C{fips}", "coverage": "none",
           "restrictions_renewables": "0", "contested_projects": "0", "projects_blocked": "0",
           "projects_advanced": "0", "projects_pending": "0", "siting_standard_jurisdictions": "0",
           "negative_check_grade": ""}
    row.update({k: str(v) for k, v in kw.items()})
    return row


def _restriction(iid, fips, currency="in_force", rtype="setback", severity=2, tech="solar",
                 scope="renewables_only", enacted=""):
    return {"instrument_id": iid, "county_fips_all": fips, "currency": currency, "restriction_type": rtype,
            "severity_score": str(severity), "technology": tech, "scope": scope, "date_enacted_iso": enacted}


def _build(summary, restrictions=(), policies=(), covariates=(), adjacency=None):
    adjacency = adjacency or {}
    return {r["county_fips"]: r for r in ct.build(list(summary), list(restrictions), list(policies),
                                                   list(covariates), lambda f: adjacency.get(f, []))}


def test_each_category_in_precedence_order():
    summary = [_summary(f) for f in ("01", "02", "03", "04", "05")]
    summary.append(_summary("06", contested_projects=1, coverage="record"))
    summary.append(_summary("07", siting_standard_jurisdictions=2, coverage="record"))
    summary.append(_summary("08", coverage="negative_check"))
    summary.append(_summary("09"))
    restrictions = [
        _restriction("a", "01", rtype="moratorium", severity=4), _restriction("a2", "01", severity=3),
        _restriction("b", "02", severity=3),
        _restriction("c", "03", severity=2),
        _restriction("d", "04", currency="pending"),
        _restriction("e", "05", currency="unknown"),
    ]
    out = _build(summary, restrictions)
    assert [out[f]["category"] for f in ("01", "02", "03", "04", "05", "06", "07", "08", "09")] == [
        "moratorium_in_force", "severe_rules_in_force", "rules_in_force", "restriction_pending",
        "restrictions_status_unknown", "contested_projects_only", "siting_standards_only",
        "checked_none_found", "not_examined"]
    assert set(ct.CATEGORIES) == {r["category"] for r in out.values()}


def test_a_lapsed_instrument_does_not_count_as_in_force():
    out = _build([_summary("01")], [_restriction("a", "01", currency="lapsed_unconfirmed", severity=4)])
    assert out["01"]["category"] == "restrictions_status_unknown"
    assert out["01"]["in_force"] == 0 and out["01"]["status_unknown"] == 1


def test_an_instrument_counts_once_across_its_technology_rows_and_in_every_county_it_touches():
    rows = [_restriction("a", "01;02", tech="solar", severity=3),
            _restriction("a", "01;02", tech="wind", severity=4, enacted="2024-05-01")]
    out = _build([_summary("01"), _summary("02")], rows)
    for f in ("01", "02"):
        assert out[f]["in_force"] == 1 and out[f]["severe_in_force"] == 1
        assert out[f]["technologies_in_force"] == "solar;wind"
        assert out[f]["latest_enacted_year"] == "2024"


def test_a_multi_sector_moratorium_still_decides_the_category_and_is_counted_apart():
    out = _build([_summary("01")], [_restriction("a", "01", rtype="moratorium", severity=4,
                                                 scope="multi_sector_data_centers")])
    assert out["01"]["category"] == "moratorium_in_force"
    assert out["01"]["multi_sector"] == 1


def test_neighbors_with_rules_in_force_counts_adjacent_in_force_categories_only():
    summary = [_summary("01"), _summary("02"), _summary("03"), _summary("04")]
    restrictions = [_restriction("a", "02", severity=3), _restriction("b", "03", currency="unknown")]
    out = _build(summary, restrictions, adjacency={"01": ["02", "03", "04", "99"]})
    assert out["01"]["neighbors"] == 3  # 99 is not a county in the summary
    assert out["01"]["neighbors_with_rules_in_force"] == 1


def test_state_context_collapses_when_every_technology_agrees():
    policies = [{"id": "p1", "state": "KY", "technology": "solar;wind;battery_storage",
                 "policy_type": "siting_authority", "who_decides": "local_government", "threshold_mw": ""}]
    out = _build([_summary("01")], policies=policies)
    assert out["01"]["state_siting_authority"] == "local_government"
    assert out["01"]["state_limits_local"] == "no"


def test_state_context_keeps_the_technology_when_values_differ():
    policies = [{"id": "p1", "state": "KY", "technology": "solar;wind", "policy_type": "siting_authority",
                 "who_decides": "hybrid", "threshold_mw": "solar:10;wind:10"}]
    out = _build([_summary("01")], policies=policies)
    assert out["01"]["state_siting_authority"] == "solar:hybrid;wind:hybrid"
    assert out["01"]["state_limits_local"] == "solar:yes;wind:yes;battery_storage:unknown"


def test_puerto_rico_is_outside_the_coverage_universe_and_covariates_carry_through():
    out = _build([_summary("72001", state="PR"), _summary("21181")],
                 covariates=[{"county_fips": "21181", "population": "7708", "pop_density_sqmi": "39.5"}])
    assert out["72001"]["in_coverage_universe"] == "no"
    assert out["21181"]["in_coverage_universe"] == "yes"
    assert out["21181"]["population"] == "7708" and out["21181"]["pop_density_sqmi"] == "39.5"


def test_every_output_column_is_filled_for_every_row():
    out = _build([_summary("01")])
    assert set(out["01"]) == set(ct.FIELDS)


def test_an_instrument_is_a_moratorium_when_any_of_its_rows_is_one():
    rows = [_restriction("a", "01", tech="solar", rtype="setback", severity=2),
            _restriction("a", "01", tech="wind", rtype="moratorium", severity=4)]
    out = _build([_summary("01")], rows)
    assert out["01"]["category"] == "moratorium_in_force" and out["01"]["moratoria_in_force"] == 1
