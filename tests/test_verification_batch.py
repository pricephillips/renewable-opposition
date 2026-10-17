"""The daily verification routine's batch picker: located sources first,
worklist order otherwise, and nothing attempted in the last SKIP_DAYS days."""
from datetime import date

import verification_batch as vb

TODAY = date(2026, 10, 14)


def r(iid, priority, located=""):
    return {"priority": str(priority), "instrument_id": iid, "state": "KS", "jurisdiction": iid,
            "technologies": "wind", "tier": "compiled_record", "legal_basis": "", "located_url": located,
            "search_query": f"q {iid}"}


def o(rid, priority):
    return {"priority": str(priority), "source_record_id": rid, "state": "IA", "project_name": rid,
            "outcome": "blocked_unverified", "what_would_confirm": "a news article", "located_url": "",
            "search_query": f"q {rid}"}


def test_located_first_then_worklist_order_and_counts():
    rows = [r("a", 1), r("b", 2), r("c", 3, located="https://example.gov/c.pdf"), r("d", 4)]
    batch = vb.pick(rows, [o("p1", 1), o("p2", 2)], [], TODAY, n_restrictions=3, n_outcomes=1)
    assert [b["key"] for b in batch] == ["c", "a", "b", "p1"]
    assert [b["queue"] for b in batch] == ["restriction"] * 3 + ["outcome"]


def test_recent_attempts_are_skipped_and_come_back_after_the_window():
    rows = [r("a", 1), r("b", 2), r("c", 3)]
    log = [{"date": "2026-10-13", "queue": "restriction", "key": "a", "outcome": "not_read"},
           {"date": "2026-09-01", "queue": "restriction", "key": "b", "outcome": "not_read"},
           {"date": "2026-10-13", "queue": "outcome", "key": "c", "outcome": "written"}]   # other queue
    assert [b["key"] for b in vb.pick(rows, [], log, TODAY, 2, 0)] == ["b", "c"]
    later = date(2026, 10, 28)                                  # 15 days on: a is due again
    assert [b["key"] for b in vb.pick(rows, [], log, later, 3, 0)] == ["a", "b", "c"]


def test_bad_log_dates_and_duplicates_are_ignored():
    rows = [r("a", 1), r("a", 2), r("b", 3)]
    log = [{"date": "yesterday", "queue": "restriction", "key": "b"}]
    assert [b["key"] for b in vb.pick(rows, [], log, TODAY, 5, 0)] == ["a", "b"]


def test_the_log_vocabulary_and_the_window_match_the_routine_doc():
    from pathlib import Path
    doc = (Path(__file__).resolve().parent.parent / "docs" / "VERIFICATION_ROUTINE.md").read_text(encoding="utf-8")
    for outcome in vb.LOG_OUTCOMES:
        assert f"`{outcome}`" in doc, outcome
    assert f"{vb.SKIP_DAYS} days" in doc
    assert ",".join(vb.LOG_FIELDS) == vb.LOG.read_text(encoding="utf-8").splitlines()[0]


def p(iid, currency="unknown", severity=2, tech="wind"):
    return {"instrument_id": iid, "state": "NE", "jurisdiction": iid, "technology": tech, "currency": currency,
            "severity_score": str(severity), "legal_basis": ""}


def test_status_rows_take_unsettled_instruments_once_ranked_by_county_impact():
    published = [p("a"), p("a", tech="solar", severity=3), p("b", severity=4), p("c"), p("d", currency="in_force"),
                 p("e", currency="lapsed_unconfirmed"), p("f")]
    work = [{"instrument_id": "c", "county_impact": "sole_severe", "priority": "9"},
            {"instrument_id": "e", "county_impact": "sole_record", "priority": "1"},
            {"instrument_id": "b", "priority": "2", "located_url": "https://example.gov/b.pdf"}]
    rows = vb.status_rows(published, work, [{"instrument_id": "f"}])         # f is settled
    assert [x["instrument_id"] for x in rows] == ["c", "e", "b", "a"]          # d is in force
    assert rows[3]["technologies"] == "wind;solar" and rows[3]["tier"].startswith("severity 3")
    batch = vb.pick([], [], [{"date": "2026-10-13", "queue": "status", "key": "c", "outcome": "not_read"}],
                    TODAY, 0, 0, rows, 2)
    assert [(b["queue"], b["key"]) for b in batch] == [("status", "b"), ("status", "e")]  # located first
