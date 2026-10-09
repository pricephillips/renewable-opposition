"""The Sabin edition crosswalk and how build_sabin_seeds uses it. Synthetic rows only."""
import build_sabin_seeds as b
import extract_sabin_edition as x
import sabin_crosswalk as cw

BLANK = {k: "" for k in x.FIELDS}


def rec(rid, section, **kw):
    return {**BLANK, "record_id": rid, "extraction_source_section": section, **kw}


OLD = [
    # Renumbered in 2026: same county, technology, mechanism and year.
    rec("REC-0001", "local_restrictions", state="KS", county="Alpha County", technology="wind",
        policy_mechanism="setback", adopted_or_event_date_text="2021", status="pending",
        short_description="Alpha County wind setback."),
    # Two 2026 entries for the same town and technology: ambiguous.
    rec("REC-0002", "local_restrictions", state="TX", municipality="Beta", technology="wind",
        policy_mechanism="setback, height_limit", status="in_force", short_description="Beta wind rules."),
    # Not in the 2026 edition at all.
    rec("REC-0003", "local_restrictions", state="IA", county="Gamma County", technology="solar",
        policy_mechanism="moratorium", status="in_force", short_description="Gamma solar moratorium."),
    # A project whose 2025 name lost a letter pair in extraction.
    rec("REC-0004", "contested_projects", state="ND", county="Mercer County", technology="wind",
        project_or_policy_name="Garrison Buje Wind Farm", status="pending", opposition_type="local_residents",
        short_description="A wind farm."),
]
NEW = [
    rec("S26R-9001", "local_restrictions", state="KS", county="Alpha County", technology="wind",
        policy_mechanism="setback (wind)", adopted_or_event_date_text="2021", status="in_force",
        short_description="Alpha County requires a 1 mile setback.", notes="Sabin 2026 entry 9001"),
    rec("S26R-9002", "local_restrictions", state="TX", municipality="City of Beta", technology="wind",
        policy_mechanism="setback (wind)", status="in_force", short_description="Beta setback."),
    rec("S26R-9003", "local_restrictions", state="TX", municipality="City of Beta", technology="wind",
        policy_mechanism="height limit (wind)", status="in_force", short_description="Beta height."),
    rec("S26P-9100", "contested_projects", state="ND", county="Mercer County", technology="wind",
        project_or_policy_name="Garrison Butte Wind Farm", status="cancelled", has_litigation="no",
        short_description="Cancelled."),
    rec("S26R-9200", "local_restrictions", state="OK", county="Delta County", technology="solar",
        policy_mechanism="ban or moratorium (solar)", status="in_force", short_description="Delta: Ban."),
]


def crosswalk(existing=None):
    return {r["rec_id"]: r for r in cw.build(OLD, NEW, existing)}


def test_renumbered_entry_matches_and_records_the_status_change():
    row = crosswalk()["REC-0001"]
    assert row["match"] == "matched" and row["entry_2026"] == "S26R-9001"
    assert row["status_changed"] == "yes" and (row["status_2025"], row["status_2026"]) == ("pending", "in_force")


def test_two_close_candidates_are_ambiguous_never_guessed():
    row = crosswalk()["REC-0002"]
    assert row["match"] == "ambiguous" and row["entry_2026"] == ""
    assert "S26R-9002" in row["candidates_2026"] and "S26R-9003" in row["candidates_2026"]


def test_missing_entry_and_damaged_spelling():
    rows = crosswalk()
    assert rows["REC-0003"]["match"] == "not_in_latest_edition"
    assert rows["REC-0004"]["entry_2026"] == "S26P-9100" and "spelling" in rows["REC-0004"]["match_basis"]


def test_reviewer_decision_wins_and_survives_a_rebuild():
    first = list(crosswalk().values())
    for r in first:
        if r["rec_id"] == "REC-0002":
            r.update(review_decision="S26R-9003", reviewer="agent:x", reviewed_on="2026-10-09")
    row = crosswalk(first)["REC-0002"]
    assert row["match"] == "matched" and row["entry_2026"] == "S26R-9003" and row["reviewer"] == "agent:x"


