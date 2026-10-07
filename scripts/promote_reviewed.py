"""Move complete review rows into the seed CSVs (pipeline step 4 -> 5).

Promotion is automatic: build-data.yml runs this before every build, so nobody
promotes anything by hand. A row is promoted as soon as it is complete, and
review_status only ever holds a row back:

  rejected   never promoted
  promoted   already in a seed; skipped, so re-running is a no-op
  anything else (pending, confirmed, lead, needs_docket_research, blank)
             promoted once complete

Two review files feed this:

  data/review/queue.csv             candidates written by parse.py extractors
                                    or added by hand. Complete means every
                                    field the seed for its entity_type
                                    (restriction, contested_project or case)
                                    requires is filled, including an http(s)
                                    source_url.
  data/review/cases_candidates.csv  litigated projects/restrictions queued by
                                    build_sabin_seeds.py. Complete means
                                    case_name, court, court_level and an
                                    http(s) case_source_url are filled: the
                                    court record the README requires.

Nothing is filled in to make a row complete; an incomplete row stays where it
is and is listed with what it lacks. A row promoted without review_status
'confirmed' says so in its seed notes ("promoted automatically ... not
reviewed by hand"). Promoted rows still pass through qc_gate in the build,
which quarantines a row that breaks a rule.

Case severity: a reviewer may set severity_score on a candidate; otherwise it
defaults to 3, the contested-projects score for "litigation filed".

Usage:
    python scripts/promote_reviewed.py [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_sabin_seeds import OUTCOME, RESTRICTION_STATUS, finalize_outcome  # noqa: E402
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
QUEUE_COMMON = ["state", "technology", "severity_score", "description", "source_url"]
# Per entity: queue column -> seed column. Only columns the seed already has,
# so a promoted row never adds a column to a seed.
QUEUE_SPECIFIC = {
    "restriction": {"jurisdiction_type": "jurisdiction_type", "restriction_type": "restriction_type",
                    "status": "status", "adopted_date": "date_enacted_iso"},
    "contested_project": {"project_name": "project_name", "county": "county",
                          "municipality": "municipality", "opposition_type": "opposition_type",
                          "first_event_date": "event_date_text", "status": "status"},
    "case": {"project_name": "project_name", "court_level": "court_level",
             "docket_number": "docket_number"},
}
NEVER = {"rejected", "promoted"}
_URL = re.compile(r"^https?://[^\s/]+\.[^\s]+$")


def provenance(row: dict, kind: str) -> str:
    """The reviewer_notes a promoted row carries, plus a line saying whether a
    person confirmed it."""
    notes = [n for n in [(row.get("reviewer_notes") or "").strip()] if n]
    if (row.get("review_status") or "").strip() != "confirmed":
        notes.append(f"promoted automatically from {kind} on {date.today().isoformat()}: "
                     "required fields complete, not reviewed by hand")
    return "; ".join(notes)

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
    out = {k: row[k] for k in QUEUE_COMMON if row.get(k)}
    out.update({dst: row[src] for src, dst in QUEUE_SPECIFIC[etype].items() if row.get(src)})
    out["source"] = f"review queue: {row.get('source_id', '')}".strip()
    notes = provenance(row, "data/review/queue.csv")
    if etype == "restriction":
        # The Sabin status rule: in_force -> active, blank -> unknown.
        status = (row.get("status") or "").strip()
        out["status"] = RESTRICTION_STATUS.get(status, status)
        if row.get("municipality") or row.get("county"):
            out["jurisdiction"] = row.get("municipality") or row.get("county")
        if row.get("effective_date"):
            notes = "; ".join(filter(None, [f"effective {row['effective_date']}", notes]))
    if etype == "contested_project":
        # The same status -> outcome ladder as the Sabin rows; a label alone is
        # never *_confirmed.
        out["outcome"], out["finality_evidence"] = finalize_outcome(
            OUTCOME.get((row.get("status") or "").strip(), "needs_review"), [])
    if etype == "case":
        out["case_id"] = case_id(row.get("project_name", ""), row.get("court_level", ""), row.get("docket_number", ""))
        # cases_seed.csv has no filing-date column; keep the date in the notes.
        filed = f"filed {row['filing_date']}" if row.get("filing_date") else ""
        out["reviewer_notes"] = "; ".join(filter(None, [filed, notes]))
    elif notes:
        out["notes"] = notes
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
        "reviewer_notes": provenance(row, "data/review/cases_candidates.csv"),
    }


def missing(entity: str, row: dict) -> list[str]:
    gaps = [f for f in REQUIRED[entity] if not str(row.get(f) or "").strip()]
    if "source_url" not in gaps and not _URL.match(str(row.get("source_url")).strip()):
        gaps.append("source_url (not http(s))")
    return gaps


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    additions: dict[str, list[dict]] = {k: [] for k in SEED_FOR}
    problems: list[str] = []

    queue = read_csv(QUEUE_PATH) if QUEUE_PATH.exists() else []
    for i, row in enumerate(queue, start=2):
        if (row.get("review_status") or "").strip() in NEVER:
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

    candidates = read_csv(CANDIDATES_PATH) if CANDIDATES_PATH.exists() else []
    waiting = 0
    for i, row in enumerate(candidates, start=2):
        if (row.get("review_status") or "").strip() in NEVER:
            continue
        need = [f for f in ("case_name", "court", "court_level", "case_source_url") if not row.get(f, "").strip()]
        if not need and not _URL.match(row["case_source_url"].strip()):
            need = ["case_source_url (not http(s))"]
        if need:
            # Most candidates await docket research; count them, list only the
            # ones a reviewer has started on.
            if len(need) < 4:
                problems.append(f"cases_candidates.csv row {i}: missing {', '.join(need)}")
            else:
                waiting += 1
            continue
        additions["case"].append(candidate_to_case(row))
        row["review_status"] = "promoted"

    for p in problems:
        print(p)
    if waiting:
        print(f"{waiting} case candidate(s) still await docket research (no case fields yet)")
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
