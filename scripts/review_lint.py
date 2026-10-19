#!/usr/bin/env python3
"""QC of what a branch changed in the review files (docs/AGENTS.md).

The build checks each review file whole (resolutions.py, negative_checks.py,
state_policies.py, promote_reviewed.py). This checks the rows a branch added
or changed against its base, for what a whole-file check cannot see: that
every change of `access` came with a recorded reading, that nobody reviewed
their own row, that a failed attempt lists what was tried, that triage left a
note, and that an agent's branch stayed in its lane. The qc-auditor runs it
before anything is pushed; anyone can.

Checks (E: error, exit 1; W: warning)
  STRUCTURE        E  a changed review file that does not parse cleanly: a row
                      with more or fewer fields than the header, a CR byte, no
                      final newline
  ACCESS           E  access outside opened, archived, snippet; or archived
                      with no archived_url
  READ_NO_NOTE     E  a row read (opened or archived) whose note is empty, or
                      whose access moved up to opened or archived while its note
                      stayed the same: a reading leaves a note saying what the
                      document says
  SNIPPET_NO_TRIES W  a snippet row whose note names no URL tried or no date
  NO_REVIEWER      E  a new or changed row of a reviewer's file with no
                      reviewer, or no date checked
  SELF_REVIEW      E  the reviewer is the drafter: reviewer = drafted_by, both
                      halves of a "drafter + reviewer" signature the same, or a
                      queue row "Reviewed by" (or "Confirmed by") its own
                      "Drafted by" signer. The date in a signature is ignored.
  CONFIRMED_UNSIGNED E a queue row set to confirmed whose notes name no
                      reviewer, or only its drafter
  AWAITING_UNSIGNED E a queue row set to awaiting_review whose notes do not
                      say "Drafted by"
  TRIAGE_NO_NOTE   E  a queue row moved off lead whose reviewer_notes did not grow
  NOTE_REWRITTEN   W  a note that lost text it had: notes are appended to
  MECHANISM        E  a queue row naming a mechanism outside
                      build_sabin_seeds.MECHANISM_TYPE
  DATE (queue)     E  a queue end_date not YYYY-MM[-DD], or a lifted or
                      expired restriction whose end_date is after today
  NO_END_DATE      W  a lifted or expired restriction with no end_date
  DATE             E  a reviewer's date (checked_on, reviewed_on, drafted_on,
                      evidence_date, date) not YYYY[-MM[-DD]], or after today
  EMDASH           W  an em dash in text a reviewer added to a note (text
                      quoted from a source keeps its own punctuation)
  LOG              E  a verification_log.csv line with an unknown queue or outcome,
                      or an examination_log.csv line with an unknown result or a
                      county_fips that is not five digits
  REMOVED          W  a review row deleted: say why in the pull request
  GENERATED        E  (--lane) a file a build regenerates was changed; restore it
  LANE             E  (--lane) a file outside the lane was changed

Lanes (--lane)
  review   research branches: the hand-kept review files,
           data/review/profile_requests.csv, config/coverage_expectations.json,
           docs/county_checks/*.md
  prose    the copy-editor: hand-written markdown (README.md, docs/,
           deliverables/), never a generated doc

Usage
  python scripts/review_lint.py                        changed rows vs origin/main
  python scripts/review_lint.py --base main --head HEAD
  python scripts/review_lint.py --lane review          also check the branch's lane
  python scripts/review_lint.py --all                  every row, not only changed ones
  python scripts/review_lint.py --selftest
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_sabin_seeds import MECHANISM_TYPE, mechanism_name  # noqa: E402
from common import ROOT  # noqa: E402
from resolutions import access_error  # noqa: E402
from examination_batch import RESULTS as EXAM_RESULTS  # noqa: E402
from verification_batch import LOG_OUTCOMES, QUEUES  # noqa: E402

LAYERS = ROOT / "config" / "layers.json"
EMDASH = "—"
NOTE_COLUMNS = ("note", "evidence_note", "reviewer_notes", "review_note", "draft_note")
DATE_COLUMNS = ("checked_on", "reviewed_on", "drafted_on", "evidence_date", "date")
_PARTIAL = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
# A queue end_date: the precision classify.currency reads (a bare year never lapses).
_END = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")

# file -> (key columns, required reviewer columns on a new or changed row)
FILES = {
    "data/review/restriction_sources.csv": (("instrument_id",), ("reviewer", "checked_on")),
    "data/review/status_resolutions.csv": (("instrument_id",), ("reviewer", "checked_on")),
    "data/review/outcome_resolutions.csv": (("source_record_id",), ("reviewer",)),
    "data/review/place_overrides.csv": (("instrument_id",), ("reviewer", "checked_on")),
    "data/review/nrel_sample_review.csv": (("standard_id",), ("reviewer", "checked_on")),
    "data/review/queue.csv": (("queue_id",), ()),
    "data/review/negative_checks.csv": (("county_fips", "scope", "checked_on"), ()),
    "data/review/state_policies_candidates.csv": (("policy_id",), ()),
    "data/review/group_candidates.csv": (("source_record_id", "group_name"), ()),
    "data/review/cases_candidates.csv": (("source_record_id", "case_name", "docket_number"), ()),
    "data/review/sabin_edition_crosswalk.csv": (("rec_id",), ()),
    "data/review/sabin_state_level_dispositions.csv": (("sabin_record_id",), ()),
    "data/review/verification_log.csv": (("date", "queue", "key", "outcome", "note"), ()),
    "data/review/examination_log.csv": (("date", "county_fips", "run"), ()),
}
ACCESS_REQUIRED = ("data/review/restriction_sources.csv", "data/review/outcome_resolutions.csv",
                   "data/review/place_overrides.csv", "data/review/status_resolutions.csv")
# A queue row with no queue_id yet (hand-added before one was assigned).
QUEUE_FALLBACK = ("source_id", "entity_type", "state", "county", "municipality", "project_name", "source_url")
# profile_requests.csv: site_profile.py records each county profiled.
# coverage_expectations.json: /verify-evidence raises a floor a read source lifts.
REVIEW_LANE_EXTRA = ("data/review/profile_requests.csv", "config/coverage_expectations.json")
REVIEW_LANE_PREFIXES = ("docs/county_checks/",)
GENERATED_PREFIXES = ("data/processed/", "data/db/", "data/snapshots/")

_SIGNER = r"(agent:[A-Za-z0-9_-]+|[^.:;(]+?)\s*(?:\(|[.:;]|$)"
_DRAFTED = re.compile(r"Drafted(?: \d{4}-\d{2}-\d{2})? by " + _SIGNER)
_REVIEWED = re.compile(r"(?:Reviewed|Confirmed)(?: \d{4}-\d{2}-\d{2})? by " + _SIGNER)


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.level} {self.code} {self.where}: {self.message}"


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def who(signature: str) -> str:
    """The signer of a signature, without its run note: 'agent:x-1 (Claude
    Code, 2026-10-09)' and 'agent:x-1 (Claude Code, 2026-10-10)' are one agent."""
    return re.sub(r"\s*\(.*$", "", _s(signature)).strip().lower()


