#!/usr/bin/env python3
"""Lane hook: what an agent of each role may read and write (docs/AGENTS.md).

A PreToolUse hook, registered once in .claude/settings.json. Claude Code
sends each tool call as JSON on stdin; inside a subagent (or a session run
with --agent) the JSON carries `agent_type`, the agent's name. When
.claude/agents/<agent_type>.md names a lane in its frontmatter
(`lane: reader`), the call is checked against that lane; any other caller,
the main session included, passes untouched. Exit 2 refuses a call, and the
message on stderr goes back to the agent with what the lane allows instead.

The hook lives in settings rather than in each agent's frontmatter because
Claude Code skips a project agent's frontmatter hooks until the workspace
trust dialog is accepted, and never runs them in a `-p` session; settings
hooks run inside subagents too.

Lanes
  reader   Research extraction (instrument-reader, outcome-reader,
           case-researcher, lead-triager, county-examiner). Reads anything in
           the repository and on the web; writes only its packet, under
           .packets/ or outside the repository.
  blind    The second reading (blind-reviewer). The reader lane, and it never
           sees what a drafter concluded: nothing under data/review/, no
           *.draft.json and no drafts/ folder, no git, no search over the
           repository root or data/ (a search names a narrower path the hook
           can check), no xargs. Everything it needs is in its blind card,
           the published data, the code and the source.
  editor   record-editor. Writes the review files a reviewer keeps by hand
           (config/layers.json "hand_edited", plus the files whose reviewer
           columns are hand-kept) and packets. It has no web tools.
  copy     copy-editor. Writes hand-written prose (README.md, docs/**.md,
           deliverables/**.md), never a doc a script generates, data, code
           or config.
  qc       qc-auditor. Runs any check on a clean checkout of the committed
           branch; writes only its report under .packets/ or outside the
           repository, and may restore files a check regenerated (git
           restore, git checkout --).

Every lane
  - never touches reports from local contacts (local_knowledge*,
    $RO_LOCAL_KNOWLEDGE, ~/.renewable-opposition), and runs site_profile.py
    only with --no-local;
  - runs git only to look (status, diff, log, show, fetch ...), never to stage,
    commit, push or move a branch: the session that started the agent commits;
  - edits no file in place from the shell (sed -i, perl -i) and sends no
    output into the repository outside its lane (redirection, tee, cp, mv,
    curl -o, wget, ...).

A guardrail, not a sandbox: `python -c` can still open any file. The lane
check in scripts/review_lint.py looks at what a branch actually changed, and
the qc-auditor runs it before anything is pushed.

Usage
  python3 .claude/hooks/agent_lane.py            the lane from agent_type (settings.json)
  python3 .claude/hooks/agent_lane.py <lane>     force a lane (tests, manual checks)
"""
from __future__ import annotations

import glob as globmod
import itertools
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[2]
PACKETS = ".packets"
LAYERS = "config/layers.json"

# Review files kept by hand that config/layers.json does not mark hand_edited:
# reviewer columns in a file a script also writes, and outcome_resolutions.csv,
# which no script writes and so is not declared there.
REVIEWER_COLUMN_FILES = {
    "data/review/queue.csv",
    "data/review/cases_candidates.csv",
    "data/review/sabin_edition_crosswalk.csv",
    "data/review/restriction_sources.csv",
    "data/review/outcome_resolutions.csv",
}
PROSE_PREFIXES = ("docs/", "deliverables/")
PROSE_FILES = {"README.md"}

# Scripts any lane but blind may run: they write nothing.
LOOK_SCRIPTS = {"review_packets.py", "review_lint.py", "verification_batch.py"}
# The blind lane runs only what reads no review file: checking its own packet.
BLIND_SCRIPTS = {"review_packets.py": {"check"}}
# Scripts allowed only with a flag (all lanes): the flag keeps them from writing
# or from reading what the lane may not read. site_profile.py still records the
# county and date in data/review/profile_requests.csv, as every profile does.
FLAGGED_SCRIPTS = {"site_profile.py": "--no-local", "promote_reviewed.py": "--dry-run"}
# Scripts whose listed subcommands write nothing (crlf --fix rewrites files).
SUBCOMMAND_SCRIPTS = {"precommit_gates.py": {"emdash", "private", "nodecheck", "--selftest"}}

