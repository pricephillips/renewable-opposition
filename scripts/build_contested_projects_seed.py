"""Build data/seed/contested_projects_seed.csv and data/review/cases_candidates.csv
from the Sabin-derived records in data/renewable_opposition_records.csv.

Input: the rows of renewable_opposition_records.csv whose
extraction_source_section is ``contested_projects`` (the project-level section
of the Sabin Center's "Opposition to Renewable Energy Facilities in the United
States" report). Nothing is looked up or invented here; every output field is
either copied from that row or derived from it by the documented rules below.

Outputs:
  data/seed/contested_projects_seed.csv   one row per contested project
  data/review/cases_candidates.csv        projects the source flags as litigated,
                                          queued for docket-level research. These
                                          are NOT cases_seed.csv rows: court,
                                          docket and parties are left blank until
                                          someone verifies them against a primary
                                          source.

Derived fields:
  outcome         four-tier vocabulary from the plan doc, mapped from source
                  ``status``:
                    cancelled, rejected                  -> blocked_confirmed
                    approved, approved_after_opposition,
                    operational                          -> advanced_confirmed
                    pending, proposed                    -> pending
                    anything else (in_force, lifted,
                    unknown, blank)                      -> needs_review
                  ``restricted_conditional`` is part of the vocabulary but no
                  source status maps to it, so it is only set by hand.
  severity_score  1-4 intensity of opposition against the project:
                    4  project blocked (outcome blocked_confirmed)
                    3  litigation filed, project not (yet) blocked
                    2  organized/resident opposition, no litigation, not approved
                    1  project advanced despite opposition, no litigation
                  Litigation that did not stop an approved project still scores 3.
  technology      source tokens normalized (storage -> battery_storage) and
                  joined with ';' so a multi-technology project stays one row.

Usage:
    python scripts/build_contested_projects_seed.py [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORDS_PATH = ROOT / "data" / "renewable_opposition_records.csv"
SEED_PATH = ROOT / "data" / "seed" / "contested_projects_seed.csv"
CANDIDATES_PATH = ROOT / "data" / "review" / "cases_candidates.csv"

SOURCE_LABEL = (
    "Sabin Center, Opposition to Renewable Energy Facilities in the United States "
    "(June 2025 ed.), via data/renewable_opposition_records.csv"
)
SOURCE_URL = (
    "https://climate.law.columbia.edu/sites/default/files/content/"
    "Opposition-Report-June-2025.pdf"
)

# Rows that are not a single identifiable project.
EXCLUDE = {
    "REC-0501": "reference to a USA Today database, not a project",
}

# Source rows with a blank technology where the project name states it.
TECHNOLOGY_OVERRIDES = {
    "REC-0279": "wind",  # New York Bight Offshore Wind Area
    "REC-0368": "transmission",  # Boardman-to-Hemingway Transmission Line
}

TECH_ALIASES = {"storage": "battery_storage"}
TECH_ORDER = ["solar", "wind", "battery_storage", "transmission", "hydro", "geothermal"]

OUTCOME = {
    "cancelled": "blocked_confirmed",
    "rejected": "blocked_confirmed",
    "approved": "advanced_confirmed",
    "approved_after_opposition": "advanced_confirmed",
    "operational": "advanced_confirmed",
    "pending": "pending",
    "proposed": "pending",
}

SEED_FIELDS = [
    "state", "project_name", "technology", "severity_score", "description",
    "outcome", "status", "has_litigation", "opposition_type",
    "county", "municipality", "event_date_text", "capacity_mw", "area_acres",
    "long_description", "source_record_id", "source", "source_url", "notes",
]

CANDIDATE_FIELDS = [
    "state", "project_name", "technology", "source_record_id", "outcome",
    "opposition_type", "event_date_text", "litigation_context",
    "case_name", "court", "court_level", "docket_number", "case_status",
    "case_source_url", "review_status",
]


def normalize_technology(raw: str) -> str:
    tokens = {TECH_ALIASES.get(t.strip(), t.strip()) for t in raw.split(",") if t.strip()}
    unknown = tokens - set(TECH_ORDER)
    if unknown:
        raise SystemExit(f"Unmapped technology token(s): {sorted(unknown)}")
    return ";".join(t for t in TECH_ORDER if t in tokens)


def outcome_for(status: str) -> str:
    return OUTCOME.get(status.strip(), "needs_review")


def severity_for(outcome: str, litigated: bool) -> int:
    if outcome == "blocked_confirmed":
        return 4
    if litigated:
        return 3
    if outcome == "advanced_confirmed":
        return 1
    return 2


def is_litigated(row: dict) -> bool:
    return row["has_litigation"].strip() == "yes" or "litigation" in row["opposition_type"]


def build(records: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    seed, candidates, excluded = [], [], []
    for r in records:
        if r["extraction_source_section"] != "contested_projects":
            continue
        rid = r["record_id"]
        if rid in EXCLUDE:
            excluded.append(f"{rid}: {EXCLUDE[rid]}")
            continue

        notes = [n for n in [r["notes"].strip()] if n]
        tech_raw = r["technology"]
        if rid in TECHNOLOGY_OVERRIDES:
            tech_raw = TECHNOLOGY_OVERRIDES[rid]
            notes.append("technology inferred from project name")
        technology = normalize_technology(tech_raw)

        outcome = outcome_for(r["status"])
        litigated = is_litigated(r)
        row = {
            "state": r["state"].strip(),
            "project_name": r["project_or_policy_name"].strip(),
            "technology": technology,
            "severity_score": severity_for(outcome, litigated),
            "description": r["short_description"].strip(),
            "outcome": outcome,
            "status": r["status"].strip(),
            "has_litigation": "yes" if litigated else r["has_litigation"].strip(),
            "opposition_type": r["opposition_type"].strip(),
            "county": r["county"].strip(),
            "municipality": r["municipality"].strip(),
            "event_date_text": r["adopted_or_event_date_text"].strip(),
            "capacity_mw": r["project_capacity_mw"].strip(),
            "area_acres": r["project_area_acres"].strip(),
            "long_description": r["long_description"].strip(),
            "source_record_id": rid,
            "source": SOURCE_LABEL,
            "source_url": SOURCE_URL,
            "notes": "; ".join(notes),
        }
        seed.append(row)

        if litigated:
            candidates.append({
                "state": row["state"],
                "project_name": row["project_name"],
                "technology": technology,
                "source_record_id": rid,
                "outcome": outcome,
                "opposition_type": row["opposition_type"],
                "event_date_text": row["event_date_text"],
                "litigation_context": row["long_description"],
                "review_status": "needs_docket_research",
            })

    seed.sort(key=lambda x: (x["state"], x["project_name"].lower()))
    candidates.sort(key=lambda x: (x["state"], x["project_name"].lower()))
    return seed, candidates, excluded


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="report counts without writing files")
    args = ap.parse_args()

    with RECORDS_PATH.open(newline="", encoding="utf-8-sig") as f:
        records = list(csv.DictReader(f))
    seed, candidates, excluded = build(records)

    by_outcome: dict[str, int] = {}
    for row in seed:
        by_outcome[row["outcome"]] = by_outcome.get(row["outcome"], 0) + 1
    print(f"Contested projects: {len(seed)} rows, {len(excluded)} excluded")
    for line in excluded:
        print(f"  - excluded {line}")
    print("  outcomes: " + ", ".join(f"{k}={v}" for k, v in sorted(by_outcome.items())))
    print(f"Case candidates (litigated projects awaiting docket research): {len(candidates)}")

    if args.dry_run:
        print(f"[dry-run] Would write {SEED_PATH} and {CANDIDATES_PATH}")
        return
    write_csv(SEED_PATH, SEED_FIELDS, seed)
    write_csv(CANDIDATES_PATH, CANDIDATE_FIELDS, candidates)
    print(f"Wrote {SEED_PATH.relative_to(ROOT)} and {CANDIDATES_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
