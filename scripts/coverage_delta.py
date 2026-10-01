#!/usr/bin/env python3
"""A column's coverage cannot silently collapse. Adapted from
pricephillips/data-center-map qc/coverage_delta.py (its spec 005, US3;
docs/PASSOFF_2026-09-29_tooling_from_data_center_map.md, B3); copied in
spirit, not imported.

qc_gate.py checks each row. Nothing checked whole columns: if Moratorium
Nation renamed `date_enacted_iso`, or the Sabin extraction dropped `county`,
every row would still pass and the column would publish empty. This compares
the non-empty count of every column of each published CSV with the previous
commit's copy and fails when a column that was well filled loses more than
THRESHOLD of its values.

Rules
  - Only columns with at least MIN_FILLED values before are judged, so a
    column that was nearly empty cannot trip the gate by losing two cells.
  - A column that disappears counts as dropping to zero.
  - Losing rows is not itself a failure (quarantine and scope rules remove
    rows on purpose), so the loss is measured as a fraction of the column's
    fill rate, not its raw count.

A deliberate drop is declared in config/coverage_exceptions.json with the
count the column is expected to have afterwards and a reason. The exception
clears only that exact count, so it cannot hide a later collapse, and once the
next build compares against the new baseline it no longer matters; delete it
then.

A column can also carry a standing floor in config/coverage_expectations.json:
the least number of values it must have, checked against the build itself
rather than the previous commit. That is how a new column is covered on the
build that introduces it (there is no previous copy to compare with), and it
keeps covering it afterwards. Raise a floor when coverage improves; lowering
one is a decision, with its reason in the file.

Writes data/processed/coverage_delta.md. Exit 1 on any failure; build-data.yml
runs it before committing, so a collapsed column is never published.

Usage
  python scripts/coverage_delta.py [--base HEAD~1]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_REL = "data/processed"
FILES = ("restrictions.csv", "contested_projects.csv", "cases.csv", "sources.csv")
OUT_MD = ROOT / PROCESSED_REL / "coverage_delta.md"
EXCEPTIONS = ROOT / "config" / "coverage_exceptions.json"
EXPECTATIONS = ROOT / "config" / "coverage_expectations.json"
THRESHOLD = 0.20
MIN_FILLED = 20


def profile(text: str) -> tuple[int, dict[str, int]]:
    """(rows, column -> non-empty count). A repeated header name keeps the
    first column."""
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"), newline="")))
    if not rows:
        return 0, {}
    header, body = rows[0], [r for r in rows[1:] if r]
    counts: dict[str, int] = {}
    for i, name in enumerate(header):
        if name not in counts:
            counts[name] = sum(1 for r in body if i < len(r) and r[i].strip())
    return len(body), counts


def compare(before: tuple[int, dict[str, int]], after: tuple[int, dict[str, int]],
            threshold: float = THRESHOLD, min_filled: int = MIN_FILLED) -> list[dict]:
    """Columns whose fill rate fell by more than threshold."""
    (rows_b, cols_b), (rows_a, cols_a) = before, after
    out = []
    for col, n_b in cols_b.items():
        if n_b < min_filled or not rows_b:
            continue
        n_a = cols_a.get(col, 0)
        rate_b, rate_a = n_b / rows_b, (n_a / rows_a if rows_a else 0.0)
        if rate_a < rate_b * (1 - threshold):
            out.append({"column": col, "before": n_b, "after": n_a,
                        "rate_before": rate_b, "rate_after": rate_a,
                        "missing": col not in cols_a})
    return out


def load_exceptions(path: Path = EXCEPTIONS) -> dict:
    if not path.exists():
        return {}
    return {k: v for k, v in json.loads(path.read_text(encoding="utf-8")).items()
            if not k.startswith("_")}


def load_expectations(path: Path = EXPECTATIONS) -> dict:
    return load_exceptions(path)


def below_floor(file: str, after: tuple[int, dict[str, int]], expectations: dict) -> list[dict]:
    """Columns of file with fewer values than their declared floor. A missing
    column has zero."""
    _, cols = after
    out = []
    for col, exp in sorted(expectations.get(file, {}).items()):
        n = cols.get(col, 0)
        if n < exp["min_filled"]:
            out.append({"column": col, "after": n, "floor": exp["min_filled"],
                        "missing": col not in cols})
    return out


def split_declared(file: str, drops: list[dict], exceptions: dict) -> tuple[list[dict], list[dict]]:
    """(undeclared failures, declared drops). A drop is declared only when its
    column's new count equals expect_after exactly."""
    failed, declared = [], []
    for d in drops:
        exc = exceptions.get(file, {}).get(d["column"])
        if exc and d["after"] == exc.get("expect_after") and exc.get("reason"):
            declared.append({**d, "reason": exc["reason"]})
        else:
            failed.append(d)
    return failed, declared