GIT_LOOK = {
    "status", "diff", "log", "show", "ls-files", "ls-tree", "rev-parse", "merge-base", "blame",
    "grep", "cat-file", "describe", "fetch", "shortlog", "rev-list", "diff-tree", "name-rev",
    "for-each-ref", "show-ref", "check-ignore", "cherry", "range-diff", "help", "version",
}
GIT_BRANCH_WRITE = {"-d", "-D", "--delete", "-m", "-M", "--move", "-c", "-C", "--copy", "-f", "--force",
                    "-u", "--set-upstream-to", "--unset-upstream", "--edit-description", "-t", "--track"}
GIT_GLOBAL_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}

PRIVATE_TOKENS = ("local_knowledge", ".renewable-opposition", "ro_local_knowledge")
SEPARATORS = {";", "&", "|", "(", ")", "`", "\n"}
REDIRECT = re.compile(r"^(?:\d+|&)?(>>?|>\||&>>?)(.*)$")
READ_REDIRECT = re.compile(r"^\d*<(?!<)(.*)$")
PREFIXES = {"sudo", "env", "time", "nohup", "command", "exec", "nice", "stdbuf", "ionice"}
SHELLS = {"bash", "sh", "zsh", "dash"}
SEARCHERS = {"rg", "ag", "ack", "ack-grep", "fd", "fdfind"}


@dataclass(frozen=True)
class Lane:
    name: str
    writes: str          # "packets", "review", "prose"
    scripts: str         # "look" (LOOK_SCRIPTS), "blind" (BLIND_SCRIPTS) or "any"
    git: str             # "look", "none", "restore"
    blind: bool = False


LANES = {
    "reader": Lane("reader", writes="packets", scripts="look", git="look"),
    "blind": Lane("blind", writes="packets", scripts="blind", git="none", blind=True),
    "editor": Lane("editor", writes="review", scripts="look", git="look"),
    "copy": Lane("copy", writes="prose", scripts="look", git="look"),
    "qc": Lane("qc", writes="packets", scripts="any", git="restore"),
}


class Refused(Exception):
    pass


# ── Where a path is ──────────────────────────────────────────────────────────

def _roots(cwd: str) -> list[Path]:
    roots = {REPO}
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        roots.add(Path(env).resolve())
    try:
        top = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True,
                             text=True, timeout=5)
        if top.returncode == 0 and top.stdout.strip():
            roots.add(Path(top.stdout.strip()).resolve())
    except (OSError, subprocess.SubprocessError):
        pass
    # Deepest first, so a worktree inside the repository is its own root.
    return sorted(roots, key=lambda p: len(p.parts), reverse=True)


def _abs(path: str, cwd: str) -> Path | None:
    if not path or path == "-" or "://" in path:
        return None
    p = os.path.expandvars(os.path.expanduser(path))
    if "$" in p:
        return None
    return Path(os.path.normpath(os.path.join(cwd, p)))


def locate(path: Path, roots: list[Path]) -> str | None:
    """The path relative to the repository (or worktree) holding it, or None
    when it is outside every one."""
    for root in roots:
        try:
            rel = PurePosixPath(path.relative_to(root).as_posix())
        except ValueError:
            continue
        parts = rel.parts
        # A worktree under .claude/worktrees/<name>/ is a checkout of its own.
        if len(parts) >= 3 and parts[0] == ".claude" and parts[1] == "worktrees":
            parts = parts[3:]
        return "/".join(parts) if parts else "."
    return None


def _hand_kept() -> set[str]:
    files = set(REVIEWER_COLUMN_FILES)
    try:
        layers = json.loads((REPO / LAYERS).read_text(encoding="utf-8"))["files"]
    except (OSError, ValueError, KeyError):
        return files
    for name, spec in layers.items():
        if spec.get("hand_edited") and name.startswith("data/review/") and "*" not in name:
            files.add(name)
    return {f for f in files if not _private(f)}


