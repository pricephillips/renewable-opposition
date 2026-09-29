#!/usr/bin/env python3
"""
processed_diff.py

Writes data/processed/diff_summary.md: what a build changed in the published
data, compared with the previous commit. Ported from pricephillips/data-center-map
master_diff.py (docs/PASSOFF_2026-09-29_tooling_from_data_center_map.md, A8);
copied, not imported.

Simpler than the original because every processed record has a stable `id`:
each of restrictions.csv, contested_projects.csv and cases.csv is compared
with daff keyed on `id`, so a changed cell reads as a modified row rather than
a removal plus an addition. The summary gives, per entity, the count of added,
removed and modified rows; every change to a tracked field (outcome, status,
case_status, finality_evidence, severity_score) with both values; and up to
DETAIL_CAP detail rows.

The output carries no timestamp or commit hash, so a build that changes no
published data rewrites the file byte for byte and build-data.yml has nothing
to commit.

Usage
  python scripts/processed_diff.py [--base HEAD~1]

CI checks out with fetch-depth: 2 so HEAD~1 exists. Without a prior revision
the summary says so and the module exits 0.
"""

from __future__ import annotations

import argparse
import csv
import io
import subprocess
import sys
from pathlib import Path

import daff

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_REL = "data/processed"
OUT_MD = ROOT / PROCESSED_REL / "diff_summary.md"
ENTITIES = ("restrictions", "contested_projects", "cases")
TRACKED = ("outcome", "status", "case_status", "finality_evidence", "severity_score")
# Human-readable label for a row, first non-empty field wins.
LABEL_FIELDS = ("project_name", "case_name", "jurisdiction")
DETAIL_CAP = 200


def read_rows(text: str) -> list[list[str]]:
    """Parse CSV text, dropping any repeated column name (keeps the first).
    Builds before 2026-09-29 wrote `id` twice."""
    rows = [r for r in csv.reader(io.StringIO(text.lstrip("\ufeff"), newline="")) if r]
    if not rows:
        return rows
    seen: set[str] = set()
    keep = []
    for i, name in enumerate(rows[0]):
        if name not in seen:
            seen.add(name)
            keep.append(i)
    return [[r[i] if i < len(r) else "" for i in keep] for r in rows]


def at_rev(rev: str, rel: str) -> str | None:
    r = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else None


def hilite(a: list[list[str]], b: list[list[str]], key: str = "id") -> list[list[str]]:
    flags = daff.CompareFlags()
    flags.addPrimaryKey(key)
    flags.show_unchanged_columns = True  # label fields; detail_columns trims
    align = daff.compareTables(daff.PythonTableView(a), daff.PythonTableView(b), flags).align()
    out: list[list] = []
    daff.TableDiff(align, flags).hilite(daff.PythonTableView(out))
    return [["" if c is None else str(c) for c in row] for row in out]


