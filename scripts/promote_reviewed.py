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

Queue rows say how their source was seen in `access` (resolutions.ACCESS).
A row whose access is blank or unknown, or `archived` with no archived_url,
is reported and not promoted, and so is any confirmed row whose access is
`snippet`: the source has to be opened or archived first.

Restriction candidates are scored by the rules published Sabin rows use, never
by a typed number. `mechanisms` is a semicolon-separated list in the
build_sabin_seeds.MECHANISM_TYPE vocabulary, and `mechanism_detail` holds
their values (distances, dBA and hours, acreage, caps). For each technology
the row names, restriction_severity and driving_type run on
mechanism_detail plus description and set severity_score, severity_basis and
restriction_type. A typed severity_score that disagrees with the computed
one is reported as a conflict and the row is not promoted. An unknown
mechanism stops the run with an error, before anything is written.

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
from build_sabin_seeds import (  # noqa: E402
    MECHANISM_TYPE, RESTRICTION_STATUS, RESTRICTION_TECH, driving_type, restriction_severity, text_about,
)
from build_seed_outputs import REQUIRED  # noqa: E402
from common import REVIEW_DIR, SEED_DIR, read_csv, technology_tokens, write_csv  # noqa: E402
from resolutions import access_error, is_read  # noqa: E402

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
    "restriction": ["restriction_type", "adopted_date", "effective_date", "mechanism_detail"],
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


class PromotionError(Exception):
    """A queue row that must stop the whole run (an unknown mechanism)."""


def mechanism_list(row: dict) -> list[str]:
    return [m.strip() for m in (row.get("mechanisms") or "").split(";") if m.strip()]


def score_restriction(row: dict) -> tuple[list[dict], list[str]]:
    """One scored seed row per technology, or ([], problems). Raises
    PromotionError on a mechanism outside MECHANISM_TYPE."""
    mechanisms = mechanism_list(row)
    unknown = [m for m in mechanisms if m not in MECHANISM_TYPE]
    if unknown:
        raise PromotionError(f"unknown mechanism(s) {unknown}; use the build_sabin_seeds.MECHANISM_TYPE "
                             "vocabulary, separated by semicolons")
    if not mechanisms:
        return [], ["mechanisms is blank; list every mechanism the instrument uses"]
    status_raw = (row.get("status") or "").strip()
    published = set(RESTRICTION_STATUS.values())
    status = status_raw if status_raw in published else RESTRICTION_STATUS.get(status_raw)
    if status is None:
        allowed = sorted(published | {k for k in RESTRICTION_STATUS if k})
        return [], [f"status {status_raw!r} is not one of {allowed} (blank means unknown)"]
    try:
        techs = technology_tokens(row.get("technology", ""))
    except ValueError as exc:
        return [], [str(exc)]
    off = [t for t in techs if t not in RESTRICTION_TECH]
    if off or not techs:
        return [], [f"technology must be among {', '.join(RESTRICTION_TECH)} to be scored"]
    types = {MECHANISM_TYPE[m] for m in mechanisms}
    text = " ".join(x for x in ((row.get("mechanism_detail") or "").strip(),
                                (row.get("description") or "").strip()) if x)
    typed = (row.get("severity_score") or "").strip()
    out, problems = [], []
    for tech in techs:
        score, basis = restriction_severity(types, tech, status, text_about(text, tech))
        if typed and typed != str(score):
            problems.append(f"typed severity_score {typed} conflicts with the computed {score} for {tech} "
                            f"({basis}); clear the typed score or correct mechanisms/mechanism_detail")
            continue
        seed = queue_to_seed(row)
        seed.update(technology=tech, severity_score=score, severity_basis=basis,
                    restriction_type=driving_type(types, basis), status=status,
                    mechanisms=", ".join(mechanisms))
        out.append(seed)
    return ([] if problems else out), problems


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
    errors: list[str] = []
    for i, row in enumerate(queue, start=2):
        if row.get("review_status") != "confirmed":
            continue
        where = f"queue.csv row {i}"
        etype = row.get("entity_type", "")
        if etype not in SEED_FOR:
            problems.append(f"{where}: entity_type {etype!r} cannot be promoted")
            continue
        bad = access_error(row)
        if bad:
            problems.append(f"{where}: {bad}")
            continue
        if not is_read(row.get("access", "")):
            problems.append(f"{where}: access is snippet (only search-index text was seen); the source has "
                            "to be opened or archived first, then set access to opened or archived")
            continue
        if etype == "restriction":
            try:
                seed_rows, why = score_restriction(row)
            except PromotionError as exc:
                errors.append(f"{where}: {exc}")
                continue
            if why:
                problems += [f"{where}: {w}" for w in why]
                continue
        else:
            seed_rows = [queue_to_seed(row)]
        gaps = sorted({g for r in seed_rows for g in missing(SEED_FOR[etype][0], r)})
        if gaps:
            problems.append(f"{where}: missing {', '.join(gaps)}")
            continue
        additions[etype].extend(seed_rows)
        row["review_status"] = "promoted"
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        print(f"{len(errors)} error(s); nothing promoted.", file=sys.stderr)
        return 1

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
