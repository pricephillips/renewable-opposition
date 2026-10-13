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


def test_a_case_that_names_no_published_record_is_reported_not_quarantined():
    datasets = {
        "contested_projects": [{"source_record_id": "REC-1"}],
        "restrictions": [{"source_record_id": "REC-2"}],
        "cases": [{"id": "c1", "state": "KS", "source_record_id": "REC-1"},
                  {"id": "c2", "state": "KS", "source_record_id": "REC-2"},
                  {"id": "c3", "state": "KS", "source_record_id": "REC-9"},
                  {"id": "c4", "state": "KS", "source_record_id": ""}],
    }
    found = qc_gate.check_links(datasets)
    assert [f["id"] for f in found] == ["c3"] and not found[0]["blocked"]
    assert found[0]["issues"][0]["code"] == "LINK_MISSING" and "REC-9" in found[0]["issues"][0]["detail"]
    assert qc_gate.check_links({"cases": []}) == []
    assert "LINK_MISSING" in {c[0] for c in qc_gate.CHECKS}
