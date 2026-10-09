"""NREL mapping, its schema guard and the restriction threshold. Synthetic rows only."""
import io

import openpyxl
import pytest

import nrel_ordinances as n
import nrel_sample


def workbook(tech="wind", header_change=None, feature="Noise", drop_sheet=None) -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, header in n.DATASETS[tech]["sheets"].items():
        if name == drop_sheet:
            continue
        ws = wb.create_sheet(name)
        if name in ("All Ordinances", "County-Level", "Municipal-Level"):
            ws.append([n.DISCLAIMER + ". Always validate."])
        h = list(header)
        if header_change and name == "All Ordinances":
            h[h.index(header_change[0])] = header_change[1]
        ws.append(h)
        if name == "All Ordinances":
            row = dict.fromkeys(header)
            row.update({"State": "Kansas", "County": "Alpha", "Jurisdiction Type": "County",
                        "County Subdivision FIPS Code": 20001, "Feature": feature, "Value": 40, "Units": "dBA"})
            ws.append([row[k] for k in header])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_schema_guard_accepts_the_expected_layout_and_refuses_changes():
    assert n.check_schema(workbook(), "wind") == []
    assert any("header changed" in p for p in n.check_schema(workbook(header_change=("Value", "Val")), "wind"))
    assert any("unknown feature" in p for p in n.check_schema(workbook(feature="Glowing Blades"), "wind"))
    assert any("missing" in p for p in n.check_schema(workbook(drop_sheet="State-Level"), "wind"))
    assert n.check_schema(b"not a workbook", "wind")[0].startswith("not a readable")


def test_load_refuses_to_read_a_changed_layout(tmp_path):
    bad = tmp_path / "w.xlsx"
    bad.write_bytes(workbook(header_change=("Units", "Unit")))
    with pytest.raises(n.SchemaError):
        n.load("wind", bad)
    good = tmp_path / "g.xlsx"
    good.write_bytes(workbook())
    assert n.load("wind", good)[0]["Feature"] == "Noise"


def test_fips_and_jurisdiction_naming():
    assert n.fips_parts(1003) == ("01003", "01003")
    assert n.fips_parts(5002777500) == ("5002777500", "50027")
    assert n.fips_parts(1000) == ("01000", "")
    # A Pennsylvania borough is a municipality, never looked up as a county.
    assert n.jurisdiction({"State": "Pennsylvania", "County": "Bedford", "Subdivision": "Bedford",
                           "Jurisdiction Type": "Borough"}) == ("Bedford Borough", "Municipality", "Borough")
    assert n.jurisdiction({"State": "Iowa", "County": "Linn", "Subdivision": None,
                           "Jurisdiction Type": "County"})[:2] == ("Linn County", "County")


def std(feature, value="", units="", summary="", tech="wind", code="20001", jtype="County"):
    return {"state": "KS", "jurisdiction": "Alpha County", "jurisdiction_type": jtype, "nrel_jurisdiction_type": jtype,
            "technology": tech, "feature": feature, "value": value, "units": units, "min_setback_ft": "",
            "summary": summary, "section": "", "ordinance_year": "2024", "ordinance_url": "https://example.org/o.pdf",
            "source_county_fips": code, "restricting": "yes" if feature in n.RESTRICTING else "",
            "nrel_id": f"{tech}:{code}", "standard_id": f"nrel:{tech}:{code}:{feature.lower()}"}


def test_restriction_threshold_uses_the_shared_rules():
    # Only non-restricting features: siting_standards only.
    assert n.restriction_rows([std("Decommissioning"), std("Roads", "1.5", "tip-height-multiplier")]) == []
    # A mild setback scores the default 2, which meets the threshold.
    (row,) = n.restriction_rows([std("Structures (Non-Participating)", "1.1", "tip-height-multiplier")])
    assert row["severity_score"] == 2 and row["status"] == "unknown" and row["nrel_id"] == "wind:20001"
    # 5x tip height scores 3; a height limit's feet are never read as a setback.
    (row,) = n.restriction_rows([std("Property Line (Non-Participating)", "5", "tip-height-multiplier"),
                                 std("Maximum Height", "430", "feet")])
    assert row["severity_score"] == 3 and "430 ft" not in row["severity_basis"]
    # An outright prohibition is a ban; a district-only one is a zoning restriction.
    (row,) = n.restriction_rows([std("Prohibitions", summary="Commercial wind energy systems are prohibited in "
                                                            "all zoning districts of the county.")])
    assert row["restriction_type"] == "ban" and row["severity_score"] == 4
    assert n.prohibition_mechanism("Wind turbines are prohibited in the R-1 district.") == "zoning restriction"
    assert n.prohibition_mechanism("A temporary moratorium on solar farms.") == "moratorium"
    assert n.prohibition_mechanism("Concentrated Solar Power systems are prohibited in all zoning districts.") \
        == "zoning restriction"


def test_noise_units_other_than_dba_are_not_read_as_dba():
    assert n.feature_text(std("Noise", "10", "dB above background")) == "noise limit 10 (decibels above background)"
    (row,) = n.restriction_rows([std("Noise", "10", "dB above background")])
    assert row["severity_score"] == 2


def test_dedupe_drops_agreeing_duplicates_and_keeps_conflicts():
    (cand,) = n.restriction_rows([std("Prohibitions", summary="Wind farms are prohibited in all zoning districts.")])
    same = {"state": "KS", "technology": "wind", "jurisdiction": "Alpha County", "jurisdiction_type": "County",
            "restriction_type": "ban", "severity_score": "4", "source": "Sabin Center, x", "source_record_id": "R1"}
    keep, conflicts = n.dedupe([dict(cand)], [same])
    assert keep == [] and conflicts[0]["decision"].startswith("duplicate")
    keep, conflicts = n.dedupe([dict(cand)], [{**same, "restriction_type": "setback", "severity_score": "2"}])
    assert len(keep) == 1 and keep[0]["conflicts_with"] == "sabin:R1" and conflicts[0]["decision"].startswith("conflict")


def test_sample_draw_is_repeatable_and_apply_needs_every_feature_confirmed():
    restrictions = [{"nrel_id": f"wind:{i:05d}", "state": "KS", "jurisdiction": f"J{i}", "technology": "wind",
                     "severity_score": "2", "restriction_type": "setback"} for i in range(100)]
    standards = [{**std("Noise", "40", "dBA", code=f"{i:05d}"), "restricting": "yes"} for i in range(100)]
    a = nrel_sample.draw(restrictions, standards, seed=7, size=5)
    assert a == nrel_sample.draw(restrictions, standards, seed=7, size=5) and len(a) == 5
    ok = {"standard_id": a[0]["standard_id"], "instrument_id": a[0]["instrument_id"], "feature": "Noise",
          "document_value": "40 dBA", "verdict": "confirmed", "access": "opened", "reviewer": "agent:r",
          "document_url": "https://example.org/o.pdf", "checked_on": "2026-10-09", "archived_url": ""}
    bad = {**ok, "standard_id": a[1]["standard_id"], "instrument_id": a[1]["instrument_id"], "verdict": "contradicts"}
    sources, added = nrel_sample.apply(a, [ok, bad], [])
    assert added == 1 and sources[0]["instrument_id"] == a[0]["instrument_id"] and sources[0]["verdict"] == "confirmed"
    assert nrel_sample.review_problems([{**ok, "access": "snippet"}], a)
