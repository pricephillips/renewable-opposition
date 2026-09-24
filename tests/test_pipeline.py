"""fetch manifest -> parse.py extractor -> review queue -> promote_reviewed -> seed."""
import csv
import shutil
from pathlib import Path

import build_seed_outputs
import common
import parse
import promote_reviewed
from extractors import courtlistener_renewables as cl

FIXTURE = Path(__file__).parent / "fixtures" / "courtlistener_search.json"


def test_courtlistener_extractor_keeps_only_renewables_cases():
    rows = cl.extract(FIXTURE, {"source_id": "courtlistener_renewables"})
    assert [r["project_name"] for r in rows] == [
        "Example Residents v. County Board of Supervisors",
        "Solar Developer LLC v. Township",
    ]
    first, second = rows
    assert first["technology"] == "wind" and first["court_level"] == "state_appellate"
    assert first["source_url"] == "https://www.courtlistener.com/opinion/1/example-residents-v-county-board/"
    assert "<mark>" not in first["evidence_text"]
    assert second["technology"] == "solar" and second["court_level"] == "federal_district"


def test_court_level_mapping():
    assert cl.court_level("ca8", "Court of Appeals for the Eighth Circuit") == "federal_appellate"
    assert cl.court_level("iowa", "Supreme Court of Iowa") == "state_supreme"
    assert cl.court_level("nysupct", "New York Supreme Court") == ""


def _patch_paths(monkeypatch, tmp_path):
    raw = tmp_path / "data" / "raw"
    review = tmp_path / "data" / "review"
    seed = tmp_path / "data" / "seed"
    for d in (raw / "courtlistener_renewables", review, seed):
        d.mkdir(parents=True)
    monkeypatch.setattr(parse, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(parse, "MANIFEST_PATH", raw / "manifest.csv")
    monkeypatch.setattr(parse, "PARSE_STATE_PATH", raw / "parse_state.csv")
    monkeypatch.setattr(parse, "QUEUE_PATH", review / "queue.csv")
    monkeypatch.setattr(promote_reviewed, "QUEUE_PATH", review / "queue.csv")
    monkeypatch.setattr(promote_reviewed, "CANDIDATES_PATH", review / "cases_candidates.csv")
    monkeypatch.setattr(promote_reviewed, "SEED_FOR", {
        "restriction": ("restrictions", seed / "restrictions_seed.csv"),
        "contested_project": ("contested_projects", seed / "contested_projects_seed.csv"),
        "case": ("cases", seed / "cases_seed.csv"),
    })
    return raw, review, seed


def test_parse_then_promote_round_trip(monkeypatch, tmp_path):
    raw, review, seed = _patch_paths(monkeypatch, tmp_path)
    stored = raw / "courtlistener_renewables" / "abc.json"
    shutil.copy(FIXTURE, stored)
    with (raw / "manifest.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source_id", "url", "fetch_date", "content_type",
                                          "status_code", "content_hash", "local_path", "error"])
        w.writeheader()
        w.writerow({"source_id": "courtlistener_renewables", "url": "u", "content_hash": "abc",
                    "local_path": "data/raw/courtlistener_renewables/abc.json", "error": ""})

    monkeypatch.setattr("sys.argv", ["parse.py"])
    parse.main()
    queue = common.read_csv(review / "queue.csv")
    assert len(queue) == 2 and {q["review_status"] for q in queue} == {"pending"}

    parse.main()  # already parsed: nothing new is queued
    assert len(common.read_csv(review / "queue.csv")) == 2

    queue[0].update(review_status="confirmed", state="IA", severity_score="3")
    common.write_csv(review / "queue.csv", queue)
    monkeypatch.setattr("sys.argv", ["promote_reviewed.py"])
    assert promote_reviewed.main() == 0
    cases = common.read_csv(seed / "cases_seed.csv")
    assert len(cases) == 1 and cases[0]["docket_number"] == "23-0001"
    assert not [f for f in build_seed_outputs.REQUIRED["cases"] if not cases[0].get(f)]
    assert common.read_csv(review / "queue.csv")[0]["review_status"] == "promoted"

    assert promote_reviewed.main() == 0  # idempotent
    assert len(common.read_csv(seed / "cases_seed.csv")) == 1


def test_promote_case_candidate_requires_case_fields(monkeypatch, tmp_path):
    _, review, seed = _patch_paths(monkeypatch, tmp_path)
    base = {"state": "AL", "project_name": "Noccalula Wind Energy Center", "technology": "wind",
            "source_record_id": "REC-0005", "linked_entity": "contested_project"}
    common.write_csv(review / "cases_candidates.csv", [
        {**base, "review_status": "confirmed", "case_name": "Residents v. Developer",
         "court": "Etowah County Circuit Court", "court_level": "state_trial",
         "case_source_url": "https://example.org/docket"},
        {**base, "review_status": "confirmed", "case_name": "Incomplete v. Row"},
        {**base, "review_status": "needs_docket_research"},
    ])
    monkeypatch.setattr("sys.argv", ["promote_reviewed.py"])
    promote_reviewed.main()
    cases = common.read_csv(seed / "cases_seed.csv")
    assert [c["case_name"] for c in cases] == ["Residents v. Developer"]
    assert cases[0]["severity_score"] == "3"
    statuses = [r["review_status"] for r in common.read_csv(review / "cases_candidates.csv")]
    assert statuses == ["promoted", "confirmed", "needs_docket_research"]
