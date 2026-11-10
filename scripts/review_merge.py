#!/usr/bin/env python3
"""Merge branches that both changed the hand-kept review files, row by row.

Every research branch appends its rows to the end of the same few files in
data/review/. Git merges text by line position, so two branches that each
append a row conflict even when the rows have nothing to do with each other,
and GitHub then refuses the second pull request until someone edits the file
by hand. This script merges those files by what a row is (its key) instead of
where it sits, so any number of branches merge over each other in any order.

  python scripts/review_merge.py origin/main            bring main into this branch
  python scripts/review_merge.py origin/claude/verify-2026-11-08 origin/claude/verify-2026-11-09
  python scripts/review_merge.py --pending              merge every verification branch not yet in HEAD
  python scripts/review_merge.py --pending --list       only name them
  python scripts/review_merge.py --selftest

Each ref is merged with `git merge`; the files below are then rebuilt from the
three versions (merge base, this branch, the other branch) and the merge is
committed. Any other conflicted path stops the run with the merge aborted.

Rules, the same whichever branch is merged into which

  log files       (verification_log.csv, examination_log.csv) have no key:
                  every line either side added is kept, once.
  keyed files     one row per key. A row only one side added, changed or
                  removed follows that side. The same change on both sides is
                  taken once.
  the same key    Two branches that each read the same item both add a row,
  added twice     and the build refuses a key listed twice (resolutions.py).
                  When the two rows reach the same conclusion (verdict,
                  outcome, or status and end date) the earlier reading is
                  kept; the later one stays in the log. When they disagree,
                  neither row is kept and a `disputed` line naming both goes
                  into verification_log.csv, the routine's own rule for two
                  readings that disagree (docs/VERIFICATION_ROUTINE.md,
                  section 3). The item comes back to the batch after the
                  skip window. A third branch that read the item without
                  that line in its log does not bring the row back: its row
                  is left out too, and its attempt stays in the log.
  a real conflict Both sides changed the same existing row differently, one
                  side changed a row the other removed, the header differs,
                  or a file with no conclusion column has the same key added
                  twice with different text. The merge is aborted and each
                  row is listed: settle it by hand.

Rows are copied byte for byte, never rewritten, so a merge changes no quoting.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT  # noqa: E402

LOG = "data/review/verification_log.csv"
LOG_FIELDS = ["date", "queue", "key", "outcome", "note"]
# path -> key columns (empty for a log), the columns holding a reading's
# conclusion, the verification_log queue a disagreement is logged under, and
# the column carrying the date read.
FILES: dict[str, dict] = {
    LOG: {"key": []},
    "data/review/examination_log.csv": {"key": []},
    "data/review/restriction_sources.csv": {"key": ["instrument_id"], "decides": ["verdict"],
                                            "queue": "restriction", "date": "checked_on"},
    "data/review/outcome_resolutions.csv": {"key": ["source_record_id"], "decides": ["outcome"],
                                            "queue": "outcome", "date": "reviewer"},
    "data/review/status_resolutions.csv": {"key": ["instrument_id"], "decides": ["status", "end_date"],
                                           "queue": "status", "date": "checked_on"},
    "data/review/place_overrides.csv": {"key": ["instrument_id"]},
    "data/review/negative_checks.csv": {"key": ["county_fips", "scope"]},
}
MARK = "scripts/review_merge.py"      # in the note of a disputed line this script wrote
PENDING_GLOB = "origin/claude/verify-*"
PENDING_DAYS = 14          # verification_batch.SKIP_DAYS: older branches are past the skip window
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class Conflict(Exception):
    pass


def records(text: str) -> list[tuple[list[str], str]]:
    """(fields, the record's own text) for each CSV record, header included."""
    lines, buf, out = text.splitlines(keepends=True), [], []

    def feed():
        for line in lines:
            buf.append(line)
            yield line
    for fields in csv.reader(feed()):
        raw = "".join(buf)
        buf.clear()
        if raw.strip():
            out.append((fields, raw if raw.endswith("\n") else raw + "\n"))
    return out


def _when(fields: dict, spec: dict) -> str:
    found = _DATE.findall(fields.get(spec.get("date", ""), "") or "")
    return max(found) if found else ""


def merge_disputes(log_text: str) -> set[tuple[str, str]]:
    """(queue, key) of the `disputed` lines an earlier merge wrote in a log."""
    return {(f[1], f[2]) for f, _ in records(log_text)[1:]
            if len(f) >= 5 and f[3] == "disputed" and MARK in f[4]}


def merge_rows(path: str, base: str, ours: str, theirs: str,
               settled: tuple[set, set] = (set(), set())) -> tuple[str, list[dict], list[str]]:
    """(merged text, disputed log lines, notes). Raises Conflict. `settled` is
    merge_disputes() of this branch's log and of the other's."""
    spec = FILES[path]
    b, o, t = records(base), records(ours), records(theirs)
    if not o or not t:
        raise Conflict(f"{path}: one side has no header")
    header = o[0][0]
    if t[0][0] != header or (b and b[0][0] != header):
        raise Conflict(f"{path}: the header differs between the branches")
    name = Path(path).name
    notes: list[str] = []
    disputed: list[dict] = []
    if not spec["key"]:
        mine = {tuple(f) for f, _ in o[1:]}
        was = {tuple(f) for f, _ in b[1:]}
        gone = was - {tuple(f) for f, _ in t[1:]}
        out = [raw for f, raw in o[1:] if tuple(f) not in gone]
        for f, raw in t[1:]:
            if tuple(f) not in mine and tuple(f) not in was:
                mine.add(tuple(f))
                out.append(raw)
        return o[0][1] + "".join(out), disputed, notes

    missing = [k for k in spec["key"] + spec.get("decides", []) if k not in header]
    if missing:
        raise Conflict(f"{path}: no column {', '.join(missing)}")
    idx = [header.index(k) for k in spec["key"]]

    def table(recs, side):
        d: dict[tuple, tuple[list[str], str]] = {}
        for f, raw in recs[1:]:
            k = tuple((f[i] if i < len(f) else "").strip() for i in idx)
            if k in d:
                raise Conflict(f"{path}: {'/'.join(k)} is listed twice on {side}")
            d[k] = (f, raw)
        return d
    B, O, T = table(b, "the merge base") if b else {}, table(o, "this branch"), table(t, "the other branch")
    problems: list[str] = []
    out: list[str] = []

    queue = spec.get("queue")
    knew_o = {k for q, k in settled[0] if q == queue}
    knew_t = {k for q, k in settled[1] if q == queue}

    def left_out(k, side_knows, other_knows) -> bool:
        """A row added on a branch that never saw the dispute an earlier merge logged."""
        label = "/".join(k)
        if label in other_knows and label not in side_knows:
            notes.append(f"{name}: {label} is already logged disputed by an earlier merge; row left out")
            return True
        return False

    def both_added(k, mine, other) -> str | None:
        decides = spec.get("decides")
        label = "/".join(k)
        if not decides:
            problems.append(f"{name}: {label} was added on both sides with different text")
            return mine[1]
        fm, fo = dict(zip(header, mine[0])), dict(zip(header, other[0]))
        cm, co = [fm[c].strip() for c in decides], [fo[c].strip() for c in decides]
        first, second = sorted([mine, other], key=lambda r: (_when(dict(zip(header, r[0])), spec), r[1]))
        if cm == co:
            notes.append(f"{name}: {label} read twice with the same conclusion ({' '.join(cm)}); "
                         "kept the earlier row")
            return first[1]
        f1, f2 = dict(zip(header, first[0])), dict(zip(header, second[0]))

        def say(f):
            what = " ".join(f"{c} {f[c].strip() or 'blank'}" for c in decides)
            return f"{what} (signed {f.get('reviewer', '').strip() or 'unsigned'})"
        disputed.append({"date": _when(f2, spec) or _when(f1, spec) or date.today().isoformat(),
                         "queue": spec["queue"], "key": label, "outcome": "disputed",
                         "note": f"Two branches each wrote a row for this item and the rows disagree: {say(f1)}; "
                                 f"{say(f2)}. Neither row was kept when the branches were merged "
                                 f"({MARK})."})
        notes.append(f"{name}: {label} read twice with different conclusions; neither row kept, logged disputed")
        return None

    for f, raw in o[1:]:
        k = tuple((f[i] if i < len(f) else "").strip() for i in idx)
        mine, was, other = O[k], B.get(k), T.get(k)
        if was is None:
            if other is None:
                if not left_out(k, knew_o, knew_t):
                    out.append(raw)
            elif other[0] == mine[0]:
                out.append(raw)
            elif left_out(k, knew_o, knew_t) or left_out(k, knew_t, knew_o):
                pass
            else:
                kept = both_added(k, mine, other)
                if kept:
                    out.append(kept)
        elif other is None:
            if mine[0] != was[0]:
                problems.append(f"{name}: {'/'.join(k)} was changed on this branch and removed on the other")
                out.append(raw)
        elif other[0] == was[0] or other[0] == mine[0]:
            out.append(raw)
        elif mine[0] == was[0]:
            out.append(other[1])
        else:
            problems.append(f"{name}: {'/'.join(k)} was changed differently on both sides")
            out.append(raw)
    for f, raw in t[1:]:
        k = tuple((f[i] if i < len(f) else "").strip() for i in idx)
        if k in O:
            continue
        was = B.get(k)
        if was is None:
            if not left_out(k, knew_t, knew_o):
                out.append(raw)
        elif f != was[0]:
            problems.append(f"{name}: {'/'.join(k)} was removed on this branch and changed on the other")
    if problems:
        raise Conflict("\n".join(problems))
    return o[0][1] + "".join(out), disputed, notes


def log_lines(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=LOG_FIELDS, lineterminator="\n")
    w.writerows(rows)
    return buf.getvalue()


def merge_files(versions: dict[str, tuple[str, str, str]],
                logs: tuple[str, str] = ("", "")) -> tuple[dict[str, str], list[str]]:
    """{path: (base, ours, theirs)} -> ({path: merged text}, notes). A
    disagreement's `disputed` lines are added to the merged log. `logs` is the
    verification log on this branch and on the other."""
    settled = (merge_disputes(logs[0]), merge_disputes(logs[1]))
    out: dict[str, str] = {}
    notes: list[str] = []
    disputed: list[dict] = []
    problems: list[str] = []
    for path, (base, ours, theirs) in versions.items():
        try:
            out[path], d, n = merge_rows(path, base, ours, theirs, settled)
        except Conflict as e:
            problems.append(str(e))
            continue
        disputed += d
        notes += n
    if problems:
        raise Conflict("\n".join(problems))
    if disputed:
        if LOG not in out:
            raise Conflict(f"{LOG}: needed for {len(disputed)} disputed line(s) but not part of this merge")
        have = {tuple(f) for f, _ in records(out[LOG])[1:]}
        new = [d for d in disputed if tuple(d[c] for c in LOG_FIELDS) not in have]
        out[LOG] += log_lines(new)
    return out, notes


# ---- git ---------------------------------------------------------------

def git(*args: str, check: bool = True) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and p.returncode:
        raise SystemExit(f"git {' '.join(args)}: {p.stderr.strip() or p.stdout.strip()}")
    return p.stdout


def show(ref: str, path: str) -> str | None:
    p = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


def pending(today: date | None = None) -> list[str]:
    """Verification branches that logged an attempt (date, queue, key) HEAD's
    log does not have, oldest first. A branch whose batch reached main some
    other way has nothing new and is left out, as is one untouched for
    PENDING_DAYS."""
    today = today or date.today()
    mine = {tuple(f[:3]) for f, _ in records(show("HEAD", LOG) or "")}      # date, queue, key
    out = []
    for ref in git("for-each-ref", "--format=%(refname:short) %(committerdate:short)",
                   f"refs/remotes/{PENDING_GLOB}").splitlines():
        name, when = ref.split()
        if date.fromisoformat(when) < today - timedelta(days=PENDING_DAYS):
            continue
        if subprocess.run(["git", "merge-base", "--is-ancestor", name, "HEAD"], cwd=ROOT).returncode == 0:
            continue
        theirs = show(name, LOG)
        if theirs and any(tuple(f[:3]) not in mine for f, _ in records(theirs)):
            out.append(name)
    return sorted(out)


def merge_ref(ref: str) -> int:
    """Merge one ref into HEAD. 0 merged or nothing to do, 1 stopped."""
    if subprocess.run(["git", "merge-base", "--is-ancestor", ref, "HEAD"], cwd=ROOT).returncode == 0:
        print(f"{ref}: already in this branch")
        return 0
    base = git("merge-base", "HEAD", ref).split()[0]
    versions = {}
    for path in FILES:
        ours, theirs = show("HEAD", path), show(ref, path)
        if ours is None or theirs is None or ours == theirs:
            continue
        versions[path] = (show(base, path) or "", ours, theirs)
    try:
        merged, notes = merge_files(versions, (show("HEAD", LOG) or "", show(ref, LOG) or ""))
    except Conflict as e:
        print(f"{ref}: not merged. Settle these by hand:\n{e}", file=sys.stderr)
        return 1
    subprocess.run(["git", "merge", "--no-ff", "--no-commit", ref], cwd=ROOT, capture_output=True, text=True)
    unmerged = [p for p in git("diff", "--name-only", "--diff-filter=U").splitlines() if p not in merged]
    if unmerged:
        git("merge", "--abort", check=False)
        print(f"{ref}: not merged. Conflicts outside the review files:\n  " + "\n  ".join(unmerged),
              file=sys.stderr)
        return 1
    for path, text in merged.items():
        (ROOT / path).write_text(text, encoding="utf-8", newline="")
        git("add", "--", path)
    git("commit", "--no-verify", "-q", "-m", f"Merge {ref}: review rows merged by key (scripts/review_merge.py)")
    print(f"{ref}: merged" + "".join(f"\n  {n}" for n in notes))
    return 0


def selftest() -> int:
    h = "instrument_id,jurisdiction,state,primary_source_url,verdict,checked_on,note,reviewer,access,archived_url\n"
    path = "data/review/restriction_sources.csv"

    def row(i, verdict="confirmed", on="2026-11-08", note="n"):
        return f'{i},P,KS,https://example.gov/{i},{verdict},{on},"{note}",a + b,opened,\n'
    base = h + row("a")
    # Two appends: both kept, ours first.
    text, d, _ = merge_rows(path, base, base + row("b"), base + row("c"))
    assert text == base + row("b") + row("c") and not d
    # The same result whichever way the merge runs, apart from order.
    back, _, _ = merge_rows(path, base, base + row("c"), base + row("b"))
    assert sorted(back.splitlines()) == sorted(text.splitlines())
    # The same item, the same verdict: the earlier reading stays.
    text, d, _ = merge_rows(path, base, base + row("b", on="2026-11-09", note="later"), base + row("b"))
    assert text == base + row("b") and not d
    # The same item, different verdicts: neither row, one disputed line.
    text, d, _ = merge_rows(path, base, base + row("b"), base + row("b", "contradicts", "2026-11-09"))
    assert text == base and [(x["queue"], x["key"], x["outcome"], x["date"]) for x in d] == \
        [("restriction", "b", "disputed", "2026-11-09")]
    # One side edits an existing row, the other leaves it: the edit wins.
    text, _, _ = merge_rows(path, base, base, h + row("a", note="re-read"))
    assert text == h + row("a", note="re-read")
    # Both edit it differently: a conflict.
    try:
        merge_rows(path, base, h + row("a", note="x"), h + row("a", note="y"))
        raise AssertionError("no conflict")
    except Conflict:
        pass
    # A quoted note with a newline stays one record, byte for byte.
    multi = row("m", note='line one\nline two, "quoted"'.replace('"', '""'))
    text, _, _ = merge_rows(path, base, base + multi, base + row("c"))
    assert text == base + multi + row("c")
    # A log keeps every line either side added, once.
    lh = "date,queue,key,outcome,note\n"
    one, two, three = "2026-11-07,restriction,a,written,x\n", "2026-11-08,restriction,a,written,x\n", \
        "2026-11-09,restriction,a,not_read,y\n"
    text, _, _ = merge_rows(LOG, lh + one, lh + one + two, lh + one + two + three)
    assert text == lh + one + two + three
    # merge_files adds the disputed line to the merged log.
    out, _ = merge_files({path: (base, base + row("b"), base + row("b", "contradicts", "2026-11-09")),
                          LOG: (lh, lh + one, lh + two)})
    assert out[LOG].startswith(lh + one + two + "2026-11-09,restriction,b,disputed,") and out[path] == base
    # A third branch that read b without seeing that line does not bring the row back...
    again, notes = merge_files({path: (base, out[path], base + row("b", on="2026-11-10"))}, (out[LOG], lh + one))
    assert again[path] == base and "left out" in notes[0]
    # ...and a branch that started from the disputed line and re-read it does.
    again, _ = merge_files({path: (out[path], out[path], out[path] + row("b", on="2026-12-01"))}, (out[LOG], out[LOG]))
    assert again[path] == base + row("b", on="2026-12-01")
    print("review_merge selftest: ok")
    return 0


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("refs", nargs="*", help="branches to merge into this one, in order")
    a.add_argument("--pending", action="store_true", help="every verification branch not yet in HEAD")
    a.add_argument("--list", action="store_true", help="with --pending: name the branches and stop")
    a.add_argument("--selftest", action="store_true")
    x = a.parse_args(argv)
    if x.selftest:
        return selftest()
    refs = list(x.refs) + (pending() if x.pending else [])
    if x.list:
        print("\n".join(refs))
        return 0
    if not refs:
        print("nothing to merge")
        return 0
    if git("status", "--porcelain", "--untracked-files=no").strip():
        print("commit or restore your changes first: the merge needs a clean tree", file=sys.stderr)
        return 1
    for ref in refs:
        if merge_ref(ref):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