def parse(text: str) -> tuple[list[str], list[dict], list[str]]:
    """(header, rows, structural problems) of a CSV text."""
    problems = []
    if not text:
        return [], [], problems
    if "\r" in text:
        problems.append("has CR bytes (CSV files are LF)")
    if not text.endswith("\n"):
        problems.append("has no final newline, so an appended row would join the last one")
    raw = list(csv.reader(io.StringIO(text.replace("\r\n", "\n"))))
    if not raw:
        return [], [], problems
    header, rows = raw[0], []
    for i, rec in enumerate(raw[1:], start=2):
        if not any(c.strip() for c in rec):
            continue
        if len(rec) != len(header):
            problems.append(f"row {i} has {len(rec)} fields, the header {len(header)}")
            continue
        rows.append(dict(zip(header, rec)))
    return header, rows, problems


def keyed(name: str, rows: list[dict]) -> dict[str, dict]:
    cols = FILES[name][0]
    out: dict[str, dict] = {}
    for r in rows:
        use = cols
        if name.endswith("queue.csv") and not _s(r.get("queue_id")):
            use = QUEUE_FALLBACK
        base = " | ".join(_s(r.get(c)) for c in use)
        k, n = base, 1
        while k in out:
            n += 1
            k = f"{base} #{n}"
        out[k] = r
    return out


def _label(name: str, key: str) -> str:
    return f"{Path(name).name}:{key[:80]}"


