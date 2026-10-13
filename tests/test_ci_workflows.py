"""The GitHub Actions workflows keep the properties that hold their minutes and
storage down (docs/pipeline_comparison.md, round eight): every job has a
timeout, a pull request's superseded run is cancelled but a run on main never
is, artifacts are kept only on failure and briefly, and the intake job commits
only what intake writes."""
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def load(name: str) -> dict:
    wf = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    wf["on"] = wf.pop(True, wf.get("on"))   # YAML 1.1 reads the key `on` as True
    return wf


def test_every_job_has_a_timeout():
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for name, job in load(path.name)["jobs"].items():
            assert "timeout-minutes" in job, f"{path.name}: job {name} would run up to 360 minutes"


def test_superseded_pull_request_runs_are_cancelled_and_main_runs_never_are():
    for name in ("validate.yml", "workflow-lint.yml"):
        c = load(name)["concurrency"]
        assert "github.event.pull_request.number" in c["group"] and "github.sha" in c["group"], name
        assert c["cancel-in-progress"] == "${{ github.event_name == 'pull_request' }}", name


def test_workflows_that_commit_share_one_group_and_never_cancel():
    for name in ("build-data.yml", "source-archive.yml", "intake.yml"):
        c = load(name)["concurrency"]
        assert c == {"group": "build-data-${{ github.ref }}", "cancel-in-progress": False}, name


def test_push_runs_on_main_only():
    for name in ("validate.yml", "build-data.yml", "workflow-lint.yml"):
        assert load(name)["on"]["push"]["branches"] == ["main"], name


def test_artifacts_are_uploaded_only_on_failure_and_kept_briefly():
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for name, job in load(path.name)["jobs"].items():
            for step in job.get("steps", []):
                if "upload-artifact" in step.get("uses", ""):
                    assert step.get("if") == "failure()", f"{path.name}:{name}"
                    assert int(step["with"]["retention-days"]) <= 7, f"{path.name}:{name}"


def test_the_python_smoke_check_drives_the_ui_tests_chromium():
    """The pinned Python Playwright must match tests/ui's @playwright/test, or
    the smoke check would need a second browser download."""
    node = json.loads((ROOT / "tests" / "ui" / "package.json").read_text())["devDependencies"]["@playwright/test"]
    steps = load("validate.yml")["jobs"]["ui"]["steps"]
    pins = [m for s in steps for m in re.findall(r"playwright==([\d.]+)", s.get("run", ""))]
    assert pins == [node]


def test_intake_runs_the_intake_stages_and_commits_only_their_files():
    job = load("intake.yml")["jobs"]["intake"]
    runs = "\n".join(s.get("run", "") for s in job["steps"])
    assert "python scripts/run_pipeline.py intake" in runs
    assert "git add data/raw/ data/review/queue.csv\n" in runs
    assert "run_pipeline.py build" not in runs and "build_database" not in runs
    assert not any("upload-artifact" in s.get("uses", "") for s in job["steps"])


def test_the_already_tested_probe_fails_closed():
    """Every GitHub API call in validate.yml's skip probe checks its own exit
    status: gh api prints an error body on stdout and exits 1, and the first
    version read that body as a timestamp and skipped an untested merge."""
    job = load("validate.yml")["jobs"]["covered"]
    step = job["steps"][0]
    assert step.get("continue-on-error") is True and int(step["timeout-minutes"]) <= 3
    script = step["run"]
    calls = re.findall(r"gh api (?:[^\n]*\\\n)*[^\n]*", script)   # a call and its continued lines
    assert len(calls) == 3
    for call in calls:
        assert "|| {" in call and "full run" in call, call
    assert '-z $extra' in script and 'activity_type == "pr_merge"' in script and "created_at" in script
    for job_name in ("validate", "ui"):
        cond = load("validate.yml")["jobs"][job_name]["if"]
        assert "needs.covered.outputs.covered != 'true'" in cond and "!cancelled()" in cond
