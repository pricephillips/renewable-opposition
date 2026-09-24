#!/usr/bin/env python3
"""Pull the renewables subset of Moratorium Nation into data/seed/restrictions_seed.csv.

Source: mjbommar/moratorium-data-2026 (CC-BY-4.0 data, MIT code).
https://github.com/mjbommar/moratorium-data-2026

What this does:
  1. Downloads the current moratorium_inventory.csv from that repo's main branch.
  2. Keeps only instruments whose `sectors` column includes solar, wind, or
     battery_storage.
  3. Explodes multi-sector rows into one row per matching technology (this
     repo's restrictions_seed.csv schema is one technology per row; Moratorium
     Nation's is one row per instrument with a multi-label sectors array).
  4. Keeps only `enacted_status` in {active, extended, pending} -- see
     "excluded" note below for why replaced/expired/rescinded are left out.
  5. Maps enacted_status to this repo's 1-4 severity scale:
       active / extended -> 4  (an in-force moratorium reads as an explicit
                                 ban under this repo's own scale definition)
       pending            -> 2  (proposed, not yet constraining -- early
                                 signal, not a material burden yet)
  6. Normalizes state to its two-letter code and carries the instrument's
     end date and coordinates.
  7. Writes data/seed/restrictions_seed.csv, overwriting any prior run's
     Moratorium-Nation-sourced rows (identified by the `source` column) while
     leaving any hand-added rows from other sources untouched.

Excluded on purpose (not a bug): `replaced`, `expired`, and `rescinded`
instruments. A `replaced` moratorium was superseded by a permanent ordinance
whose actual stringency this dataset doesn't capture -- scoring it here would
be a guess, not a fact. `expired`/`rescinded` are no longer in force, so they
are not currently "restrictions" under this repo's own definition. Revisit
this decision once restrictions_seed.csv has a status field with a place to
put the disposition.

Usage:
    python scripts/fetch_moratorium_nation.py
    python scripts/fetch_moratorium_nation.py --dry-run   # print, don't write

Requires: requests (falls back to urllib if requests isn't installed).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import read_csv, state_code, write_csv  # noqa: E402

SOURCE_CSV_URL = (
    "https://raw.githubusercontent.com/mjbommar/moratorium-data-2026"
    "/main/data/moratorium_inventory.csv"
)
SOURCE_LABEL = "Moratorium Nation (mjbommar/moratorium-data-2026), CC-BY-4.0"
SOURCE_URL = (
    "https://github.com/mjbommar/moratorium-data-2026/blob/main"
    "/data/moratorium_inventory.csv"
)

TARGET_SECTORS = {"solar", "wind", "battery_storage"}
KEEP_STATUS = {"active", "extended", "pending"}
SEVERITY_BY_STATUS = {"active": 4, "extended": 4, "pending": 2}

FIELDNAMES = [
    "state",
    "technology",
    "restriction_type",
    "severity_score",
    "description",
    "status",
    "jurisdiction",
    "jurisdiction_type",
    "date_enacted_iso",
    "current_end_date_iso",
    "latitude",
    "longitude",
    "needs_verification",
    "moratorium_id",
    "source",
    "source_url",
]

ROOT = Path(__file__).resolve().parent.parent
SEED_PATH = ROOT / "data" / "seed" / "restrictions_seed.csv"


def fetch_source_csv() -> str:
    try:
        import requests  # type: ignore

        resp = requests.get(SOURCE_CSV_URL, timeout=30)
        resp.raise_for_status()
        return resp.text
    except ImportError:
        from urllib.request import urlopen

        with urlopen(SOURCE_CSV_URL, timeout=30) as f:  # nosec B310 - fixed https URL
            return f.read().decode("utf-8-sig")


def build_description(row: dict) -> str:
    parts = []
    if row.get("trigger"):
        parts.append(row["trigger"].strip())
    if row.get("current_status"):
        parts.append(row["current_status"].strip())
    if row.get("legal_basis"):
        parts.append("Legal basis: " + row["legal_basis"].strip())
    text = ". ".join(p.rstrip(".") for p in parts if p)
    return text + "." if text else ""


def transform(csv_text: str) -> tuple[list[dict], list[tuple[str, str, list[str]]]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    out_rows: list[dict] = []
    excluded: list[tuple[str, str, list[str]]] = []

    for row in reader:
        try:
            sectors = set(json.loads(row["sectors"])) if row.get("sectors") else set()
        except (json.JSONDecodeError, TypeError):
            sectors = set()

        hit = sorted(sectors & TARGET_SECTORS)
        if not hit:
            continue

        status = row.get("enacted_status", "")
        if status not in KEEP_STATUS:
            excluded.append((row.get("moratorium_id", ""), status, hit))
            continue

        description = build_description(row)
        for tech in hit:
            out_rows.append(
                {
                    "state": state_code(row.get("state_abbrev") or row.get("state", "")),
                    "technology": tech,
                    "restriction_type": "moratorium",
                    "severity_score": SEVERITY_BY_STATUS[status],
                    "description": description,
                    "status": status,
                    "jurisdiction": row.get("jurisdiction", ""),
                    "jurisdiction_type": row.get("jurisdiction_type", ""),
                    "date_enacted_iso": row.get("date_enacted_iso", ""),
                    "current_end_date_iso": row.get("current_end_date_iso", ""),
                    "latitude": row.get("latitude", ""),
                    "longitude": row.get("longitude", ""),
                    # Moratorium Nation marks facts it has not yet confirmed
                    # with [VERIFY] tags; carry that flag instead of dropping rows.
                    "needs_verification": "yes" if row.get("has_verify_tags", "").lower() == "true" else "",
                    "moratorium_id": row.get("moratorium_id", ""),
                    "source": SOURCE_LABEL,
                    "source_url": SOURCE_URL,
                }
            )
    return out_rows, excluded


def load_existing_non_moratorium_nation_rows() -> list[dict]:
    """Preserve any rows in restrictions_seed.csv that came from elsewhere."""
    return [r for r in read_csv(SEED_PATH) if r.get("source") != SOURCE_LABEL]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Print a summary; do not write the CSV."
    )
    parser.add_argument(
        "--source-file", type=Path,
        help="Read a local copy of moratorium_inventory.csv instead of downloading it.",
    )
    args = parser.parse_args()

    if args.source_file:
        csv_text = args.source_file.read_text(encoding="utf-8-sig")
    else:
        csv_text = fetch_source_csv()
    new_rows, excluded = transform(csv_text)
    kept_rows = load_existing_non_moratorium_nation_rows()
    all_rows = new_rows + kept_rows

    print(f"Moratorium Nation: {len(new_rows)} renewables rows kept "
          f"(active/extended/pending), {len(excluded)} excluded "
          f"(replaced/expired/rescinded):")
    for moratorium_id, status, sectors in excluded:
        print(f"  - {moratorium_id}: {status} ({', '.join(sectors)})")
    if kept_rows:
        print(f"Preserved {len(kept_rows)} existing non-Moratorium-Nation row(s).")

    if args.dry_run:
        print(f"[dry-run] Would write {len(all_rows)} total rows to {SEED_PATH}")
        return 0

    # Moratorium Nation rows first, then rows from other sources, which may
    # carry extra columns (write_csv keeps them).
    write_csv(SEED_PATH, new_rows + kept_rows, FIELDNAMES)
    print(f"Wrote {len(all_rows)} total rows to {SEED_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
