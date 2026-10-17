"""The agent roster (.claude/agents/, docs/AGENTS.md): every agent declares a
lane the hook knows, holds only the tools its lane needs, and is documented."""
import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / ".claude" / "agents"
ROSTER = ROOT / "docs" / "AGENTS.md"
COMMANDS = ROOT / ".claude" / "commands"
SETTINGS = ROOT / ".claude" / "settings.json"
HOOK = 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/agent_lane.py"'
LANES = {"reader", "blind", "editor", "copy", "qc"}
WEB = {"WebFetch", "WebSearch"}
EDIT = {"Edit", "MultiEdit", "NotebookEdit"}
MATCHED = {"Bash", "Edit", "MultiEdit", "Write", "NotebookEdit", "Read", "Grep", "Glob"}
# What each lane's agents may hold. Readers and reviewers write only their
# packet (Write); editors cannot browse, so they add no fact a reader did not see.
ALLOWED = {
    "reader": {"Read", "Grep", "Glob", "Bash", "WebFetch", "WebSearch", "Write"},
    "blind": {"Read", "Grep", "Glob", "Bash", "WebFetch", "WebSearch", "Write"},
    "editor": {"Read", "Grep", "Glob", "Bash", "Edit", "Write"},
    "copy": {"Read", "Grep", "Glob", "Bash", "Edit", "Write"},
    "qc": {"Read", "Grep", "Glob", "Bash", "WebFetch", "Write"},
}


def agents():
    out = {}
    for path in sorted(AGENTS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
        assert m, f"{path.name}: no frontmatter"
        out[path.stem] = (yaml.safe_load(m.group(1)), m.group(2), text)
    return out


def lane_of(meta):
    return meta["lane"]


def test_the_lane_hook_runs_from_settings_for_every_agent():
    """Claude Code skips a project agent's frontmatter hooks until the
    workspace is trusted, and always in a -p run, so the lane hook is
    registered in settings, where it also runs inside subagents."""
    pre = json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
    (entry,) = [e for e in pre if any("agent_lane.py" in h["command"] for h in e["hooks"])]
    assert set(entry["matcher"].split("|")) == MATCHED
    assert [h["command"] for h in entry["hooks"]] == [HOOK]
    for name, (meta, _, _) in agents().items():
        assert "hooks" not in meta, f"{name}: the lane comes from settings.json, not frontmatter hooks"


def test_there_are_agents_for_each_part_of_the_work():
    lanes = {lane_of(meta) for meta, _, _ in agents().values()}
    assert lanes == LANES


@pytest.mark.parametrize("name", sorted(p.stem for p in AGENTS.glob("*.md")))
def test_each_agent_is_well_formed_and_in_its_lane(name):
    meta, body, text = agents()[name]
    assert meta["name"] == name
    assert len(meta["description"]) > 200, "say when to use it"
    tools = {t.strip() for t in meta["tools"].split(",")}
    lane = lane_of(meta)
    assert tools <= ALLOWED[lane], f"{name} ({lane}) holds {sorted(tools - ALLOWED[lane])}"
    assert "Agent" not in tools and "Workflow" not in tools
    if lane in ("reader", "blind", "qc"):
        assert not tools & EDIT, "readers, reviewers and the auditor edit nothing"
    if lane in ("editor", "copy"):
        assert not tools & WEB, "editors add no fact a reader did not see"
    assert "—" not in text
    # Every agent is told the rules that hold in every lane.
    assert "local" in body and "em dash" in body
    assert re.search(r"agent:" + re.escape(name) + r"-\d", body) or lane in ("editor", "copy", "qc")


def test_the_auditor_audits_the_branch_on_a_clean_checkout():
    """A worktree-isolated agent starts at the default branch, not the branch
    under audit, so the auditor runs in the checkout and stops on a tree with
    uncommitted work before any check regenerates files it then restores."""
    meta, body, _ = agents()["qc-auditor"]
    assert "isolation" not in meta
    assert "git status --short" in body and "stop here" in body


def test_the_roster_documents_every_agent_and_nothing_else():
    roster = ROSTER.read_text(encoding="utf-8").split("\n## Roster\n", 1)[1].split("\n## ", 1)[0]
    table = re.findall(r"^\| `([a-z-]+)` \|", roster, re.M)
    assert sorted(table) == sorted(agents()), "docs/AGENTS.md roster table and .claude/agents/ differ"
    for name, (meta, _, _) in agents().items():
        row = next(line for line in roster.splitlines() if line.startswith(f"| `{name}` |"))
        assert f"`{lane_of(meta)}`" in row, f"{name}: the roster names a different lane"


def test_commands_and_docs_name_only_agents_that_exist():
    """A command or doc that starts `some-reader` must find it in .claude/agents/."""
    names = set(agents())
    role = re.compile(r"`([a-z]+(?:-[a-z]+)*-(?:reader|reviewer|editor|researcher|triager|examiner|auditor|analyst|checker))`")
    used = set()
    for path in [*COMMANDS.glob("*.md"), ROSTER, ROOT / "docs" / "VERIFICATION_ROUTINE.md", ROOT / "README.md"]:
        for name in role.findall(path.read_text(encoding="utf-8")):
            assert name in names, f"{path.name} names {name}, which is not in .claude/agents/"
            used.add(name)
    assert used == names, f"agents no command or doc uses: {sorted(names - used)}"
