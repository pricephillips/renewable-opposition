import json

import build_seed_outputs as bso
from common import read_csv


def test_validate_flags_missing_source_url_bad_severity_and_state():
    rows = [
        {"state": "Ohio", "technology": "wind", "restriction_type": "ban", "severity_score": 4,
         "description": "d", "source_url": "https://x.org"},
        {"state": "OH", "technology": "wind", "restriction_type": "ban", "severity_score": 5,
         "description": "d", "source_url": None},
        {"state": "Atlantis", "technology": "wind", "restriction_type": "ban", "severity_score": 2,
         "description": "d", "source_url": "https://x.org"},
    ]
    errors = bso.validate("restrictions", "r.csv", rows)
    assert rows[0]["state"] == "OH"
    assert any("row 3 missing required fields: source_url" in e for e in errors)
    assert any("row 3 severity_score 5" in e for e in errors)
    assert any("row 4" in e and "Atlantis" in e for e in errors)


def test_record_id_is_stable_and_technology_specific():
    row = {"source_url": "u", "moratorium_id": "ct-morris-2026", "technology": "solar"}
    assert bso.record_id("restrictions", row) == bso.record_id("restrictions", dict(row))
    assert bso.record_id("restrictions", row) != bso.record_id("restrictions", {**row, "technology": "wind"})


def test_full_build_writes_csv_json_and_sources(monkeypatch, tmp_path):
    monkeypatch.setattr(bso, "PROCESSED_DIR", tmp_path)
    assert bso.main() == 0
    restrictions = json.loads((tmp_path / "restrictions.json").read_text())
    assert len(restrictions) == len(read_csv(tmp_path / "restrictions.csv"))
    ids = [r["id"] for r in restrictions]
    assert len(ids) == len(set(ids))
    assert all(r["sources"] and r["source_id"].startswith("src_") for r in restrictions)
    sources = read_csv(tmp_path / "sources.csv")
    assert {s["source_id"] for s in sources} >= {r["source_id"] for r in restrictions}
    assert sum(int(s["record_count"]) for s in sources) >= len(restrictions)
