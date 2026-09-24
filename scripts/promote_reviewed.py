"""Move human-confirmed review rows into the seed CSVs (pipeline step 4 -> 5).

Two review files feed this:

  data/review/queue.csv             candidates written by parse.py extractors.
                                    A row is promoted when review_status is
                                    'confirmed'; it goes to the seed for its
                                    entity_type (restriction, contested_project
                                    or case).
  data/review/cases_candidates.csv  litigated projects/restrictions queued by
                                    build_sabin_seeds.py. A row is promoted to
                                    cases_seed.csv when review_status is
                                    'confirmed' and case_name, court,
                                    court_level and case_source_url are filled.

A promoted row is marked 'promoted' in its review file, so re-running is a
no-op. Rows missing a seed's required fields are reported and left alone.

Case severity: a reviewer may set severity_score on a candidate; otherwise it
defaults to 3, the contested-projects score for "litigation filed".

Usage:
    python scripts/promote_reviewed.py [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_seed_outputs import REQUIRED  # noqa: E402
from common import REVIEW_DIR, SEED_DIR, read_csv, write_csv  # noqa: E402

QUEUE_PATH = REVIEW_DIR / "queue.csv"
CANDIDATES_PATH = REVIEW_DIR / "cases_candidates.csv"

SEED_FOR = {
    "restriction": ("restrictions", SEED_DIR / "restrictions_seed.csv"),
    "contested_project": ("contested_projects", SEED_DIR / "contested_projects_seed.csv"),
    "case": ("cases", SEED_DIR / "cases_seed.csv"),
}

# review/queue.csv columns carried into every seed row (when non-empty).
QUEUE_COMMON = [
    "state", "county", "municipality", "jurisdiction_type", "project_name",
    "technology", "severity_score", "description", "source_url",
]
QUEUE_SPECIFIC = {
    "restriction": ["restriction_type", "adopted_date", "effective_date"],
    "contested_project": ["opposition_type", "first_event_date", "status"],
    "case": ["court_level", "filing_date", "docket_number"],
}

CASE_FIELDS = [
    "state", "project_name", "technology", "court_level", "severity_score",
    "description", "case_name", "court", "docket_number", "case_status",
    "linked_entity", "source_record_id", "case_id", "source", "source_url",
    "case_source_url", "reviewer_notes",
]


def case_id(case_name: str, court: str, docket: str) -> str:
    raw = f"{case_name}|{court}|{docket}".lower()
    return "case_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def queue_to_seed(row: dict) -> dict:
    etype = row["entity_type"]
    out = {k: row[k] for k in QUEUE_COMMON + QUEUE_SPECIFIC[etype] if row.get(k)}
    if etype == "restriction" and (row.get("municipality") or row.get("county")):
        out["jurisdiction"] = row.get("municipality") or row.get("county")
    out["source"] = f"review queue: {row.get('source_id', '')}".strip()
    if row.get("reviewer_notes"):
        out["reviewer_notes"] = row["reviewer_notes"]
    if etype == "case":
        out["case_id"] = case_id(row.get("project_name", ""), row.get("court_level", ""), row.get("docket_number", ""))
    return out


def candidate_to_case(row: dict) -> dict:
    return {
        "state": row["state"],
        "project_name": row["project_name"],
        "technology": row["technology"],
        "court_level": row["court_level"],
        "severity_score": row.get("severity_score") or 3,
        "description": f"{row['case_name']} ({row['court']}) - litigation over {row['project_name']}",
        "case_name": row["case_name"],
        "court": row["court"],
        "docket_number": row.get("docket_number", ""),
        "case_status": row.get("case_status", ""),
        "linked_entity": row.get("linked_entity", ""),
        "source_record_id": row.get("source_record_id", ""),
        "case_id": case_id(row["case_name"], row["court"], row.get("docket_number", "")),
        "source": "Reviewed case record",
        "source_url": row["case_source_url"],
        "case_source_url": row["case_source_url"],
        "reviewer_notes": row.get("reviewer_notes", ""),
    }


def missing(entity: str, row: dict) -> list[str]:
    return [f for f in REQUIRED[entity] if not str(row.get(f) or "").strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    additions: dict[str, list[dict]] = {k: [] for k in SEED_FOR}
    problems: list[str] = []

    queue = read_csv(QUEUE_PATH)
    for i, row in enumerate(queue, start=2):
        if row.get("review_status") != "confirmed":
            continue
        etype = row.get("entity_type", "")
        if etype not in SEED_FOR:
            problems.append(f"queue.csv row {i}: entity_type {etype!r} cannot be promoted")
            continue
        seed_row = queue_to_seed(row)
        gaps = missing(SEED_FOR[etype][0], seed_row)
        if gaps:
            problems.append(f"queue.csv row {i}: missing {', '.join(gaps)}")
            continue
        additions[etype].append(seed_row)
        row["review_status"] = "promoted"

    candidates = read_csv(CANDIDATES_PATH)
    for i, row in enumerate(candidates, start=2):
        if row.get("review_status") != "confirmed":
            continue
        need = [f for f in ("case_name", "court", "court_level", "case_source_url") if not row.get(f, "").strip()]
        if need:
            problems.append(f"cases_candidates.csv row {i}: missing {', '.join(need)}")
            continue
        additions["case"].append(candidate_to_case(row))
        row["review_status"] = "promoted"

    for p in problems:
        print(p)
    total = sum(len(v) for v in additions.values())
    print(f"{total} row(s) to promote: " + ", ".join(f"{k}={len(v)}" for k, v in additions.items()))
    if args.dry_run or not total:
        return 0

    for etype, rows in additions.items():
        if not rows:
            continue
        _, path = SEED_FOR[etype]
        existing = read_csv(path)
        known = {r.get("case_id") for r in existing if r.get("case_id")}
        fresh = [r for r in rows if not r.get("case_id") or r["case_id"] not in known]
        fields = CASE_FIELDS if etype == "case" else list(existing[0].keys()) if existing else None
        write_csv(path, existing + fresh, fields)
        print(f"Appended {len(fresh)} row(s) to {path.name}")
    if queue:
        write_csv(QUEUE_PATH, queue, list(queue[0].keys()))
    if candidates:
        write_csv(CANDIDATES_PATH, candidates, list(candidates[0].keys()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
