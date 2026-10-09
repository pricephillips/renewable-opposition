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

    # Search API results are index text: they wait until the opinion is opened, and
    # no one confirms anything; filling the fields the API lacks is the rest.
    assert {q["access"] for q in queue} == {"snippet"}
    queue[0].update(state="IA", severity_score="3")
    common.write_csv(review / "queue.csv", queue)
    monkeypatch.setattr("sys.argv", ["promote_reviewed.py"])
    assert promote_reviewed.main() == 0
    assert not common.read_csv(seed / "cases_seed.csv")

    queue[0].update(access="opened")
    common.write_csv(review / "queue.csv", queue)
    assert promote_reviewed.main() == 0
    cases = common.read_csv(seed / "cases_seed.csv")
    assert len(cases) == 1 and cases[0]["docket_number"] == "23-0001"
    assert not [f for f in build_seed_outputs.REQUIRED["cases"] if not cases[0].get(f)]
    assert "promoted automatically" in cases[0]["reviewer_notes"]
    header = (seed / "cases_seed.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    n = len(promote_reviewed.CASE_FIELDS)
    # Only the evidence and link columns are added to the seed.
    assert header[:n] == promote_reviewed.CASE_FIELDS
    assert set(header[n:]) <= set(promote_reviewed.EVIDENCE_COLUMNS)
    # The second extractor row has no state or severity: it waits, never guessed.
    assert [q["review_status"] for q in common.read_csv(review / "queue.csv")] == ["promoted", "pending"]

    assert promote_reviewed.main() == 0  # idempotent
    assert len(common.read_csv(seed / "cases_seed.csv")) == 1


def test_promote_case_candidate_requires_case_fields(monkeypatch, tmp_path):
    _, review, seed = _patch_paths(monkeypatch, tmp_path)
    base = {"state": "AL", "project_name": "Noccalula Wind Energy Center", "technology": "wind",
            "source_record_id": "REC-0005", "linked_entity": "contested_project"}
    found = {"case_name": "Residents v. Developer", "court": "Etowah County Circuit Court",
             "court_level": "state_trial", "case_source_url": "https://example.org/docket"}
    common.write_csv(review / "cases_candidates.csv", [
        {**base, "review_status": "confirmed", **found},
        {**base, "review_status": "needs_docket_research", **found, "case_name": "Researched v. Row"},
        {**base, "review_status": "rejected", **found, "case_name": "Rejected v. Row"},
        {**base, "review_status": "lead", **found, "case_name": "News v. Row",
         "case_source_url": "example.org/story"},
        {**base, "review_status": "confirmed", "case_name": "Incomplete v. Row"},
        {**base, "review_status": "needs_docket_research"},
    ])
    monkeypatch.setattr("sys.argv", ["promote_reviewed.py"])
    promote_reviewed.main()
    cases = common.read_csv(seed / "cases_seed.csv")
    assert [c["case_name"] for c in cases] == ["Residents v. Developer", "Researched v. Row"]
    assert cases[0]["severity_score"] == "3"
    assert "promoted automatically" not in cases[0]["reviewer_notes"]   # a person confirmed it
    assert "not reviewed by hand" in cases[1]["reviewer_notes"]
    statuses = [r["review_status"] for r in common.read_csv(review / "cases_candidates.csv")]
    assert statuses == ["promoted", "promoted", "rejected", "lead", "confirmed", "needs_docket_research"]


QUEUE_ROW = {"source_id": "manual", "entity_type": "restriction", "review_status": "pending",
             "state": "IA", "county": "Linn County", "jurisdiction_type": "County", "technology": "solar",
             "severity_score": "2", "description": "300 ft solar setback from dwellings.",
             "source_url": "https://www.linncountyiowa.gov/minutes", "restriction_type": "setback",
             "adopted_date": "2023-09-20", "effective_date": "2023-09-28", "reviewer_notes": "seen in minutes",
             "access": "opened", "mechanisms": "setback", "mechanism_detail": "Panels 300 ft from dwellings.",
             "status": "active"}


def test_a_complete_queue_row_is_promoted_into_the_seed_columns(monkeypatch, tmp_path):
    _, review, seed = _patch_paths(monkeypatch, tmp_path)
    real = Path(__file__).resolve().parent.parent / "data" / "seed" / "restrictions_seed.csv"
    header = real.read_text(encoding="utf-8").splitlines()[0].split(",")
    common.write_csv(seed / "restrictions_seed.csv",
                     [{**{k: "" for k in header}, "state": "OH", "source": "Moratorium Nation x"}], header)
    common.write_csv(review / "queue.csv", [
        QUEUE_ROW,
        {**QUEUE_ROW, "county": "Benton County", "review_status": "rejected"},
        {**QUEUE_ROW, "county": "Jones County", "description": ""},
        {**QUEUE_ROW, "county": "Story County", "source_url": "not a url"},
        {**QUEUE_ROW, "county": "Polk County", "access": "snippet"},
    ])
    monkeypatch.setattr("sys.argv", ["promote_reviewed.py"])
    assert promote_reviewed.main() == 0
    rows = common.read_csv(seed / "restrictions_seed.csv")
    assert list(rows[0])[:len(header)] == header         # only evidence and link columns are added
    assert set(list(rows[0])[len(header):]) <= set(promote_reviewed.EVIDENCE_COLUMNS)
    (r,) = rows[1:]
    assert (r["jurisdiction"], r["jurisdiction_type"], r["date_enacted_iso"], r["status"]) == \
        ("Linn County", "County", "2023-09-20", "active")
    assert r["source"] == "review queue: manual"
    assert r["notes"].startswith("effective 2023-09-28; seen in minutes; promoted automatically")
    assert r["long_description"] == "Panels 300 ft from dwellings."
    assert [q["review_status"] for q in common.read_csv(review / "queue.csv")] == \
        ["promoted", "rejected", "pending", "pending", "pending"]
    assert promote_reviewed.main() == 0                  # idempotent
    assert common.read_csv(seed / "restrictions_seed.csv") == rows


def test_the_data_build_promotes_before_it_builds_and_commits_the_seeds():
    import run_pipeline
    wf = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "build-data.yml").read_text()
    # The workflow runs the build stages from scripts/run_pipeline.py, which
    # promotes before it builds.
    assert "python scripts/run_pipeline.py build" in wf
    names = [s[0] for s in run_pipeline.BUILD]
    assert names.index("promote_reviewed") < names.index("build_seed_outputs")
    assert "git add data/seed/ data/review/queue.csv data/review/cases_candidates.csv" in wf
    for path in ("data/review/queue.csv", "data/review/cases_candidates.csv",
                 "data/review/place_overrides.csv", "scripts/promote_reviewed.py"):
        assert f"- '{path}'" in wf, path
