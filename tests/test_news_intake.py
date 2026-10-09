"""Harvested news never writes to a seed or a published file: parse.py and every
extractor write candidates to data/review/ only, and they go through the same
review and promotion gates as hand-entered rows (README, roadmap)."""
from pathlib import Path

import layer_audit as la

ROOT = Path(__file__).resolve().parent.parent
# parse.py's own bookkeeping: which raw files it has parsed. Not a record.
PARSE_STATE = "data/raw/parse_state.csv"


def targets(rel: str) -> set[str]:
    found, unresolved = la.module_writes(ROOT / rel, la.common_env(), rel=rel)
    assert unresolved == [], unresolved      # every write must be visible to this check
    return found


def test_parse_writes_candidates_to_review_only():
    found = targets("scripts/parse.py") - {PARSE_STATE}
    assert found == {"data/review/queue.csv"}
    assert not [t for t in targets("scripts/parse.py") if t.startswith(("data/seed", "data/processed"))]


def test_every_extractor_writes_to_review_or_nowhere():
    extractors = sorted((ROOT / "scripts" / "extractors").glob("*.py"))
    assert extractors
    for path in extractors:
        rel = path.relative_to(ROOT).as_posix()
        assert all(t.startswith("data/review/") for t in targets(rel)), rel


def test_queue_rows_reach_a_seed_only_through_promote_reviewed():
    import json
    layers = json.loads((ROOT / "config" / "layers.json").read_text(encoding="utf-8"))["files"]
    for seed in ("data/seed/restrictions_seed.csv", "data/seed/contested_projects_seed.csv",
                 "data/seed/cases_seed.csv"):
        assert "scripts/parse.py" not in layers[seed]["writers"]
        assert not any("extractors" in w for w in layers[seed]["writers"])
    assert layers["data/review/queue.csv"]["writers"] == ["scripts/parse.py", "scripts/promote_reviewed.py"]