def _generated_docs() -> set[str]:
    try:
        layers = json.loads((REPO / LAYERS).read_text(encoding="utf-8"))["files"]
    except (OSError, ValueError, KeyError):
        return set()
    return {name for name, spec in layers.items() if spec.get("writers") and name.endswith(".md")}


def _private(text: str) -> bool:
    low = text.lower()
    return any(t in low for t in PRIVATE_TOKENS)


def is_draft(rel: str) -> bool:
    parts = rel.split("/")
    return rel.endswith(".draft.json") or "drafts" in parts[:-1]


def _blind_hidden(rel: str) -> bool:
    return rel == "data/review" or rel.startswith("data/review/") or is_draft(rel)


# ── Rules ────────────────────────────────────────────────────────────────────

def check_write(lane: Lane, path: Path | None, roots: list[Path], what: str) -> None:
    if path is None:
        return
    if _private(str(path)):
        raise Refused(f"{what} {path}: reports from local contacts stay outside every agent's reach")
    rel = locate(path, roots)
    if rel is None or rel in ("/dev/null",):
        return
    if rel == PACKETS or rel.startswith(PACKETS + "/"):
        if lane.blind and is_draft(rel):
            raise Refused(f"{what} {rel}: a blind reviewer writes only its own *.review.json packet")
        return
    if lane.writes == "review" and rel in _hand_kept():
        return
    if lane.writes == "prose" and rel.endswith(".md") and rel not in _generated_docs() \
            and (rel in PROSE_FILES or rel.startswith(PROSE_PREFIXES)):
        return
    allowed = {
        "packets": f"only under {PACKETS}/ or outside the repository",
        "review": f"only the hand-kept review files ({', '.join(sorted(_hand_kept()))}) and {PACKETS}/",
        "prose": "only hand-written markdown (README.md, docs/, deliverables/; not a generated doc) "
                 f"and {PACKETS}/",
    }[lane.writes]
    raise Refused(f"{what} {rel}: the {lane.name} lane writes {allowed}")


def check_read(lane: Lane, path: Path | None, roots: list[Path], what: str) -> None:
    if path is None:
        return
    if _private(str(path)):
        raise Refused(f"{what} {path}: reports from local contacts stay outside every agent's reach")
    if not lane.blind:
        return
    rel = locate(path, roots)
    if rel is not None and _blind_hidden(rel):
        raise Refused(f"{what} {rel}: a blind reviewer works from its blind card, the published data "
                      "(data/processed/, data/db/), the code and the source itself, never data/review/ "
                      "or a draft packet")


def _blind_search_scope(path: Path, roots: list[Path]) -> None:
    rel = locate(path, roots)
    if rel is None:
        return
    if rel in (".", "data") or _blind_hidden(rel):
        raise Refused(f"search over {rel}: it would read data/review/; a blind reviewer searches a narrower "
                      "path (data/processed, scripts, docs, config)")


# ── Shell parsing ────────────────────────────────────────────────────────────

def split_commands(cmd: str) -> list[str]:
    """The simple commands in a shell string: split on unquoted ; & | && ||,
    newlines, parentheses, backticks and $( ; heredoc bodies are dropped."""
    out, buf = [], []
    single = double = False
    heredocs: list[tuple[str, bool]] = []
    i, n = 0, len(cmd)

    def flush():
        s = "".join(buf).strip()
        if s:
            out.append(s)
        buf.clear()

    while i < n:
        c = cmd[i]
        if single:
            buf.append(c)
            single = c != "'"
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            buf.append(cmd[i:i + 2])
            i += 2
            continue
        if double:
            buf.append(c)
            double = c != '"'
            i += 1
            continue
        if c == "'":
            single = True
        elif c == '"':
            double = True
        elif c == "<" and cmd.startswith("<<", i) and not cmd.startswith("<<<", i):
            m = re.match(r"<<(-?)\s*(['\"]?)([A-Za-z0-9_.-]+)\2", cmd[i:])
            if m:
                heredocs.append((m.group(3), bool(m.group(1))))
                buf.append(m.group(0))
                i += len(m.group(0))
                continue
        elif c == "$" and i + 1 < n and cmd[i + 1] == "(":
            flush()
            i += 2
            continue
        elif c == "&" and ((buf and buf[-1].endswith(">")) or cmd.startswith("&>", i)):
            buf.append(c)
            i += 1
            continue
        elif c == "|" and buf and buf[-1].endswith(">"):
            buf.append(c)
            i += 1
            continue
        elif c in SEPARATORS:
            flush()
            i += 1
            if c == "\n" and heredocs:
                # Skip each heredoc body up to its delimiter line.
                for delim, strip_tabs in heredocs:
                    while i < n:
                        end = cmd.find("\n", i)
                        line = cmd[i:] if end < 0 else cmd[i:end]
                        i = n if end < 0 else end + 1
                        if (line.lstrip("\t") if strip_tabs else line) == delim:
                            break
                heredocs.clear()
            continue
        buf.append(c)
        i += 1
    flush()
    return out


