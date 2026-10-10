"""The Ohio SB 52 worklist: queue rows count as a first pass, rejected ones do not. Synthetic rows only."""
import ohio_sb52_worklist as ow

HURON, SANDUSKY = "39077", "39143"


def queue_row(county, status):
    return {"state": "OH", "county": county, "review_status": status, "extracted_at": "2026-10-09",
            "description": f"{county} commissioners adopted a restricted-area resolution."}


def test_a_queue_row_awaiting_review_counts_as_a_first_pass():
    rows = ow.build([], [], [], [queue_row("Huron County", "awaiting_review"), queue_row("Sandusky County", "rejected")],
                    [], [HURON, SANDUSKY])
    by = {r["county_fips"]: r for r in rows}
    assert by[HURON]["first_pass"] == "2026-10-09" and by[HURON]["pending_queue"] and not by[HURON]["next_step"]
    assert by[SANDUSKY]["first_pass"] == "" and by[SANDUSKY]["next_step"]


def test_a_negative_check_sets_the_first_pass():
    check = {"county_fips": SANDUSKY, "checked_on": "2026-10-01", "scope": "restrictions"}
    (row,) = ow.build([], [], [], [], [check], [SANDUSKY])
    assert row["first_pass"] == "2026-10-01" and row["negative_check"] == "2026-10-01 (restrictions)"