def _note_cols(row: dict) -> list[str]:
    return [c for c in NOTE_COLUMNS if c in row]


def _note(row: dict | None) -> str:
    return " ".join(_s(row.get(c)) for c in _note_cols(row)) if row else ""


def _added_text(old: str, new: str) -> str:
    return new[len(old):] if old and new.startswith(old) else new


def check_row(name: str, key: str, old: dict | None, new: dict, today: date) -> list[Finding]:
    f: list[Finding] = []
    where = _label(name, key)

    def add(level, code, msg):
        f.append(Finding(level, code, where, msg))

    _, required = FILES[name]
    # access
    access = _s(new.get("access"))
    # nrel_sample_review.csv leaves access blank on an unverifiable row
    # (nrel_sample.py); queue and group rows carry it once they have a source.
    if "access" in new and (access or name in ACCESS_REQUIRED):
        bad = access_error(new)
        if bad:
            add("E", "ACCESS", bad)
    for col in ("draft_access", "review_access"):
        if _s(new.get(col)) and _s(new.get(col)) not in ("opened", "archived", "snippet"):
            add("E", "ACCESS", f"{col} {new.get(col)!r} must be opened, archived or snippet")
    # a reading leaves a note
    was = _s(old.get("access")) if old else ""
    if access in ("opened", "archived"):
        if not _note(new).strip() and _note_cols(new):
            add("E", "READ_NO_NOTE", f"access {access} with an empty note: say what the document says")
        elif old is not None and was not in ("opened", "archived") and _note(old) == _note(new):
            add("E", "READ_NO_NOTE", f"access moved from {was or 'blank'} to {access} with the note unchanged: "
                                     "a reading leaves a note saying what the document says")
    if access == "snippet" and _note_cols(new):
        text = _note(new)
        if "http" not in text or not _DAY.search(text):
            add("W", "SNIPPET_NO_TRIES", "a snippet row's note lists each URL tried, the date and what it returned")
    # reviewer columns
    for col in required:
        if col in new and not _s(new.get(col)):
            add("E", "NO_REVIEWER", f"{col} is blank on a new or changed row")
    # self-review
    rev, drafter = _s(new.get("reviewer")), _s(new.get("drafted_by"))
    if rev and drafter and who(rev) == who(drafter):
        add("E", "SELF_REVIEW", f"reviewer {rev!r} drafted the row")
    if " + " in rev:
        halves = [who(h) for h in rev.split(" + ")]
        if len(set(halves)) < len(halves):
            add("E", "SELF_REVIEW", f"both readings in {rev!r} are by one agent")
    if name.endswith("queue.csv"):
        f += _queue_row(where, old, new, today)
    # notes are appended to
    if old is not None:
        for col in _note_cols(new):
            before, after = _s(old.get(col)), _s(new.get(col))
            if before and not after.startswith(before) and before not in after:
                f.append(Finding("W", "NOTE_REWRITTEN", where, f"{col} lost text it had; append rather than rewrite"))
    for col in _note_cols(new):
        if EMDASH in _added_text(_s(old.get(col)) if old else "", _s(new.get(col))):
            f.append(Finding("W", "EMDASH", where, f"{col} has an em dash; outside a quotation use a comma, "
                                                   "colon or parentheses"))
    # dates
    for col in DATE_COLUMNS:
        v = _s(new.get(col))
        if not v:
            continue
        if not _PARTIAL.match(v):
            add("E", "DATE", f"{col} {v!r} is not YYYY[-MM[-DD]]")
        elif len(v) == 10 and date.fromisoformat(v) > today:
            add("E", "DATE", f"{col} {v} is after today")
    if name.endswith("verification_log.csv"):
        if _s(new.get("queue")) not in QUEUES:
            add("E", "LOG", f"queue {new.get('queue')!r} must be one of {', '.join(QUEUES)}")
        if _s(new.get("outcome")) not in LOG_OUTCOMES:
            add("E", "LOG", f"outcome {new.get('outcome')!r} must be one of {', '.join(LOG_OUTCOMES)}")
    if name.endswith("examination_log.csv"):
        if _s(new.get("result")) not in EXAM_RESULTS:
            add("E", "LOG", f"result {new.get('result')!r} must be one of {', '.join(EXAM_RESULTS)}")
        if not re.fullmatch(r"\d{5}", _s(new.get("county_fips"))):
            add("E", "LOG", f"county_fips {new.get('county_fips')!r} must be five digits")
    return f