def _tokens(segment: str) -> list[tuple[str, str]]:
    """(raw, value) for each word: raw keeps its quotes, so a quoted "> 1000"
    is an argument and not a redirection; value is what the program gets.
    Never raises: an unclosed quote runs to the end of the segment."""
    out: list[tuple[str, str]] = []
    raw: list[str] = []
    val: list[str] = []
    quote, started, i, n = "", False, 0, len(segment)
    while i < n:
        c = segment[i]
        if quote:
            raw.append(c)
            if c == quote:
                quote = ""
            elif quote == '"' and c == "\\" and i + 1 < n:
                raw.append(segment[i + 1])
                val.append(segment[i + 1])
                i += 1
            else:
                val.append(c)
        elif c in " \t\r\n":
            if started:
                out.append(("".join(raw), "".join(val)))
                raw, val, started = [], [], False
        else:
            started = True
            raw.append(c)
            if c in "'\"":
                quote = c
            elif c == "\\" and i + 1 < n:
                raw.append(segment[i + 1])
                val.append(segment[i + 1])
                i += 1
            else:
                val.append(c)
        i += 1
    if started:
        out.append(("".join(raw), "".join(val)))
    return out


def _strip_prefixes(words: list[tuple[str, str]]) -> list[tuple[str, str]]:
    i = 0
    while i < len(words):
        tok = words[i][1]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[i][0]):
            i += 1
        elif tok in PREFIXES:
            i += 1
            while i < len(words) and words[i][1].startswith("-"):
                i += 1
        elif tok == "timeout":
            i += 1
            while i < len(words) and words[i][1].startswith("-"):
                i += 1
            i += 1  # the duration
        else:
            break
    return words[i:]


def _split_redirects(words: list[tuple[str, str]]) -> tuple[list[str], list[str], list[str]]:
    """(arguments, files written by redirection, files read by redirection).
    A redirection is found in the raw word, so a quoted ">" is an argument."""
    args, writes, reads = [], [], []
    i = 0
    while i < len(words):
        raw, val = words[i]
        if raw.startswith("<<"):
            i += 2 if raw in ("<<", "<<-") else 1
            continue
        for pattern, sink, group in ((REDIRECT, writes, 2), (READ_REDIRECT, reads, 1)):
            if pattern.match(raw):
                m = pattern.match(val)
                target = m.group(group) if m else ""
                if not target and i + 1 < len(words):
                    target = words[i + 1][1]
                    i += 1
                if target and not target.startswith("&"):
                    sink.append(target)
                break
        else:
            args.append(val)
        i += 1
    return args, writes, reads


def _positionals(args: list[str]) -> list[str]:
    return [a for a in args if not a.startswith("-")]


def _option_value(args: list[str], *names: str) -> list[str]:
    vals = []
    for j, a in enumerate(args):
        for name in names:
            if a == name and j + 1 < len(args):
                vals.append(args[j + 1])
            elif name.startswith("--") and a.startswith(name + "="):
                vals.append(a.split("=", 1)[1])
            elif not name.startswith("--") and a.startswith(name) and len(a) > len(name):
                vals.append(a[len(name):])
    return vals


