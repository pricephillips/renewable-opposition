"""Bill outcome model: the renewables adapter (scripts/bill_outlook.py) and its shared core."""
import copy
from datetime import date

import bill_outlook as bo
import policy_outlook_core as core
from common import read_csv


def test_core_selftest_and_lock():
    core._selftest()
    assert core.lock_problems(bo.LOCK, core.__file__) == []


def test_config_precedents_trace_to_state_policies():
    cfg = bo.load_config()
    assert bo.config_problems(cfg, read_csv(bo.POLICIES)) == []


def test_config_check_catches_an_unsourced_date():
    cfg = copy.deepcopy(bo.load_config())
    cfg["precedents"][0]["date_quote"] = "effective sometime in 2024"
    cfg["precedents"][1]["state_policy_ids"] = ["XX-none-1"]
    cfg["bills"] = [{"id": "b1", "state": "MI", "group": "nope"}]
    probs = bo.config_problems(cfg, read_csv(bo.POLICIES))
    assert any("date_quote not found" in p for p in probs)
    assert any("missing from state_policies" in p for p in probs)
    assert any("missing source_url" in p for p in probs) and any("unknown group" in p for p in probs)


def test_events_from_each_table():
    ev = bo.build_events(
        [{"id": "r1", "state": "MI", "date_enacted_iso": "2025-03-01", "date_text": ""},
         {"id": "r2", "state": "MI", "date_enacted_iso": "", "date_text": "Adopted 2024"},
         {"id": "r3", "state": "MI", "date_enacted_iso": "", "date_text": "no date"}],
        [{"id": "p1", "state": "OH", "outcome": "blocked_confirmed", "resolution_date": "2023-05-01"},
         {"id": "p2", "state": "OH", "outcome": "pending", "event_date_text": "2023"}],
        [{"row_id": "q1", "source": "queue", "state": "IN", "outcome": "withdrawn", "outcome_date": "2024-01-02"},
         {"row_id": "q2", "source": "queue", "state": "IN", "outcome": "active", "outcome_date": ""}])
    assert [(e["ref"], e["kind"], e["date"]) for e in ev] == [
        ("r1", "local_restriction", "2025-03-01"), ("r2", "local_restriction", "2024"),
        ("p1", "project_blocked", "2023-05-01"), ("q1", "queue_withdrawn", "2024-01-02")]


def test_bill_gets_both_branches_and_report_has_no_banned_wording():
    cfg = copy.deepcopy(bo.load_config())
    cfg["bills"] = [{"id": "XX-HB-1", "state": "PA", "group": "limits_local", "source_url": "https://example.org"}]
    policies = read_csv(bo.POLICIES)
    res = bo.run(cfg, policies, read_csv(bo.RESTRICTIONS), read_csv(bo.PROJECTS), read_csv(bo.QUEUE),
                 date(2026, 11, 24))
    b = res["bills"][0]
    assert set(b["passes"]) == set(cfg["metrics"]) == set(b["fails"])
    for p in b["passes"].values():
        assert p["status"] in ("ok", "mixed", "too_few_precedents")
        assert p["score"] is None or -2 <= p["score"] <= 2
    assert res["stamp"]["as_of"] == "2026-11-24" and res["recent_record"]
    text = bo.report(cfg, res)
    assert core.banned_hits(text) == [] and "XX-HB-1" in text
