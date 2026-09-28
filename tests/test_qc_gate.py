import qc_gate
import state_bounds


def test_qc_gate_selftest():
    assert qc_gate.selftest() == 0


def test_state_bounds_selftest():
    assert state_bounds.selftest() == 0


def test_blocked_row_is_quarantined_not_dropped():
    rows = [
        {"id": "ok", "state": "VA", "status": "active", "source_url": "https://x.org"},
        {"id": "bad", "state": "PA", "latitude": 32.5, "longitude": -91.6, "status": "active",
         "source_url": "https://x.org"},
    ]
    passed, quarantined, findings = qc_gate.run("restrictions", rows)
    assert [r["id"] for r in passed] == ["ok"]
    assert [r["id"] for r in quarantined] == ["bad"]
    assert quarantined[0]["qc_issues"][0]["code"] == "COORD_OUTSIDE_STATE"