def test_merge_keeps_ids_holds_candidates_and_never_deletes():
    records, worklist = b.merge_editions(NEW, OLD, list(crosswalk().values()))
    by_id = {r["record_id"]: r for r in records}
    # Matched: the 2026 entry under the 2025 id, with what 2026 does not record carried.
    assert by_id["REC-0001"]["_edition"] == "2026-09" and "S26R-9001" not in by_id
    assert by_id["REC-0004"]["opposition_type"] == "local_residents"
    assert "carried from the 2025 edition" in by_id["REC-0004"]["notes"]
    # Missing and ambiguous 2025 records stay, marked; ambiguous candidates are held.
    assert by_id["REC-0003"]["_edition_status"] == "not_in_latest_edition"
    assert by_id["REC-0002"]["_edition_status"] == "crosswalk_ambiguous"
    assert "S26R-9002" not in by_id and "S26R-9003" not in by_id
    # A new entry keeps its own id.
    assert by_id["S26R-9200"]["_edition_status"] == "in_latest_edition"
    kinds = {(w["record_id"], w["edition_status"]) for w in worklist}
    assert ("REC-0003", "not_in_latest_edition") in kinds and ("S26R-9002", "held") in kinds


def test_new_edition_rows_are_built_and_pinned_to_their_2025_ids():
    records, _ = b.merge_editions(NEW, OLD, list(crosswalk().values()))
    rows, held, _ = b.build_restrictions(records, {})
    alpha = [r for r in rows if r["source_record_id"] == "REC-0001"][0]
    assert alpha["status"] == "active" and alpha["source"] == b.SOURCE_LABEL and alpha["mechanisms"] == "setback (wind)"
    delta = [r for r in rows if r["source_record_id"] == "S26R-9200"][0]
    assert delta["restriction_type"] == "ban_or_moratorium" and delta["severity_score"] == 4
    gamma = [r for r in rows if r["source_record_id"] == "REC-0003"][0]
    assert gamma["source"] == b.SOURCE_LABEL_2025 and gamma["edition_status"] == "not_in_latest_edition"
    existing = [{"source": b.SOURCE_LABEL_2025, "source_record_id": "REC-0001", "technology": "wind",
                 "pinned_id": "res_old"}]
    b.pin_ids(rows, existing, "restrictions")
    assert alpha["pinned_id"] == "res_old" and "pinned_id" not in delta


def test_mechanism_qualifiers_apply_per_technology():
    mechs = ["ban/prohibition (solar)", "setback (wind)", "noise limit"]
    assert b.mechanisms_for(mechs, "wind") == ["setback (wind)", "noise limit"]
    assert b.mechanisms_for(["moratorium (solar+storage)"], "battery_storage") == ["moratorium (solar+storage)"]
    assert b.mechanism_name("setback (wind)") == "setback"


def test_extraction_helpers():
    rules, body = x.split_rules("<p>Rule 1: Ban / Moratorium (solar) | Rule 6a: Setback Restriction (wind)<br />"
                                "The county adopted a moratorium on solar.</p>")
    assert rules == ["Ban / Moratorium (solar)", "Setback Restriction (wind)"]
    assert x.mechanisms(rules, body, ["solar", "wind"]) == ["moratorium (solar)", "setback (wind)"]
    assert x.ban_or_moratorium("Solar farms are prohibited in all districts.") == "ban/prohibition"
    assert x.ban_or_moratorium("Removed solar from permitted uses.") == x.UNSTATED
    rows = x.read_export('ID,Title,County,County\n1,"A County","A County",20001\n', ["ID", "Title", "County", "County"])
    assert rows == [{"ID": "1", "Title": "A County", "County": "A County", "County FIPS": "20001"}]
    page = "<p>at least 888 state and local restrictions ... at least 567 projects that faced, across 48 states</p>"
    assert x.headline_totals(page) == {"restrictions": 888, "projects": 567, "states": 48}
