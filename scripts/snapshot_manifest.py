"""Append a row to data/snapshots/manifest.csv for each published output that changed.

Borrowed from pricephillips/data-center-map's snapshots/manifest.csv: a dated,
hashed record of what each published file contained, so a count quoted on a
given day can be traced to the exact artifact behind it and any drop in
records is visible after the fact.

A row is appended only when a file's hash differs from the last row recorded
for it, so a nightly run that changes nothing writes nothing. The manifest is
append-only; never rewrite it.

Usage
  python scripts/snapshot_manifest.py            append changed files
  python scripts/snapshot_manifest.py --dry-run  print what would be appended
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROCESSED_DIR, ROOT, read_csv  # noqa: E402

MANIFEST = ROOT / "data" / "snapshots" / "manifest.csv"
FIELDS = ["date", "file", "rows", "sha256"]
TRACKED = ["restrictions.csv", "contested_projects.csv", "cases.csv", "sources.csv"]


def file_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as f:
        return max(sum(1 for _ in csv.reader(f)) - 1, 0)


def pending_rows(today: str) -> list[dict]:
    last = {r["file"]: r["sha256"] for r in read_csv(MANIFEST)}
    out = []
    for name in TRACKED:
        path = PROCESSED_DIR / name
        if not path.exists():
            continue
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if last.get(name) != sha:
            out.append({"date": today, "file": name, "rows": file_rows(path), "sha256": sha})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    rows = pending_rows(date.today().isoformat())
    for r in rows:
        print(f"{r['date']} {r['file']}: {r['rows']} rows, sha256 {r['sha256'][:12]}")
    if not rows:
        print("no published file changed; manifest untouched")
    if args.dry_run or not rows:
        return 0
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    new = not MANIFEST.exists()
    with MANIFEST.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
