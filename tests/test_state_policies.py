"""state_policies validation and the recorded-review rule. Synthetic rows only."""
import state_policies as sp

GOOD = {
    "policy_id": "OH-siting_authority-1", "state": "OH", "technology": "solar;wind", "policy_type": "siting_authority",
    "who_decides": "hybrid", "state_body": "Ohio Power Siting Board", "threshold_mw": "solar:50;wind:5",
    "summary": "The board decides large projects; counties decide smaller ones.",
    "statute_citation": "Ohio Rev. Code 4906.01", "statute_url": "https://codes.ohio.gov/ohio-revised-code/section-4906.01",
    "lbnl_reference": "Laws in Order (2024), p. 60", "sabin_record_ids": "", "amendments_note": "none shown",
    "drafted_by": "agent:drafter-1", "drafted_on": "2026-10-09", "draft_access": "opened", "draft_note": "",
    "reviewer": "agent:reviewer-1", "reviewed_on": "2026-10-09", "review_access": "opened",
    "review_archived_url": "", "review_verdict": "confirmed", "review_note": "",
}


def test_a_reviewed_row_publishes_as_verified():
    published, held, errors = sp.build([dict(GOOD)])
    assert errors == [] and held == []
    (row,) = published
    assert row["id"] == "OH-siting_authority-1" and row["verification"] == "verified"
    assert row["evidence_level"] == "primary_source" and row["source_url"] == GOOD["statute_url"]


def test_rows_without_a_proper_review_are_held_with_the_reason():
    cases = {
        "no recorded review": {"reviewer": ""},
        "self-review": {"reviewer": "agent:drafter-1"},
        "only as snippet": {"review_access": "snippet"},
        "review verdict contradicts": {"review_verdict": "contradicts", "review_note": "threshold is 20 MW"},
    }
    for i, (why, change) in enumerate(cases.items()):
        published, held, errors = sp.build([{**GOOD, "policy_id": f"OH-other-{i}", **change}])
        assert errors == [] and published == [] and why in held[0]["reason"], why


def test_structural_errors_stop_the_build():
    bad = [
        {**GOOD, "policy_type": "vibes"},
        {**GOOD, "policy_id": "X-1", "threshold_mw": "solar=50"},
        {**GOOD, "policy_id": "X-2", "who_decides": ""},
        {**GOOD, "policy_id": "X-3", "statute_url": "codes.ohio.gov"},
        {**GOOD, "policy_id": "X-4", "technology": "coal"},
        {**GOOD, "policy_id": "X-5", "summary": "A rule — with a dash."},
        {**GOOD, "policy_id": "X-5"},
    ]
    published, held, errors = sp.build(bad)
    assert published == [] and len(errors) >= 7
    joined = " ".join(errors)
    for word in ("policy_type", "threshold_mw", "who_decides", "statute_url", "technology", "em dash", "repeats"):
        assert word in joined, word


def test_framework_lists_siting_authority_first():
    rows = [{**GOOD, "id": "OH-local_opt_out-1", "policy_type": "local_opt_out"},
            {**GOOD, "id": "OH-siting_authority-1"}, {**GOOD, "id": "IN-x", "state": "IN"}]
    assert [r["id"] for r in sp.framework(rows, "OH")] == ["OH-siting_authority-1", "OH-local_opt_out-1"]