def _cluster_value(args: list[str], letter: str, flag_only: bool = False) -> list[str]:
    """Values of a one-letter option that may end a cluster: -o FILE, -sSLo FILE,
    -oFILE. With flag_only, the option takes no value (curl -O) and its
    presence is returned as [""]."""
    vals = []
    for j, a in enumerate(args):
        m = re.match(rf"^-([A-Za-z]*){letter}(\S*)$", a)
        if not m or a.startswith("--"):
            continue
        if flag_only:
            vals.append("")
        elif m.group(2):
            vals.append(m.group(2))
        elif j + 1 < len(args):
            vals.append(args[j + 1])
    return vals


def _write_targets(prog: str, args: list[str], cwd: str) -> list[str]:
    pos = _positionals(args)
    if prog in ("rm", "rmdir", "touch", "truncate", "mkdir", "tee", "mv", "shred"):
        return pos
    if prog in ("chmod", "chown", "chgrp"):
        return pos[1:]
    if prog in ("cp", "ln", "install", "rsync", "scp"):
        return pos[-1:] if len(pos) > 1 else []
    if prog == "dd":
        return [a[3:] for a in args if a.startswith("of=")]
    if prog == "curl":
        outs = _option_value(args, "--output") + _cluster_value(args, "o")
        if _cluster_value(args, "O", flag_only=True) or "--remote-name" in args or "--remote-name-all" in args:
            outs += _option_value(args, "--output-dir") or [cwd]
        return outs
    if prog == "wget":
        outs = _option_value(args, "--output-document") + _cluster_value(args, "O")
        return outs or _option_value(args, "-P", "--directory-prefix") or [cwd]
    if prog in ("pdftotext", "pdftoppm", "pdfimages", "pdftohtml", "pdfseparate"):
        if len(pos) >= 2 and pos[1] != "-":
            return [pos[1]]
        if prog == "pdftotext" and len(pos) == 1:
            return [re.sub(r"\.pdf$", "", pos[0], flags=re.I) + ".txt"]
        return []
    if prog == "unzip":
        return _option_value(args, "-d") or [cwd]
    if prog == "tar":
        mode = args[0] if args else ""
        if "x" in mode.lstrip("-") or "--extract" in args or "-x" in args:
            return _option_value(args, "-C", "--directory") or [cwd]
    return []


def _in_place(prog: str, args: list[str]) -> bool:
    if prog == "sed":
        return any(a == "--in-place" or a.startswith("--in-place=")
                   or (re.match(r"^-[A-Za-z]*i", a) and not a.startswith("--")) for a in args)
    if prog in ("perl", "ruby"):
        return any(re.match(r"^-[a-zA-Z0-9]*i", a) and not a.startswith(("-I", "-M", "--")) for a in args)
    return False


def _git(lane: Lane, args: list[str]) -> None:
    if lane.git == "none":
        raise Refused("git: a blind reviewer does not use git (a diff or log would show what the drafter "
                      "wrote); its card and the source are all it reads")
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in GIT_GLOBAL_WITH_ARG else 1
    if i >= len(args):
        return
    sub, rest = args[i], args[i + 1:]
    if sub in GIT_LOOK:
        return
    if sub == "branch" and not _positionals(rest) and not (set(rest) & GIT_BRANCH_WRITE):
        return
    if sub == "worktree" and rest[:1] == ["list"]:
        return
    if sub == "remote" and (not _positionals(rest) or rest[0] in ("show", "get-url")):
        return
    if sub == "stash" and rest[:1] == ["list"]:
        return
    if lane.git == "restore" and (sub == "restore" or (sub == "checkout" and "--" in rest)):
        return
    raise Refused(f"git {sub}: agents look with git (status, diff, log, show) and never stage, commit, push "
                  "or move a branch; the session that started the agent does that")


