#!/usr/bin/env python3
"""
headline_history.py

Keeps data/snapshots/headline_history.csv: the headline figures as each
data build published them, one row per day on which they changed, so the
dashboard can show what changed from build to build
(docs/national_database_design.md, phase 5).

The figures come from data/processed/headline_metrics.json, the numbers to
quote. A figure the metrics did not carry yet on a given day (county coverage
before it existed, for one) is left blank, never filled in.

Modes
  default      read the current headline_metrics.json; if its figures differ
               from the last row, add a row for today (or replace today's row,
               so a day holds the figures its last build published). Run by
               the Build dashboard data workflow after the processed build.
  --backfill   rebuild the file from the git history of
               headline_metrics.json (needs the full history: git fetch
               --unshallow), one row per day on which the figures changed.

Usage
  python scripts/headline_history.py
  python scripts/headline_history.py --backfill
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import PROCESSED_DIR, ROOT, read_csv, write_csv  # noqa: E402

HISTORY = ROOT / "data" / "snapshots" / "headline_history.csv"
METRICS = PROCESSED_DIR / "headline_metrics.json"
METRICS_IN_GIT = "data/processed/headline_metrics.json"

# column -> path into headline_metrics.json
FIGURES = {
    "restrictions": ("restrictions", "by_scope", "renewables_only", "instruments"),
    "severe_restrictions": ("restrictions", "by_scope", "renewables_only", "severe_instruments"),
    "verified_restrictions": ("restrictions", "by_scope", "renewables_only", "by_verification", "verified"),
    "multi_sector_restrictions": ("restrictions", "by_scope", "multi_sector_data_centers", "instruments"),
    "contested_projects": ("contested_projects", "projects"),
    "confirmed_outcomes": ("contested_projects", "confirmed_outcomes"),
    "verified_projects": ("contested_projects", "by_verification", "verified"),
    "cases": ("cases", "cases"),
    "siting_standard_rows": ("siting_standards", "rows"),
    "state_policies": ("state_policies", "rows"),
    "counties_with_records": ("county_coverage", "with_any_record"),
    "counties_not_examined": ("county_coverage", "with_neither"),
}
FIELDS = ["date"] + list(FIGURES)


def figures(metrics: dict) -> dict[str, str]:
    out = {}
    for col, path in FIGURES.items():
        v = metrics
        for k in path:
            v = v.get(k) if isinstance(v, dict) else None
            if v is None:
                break
        # A verification breakdown with no verified rows omits the key: zero,
        # once the breakdown itself exists.
        if v is None and path[-1] == "verified":
            parent = metrics
            for k in path[:-1]:
                parent = parent.get(k) if isinstance(parent, dict) else None
            v = 0 if isinstance(parent, dict) else None
        out[col] = "" if v is None else str(v)
    return out


def add(rows: list[dict], day: str, figs: dict[str, str]) -> list[dict]:
    """rows with figs recorded for day: nothing changes when they equal the
    last row's; a row already dated day is replaced."""
    last = rows[-1] if rows else None
    if last and all(last.get(c, "") == figs[c] for c in FIGURES):
        return rows
    row = {"date": day, **figs}
    if last and last["date"] == day:
        rows = rows[:-1]
        if rows and all(rows[-1].get(c, "") == figs[c] for c in FIGURES):
            return rows
    return rows + [row]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def backfill() -> list[dict]:
    if _git("rev-parse", "--is-shallow-repository").strip() == "true":
        raise SystemExit("headline_history: a shallow clone has only part of the history; "
                         "run git fetch --unshallow first")
    commits = _git("log", "--reverse", "--format=%H %cI", "--", METRICS_IN_GIT).split("\n")
    rows: list[dict] = []
    for line in filter(None, commits):
        sha, when = line.split(" ", 1)
        day = datetime.fromisoformat(when).astimezone(timezone.utc).date().isoformat()
        try:
            metrics = json.loads(_git("show", f"{sha}:{METRICS_IN_GIT}"))
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        rows = add(rows, day, figures(metrics))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backfill", action="store_true", help="rebuild from the git history")
    args = ap.parse_args(argv)
    if args.backfill:
        rows = backfill()
    else:
        rows = read_csv(HISTORY) if HISTORY.exists() else []
        rows = add(rows, date.today().isoformat(), figures(json.loads(METRICS.read_text(encoding="utf-8"))))
    write_csv(HISTORY, rows, FIELDS)
    print(f"headline_history: {len(rows)} rows in {HISTORY.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
