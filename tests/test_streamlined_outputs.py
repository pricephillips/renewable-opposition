"""County summary, data package and the pipeline runner."""
import json

import pytest

import county_summary
import datapackage
import run_pipeline
from common import write_csv


def test_county_summary_counts_instruments_and_keeps_scopes_apart():
    datasets = {
        "restrictions": [
            # One instrument, two technology rows, two counties.
            {"instrument_id": "i1", "county_fips_all": "01001;01003", "scope": "renewables_only",
             "severity_score": 4, "verification": "verified"},
            {"instrument_id": "i1", "county_fips_all": "01001;01003", "scope": "renewables_only",
             "severity_score": 2, "verification": "unverified"},
            {"instrument_id": "i2", "county_fips_all": "01001", "scope": "multi_sector_data_centers",
             "severity_score": 4},
        ],
        "contested_projects": [
            {"instrument_id": "p1", "source_record_id": "REC-1", "county_fips_all": "01001",
             "outcome": "blocked_unverified", "facility_match": "strong"},
        ],
        "cases": [{"instrument_id": "c1", "source_record_id": "REC-1"}],
    }
    standards = [{"county_fips_all": "01005", "jurisdiction": "X", "technology": "wind"},
                 {"county_fips_all": "01005", "jurisdiction": "X", "technology": "wind"}]
    checks = [{"county_fips": "01007", "checked_on": "2026-10-01"}]
    rows = {r["county_fips"]: r for r in county_summary.build(
        datasets, standards, checks, ["01001", "01003", "01005", "01007", "01009"],
        lambda f: f"County {f}", lambda f: "AL")}
    a = rows["01001"]
    assert (a["restrictions_renewables"], a["restrictions_renewables_severe"],
            a["restrictions_renewables_verified"], a["restrictions_multi_sector"]) == (1, 1, 1, 1)
    assert (a["contested_projects"], a["projects_blocked"], a["projects_matched_to_plant"], a["cases"]) == (1, 1, 1, 1)
    assert rows["01003"]["restrictions_renewables"] == 1 and rows["01003"]["cases"] == 0
    assert rows["01005"]["siting_standard_jurisdictions"] == 1
    assert [rows[f]["coverage"] for f in ("01001", "01005", "01007", "01009")] == [
        "record", "record", "negative_check", "none"]
    assert rows["01007"]["negative_check_on"] == "2026-10-01"


def test_datapackage_describes_each_published_table(tmp_path):
    write_csv(tmp_path / "cases.csv", [{"id": "cas_1", "severity_score": 3, "verification": "verified"}])
    (tmp_path / "cases.json").write_text("[]")
    pkg = datapackage.build(tmp_path)
    assert [r["name"] for r in pkg["resources"]] == ["cases"]
    res = pkg["resources"][0]
    assert res["rows"] == 1 and res["json_path"] == "cases.json"
    fields = {f["name"]: f for f in res["schema"]["fields"]}
    assert fields["severity_score"]["type"] == "integer" and fields["id"]["type"] == "string"
    assert "description" in fields["verification"]
    assert all(s["license"] for s in res["sources"])
    json.dumps(pkg)  # serializable


def test_runner_build_stages_match_the_workflow_order():
    names = [s[0] for s in run_pipeline.BUILD]
    assert names[:2] == ["promote_reviewed", "build_seed_outputs"]
    assert names.index("coverage_delta") < names.index("snapshot_manifest")
    assert [s[0] for s in run_pipeline.REFRESH][-1] == "fetch_facilities"
    for _, cmd, _, _ in run_pipeline.REFRESH + run_pipeline.BUILD:
        assert (run_pipeline.ROOT / cmd[0]).exists(), cmd


def test_runner_refuses_an_unknown_stage(monkeypatch):
    monkeypatch.setattr("sys.argv", ["run_pipeline.py", "refresh", "--only", "nope"])
    with pytest.raises(SystemExit):
        run_pipeline.main()


def test_runner_stops_at_the_first_failure(monkeypatch):
    calls = []

    def fake(stage, summary, dry_run):
        calls.append(stage[0])
        return 3 if stage[0] == "build_seed_outputs" else 0
    monkeypatch.setattr(run_pipeline, "run", fake)
    monkeypatch.setattr("sys.argv", ["run_pipeline.py"])
    assert run_pipeline.main() == 3
    assert calls == ["promote_reviewed", "build_seed_outputs"]
