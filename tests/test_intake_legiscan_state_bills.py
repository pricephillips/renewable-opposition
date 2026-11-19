"""Offline tests for scripts/fetch_legiscan.py (the weekly LegiScan state bill feed)."""
from datetime import date

import fetch_legiscan as fl
import pytest
from common import read_csv

TODAY = date(2026, 11, 19)

DATASETS = [
    {"state_id": 45, "session_id": 2101, "year_start": 2025, "year_end": 2026, "special": 0,
     "session_name": "2025-2026 Regular Session", "dataset_hash": "h1", "dataset_date": "2026-11-15"},
    {"state_id": 45, "session_id": 1900, "year_start": 2023, "year_end": 2024, "special": 0,
     "session_name": "2023-2024 Regular Session", "dataset_hash": "old", "dataset_date": "2024-06-01"},
]

MASTERLIST = {
    "session": {"session_id": 2101, "session_name": "2025-2026 Regular Session"},
    "0": {"bill_id": 501, "number": "H101", "change_hash": "c1", "url": "https://legiscan.com/VT/bill/H101/2025",
          "status_date": "2026-03-01", "status": 1, "last_action_date": "2026-03-01",
          "last_action": "Referred to Committee on Energy",
          "title": "An act relating to setbacks for solar energy facilities",
          "description": "This bill sets minimum setbacks for ground-mounted solar facilities."},
    "1": {"bill_id": 502, "number": "S20", "change_hash": "c2", "url": "https://legiscan.com/VT/bill/S20/2025",
          "status_date": "2026-02-01", "status": 1, "last_action_date": "2026-02-01", "last_action": "Read first time",
          "title": "An act relating to a solar energy tax credit",
          "description": "This bill creates an income tax credit for residential solar panels."},
    "2": {"bill_id": 503, "number": "H7", "change_hash": "c3", "url": "https://legiscan.com/VT/bill/H7/2025",
          "status_date": "2026-01-10", "status": 4, "last_action_date": "2026-05-01", "last_action": "Signed by Governor",
          "title": "An act relating to wind turbine siting and municipal approval",
          "description": "Preempts local ordinances for wind energy facilities over 10 MW."},
}

BILLS = {
    "501": {"bill_id": 501, "change_hash": "c1", "state_link": "https://legislature.vermont.gov/bill/status/2026/H.101",
            "subjects": [{"subject_id": 1, "subject_name": "Energy"}],
            "texts": [{"date": "2026-01-05", "state_link": "https://example.gov/H101-intro.pdf"},
                      {"date": "2026-03-01", "state_link": "https://example.gov/H101-amended.pdf"}]},
    "503": {"bill_id": 503, "change_hash": "c3", "state_link": "https://legislature.vermont.gov/bill/status/2026/H.7",
            "subjects": [], "texts": []},
}

CFG = fl.load_config()


class FakeClient:
    def __init__(self, masterlist=MASTERLIST, datasets=DATASETS, key="SECRETKEY"):
        self.masterlist, self.datasets, self.key = masterlist, datasets, key
        self.calls = []
        self.queries = 0

    def call(self, op, **params):
        self.calls.append((op, params))
        self.queries += 1
        if op == "getDatasetList":
            wrong_state = params.get("state") not in (None, "VT")
            return {"status": "OK", "datasetlist": [] if wrong_state else self.datasets}
        if op == "getMasterList":
            return {"status": "OK", "masterlist": self.masterlist}
        if op == "getBill":
            return {"status": "OK", "bill": BILLS[str(params["id"])]}
        raise AssertionError(op)


@pytest.fixture(autouse=True)
def _temp_outputs(monkeypatch, tmp_path):
    monkeypatch.setattr(fl, "LEADS_PATH", tmp_path / "leads.csv")
    monkeypatch.setattr(fl, "SESSIONS_PATH", tmp_path / "sessions.csv")


def _run(tmp_path, client, **kw):
    return fl.run(client, CFG, TODAY, **kw)


def test_the_filter_needs_a_technology_term_and_a_siting_term():
    m = fl.Matcher(CFG)
    assert m.match("An act relating to setbacks for solar energy facilities")[0] == ["solar"]
    assert m.match("An act relating to a solar energy tax credit") is None
    assert m.match("An act relating to county zoning for schools") is None
    techs, terms = m.match("Moratorium on battery energy storage systems in townships")
    assert techs == ["battery_storage"] and "moratorium" in terms
    assert m.match("Windstorm insurance and county roads") is None