def at_rev(rev: str, rel: str) -> str | None:
    r = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else None


def render(results: dict[str, list[dict] | None], declared: list[tuple[str, dict]] = (),
           floors: list[tuple[str, dict]] = (), floors_checked: int = 0) -> str:
    lines = ["# Column coverage", "",
             f"Each published CSV against the previous commit. A column with at least "
             f"{MIN_FILLED} values fails when its fill rate drops by more than "
             f"{int(THRESHOLD * 100)} percent.", ""]
    failed = [(f, d) for f, ds in results.items() if ds for d in ds]
    if floors:
        lines += ["Below the floor in config/coverage_expectations.json:", "",
                  "| File | Column | Values | Floor |", "|---|---|---:|---:|"]
        lines += [f"| {f} | {d['column']} | {'column missing' if d['missing'] else d['after']} | "
                  f"{d['floor']} |" for f, d in floors]
        lines.append("")
    elif floors_checked:
        lines += [f"Every declared floor holds ({floors_checked} checked).", ""]
    if declared:
        lines += ["Declared drops (config/coverage_exceptions.json):", ""]
        lines += [f"- {f} `{d['column']}`: {d['before']} -> {d['after']}. {d['reason']}"
                  for f, d in declared]
        lines.append("")
    if not failed:
        if floors:
            return "\n".join(lines) + "\n"
        compared = [f for f, ds in results.items() if ds is not None]
        lines.append(f"No column collapsed ({len(compared)} files compared).")
        return "\n".join(lines) + "\n"
    lines += ["| File | Column | Before | After | Fill before | Fill after |",
              "|---|---|---:|---:|---:|---:|"]
    for f, d in failed:
        after = "column missing" if d["missing"] else str(d["after"])
        lines.append(f"| {f} | {d['column']} | {d['before']} | {after} | "
                     f"{d['rate_before']:.0%} | {d['rate_after']:.0%} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="HEAD~1")
    args = ap.parse_args(argv)
    results: dict[str, list[dict] | None] = {}
    declared: list[tuple[str, dict]] = []
    exceptions = load_exceptions()
    expectations = load_expectations()
    floors: list[tuple[str, dict]] = []
    floors_checked = sum(len(v) for v in expectations.values())
    for name in FILES:
        rel = f"{PROCESSED_REL}/{name}"
        old = at_rev(args.base, rel)
        path = ROOT / rel
        if path.exists():
            floors += [(name, d) for d in below_floor(name, profile(path.read_text(encoding="utf-8")),
                                                       expectations)]
        if old is None or not path.exists():
            results[name] = None
            continue
        drops = compare(profile(old), profile(path.read_text(encoding="utf-8")))
        results[name], ok = split_declared(name, drops, exceptions)
        declared += [(name, d) for d in ok]
    OUT_MD.write_text(render(results, declared, floors, floors_checked), encoding="utf-8", newline="\n")
    failures = [(f, d) for f, ds in results.items() if ds for d in ds]
    for f, d in failures:
        print(f"coverage_delta: {f} column {d['column']}: {d['before']} -> {d['after']}")
    for f, d in floors:
        print(f"coverage_delta: {f} column {d['column']}: {d['after']} below floor {d['floor']}")
    print(f"coverage_delta: {len(failures)} collapsed column(s), {len(floors)} below floor")
    return 1 if failures or floors else 0


if __name__ == "__main__":
    sys.exit(main())
