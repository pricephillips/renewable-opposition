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
    monkeypatch.setattr(parse, "SEED_PATHS", {e: seed / f"{e}.csv" for e in ("restriction", "contested_project", "case")})
    monkeypatch.setattr(parse, "CITED_PATHS", [])
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
    assert parse.main() == 0
    queue = common.read_csv(review / "queue.csv")
    # Machine-harvested rows enter as leads, each with its own queue_id, and
    # the raw file is recorded relative to the repository.
    assert len(queue) == 2 and {q["review_status"] for q in queue} == {"lead"}
    assert len({q["queue_id"] for q in queue}) == 2 and all(q["queue_id"].startswith("q_") for q in queue)
    assert {q["raw_path"] for q in queue} == {"data/raw/courtlistener_renewables/abc.json"}

    parse.main()  # already parsed: nothing new is queued
    assert len(common.read_csv(review / "queue.csv")) == 2

    # Search API results are index text: they wait until the opinion is opened, and
    # no one confirms anything; filling the fields the API lacks is the rest.
    assert {q["access"] for q in queue} == {"snippet"}
    queue[0].update(state="IA", severity_score="3", access="opened")
    common.write_csv(review / "queue.csv", queue)
    monkeypatch.setattr("sys.argv", ["promote_reviewed.py"])
    # A lead is never promoted, however complete, until someone triages it.
    assert promote_reviewed.main() == 0
    assert not common.read_csv(seed / "cases_seed.csv")

    queue[0].update(review_status="pending", access="snippet")
    common.write_csv(review / "queue.csv", queue)
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
    # The second extractor row is still an untriaged lead: it waits, never guessed.
    after = common.read_csv(review / "queue.csv")
    assert [q["review_status"] for q in after] == ["promoted", "lead"]
    assert after[0]["queue_id"] == queue[0]["queue_id"]  # the intake key is kept on promotion

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


def test_a_candidate_the_repository_already_holds_is_not_queued_twice():
    def cand(**kw):
        base = dict(source_id="src_a", entity_type="restriction", state="KS", county="Cherokee County",
                    source_url="https://county.gov/ordinance.pdf", description="d")
        return parse.CandidateRecord(**{**base, **kw})

    queue = [{"entity_type": "restriction", "state": "KS", "county": "Cherokee County", "source_id": "web_x",
              "source_url": "https://COUNTY.gov/ordinance.pdf/", "review_status": "promoted"}]
    seeds = {"contested_project": [{"state": "KS", "project_name": "Rainbow Springs Solar",
                                    "source_url": "https://news.example.org/a", "pinned_id": "con_1"}],
             "restriction": [], "case": []}
    known = parse.Known(queue, seeds)
    kept, dropped = parse.dedupe([
        cand(),                                                        # same document as the queue row
        cand(county="Elk County", source_url="https://elk.gov/o.pdf"),  # new
        cand(county="Elk County", source_url="https://elk.gov/o.pdf"),  # a second copy in the batch
        cand(entity_type="contested_project", county="", project_name="rainbow springs solar",
             source_url="https://other.example.org/b"),                # the seed's project, another URL
        cand(entity_type="case", county="", project_name="X v. Y", source_url=""),   # no URL: kept
    ], known)
    assert [c.county or c.project_name for c in kept] == ["Elk County", "rainbow springs solar", "X v. Y"]
    assert len(dropped) == 2 and "queue row from web_x" in dropped[0] and "src_a" in dropped[1]
    assert kept[1].reviewer_notes.startswith("possible duplicate of seed con_1")
    assert kept[0].reviewer_notes == ""