def _queue_row(where: str, old: dict | None, new: dict, today: date) -> list[Finding]:
    f: list[Finding] = []
    # end_date: any date for an instrument still running (a moratorium's term);
    # for one lifted or expired, the date it stopped, never after today.
    end, rstatus = _s(new.get("end_date")), _s(new.get("status"))
    gone = _s(new.get("entity_type")) == "restriction" and rstatus in ("lifted", "expired")
    if end and not _END.match(end):
        f.append(Finding("E", "DATE", where, f"end_date {end!r} is not YYYY-MM or YYYY-MM-DD"))
    elif gone and end and end > today.isoformat()[: len(end)]:
        f.append(Finding("E", "DATE", where, f"status {rstatus} with end_date {end} after today; an instrument "
                                             "that still applies is active until then"))
    elif gone and not end:
        f.append(Finding("W", "NO_END_DATE", where, f"status {rstatus} with no end_date: record the date it "
                                                   "stopped applying, from the source"))
    status, notes = _s(new.get("review_status")), _s(new.get("reviewer_notes"))
    before = _s(old.get("review_status")) if old else ""
    drafters = {who(m) for m in _DRAFTED.findall(notes)}
    reviewers = {who(m) for m in _REVIEWED.findall(notes)}
    for r in reviewers & drafters:
        f.append(Finding("E", "SELF_REVIEW", where, f"{r} drafted this row and reviewed it"))
    if status == "confirmed" and before != "confirmed" and not (reviewers - drafters):
        f.append(Finding("E", "CONFIRMED_UNSIGNED", where,
                         "set to confirmed with no reviewer named other than the drafter: append "
                         "'Reviewed <date> by <signature>: confirmed' to reviewer_notes"))
    if status == "awaiting_review" and before != "awaiting_review" and not drafters:
        f.append(Finding("E", "AWAITING_UNSIGNED", where,
                         "awaiting_review with no 'Drafted by <signature>' in reviewer_notes"))
    if old is not None and before == "lead" and status != "lead" and len(notes) <= len(_s(old.get("reviewer_notes"))):
        f.append(Finding("E", "TRIAGE_NO_NOTE", where,
                         f"moved from lead to {status} with no note: append the date, what was read and why"))
    # Exactly as promote_reviewed.mechanism_list and score_restriction read it.
    for m in (x.strip() for x in _s(new.get("mechanisms")).split(";")):
        if m and mechanism_name(m) not in MECHANISM_TYPE:
            f.append(Finding("E", "MECHANISM", where,
                             f"mechanism {m!r} is not in build_sabin_seeds.MECHANISM_TYPE"))
    return f


