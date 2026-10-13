"""One row per build date on which a headline number changed; nothing when
nothing moved. Synthetic metrics only."""
import json

import snapshot_manifest as sm
from common import read_csv

METRICS = {
    "restrictions": {"by_scope": {
        "renewables_only": {"instruments": 10, "severe_instruments": 4, "by_verification": {"verified": 1},
                            "by_currency": {"in_force": 9, "lapsed_unconfirmed": 1}},
        "multi_sector_data_centers": {"instruments": 2, "severe_instruments": 2, "by_verification": {}}}},
    "contested_projects": {"projects": 5, "confirmed_outcomes": 2, "by_verification": {"verified": 3}},
    "cases": {"cases": 1},
    "county_coverage": {"with_any_record": 7, "with_negative_check": 1, "with_neither": 3000},
}


def test_history_appends_only_when_a_number_changes(monkeypatch, tmp_path):
    monkeypatch.setattr(sm, "METRICS", tmp_path / "headline_metrics.json")
    monkeypatch.setattr(sm, "HISTORY", tmp_path / "headline_history.csv")
    (tmp_path / "headline_metrics.json").write_text(json.dumps(METRICS))
    row = sm.pending_history("2026-10-13")
    assert row and list(row) == sm.HISTORY_FIELDS
    assert (row["restriction_instruments"], row["restriction_lapsed"], row["projects_verified"]) == ("10", "1", "3")
    sm.append_rows(sm.HISTORY, sm.HISTORY_FIELDS, [row])
    assert sm.pending_history("2026-10-14") is None          # same numbers the next day: nothing
    changed = json.loads(json.dumps(METRICS))
    changed["contested_projects"]["confirmed_outcomes"] = 3
    (tmp_path / "headline_metrics.json").write_text(json.dumps(changed))
    nxt = sm.pending_history("2026-10-14")
    assert nxt and nxt["projects_confirmed"] == "3"
    sm.append_rows(sm.HISTORY, sm.HISTORY_FIELDS, [nxt])
    assert [r["date"] for r in read_csv(sm.HISTORY)] == ["2026-10-13", "2026-10-14"]


def test_no_metrics_file_means_nothing_to_record(monkeypatch, tmp_path):
    monkeypatch.setattr(sm, "METRICS", tmp_path / "missing.json")
    assert sm.pending_history("2026-10-13") is None