def check_command(lane: Lane, command: str, cwd: str, roots: list[Path], depth: int = 0) -> None:
    if _private(command):
        raise Refused("the command names reports from local contacts, which stay outside every agent's reach")
    if lane.blind and ("data/review" in command or ".draft.json" in command):
        raise Refused("the command names data/review/ or a draft packet; a blind reviewer never touches either")
    for segment in split_commands(command):
        argv = _strip_prefixes(_tokens(segment))
        if not argv:
            continue
        args, writes, reads = _split_redirects(argv)
        for target in writes:
            check_write(lane, _abs(target, cwd), roots, "redirect into")
        for target in reads:
            check_read(lane, _abs(target, cwd), roots, "read")
        if not args:
            continue
        prog, rest = os.path.basename(args[0]), args[1:]
        if prog == "cd":
            dest = _abs(rest[0], cwd) if rest and rest[0] != "-" else Path.home()
            if dest is not None:
                cwd = str(dest)
            continue
        if prog in SHELLS or prog == "eval":
            inner = rest[rest.index("-c") + 1] if "-c" in rest and rest.index("-c") + 1 < len(rest) else (
                " ".join(rest) if prog == "eval" else None)
            if inner and depth < 3:
                check_command(lane, inner, cwd, roots, depth + 1)
            continue
        if prog == "git":
            _git(lane, rest)
            continue
        if _in_place(prog, rest):
            raise Refused(f"{prog} in place: the {lane.name} lane edits no file from the shell; "
                          + ("use the Edit tool on a file the lane may write" if lane.writes != "packets"
                             else "write a copy under .packets/ or /tmp instead"))
        for target in _write_targets(prog, rest, cwd):
            check_write(lane, _abs(target, cwd), roots, f"{prog} writing")
        if prog.startswith("python"):
            _python(lane, rest, cwd, roots)
        if lane.blind:
            _blind_command(prog, rest, cwd, roots)


def _python(lane: Lane, args: list[str], cwd: str, roots: list[Path]) -> None:
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-c", "-m"):
            return
        if a in ("-X", "-W"):
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        break
    if i >= len(args):
        return
    script = _abs(args[i], cwd)
    rel = locate(script, roots) if script else None
    if rel is None:
        return
    name, script_args = os.path.basename(rel), args[i + 1:]
    if name in FLAGGED_SCRIPTS and FLAGGED_SCRIPTS[name] not in script_args:
        raise Refused(f"{rel} runs only with {FLAGGED_SCRIPTS[name]} in an agent lane")
    if lane.scripts == "any" or not rel.startswith("scripts/"):
        return
    if lane.scripts == "blind":
        if script_args[:1] and script_args[0] in BLIND_SCRIPTS.get(name, set()):
            return
        raise Refused(f"{rel}: a blind reviewer runs only `review_packets.py check` on its own packet; "
                      "the other scripts read data/review/")
    if name in LOOK_SCRIPTS or name in FLAGGED_SCRIPTS:
        return
    if name in SUBCOMMAND_SCRIPTS and script_args[:1] and script_args[0] in SUBCOMMAND_SCRIPTS[name]:
        return
    raise Refused(f"{rel}: the {lane.name} lane runs only scripts that write nothing "
                  f"({', '.join(sorted(LOOK_SCRIPTS))}); builds and worklists are the qc-auditor's "
                  "or the orchestrating session's")


def _search_paths(prog: str, args: list[str], cwd: str) -> list[str]:
    """The paths a recursive search covers: its arguments that name an
    existing path, or the working directory when none does."""
    if prog == "find":
        paths = []
        for a in args:
            if a.startswith(("-", "(", "!")):
                break
            paths.append(a)
        return paths or [cwd]
    positional = _positionals(args)
    # grep, rg, ag, ack: the first operand is the pattern unless -e or -f gave it.
    if not any(a in ("-e", "-f", "--regexp", "--file") or a.startswith(("--regexp=", "--file=")) for a in args):
        positional = positional[1:]
    return positional or [cwd]