def lint_file(name: str, base_text: str, head_text: str, today: date, every_row: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    _, base_rows, _ = parse(base_text)
    _, head_rows, problems = parse(head_text)
    findings += [Finding("E", "STRUCTURE", Path(name).name, p) for p in problems]
    old, new = keyed(name, base_rows), keyed(name, head_rows)
    for key, row in new.items():
        prior = old.get(key)
        # A column added to the file since the base, left blank, is not an
        # edit of the row.
        same = prior is not None and set(prior) <= set(row) \
            and all(prior[k] == v if k in prior else not _s(v) for k, v in row.items())
        if same and not every_row:
            continue
        findings += check_row(name, key, None if every_row else prior, row, today)
    for key in old.keys() - new.keys():
        findings.append(Finding("W", "REMOVED", _label(name, key), "row deleted; say why in the pull request"))
    return findings


# ── Lanes ────────────────────────────────────────────────────────────────────

def _layers() -> dict:
    try:
        return json.loads(LAYERS.read_text(encoding="utf-8"))["files"]
    except (OSError, ValueError, KeyError):
        return {}


def _generated(path: str, layers: dict) -> bool:
    if path.startswith(GENERATED_PREFIXES):
        return True
    spec = layers.get(path)
    return bool(spec and spec.get("layer") == "derived")


def lane_findings(paths: list[str], lane: str, layers: dict | None = None) -> list[Finding]:
    layers = _layers() if layers is None else layers
    out = []
    for p in sorted(set(paths)):
        if p.startswith(".packets/"):
            continue
        if _generated(p, layers):
            out.append(Finding("E", "GENERATED", p, "a build regenerates this file; restore it "
                                                    f"(git checkout <base> -- {p})"))
            continue
        if lane == "review":
            ok = p in FILES or p in REVIEW_LANE_EXTRA or (p.startswith(REVIEW_LANE_PREFIXES) and p.endswith(".md"))
        else:
            spec = layers.get(p) or {}
            ok = p.endswith(".md") and not spec.get("writers") and (
                p == "README.md" or p.startswith(("docs/", "deliverables/")))
        if not ok:
            out.append(Finding("E", "LANE", p, f"outside the {lane} lane; a research branch changes review "
                               "files and pass notes, a prose branch hand-written markdown"))
    return out


# ── Git ──────────────────────────────────────────────────────────────────────

def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def resolve_base(base: str) -> str:
    for ref in ([base] if base else ["origin/main", "main", "HEAD"]):
        if _git("rev-parse", "--verify", "--quiet", ref).strip():
            mb = _git("merge-base", ref, "HEAD").strip()
            return mb or ref
    raise SystemExit(f"review_lint: no base ref {base or 'origin/main, main or HEAD'}")


def text_at(rev: str | None, path: str) -> str:
    if rev is None:
        p = ROOT / path
        return p.read_text(encoding="utf-8") if p.exists() else ""
    return _git("show", f"{rev}:{path}")


def changed_paths(base: str, head: str | None) -> list[str]:
    if head is None:
        names = _git("diff", "--name-only", base).splitlines()
        names += _git("ls-files", "--others", "--exclude-standard").splitlines()
    else:
        names = _git("diff", "--name-only", base, head).splitlines()
    return [n for n in names if n]


def run(base: str, head: str | None, lane: str | None, every_row: bool, today: date) -> list[Finding]:
    paths = changed_paths(base, head)
    findings: list[Finding] = []
    for name in FILES:
        if not every_row and name not in paths:
            continue
        findings += lint_file(name, "" if every_row else text_at(base, name), text_at(head, name), today, every_row)
    if lane:
        findings += lane_findings(paths, lane)
    return findings


def selftest() -> int:
    t = date(2026, 10, 16)
    q = "data/review/queue.csv"
    head = "queue_id,review_status,reviewer_notes,access,mechanisms\n"
    base = head + "q1,lead,Found by GDELT.,snippet,\n"
    triaged = head + "q1,pending,Found by GDELT.,snippet,\n"
    codes = {x.code for x in lint_file(q, base, triaged, t)}
    checks = [
        ("triage without a note", "TRIAGE_NO_NOTE" in codes),
        ("a clean file has nothing", lint_file(q, base, base, t) == []),
        ("self-review", any(x.code == "SELF_REVIEW" for x in lint_file(
            q, base, head + 'q1,confirmed,"Drafted by agent:a-1 (Claude Code, 2026-10-01). '
            'Reviewed by agent:a-1 (Claude Code, 2026-10-02): confirmed.",opened,ban\n', t))),
        ("a lane", [x.code for x in lane_findings(["data/processed/restrictions.csv"], "review", {})]
         == ["GENERATED"]),
    ]
    for name, ok in checks:
        print(("ok   " if ok else "FAIL ") + name)
    return 0 if all(ok for _, ok in checks) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="", help="ref to compare with (default: the merge base with origin/main)")
    ap.add_argument("--head", default=None, help="ref to check (default: the working tree)")
    ap.add_argument("--lane", choices=("review", "prose"), help="also check that the branch stayed in a lane")
    ap.add_argument("--all", action="store_true", help="check every row, not only changed ones")
    ap.add_argument("--today", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    today = date.fromisoformat(a.today) if a.today else date.today()
    base = resolve_base(a.base)
    findings = run(base, a.head, a.lane, a.all, today)
    for x in sorted(findings, key=lambda x: (x.level, x.code, x.where)):
        print(x)
    errors = sum(x.level == "E" for x in findings)
    warnings = len(findings) - errors
    print(f"review_lint: {errors} error(s), {warnings} warning(s) against {base[:12]}"
          + (f", lane {a.lane}" if a.lane else ""))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
