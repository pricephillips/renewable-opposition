"""Append a row to data/snapshots/manifest.csv for each published output that changed.

Borrowed from pricephillips/data-center-map's snapshots/manifest.csv: a dated,
hashed record of what each published file contained, so a count quoted on a
given day can be traced to the exact artifact behind it and any drop in
records is visible after the fact.

A row is appended only when a file's hash differs from the last row recorded
for it, so a nightly run that changes nothing writes nothing. The manifest is
append-only; never rewrite it.

data/snapshots/headline_history.csv is the same idea for the numbers: one row
per build date on which any headline figure changed (restriction instruments,
severe, verified, lapsed, multi-sector, projects, confirmed and verified
outcomes, cases, county coverage), read from headline_metrics.json. A number
quoted on a given day can be found by date, and a trend can be drawn without
replaying builds. After pricephillips/data-center-map's dated change log
(change_log.csv, calibration_history.csv); copied in spirit, not imported.

Usage
  python scripts/snapshot_manifest.py            append changed files
  python scripts/snapshot_manifest.py --dry-run  print what would be appended
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROCESSED_DIR, ROOT, read_csv  # noqa: E402

MANIFEST = ROOT / "data" / "snapshots" / "manifest.csv"
FIELDS = ["date", "file", "rows", "sha256"]
TRACKED = ["restrictions.csv", "contested_projects.csv", "cases.csv", "sources.csv", "county_summary.csv"]
HISTORY = ROOT / "data" / "snapshots" / "headline_history.csv"
METRICS = PROCESSED_DIR / "headline_metrics.json"
HISTORY_FIELDS = ["date", "restriction_instruments", "restriction_severe", "restriction_verified",
                  "restriction_lapsed", "multi_sector_instruments", "projects", "projects_confirmed",
                  "projects_verified", "cases", "counties_with_record", "counties_with_negative_check",
                  "counties_with_neither"]


def history_row(metrics: dict, today: str) -> dict:
    """The headline numbers as one flat row (every value a string, as the CSV
    holds them, so a stored row compares equal to a fresh one)."""
    ren = metrics["restrictions"]["by_scope"]["renewables_only"]
    multi = metrics["restrictions"]["by_scope"]["multi_sector_data_centers"]
    proj, cases = metrics["contested_projects"], metrics["cases"]
    cov = metrics.get("county_coverage") or {}
    row = {
        "date": today,
        "restriction_instruments": ren["instruments"],
        "restriction_severe": ren["severe_instruments"],
        "restriction_verified": ren["by_verification"].get("verified", 0),
        "restriction_lapsed": ren.get("by_currency", {}).get("lapsed_unconfirmed", 0),
        "multi_sector_instruments": multi["instruments"],
        "projects": proj["projects"],
        "projects_confirmed": proj["confirmed_outcomes"],
        "projects_verified": proj["by_verification"].get("verified", 0),
        "cases": cases["cases"],
        "counties_with_record": cov.get("with_any_record", ""),
        "counties_with_negative_check": cov.get("with_negative_check", ""),
        "counties_with_neither": cov.get("with_neither", ""),
    }
    return {k: str(v) for k, v in row.items()}


def pending_history(today: str) -> dict | None:
    """The row to append, or None when no number changed (or no metrics exist)."""
    if not METRICS.exists():
        return None
    row = history_row(json.loads(METRICS.read_text(encoding="utf-8")), today)
    last = read_csv(HISTORY)
    if last and all(last[-1].get(k, "") == v for k, v in row.items() if k != "date"):
        return None
    return row


def append_rows(path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerows(rows)


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
    today = date.today().isoformat()
    rows = pending_rows(today)
    for r in rows:
        print(f"{r['date']} {r['file']}: {r['rows']} rows, sha256 {r['sha256'][:12]}")
    if not rows:
        print("no published file changed; manifest untouched")
    history = pending_history(today)
    if history:
        print("headline numbers changed: " + ", ".join(f"{k} {v}" for k, v in history.items() if k != "date"))
    else:
        print("no headline number changed; history untouched")
    if args.dry_run:
        return 0
    if rows:
        append_rows(MANIFEST, FIELDS, rows)
    if history:
        append_rows(HISTORY, HISTORY_FIELDS, [history])
    return 0


if __name__ == "__main__":
    sys.exit(main())