def _blind_command(prog: str, args: list[str], cwd: str, roots: list[Path]) -> None:
    if prog == "xargs":
        raise Refused("xargs: a blind reviewer names the files it reads, so the lane can check each one")
    recursive = prog in SEARCHERS or prog == "find" or (prog in ("grep", "egrep", "fgrep") and any(
        a in ("-r", "-R", "--recursive", "--dereference-recursive") or a.startswith("--directories=recurse")
        or (re.match(r"^-[A-Za-z]*[rR]", a) and not a.startswith("--")) for a in args))
    if recursive:
        for target in _search_paths(prog, args, cwd):
            path = _abs(target, cwd)
            if path is not None:
                _blind_search_scope(path, roots)
    for a in args:
        if a.startswith("-"):
            continue
        p = _abs(a, cwd)
        if p is None:
            continue
        if any(ch in a for ch in "*?["):
            for hit in itertools.islice(globmod.iglob(str(p), recursive=True), 5000):
                check_read(LANES["blind"], Path(hit), roots, "read")
        else:
            check_read(LANES["blind"], p, roots, "read")


# ── Tool calls ───────────────────────────────────────────────────────────────

def decide(lane_name: str, payload: dict) -> str:
    """'' when the call may go ahead, else why it is refused."""
    lane = LANES.get(lane_name)
    if lane is None:
        return f"agent_lane.py: unknown lane {lane_name!r} (one of {', '.join(LANES)})"
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input") or {}
    cwd = payload.get("cwd") or os.getcwd()
    roots = _roots(cwd)
    try:
        if tool == "Bash":
            check_command(lane, str(inp.get("command", "")), cwd, roots)
        elif tool in ("Edit", "MultiEdit", "Write", "NotebookEdit"):
            path = inp.get("file_path") or inp.get("notebook_path") or ""
            check_write(lane, _abs(str(path), cwd), roots, tool)
        elif tool == "Read":
            check_read(lane, _abs(str(inp.get("file_path", "")), cwd), roots, "Read")
        elif tool == "Grep":
            path = _abs(str(inp.get("path") or cwd), cwd)
            check_read(lane, path, roots, "Grep")
            for text in (str(inp.get("glob") or ""), str(inp.get("pattern") or "")):
                if _private(text):
                    raise Refused("Grep for reports from local contacts: they stay outside every agent's reach")
            if lane.blind:
                if path is not None:
                    _blind_search_scope(path, roots)
                if "draft" in str(inp.get("glob") or "") or "review" in str(inp.get("glob") or ""):
                    raise Refused("Grep over review files or drafts: a blind reviewer never reads either")
        elif tool == "Glob":
            for text in (str(inp.get("pattern") or ""), str(inp.get("path") or "")):
                if _private(text):
                    raise Refused("Glob for reports from local contacts: they stay outside every agent's reach")
                if lane.blind and "draft" in text:
                    raise Refused("Glob for draft packets: a blind reviewer never reads one")
    except Refused as why:
        return f"[{lane.name} lane] {why}"
    return ""


_LANE_FIELD = re.compile(r"^lane:\s*([a-z]+)\s*$", re.M)


def lane_for(agent_type: str, agents_dir: Path | None = None) -> str | None:
    """The lane .claude/agents/<agent_type>.md names in its frontmatter, or
    None for any other caller (the main session, a built-in or plugin agent)."""
    if not agent_type or not re.fullmatch(r"[A-Za-z0-9_-]+", agent_type):
        return None
    if agents_dir is None:
        project = os.environ.get("CLAUDE_PROJECT_DIR")
        agents_dir = (Path(project) if project else REPO) / ".claude" / "agents"
    try:
        text = (agents_dir / f"{agent_type}.md").read_text(encoding="utf-8")
    except OSError:
        return None
    front = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    m = _LANE_FIELD.search(front.group(1)) if front else None
    return m.group(1) if m else None


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        if len(argv) == 1:
            return 0  # no agent can be named, so nothing to hold to a lane
        payload = None
    lane = argv[1] if len(argv) == 2 else lane_for(str((payload or {}).get("agent_type") or ""))
    if lane is None:
        return 0
    try:
        if payload is None:
            raise ValueError("the hook input is not JSON")
        refusal = decide(lane, payload)
    except Exception as exc:  # noqa: BLE001 - a broken check refuses rather than waves through
        refusal = f"agent_lane.py could not check this call ({type(exc).__name__}: {exc}); refused to be safe"
    if refusal:
        print(refusal, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