def _split(diff: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    """The header row (tag @@) and the data rows after it. A schema-change row
    (tag !) may precede the header."""
    for i, row in enumerate(diff):
        if row and row[0] == "@@":
            return row, diff[i + 1:]
    return (diff[0] if diff else []), diff[1:]


def counts(diff: list[list[str]]) -> dict[str, int]:
    n = {"added": 0, "removed": 0, "modified": 0}
    for row in _split(diff)[1]:
        tag = row[0] if row else ""
        if tag == "+++":
            n["added"] += 1
        elif tag == "---":
            n["removed"] += 1
        elif "->" in tag:
            n["modified"] += 1
    return n


def _after(v: str, tag: str) -> str:
    marker = "-->" if tag == "-->" else "->"
    return v.split(marker)[-1] if marker in v else v


def _label(row: list[str], idx: dict[str, int], tag: str) -> str:
    def get(c: str) -> str:
        i = idx.get(c)
        return _after(row[i], tag) if i is not None and i < len(row) else ""
    name = next((get(f) for f in LABEL_FIELDS if get(f)), "")
    rid, st = get("id"), get("state")
    return f"{rid} ({name}, {st})" if name else f"{rid} ({st})" if st else rid


def tracked_changes(entity: str, diff: list[list[str]]) -> list[dict[str, str]]:
    """Modified cells in TRACKED columns, with both values."""
    header, body = _split(diff)
    idx = {h: i for i, h in enumerate(header)}
    changes = []
    for row in body:
        tag = row[0] if row else ""
        if "->" not in tag:
            continue
        marker = "-->" if tag == "-->" else "->"
        for col in TRACKED:
            i = idx.get(col)
            if i is None or i >= len(row) or marker not in row[i]:
                continue
            before, _, after = row[i].partition(marker)
            changes.append({"entity": entity, "row": _label(row, idx, tag),
                            "column": col, "before": before, "after": after})
    return changes


def detail_columns(header: list[str], body: list[list[str]]) -> list[int]:
    """Indexes to show in a detail table: the daff tag, id, the label fields,
    and every column with a modified cell. Unchanged long text stays out."""
    keep = {"@@", "id", "state", *LABEL_FIELDS}
    changed = {i for r in body if "->" in (r[0] if r else "")
               for i, c in enumerate(r[1:], 1) if "->" in c}
    return [i for i, h in enumerate(header) if h in keep or i in changed]


def esc(v: str) -> str:
    return str(v).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def render(results: dict[str, list[list[str]] | None]) -> str:
    """results maps entity to its hilite table, or None when the base
    revision has no copy of the file."""
    intro = ["# Processed data diff", "",
             "What the last build changed in `data/processed/`, compared with the "
             "previous commit. Rows are matched on `id`.", ""]
    if all(d is None for d in results.values()):
        return "\n".join(intro + ["No prior revision to compare against.", ""])
    lines = list(intro)

    lines += ["## Row counts", "", "| Entity | Added | Removed | Modified |",
              "|---|---|---|---|"]
    changes: list[dict[str, str]] = []
    any_change = False
    for entity, d in results.items():
        if d is None:
            lines.append(f"| {entity} | new file | | |")
            any_change = True
            continue
        n = counts(d)
        any_change |= any(n.values())
        lines.append(f"| {entity} | {n['added']} | {n['removed']} | {n['modified']} |")
        changes += tracked_changes(entity, d)
    lines.append("")
    if not any_change:
        return "\n".join(intro + ["No changes.", ""])

    lines += ["## Tracked field changes", ""]
    if changes:
        lines += ["| Entity | Row | Column | Before | After |", "|---|---|---|---|---|"]
        lines += [f"| {c['entity']} | {esc(c['row'])} | {c['column']} | {esc(c['before'])} | "
                  f"{esc(c['after'])} |" for c in changes]
    else:
        lines.append("No changes to " + ", ".join(TRACKED) + ".")

    lines += ["", "## Detail", ""]
    shown = 0
    for entity, d in results.items():
        if d is None:
            continue
        header, body = _split(d)
        body = [r for r in body if r and r[0] not in ("", "...", ":")]
        if not body:
            continue
        room = DETAIL_CAP - shown
        cols = detail_columns(header, body)
        lines += [f"### {entity}", "",
                  "| " + " | ".join(esc(header[i]) for i in cols) + " |",
                  "|" + "---|" * len(cols)]
        lines += ["| " + " | ".join(esc(r[i] if i < len(r) else "") for i in cols) + " |"
                  for r in body[:max(room, 0)]]
        if len(body) > room:
            lines += ["", f"{len(body) - max(room, 0)} further rows not shown."]
        lines.append("")
        shown += min(len(body), max(room, 0))
    if not shown:
        lines += ["No row-level changes.", ""]
    return "\n".join(lines).rstrip("\n") + "\n"


def build(base: str) -> str:
    results: dict[str, list[list[str]] | None] = {}
    for entity in ENTITIES:
        rel = f"{PROCESSED_REL}/{entity}.csv"
        old = at_rev(base, rel)
        if old is None:
            results[entity] = None
            continue
        new = (ROOT / rel).read_text(encoding="utf-8")
        results[entity] = hilite(read_rows(old), read_rows(new))
    return render(results)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="HEAD~1")
    args = ap.parse_args(argv)
    text = build(args.base)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(text, encoding="utf-8", newline="\n")
    print(f"processed_diff: wrote {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
