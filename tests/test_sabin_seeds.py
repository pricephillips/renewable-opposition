import build_sabin_seeds as b
from common import read_csv


def test_setback_feet_parses_feet_miles_and_words():
    assert b.setback_feet("set back 1,500 feet and 3,000 ft from lines") == 3000
    assert b.setback_feet("a 1.5-mile buffer") == 1.5 * 5280
    assert b.setback_feet("at least one mile from homes") == 5280
    assert b.setback_feet("0.5 miles (2,640 feet)") == 2640
    assert b.setback_feet("no distance here") == 0


def test_height_multiplier():
    assert b.height_multiplier("the greater of 1 mile or 10 times turbine height") == 10
    assert b.height_multiplier("1.5x the total height") == 1.5
    assert b.height_multiplier("300 feet in height") == 0


def test_text_about_keeps_only_sentences_for_the_technology():
    text = "Wind turbines must be set back 1 mile. Solar farms need 200 feet."
    assert "200 feet" in b.text_about(text, "solar") and "mile" not in b.text_about(text, "solar")
    assert b.text_about("Facilities need 1 mile.", "solar") == "Facilities need 1 mile."
    assert b.text_about("Turbines need 1 mile.", "solar") == ""


def test_restriction_severity_rules():
    assert b.restriction_severity({"ban"}, "solar", "active", "")[0] == 4
    assert b.restriction_severity({"moratorium"}, "wind", "active", "")[0] == 4
    assert b.restriction_severity({"moratorium"}, "wind", "pending", "")[0] == 2
    assert b.restriction_severity({"setback"}, "wind", "active", "2 miles from homes")[0] == 3
    assert b.restriction_severity({"setback"}, "wind", "active", "1,000 feet")[0] == 2
    assert b.restriction_severity({"setback"}, "solar", "active", "1,000 feet")[0] == 3
    assert b.restriction_severity({"noise_limit"}, "wind", "active", "35 dBA")[0] == 3
    assert b.restriction_severity({"height_limit"}, "wind", "active", "")[0] == 3
    assert b.restriction_severity({"height_limit"}, "solar", "active", "")[0] == 2
    assert b.restriction_severity({"setback"}, "wind", "pending", "2 miles")[0] == 2


def test_real_build_invariants():
    records = read_csv(b.RECORDS_PATH)
    restrictions, review, _ = b.build_restrictions(records, {})
    assert restrictions, "expected Sabin restriction rows"
    for row in restrictions:
        assert row["status"] in {"active", "extended", "pending", "unknown"}
        assert row["technology"] in b.RESTRICTION_TECH
        assert 1 <= row["severity_score"] <= 4
        assert row["source_url"] and row["jurisdiction"]
    held = {r["source_record_id"] for r in review}
    assert "REC-0212" in held  # preemption law, not a restriction
    contested, _, excluded = b.build_contested(records)
    assert len(contested) + len(excluded) == sum(
        1 for r in records if r["extraction_source_section"] == "contested_projects"
    )


def test_duplicate_moratorium_is_held_back():
    records = [r for r in read_csv(b.RECORDS_PATH) if r["record_id"] == "REC-0401"]
    mn_index = {("SD::county::pennington", "solar"): "sd-pennington-county-2024"}
    restrictions, review, _ = b.build_restrictions(records, mn_index)
    assert [r["technology"] for r in restrictions] == ["wind"]
    assert review[0]["reason"].startswith("duplicate of Moratorium Nation")


def test_merge_candidates_keeps_reviewer_work():
    generated = [{"source_record_id": "REC-1", "project_name": "P", "litigation_context": "new text",
                  "review_status": "needs_docket_research"}]
    existing = [
        {"source_record_id": "REC-1", "case_name": "A v. B", "court": "X", "review_status": "confirmed"},
        {"source_record_id": "REC-1", "case_name": "C v. D", "court": "Y", "review_status": "confirmed"},
    ]
    merged = b.merge_candidates(generated, existing)
    assert [m["case_name"] for m in merged] == ["A v. B", "C v. D"]
    assert all(m["litigation_context"] == "new text" and m["review_status"] == "confirmed" for m in merged)
    assert b.merge_candidates(generated, []) == generated


def test_label_alone_is_never_confirmed():
    assert b.finalize_outcome("blocked_unverified", []) == ("blocked_unverified", "outcome_label_only")
    wrong_way = [{"case_status": "ruled_for_developer", "case_name": "X v. Y"}]
    assert b.finalize_outcome("blocked_unverified", wrong_way)[0] == "blocked_unverified"
    right_way = [{"case_status": "ruled_for_opposition", "case_name": "X v. Y"}]
    assert b.finalize_outcome("blocked_unverified", right_way) == ("blocked_confirmed", "court_ruling: X v. Y")
    assert b.finalize_outcome("pending", right_way) == ("pending", "none")
