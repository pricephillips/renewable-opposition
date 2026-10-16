"""The lane hook (.claude/hooks/agent_lane.py): what each agent role may read
and write (docs/AGENTS.md)."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / ".claude" / "hooks" / "agent_lane.py"
_spec = importlib.util.spec_from_file_location("agent_lane", HOOK)
lane = importlib.util.module_from_spec(_spec)
sys.modules["agent_lane"] = lane
_spec.loader.exec_module(lane)

R = str(ROOT)


def bash(lane_name, command, cwd=R):
    return lane.decide(lane_name, {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd})


def tool(lane_name, name, cwd=R, **inp):
    return lane.decide(lane_name, {"tool_name": name, "tool_input": inp, "cwd": cwd})


def ok(result):
    return result == ""


# ── Every lane ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", sorted(lane.LANES))
def test_no_lane_reaches_reports_from_local_contacts(name):
    assert not ok(bash(name, "cat ~/.renewable-opposition/local_knowledge.csv"))
    assert not ok(bash(name, "head \"$RO_LOCAL_KNOWLEDGE\""))
    assert not ok(tool(name, "Read", file_path=f"{R}/data/review/local_knowledge.csv"))
    assert not ok(tool(name, "Grep", pattern="claim", path=f"{R}/data/review", glob="local_knowledge*"))
    assert not ok(bash(name, "python3 scripts/site_profile.py --fips 19113"))
    # A profile prints pending review rows, so a blind reviewer runs none at all.
    assert ok(bash(name, "python3 scripts/site_profile.py --fips 19113 --no-local")) == (name != "blind")


@pytest.mark.parametrize("name", sorted(lane.LANES))
def test_no_lane_stages_commits_pushes_or_moves_a_branch(name):
    for cmd in ("git commit -m x", "git push -u origin b", "git add data/review/queue.csv",
                "git checkout main", "git reset --hard", "git branch -D x", "git rebase main",
                "git -C /tmp/x commit -m y", "bash -c 'git push'", "git status && git push"):
        assert not ok(bash(name, cmd)), (name, cmd)


@pytest.mark.parametrize("name", sorted(set(lane.LANES) - {"blind"}))
def test_looking_with_git_is_fine(name):
    for cmd in ("git status", "git diff origin/main -- data/review", "git log --oneline -5",
                "git -C /tmp show HEAD:README.md", "git fetch origin main", "git branch --show-current",
                "git merge-base HEAD origin/main"):
        assert ok(bash(name, cmd)), (name, cmd)


@pytest.mark.parametrize("name", sorted(lane.LANES))
def test_no_lane_edits_in_place_from_the_shell(name):
    assert not ok(bash(name, "sed -i 's/a/b/' data/review/queue.csv"))
    assert not ok(bash(name, "sed --in-place=.bak 's/a/b/' docs/x.md"))
    assert not ok(bash(name, "perl -pi -e 's/a/b/' README.md"))
    assert ok(bash(name, "sed -n 1,5p README.md"))
    assert ok(bash(name, "perl -ne 'print if /x/' README.md"))


# ── reader ───────────────────────────────────────────────────────────────────

def test_reader_writes_only_its_packet_or_outside_the_repository():
    assert ok(tool("reader", "Write", file_path=f"{R}/.packets/r1/restriction/X.draft.json"))
    assert ok(tool("reader", "Write", file_path="/tmp/notes.txt"))
    for path in ("data/review/queue.csv", "data/processed/restrictions.csv", "scripts/x.py", "README.md"):
        assert not ok(tool("reader", "Write", file_path=f"{R}/{path}")), path
        assert not ok(tool("reader", "Edit", file_path=f"{R}/{path}")), path


def test_reader_shell_output_goes_outside_the_repository():
    assert ok(bash("reader", "curl -sSL https://county.gov/o.pdf -o /tmp/o.pdf && pdftotext /tmp/o.pdf -"))
    assert ok(bash("reader", "echo hi > /tmp/x 2>&1; echo again >> .packets/r1/log.txt"))
    assert ok(bash("reader", "wget -q -O /tmp/page.html https://county.gov/"))
    assert ok(bash("reader", "wget https://county.gov/o.pdf", cwd="/tmp"))
    assert not ok(bash("reader", "curl -sSLo o.pdf https://county.gov/o.pdf"))
    assert not ok(bash("reader", "curl -LO https://county.gov/o.pdf"))
    assert not ok(bash("reader", "wget https://county.gov/o.pdf"))
    assert not ok(bash("reader", "echo x > data/review/queue.csv"))
    assert not ok(bash("reader", "cd data && echo x >> review/queue.csv"))
    assert not ok(bash("reader", "printf x | tee data/review/notes.txt"))
    assert not ok(bash("reader", "cp /tmp/o.pdf data/raw/o.pdf"))
    assert not ok(bash("reader", "pdftotext /tmp/o.pdf o.txt"))
    assert not ok(bash("reader", "rm -f data/processed/qc_report.md"))


def test_reader_runs_only_scripts_that_write_nothing():
    assert ok(bash("reader", "python3 scripts/review_packets.py card restriction mn:ks-x"))
    assert ok(bash("reader", "python3 scripts/verification_batch.py --csv"))
    assert ok(bash("reader", "python3 -c 'import csv; print(1)'"))
    assert ok(bash("reader", "python3 /tmp/parse_pdf.py /tmp/o.pdf"))
    for script in ("build_seed_outputs.py", "run_pipeline.py", "promote_reviewed.py", "verification_worklist.py"):
        assert not ok(bash("reader", f"python3 scripts/{script}")), script
    assert ok(bash("reader", "python3 scripts/promote_reviewed.py --dry-run"))


def test_a_quoted_angle_bracket_is_an_argument_not_a_redirection():
    assert ok(bash("reader", 'grep -n "> 1000 feet" /tmp/ordinance.txt'))
    assert ok(bash("reader", "grep -c '>500' /tmp/o.txt > /tmp/count"))
    assert not ok(bash("reader", 'echo "x" >"data/review/queue.csv"'))
    assert not ok(bash("reader", "echo x 1> data/review/queue.csv"))
    assert ok(bash("blind", "wc -l < /tmp/o.txt"))
    assert not ok(bash("blind", "cd data && wc -l < review/queue.csv"))
    assert lane._tokens("a 'b c' \"d\\\"e\" f\\ g") == [
        ("a", "a"), ("'b c'", "b c"), ('"d\\"e"', 'd"e'), ("f\\ g", "f g")]


def test_heredoc_bodies_are_data_not_commands():
    cmd = "cat > /tmp/note.md <<'EOF'\ngit commit -m 'not a command'\nrm -rf data\nEOF\nwc -l /tmp/note.md"
    assert ok(bash("reader", cmd))
    assert ok(bash("reader", "tee /tmp/x << EOF\nhello\nEOF"))
    assert not ok(bash("reader", "cat <<EOF > data/review/x.csv\na,b\nEOF"))


# ── blind ────────────────────────────────────────────────────────────────────

def test_blind_reviewer_never_sees_review_files_or_drafts():
    assert not ok(tool("blind", "Read", file_path=f"{R}/data/review/queue.csv"))
    assert not ok(tool("blind", "Read", file_path=f"{R}/.packets/r1/restriction/X.draft.json"))
    assert not ok(tool("blind", "Read", file_path=f"{R}/.packets/r1/drafts/X.json"))
    assert ok(tool("blind", "Read", file_path=f"{R}/.packets/r1/restriction/X.blind.json"))
    assert ok(tool("blind", "Read", file_path=f"{R}/data/processed/restrictions.csv"))
    assert not ok(bash("blind", "cat data/review/restriction_sources.csv"))
    assert not ok(bash("blind", "cd data && grep REC review/queue.csv"))
    assert not ok(bash("blind", "cat data/*/queue.csv"))
    assert not ok(bash("blind", "cat .packets/r1/restriction/X.draft.json"))
    assert not ok(bash("blind", "python3 -c \"open('data/review/queue.csv').read()\""))
    assert ok(bash("blind", "grep -n 'REC-0122' data/processed/restrictions.csv"))
    assert ok(bash("blind", "python3 scripts/review_packets.py check .packets/r1/restriction/X.review.json"))
    for cmd in ("python3 scripts/review_packets.py card restriction mn:x",
                "python3 scripts/review_packets.py blind-row lead q_1", "python3 scripts/review_lint.py",
                "python3 scripts/verification_batch.py"):
        assert not ok(bash("blind", cmd)), cmd


def test_blind_reviewer_searches_only_where_the_lane_can_check():
    assert not ok(bash("blind", "grep -rn Cherokee ."))
    assert not ok(bash("blind", "rg Cherokee"))
    assert not ok(bash("blind", "find . -name '*.csv' -exec grep -l Cherokee {} +"))
    assert not ok(bash("blind", "ls | xargs cat"))
    assert not ok(bash("blind", "git log -p"))
    assert not ok(tool("blind", "Grep", pattern="Cherokee"))
    assert not ok(tool("blind", "Grep", pattern="Cherokee", path=f"{R}/data"))
    assert not ok(tool("blind", "Grep", pattern="Cherokee", path=f"{R}/data/processed", glob="*draft*"))
    assert ok(tool("blind", "Grep", pattern="Cherokee", path=f"{R}/data/processed"))
    assert ok(tool("blind", "Grep", pattern="MECHANISM_TYPE", path=f"{R}/scripts"))


def test_blind_reviewer_writes_its_review_packet_never_a_draft():
    assert ok(tool("blind", "Write", file_path=f"{R}/.packets/r1/restriction/X.review.json"))
    assert not ok(tool("blind", "Write", file_path=f"{R}/.packets/r1/restriction/X.draft.json"))
    assert not ok(tool("blind", "Write", file_path=f"{R}/data/review/restriction_sources.csv"))


# ── editor ───────────────────────────────────────────────────────────────────

def test_editor_writes_the_hand_kept_review_files_only():
    for path in ("restriction_sources.csv", "outcome_resolutions.csv", "queue.csv", "negative_checks.csv",
                 "verification_log.csv", "place_overrides.csv", "state_policies_candidates.csv",
                 "cases_candidates.csv", "group_candidates.csv"):
        assert ok(tool("editor", "Edit", file_path=f"{R}/data/review/{path}")), path
    for path in ("data/review/restriction_worklist.csv", "data/review/fips_misses.csv",
                 "data/processed/restrictions.csv", "data/seed/restrictions_seed.csv", "scripts/qc_gate.py",
                 "docs/AGENTS.md"):
        assert not ok(tool("editor", "Edit", file_path=f"{R}/{path}")), path


def test_editor_appends_a_reconciled_row():
    cmd = ("python3 scripts/review_packets.py reconcile .packets/r1/restriction/X.blind.json "
           ".packets/r1/restriction/X.draft.json .packets/r1/restriction/X.review.json --row "
           ">> data/review/restriction_sources.csv")
    assert ok(bash("editor", cmd))
    assert not ok(bash("editor", "python3 scripts/review_packets.py x >> data/processed/restrictions.csv"))
    assert not ok(bash("editor", "python3 scripts/promote_reviewed.py"))


def test_a_worktree_is_its_own_checkout():
    wt = f"{R}/.claude/worktrees/agent-1"
    assert ok(tool("editor", "Edit", file_path=f"{wt}/data/review/queue.csv"))
    assert not ok(tool("reader", "Edit", file_path=f"{wt}/data/review/queue.csv"))
    assert not ok(tool("blind", "Read", file_path=f"{wt}/data/review/queue.csv"))


# ── copy ─────────────────────────────────────────────────────────────────────

def test_copy_editor_writes_hand_written_prose_only():
    for path in ("README.md", "docs/AGENT_REVIEW.md", "docs/county_checks/2026-10-16_x.md",
                 "deliverables/county_reports/brief.md"):
        assert ok(tool("copy", "Edit", file_path=f"{R}/{path}")), path
    for path in ("docs/codebook.md", "docs/surfaces.md", "docs/coverage_audit.md", "scripts/codebook.py",
                 "data/review/queue.csv", "national-dashboard.html", "config/county_report.json"):
        assert not ok(tool("copy", "Edit", file_path=f"{R}/{path}")), path
    assert ok(bash("copy", "vale --no-wrap README.md && python3 scripts/precommit_gates.py emdash README.md"))
    assert not ok(bash("copy", "python3 scripts/precommit_gates.py crlf --fix data/review/queue.csv"))


# ── qc ───────────────────────────────────────────────────────────────────────

def test_qc_runs_checks_and_restores_what_they_regenerate():
    assert ok(bash("qc", "python3 scripts/build_seed_outputs.py && python3 -m pytest -q"))
    assert ok(bash("qc", "python3 scripts/review_lint.py --base origin/main --lane review"))
    assert ok(bash("qc", "git checkout -- data/processed data/review/*_worklist.csv"))
    assert ok(bash("qc", "git restore data/processed"))
    assert not ok(bash("qc", "git checkout main"))
    assert not ok(tool("qc", "Edit", file_path=f"{R}/data/review/queue.csv"))
    assert ok(tool("qc", "Write", file_path=f"{R}/.packets/r1/qc_report.md"))


# ── The hook itself ──────────────────────────────────────────────────────────

def test_split_commands():
    assert lane.split_commands("a && b || c; d | e & f") == ["a", "b", "c", "d", "e", "f"]
    assert lane.split_commands("echo 'a; b' \"c && d\"") == ["echo 'a; b' \"c && d\""]
    assert lane.split_commands("x 2>&1 | y") == ["x 2>&1", "y"]
    assert lane.split_commands("echo $(git rev-parse HEAD)") == ["echo", "git rev-parse HEAD"]


def test_unknown_lane_and_runs_as_a_hook():
    assert "unknown lane" in lane.decide("nope", {"tool_name": "Read", "tool_input": {}})
    call = {"tool_name": "Write", "tool_input": {"file_path": f"{R}/data/review/queue.csv"}, "cwd": R}
    refused = subprocess.run([sys.executable, str(HOOK), "reader"], input=json.dumps(call),
                             capture_output=True, text=True)
    assert refused.returncode == 2 and "[reader lane]" in refused.stderr
    call["tool_input"]["file_path"] = f"{R}/.packets/x.draft.json"
    allowed = subprocess.run([sys.executable, str(HOOK), "reader"], input=json.dumps(call),
                             capture_output=True, text=True)
    assert allowed.returncode == 0 and allowed.stderr == ""
    broken = subprocess.run([sys.executable, str(HOOK), "reader"], input="not json", capture_output=True, text=True)
    assert broken.returncode == 2 and "refused to be safe" in broken.stderr
