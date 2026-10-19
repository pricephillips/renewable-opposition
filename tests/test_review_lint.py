"""QC of a branch's review-file changes (scripts/review_lint.py, docs/AGENTS.md)."""
import csv
import io
from datetime import date

import review_lint as rl

T = date(2026, 10, 16)
RS = "data/review/restriction_sources.csv"
OR = "data/review/outcome_resolutions.csv"
Q = "data/review/queue.csv"
SP = "data/review/state_policies_candidates.csv"
LOG = "data/review/verification_log.csv"
D1 = "agent:instrument-reader-1 (Claude Code, 2026-10-16)"
R1 = "agent:blind-reviewer-1 (Claude Code, 2026-10-16)"


def text(fields, rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def codes(findings, level=None):
    return {f.code for f in findings if level is None or f.level == level}


RS_FIELDS = ["instrument_id", "jurisdiction", "state", "primary_source_url", "verdict", "checked_on", "note",
             "reviewer", "access", "archived_url"]


def rs(**kw):
    row = {"instrument_id": "mn:x", "jurisdiction": "Glenville", "state": "NY",
           "primary_source_url": "https://town.gov/law.pdf", "verdict": "confirmed", "checked_on": "2026-10-16",
           "note": "Local Law 7 of 2025 imposes a 12-month moratorium on battery storage.",
           "reviewer": f"{D1} + {R1}", "access": "opened", "archived_url": ""}
    row.update(kw)
    return row


def test_an_unchanged_file_has_no_findings_and_a_clean_new_row_passes():
    base = text(RS_FIELDS, [rs(instrument_id="mn:a")])
    assert rl.lint_file(RS, base, base, T) == []
    assert rl.lint_file(RS, base, text(RS_FIELDS, [rs(instrument_id="mn:a"), rs()]), T) == []


def test_a_reading_leaves_a_note():
    snippet = rs(access="snippet", note="2026-10-01: https://town.gov/law.pdf returned HTTP 403")
    base = text(RS_FIELDS, [snippet])
    upgraded = text(RS_FIELDS, [{**snippet, "access": "opened"}])
    assert "READ_NO_NOTE" in codes(rl.lint_file(RS, base, upgraded, T), "E")
    read = text(RS_FIELDS, [{**snippet, "access": "opened", "note": snippet["note"] + " Opened 2026-10-16: ..."}])
    assert "READ_NO_NOTE" not in codes(rl.lint_file(RS, base, read, T))
    assert "READ_NO_NOTE" in codes(rl.lint_file(RS, "", text(RS_FIELDS, [rs(note="")]), T), "E")


def test_a_snippet_row_lists_what_was_tried():
    assert "SNIPPET_NO_TRIES" in codes(rl.lint_file(RS, "", text(RS_FIELDS, [rs(access="snippet", note="blocked")]),
                                                    T), "W")


def test_access_and_reviewer_columns_and_dates():
    found = codes(rl.lint_file(RS, "", text(RS_FIELDS, [rs(access="read"), rs(instrument_id="mn:b", reviewer=""),
                                                        rs(instrument_id="mn:c", checked_on="2026-10-17"),
                                                        rs(instrument_id="mn:d", access="archived")]), T), "E")
    assert {"ACCESS", "NO_REVIEWER", "DATE"} <= found


def test_no_self_review_whatever_the_signature_date():
    same = rs(reviewer="agent:x-1 (Claude Code, 2026-10-15) + agent:x-1 (Claude Code, 2026-10-16)")
    assert "SELF_REVIEW" in codes(rl.lint_file(RS, "", text(RS_FIELDS, [same]), T), "E")
    fields = ["policy_id", "drafted_by", "reviewer", "review_access"]
    row = {"policy_id": "KS-1", "drafted_by": "agent:state-policy-drafter-1 (Claude Code, 2026-10-09)",
           "reviewer": "agent:state-policy-drafter-1 (Claude Code, 2026-10-10)", "review_access": "opened"}
    assert "SELF_REVIEW" in codes(rl.lint_file(SP, "", text(fields, [row]), T), "E")


Q_FIELDS = ["queue_id", "review_status", "reviewer_notes", "access", "mechanisms", "source_id", "entity_type",
            "state", "county", "municipality", "project_name", "source_url"]


def q(**kw):
    row = dict.fromkeys(Q_FIELDS, "")
    row.update(queue_id="q_1", review_status="lead", reviewer_notes="Found by GDELT 2026-10-14.", access="snippet")
    row.update(kw)
    return row


def test_queue_triage_and_review_signatures():
    base = text(Q_FIELDS, [q()])
    bare = text(Q_FIELDS, [q(review_status="pending")])
    assert "TRIAGE_NO_NOTE" in codes(rl.lint_file(Q, base, bare, T), "E")
    noted = text(Q_FIELDS, [q(review_status="pending",
                              reviewer_notes="Found by GDELT 2026-10-14. Triaged 2026-10-16 by agent:lead-triager-1 "
                                             "(Claude Code, 2026-10-16): on topic, placed by the headline.")])
    assert codes(rl.lint_file(Q, base, noted, T), "E") == set()

    drafted = "Drafted by agent:county-examiner-1 (Claude Code, 2026-10-16). Read the code."
    awaiting = text(Q_FIELDS, [q(review_status="awaiting_review", reviewer_notes="Read the code.", access="opened")])
    assert "AWAITING_UNSIGNED" in codes(rl.lint_file(Q, "", awaiting, T), "E")
    ok = text(Q_FIELDS, [q(review_status="awaiting_review", reviewer_notes=drafted, access="opened")])
    assert codes(rl.lint_file(Q, "", ok, T), "E") == set()

    unsigned = text(Q_FIELDS, [q(review_status="confirmed", reviewer_notes=drafted, access="opened")])
    assert "CONFIRMED_UNSIGNED" in codes(rl.lint_file(Q, ok, unsigned, T), "E")
    own = drafted + " Reviewed 2026-10-16 by agent:county-examiner-1 (Claude Code, 2026-10-16): confirmed."
    found = codes(rl.lint_file(Q, ok, text(Q_FIELDS, [q(review_status="confirmed", reviewer_notes=own,
                                                        access="opened")]), T), "E")
    assert {"SELF_REVIEW", "CONFIRMED_UNSIGNED"} <= found
    other = drafted + " Reviewed 2026-10-16 by agent:blind-reviewer-2 (Claude Code, 2026-10-16): confirmed."
    assert codes(rl.lint_file(Q, ok, text(Q_FIELDS, [q(review_status="confirmed", reviewer_notes=other,
                                                       access="opened")]), T), "E") == set()


def test_queue_mechanisms_must_be_in_the_vocabulary():
    row = q(review_status="pending", reviewer_notes="Triaged.", mechanisms="setback; laser fence")
    assert "MECHANISM" in codes(rl.lint_file(Q, "", text(Q_FIELDS, [row]), T), "E")


def test_notes_are_appended_to_and_em_dashes_stay_in_quotations():
    base = text(Q_FIELDS, [q(reviewer_notes="Found by GDELT 2026-10-14.")])
    rewritten = text(Q_FIELDS, [q(reviewer_notes="Something else entirely, triaged.")])
    assert "NOTE_REWRITTEN" in codes(rl.lint_file(Q, base, rewritten, T), "W")
    dash = text(Q_FIELDS, [q(reviewer_notes="Found by GDELT 2026-10-14. Placed — by the headline.")])
    assert "EMDASH" in codes(rl.lint_file(Q, base, dash, T), "W")
    old_dash = text(Q_FIELDS, [q(reviewer_notes="Quoted: \"a — b\".")])
    grown = text(Q_FIELDS, [q(reviewer_notes="Quoted: \"a — b\". Triaged 2026-10-16.")])
    assert "EMDASH" not in codes(rl.lint_file(Q, old_dash, grown, T))


def test_structure_and_removed_rows():
    base = text(RS_FIELDS, [rs(), rs(instrument_id="mn:b")])
    broken = base.replace("\n", "\r\n")
    assert "STRUCTURE" in codes(rl.lint_file(RS, base, broken, T), "E")
    assert "STRUCTURE" in codes(rl.lint_file(RS, base, base.rstrip("\n"), T), "E")
    assert "STRUCTURE" in codes(rl.lint_file(RS, base, base + "mn:z,extra\n", T), "E")
    assert "REMOVED" in codes(rl.lint_file(RS, base, text(RS_FIELDS, [rs()]), T), "W")


def test_log_lines_use_the_routine_vocabulary():
    fields = ["date", "queue", "key", "outcome", "note"]
    bad = text(fields, [{"date": "2026-10-16", "queue": "restriction", "key": "mn:x", "outcome": "skipped",
                         "note": "x"}])
    assert "LOG" in codes(rl.lint_file(LOG, text(fields, []), bad, T), "E")


def test_examination_log_lines_name_a_result_and_a_county():
    name = "data/review/examination_log.csv"
    fields = ["date", "county_fips", "state", "county", "run", "result", "drafted_by", "note"]
    good = {"date": "2026-10-16", "county_fips": "50015", "state": "VT", "county": "Lamoille",
            "run": "2026-10-16-sweep", "result": "leads", "drafted_by": D1, "note": "Two towns not online."}
    assert rl.lint_file(name, text(fields, []), text(fields, [good]), T) == []
    for change in ({"result": "done"}, {"county_fips": "5015"}):
        found = rl.lint_file(name, text(fields, []), text(fields, [{**good, **change}]), T)
        assert "LOG" in codes(found, "E"), change
    assert "LANE" not in codes(rl.lane_findings([name], "review", {}))


def test_lanes():
    layers = {"docs/codebook.md": {"writers": ["scripts/codebook.py"], "layer": "derived"},
              "data/review/restriction_worklist.csv": {"layer": "derived"}}
    research = ["data/review/restriction_sources.csv", "data/review/verification_log.csv",
                "docs/county_checks/2026-10-16_x.md", ".packets/r/x.draft.json"]
    assert rl.lane_findings(research, "review", layers) == []
    found = rl.lane_findings(["data/processed/restrictions.csv", "data/review/restriction_worklist.csv",
                              "scripts/qc_gate.py", "README.md"], "review", layers)
    assert {(f.code, f.where) for f in found} == {
        ("GENERATED", "data/processed/restrictions.csv"), ("GENERATED", "data/review/restriction_worklist.csv"),
        ("LANE", "README.md"), ("LANE", "scripts/qc_gate.py")}
    prose = rl.lane_findings(["README.md", "docs/AGENTS.md", "docs/codebook.md", "data/review/queue.csv"],
                             "prose", layers)
    assert {(f.code, f.where) for f in prose} == {("LANE", "data/review/queue.csv"), ("GENERATED", "docs/codebook.md")}


def test_the_committed_review_files_have_no_errors():
    """Every row as it stands passes the row checks (warnings allowed): the
    lint starts clean, so an error on a branch is the branch's. Checked as of
    today: a row read today is not "after today", whatever T says."""
    today = date.today()
    findings = [f for name in rl.FILES for f in rl.lint_file(name, "", rl.text_at(None, name), today,
                                                             every_row=True)]
    assert [str(f) for f in findings if f.level == "E"] == []


def test_selftest():
    assert rl.main(["--selftest"]) == 0


def test_queue_end_dates():
    fields = Q_FIELDS + ["status", "end_date"]

    def lint(**kw):
        return rl.lint_file(Q, "", text(fields, [q(entity_type="restriction", access="opened", **kw)]), T)
    assert codes(lint(status="active", end_date="2027-03-31")) == set()     # a term that runs on
    assert "DATE" in codes(lint(status="active", end_date="March 2027"), "E")
    assert "DATE" in codes(lint(status="active", end_date="2027"), "E")    # a bare year never lapses
    assert "DATE" in codes(lint(status="expired", end_date="2026-12-01"), "E")
    assert codes(lint(status="lifted", end_date="2026-01-19")) == set()
    assert codes(lint(status="expired", end_date="2026-10")) == set()      # this month: not after today
    assert "NO_END_DATE" in codes(lint(status="lifted"), "W")


def test_a_new_blank_column_does_not_change_a_row():
    base = text(Q_FIELDS, [q(reviewer_notes="")])
    migrated = text(Q_FIELDS + ["end_date"], [q(reviewer_notes="", end_date="")])
    assert rl.lint_file(Q, base, migrated, T) == []
    filled = text(Q_FIELDS + ["end_date"], [q(reviewer_notes="", end_date="2025-04-06")])
    assert rl.lint_file(Q, base, filled, T) != []      # an edited row is checked again
    spaced = text(Q_FIELDS + ["end_date"], [q(reviewer_notes=" ", end_date="")])
    assert rl.lint_file(Q, base, spaced, T) != []      # so is a whitespace-only edit