def test_a_first_run_keeps_siting_bills_and_looks_up_their_detail(tmp_path):
    client = FakeClient()
    stats = _run(tmp_path, client)
    leads = {r["bill_id"]: r for r in read_csv(tmp_path / "leads.csv")}
    assert set(leads) == {"501", "503"}
    assert leads["501"]["state"] == "VT" and leads["501"]["review_status"] == "lead"
    assert leads["501"]["text_url"] == "https://example.gov/H101-amended.pdf"
    assert leads["501"]["subjects"] == "Energy"
    assert leads["503"]["status"] == "Passed" and leads["503"]["technology"] == "wind"
    assert leads["503"]["change_hash"] == "c3"
    # Only the current session is read; the 2023-2024 one is past.
    assert [p for op, p in client.calls if op == "getMasterList"] == [{"id": "2101"}]
    assert stats["bills_kept"] == 2 and stats["new_leads"] == 2 and stats["queries"] == 4


def test_an_unchanged_session_costs_one_query(tmp_path):
    _run(tmp_path, FakeClient())
    client = FakeClient()
    stats = _run(tmp_path, client)
    assert [op for op, _ in client.calls] == ["getDatasetList"]
    assert stats["sessions_unchanged"] == 1


def test_a_changed_bill_is_looked_up_again_and_review_fields_survive(tmp_path):
    _run(tmp_path, FakeClient())
    rows = read_csv(tmp_path / "leads.csv")
    for r in rows:
        if r["bill_id"] == "503":
            r.update(review_status="pending", reviewer="agent:x", review_note="read the act")
    fl.write_csv(tmp_path / "leads.csv", rows, fl.LEAD_FIELDS)

    ml = {k: dict(v) for k, v in MASTERLIST.items()}
    ml["2"]["change_hash"] = "c3b"
    ml["2"]["last_action"] = "Effective July 1"
    datasets = [dict(DATASETS[0], dataset_hash="h2")]
    client = FakeClient(masterlist=ml, datasets=datasets)
    _run(tmp_path, client)
    assert [p["id"] for op, p in client.calls if op == "getBill"] == ["503"]
    lead = {r["bill_id"]: r for r in read_csv(tmp_path / "leads.csv")}["503"]
    assert lead["review_status"] == "pending" and lead["review_note"] == "read the act"
    assert lead["last_action"] == "Effective July 1" and lead["first_seen"] == "2026-11-19"


def test_the_lookup_cap_defers_the_rest_to_the_next_run(tmp_path):
    stats = _run(tmp_path, FakeClient(), max_bills=1)
    assert stats["bills_looked_up"] == 1 and stats["lookups_deferred"] == 1
    client = FakeClient()
    stats = _run(tmp_path, client, max_bills=5)
    assert [op for op, _ in client.calls] == ["getDatasetList", "getBill"]
    assert all(r["change_hash"] for r in read_csv(tmp_path / "leads.csv"))


def test_a_state_filter_asks_legiscan_for_that_state_only(tmp_path):
    client = FakeClient()
    _run(tmp_path, client, states={"VT"})
    assert client.calls[0] == ("getDatasetList", {"state": "VT"})
    fl.LEADS_PATH.unlink()
    fl.SESSIONS_PATH.unlink()
    client = FakeClient()
    _run(tmp_path, client, states={"NH"})
    assert [op for op, _ in client.calls] == ["getDatasetList"]


def test_the_key_never_appears_in_an_error(monkeypatch):
    import requests

    client = fl.Client("SECRETKEY", "https://api.legiscan.com/")

    def boom(*a, **k):
        raise requests.ConnectionError("failed: https://api.legiscan.com/?key=SECRETKEY&op=getBill")

    monkeypatch.setattr(client.session, "get", boom)
    monkeypatch.setattr(fl.time, "sleep", lambda s: None)
    with pytest.raises(fl.LegiScanError) as e:
        client.call("getBill", id=1)
    assert "SECRETKEY" not in str(e.value) and "***" in str(e.value)


def test_no_key_skips_quietly(monkeypatch, capsys):
    monkeypatch.delenv(fl.KEY_ENV, raising=False)
    assert fl.main([]) == 0
    assert "not set" in capsys.readouterr().out
