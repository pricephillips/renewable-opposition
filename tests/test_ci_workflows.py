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
    for name in ("build-data.yml", "source-archive.yml", "intake.yml", "model-inputs.yml", "cost-layer.yml"):
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


def test_the_build_commits_the_queue_matches_and_the_monthly_fetch_still_reruns_them():
    """Every build rewrites the queue matches from the contested projects it
    just built and commits them, so a merged outcome change never leaves them
    behind; model-inputs.yml reruns them after a new Queued Up edition."""
    build = load("build-data.yml")
    runs = "\n".join(s.get("run", "") for s in build["jobs"]["build-data"]["steps"])
    for path in ("data/reference/queue_matches.csv", "data/reference/queue_matches_report.md"):
        assert re.search(rf"git add [^\n]*{re.escape(path)}", runs), path
    for path in ("scripts/queue_matches.py", "data/reference/queue_projects.csv"):
        assert path in build["on"]["push"]["paths"], path
    fetch = next(s["run"] for s in load("model-inputs.yml")["jobs"]["fetch"]["steps"] if s.get("name") == "Fetch")
    assert "--only fetch_queued_up" in fetch and "--only queue_matches" in fetch and "--skip-build" in fetch


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


def test_the_cost_layer_runs_weekly_and_commits_only_its_outputs_on_main():
    """The cost layer (scripts/cost_ledger.py, scripts/cost_cfo.py) runs on a
    weekly schedule, commits only data/cost/ and only on main, and keeps the
    stale-anchor issue on main only."""
    wf = load("cost-layer.yml")
    assert [c["cron"].split()[2:] for c in wf["on"]["schedule"]] == [["*", "*", "3"]]
    assert wf["on"]["push"]["branches-ignore"] == ["main"]
    steps = wf["jobs"]["cost-layer"]["steps"]
    runs = "\n".join(s.get("run", "") for s in steps)
    assert "python scripts/cost_ledger.py" in runs and "python scripts/cost_cfo.py" in runs
    assert "set -o pipefail" in runs
    adds = re.findall(r"git add ([^\n]+)", runs)
    assert adds == ["data/cost/"]
    for s in steps:
        if "git push" in s.get("run", "") or "gh issue" in s.get("run", ""):
            assert "github.ref == 'refs/heads/main'" in s.get("if", ""), s.get("name")


def test_build_failure_issues_are_reused_and_closed_on_success():
    """A failed build on main opens one issue and comments on it after that;
    the next successful build on main closes it. Before this, nine failure
    issues from 23 October to 3 November stayed open after the build
    recovered."""
    steps = {s.get("name"): s for s in load("build-data.yml")["jobs"]["build-data"]["steps"]}
    opener = steps["Open an issue on failure (main only)"]
    closer = steps["Close failure issues once the build succeeds (main only)"]
    assert "github.ref == 'refs/heads/main'" in opener["if"] and "failure()" in opener["if"]
    assert "github.ref == 'refs/heads/main'" in closer["if"] and closer["if"].startswith("success()")
    title = "Build dashboard data failed"
    assert title in opener["with"]["script"] and "createComment" in opener["with"]["script"]
    assert title in closer["with"]["script"] and "state: 'closed'" in closer["with"]["script"]
    names = list(steps)
    assert names.index(closer["name"]) > names.index("Commit processed data")
