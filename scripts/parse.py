"""
parse.py
--------
Parser layer for the renewable-opposition pipeline.

Responsibilities:
  1. Read data/raw/manifest.csv (written by fetch.py).
  2. For each unprocessed raw file, dispatch to a source-specific extractor.
  3. Each extractor returns a list of CandidateRecord dicts.
  4. Append candidates to data/review/queue.csv for human confirmation.
  5. Track which manifest rows have been parsed in data/raw/parse_state.csv
     so re-runs are idempotent (skip already-parsed files).

Extractor registry
------------------
Extractors live in scripts/extractors/<source_id>.py and must expose:

    def extract(raw_path: Path, source: dict) -> list[dict]:
        ...

If no extractor exists for a source_id, the file is logged as skipped.
This is intentional: add extractors incrementally as sources are prioritized.

Usage:
    python scripts/parse.py                    # parse all unprocessed files
    python scripts/parse.py --source <id>      # parse only this source_id
    python scripts/parse.py --dry-run          # print plan, no writes
    python scripts/parse.py --reparse <id>     # re-parse source, re-queue candidates
"""

import argparse
import csv
import importlib
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "data" / "raw" / "manifest.csv"
PARSE_STATE_PATH = REPO_ROOT / "data" / "raw" / "parse_state.csv"
QUEUE_PATH = REPO_ROOT / "data" / "review" / "queue.csv"
EXTRACTORS_DIR = Path(__file__).resolve().parent / "extractors"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CandidateRecord — the unit that flows into the review queue
# ---------------------------------------------------------------------------

@dataclass
class CandidateRecord:
    """
    A single candidate extraction awaiting human review.

    Fields left empty are expected to be filled during review or by a later
    enrichment pass. Required fields: entity_type, source_id, raw_path.

    entity_type must be one of: restriction | contested_project | case | unknown
    review_status starts as 'pending'; reviewer sets to 'confirmed' or 'rejected'.
    """
    # Provenance
    source_id: str = ""
    raw_path: str = ""
    extracted_at: str = ""

    # Classification
    entity_type: str = "unknown"          # restriction | contested_project | case | unknown
    review_status: str = "pending"        # pending | confirmed | rejected
    reviewer_notes: str = ""

    # Jurisdiction
    state: str = ""
    county: str = ""
    municipality: str = ""
    jurisdiction_type: str = ""

    # Project / restriction shared
    project_name: str = ""
    technology: str = ""                  # solar | wind | battery | offshore_wind | mixed
    severity_score: str = ""             # 1-4
    description: str = ""
    source_url: str = ""

    # Restriction-specific
    restriction_type: str = ""           # moratorium | ban | setback | height_limit | zoning_amendment | other
    adopted_date: str = ""
    effective_date: str = ""

    # Contested project-specific
    opposition_type: str = ""            # public_hearing | petition | permit_denial | campaign | settlement
    first_event_date: str = ""
    status: str = ""

    # Case-specific
    court_level: str = ""               # state_trial | state_appellate | federal_district | agency
    filing_date: str = ""
    docket_number: str = ""

    # Evidence
    evidence_text: str = ""             # verbatim excerpt that triggered extraction


QUEUE_FIELDS = list(CandidateRecord.__dataclass_fields__.keys())


# ---------------------------------------------------------------------------
# Parse state — tracks which (source_id, content_hash) pairs are done
# ---------------------------------------------------------------------------

PARSE_STATE_FIELDS = ["source_id", "content_hash", "raw_path", "parsed_at", "candidate_count"]


def load_parse_state(path: Path) -> set[tuple[str, str]]:
    """Return set of (source_id, content_hash) already parsed."""
    if not path.exists():
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {(r["source_id"], r["content_hash"]) for r in csv.DictReader(f)}


def append_parse_state(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PARSE_STATE_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(record)


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------

def append_queue(path: Path, candidates: list[CandidateRecord]) -> None:
    if not candidates:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=QUEUE_FIELDS)
        if write_header:
            writer.writeheader()
        for c in candidates:
            writer.writerow(asdict(c))


# ---------------------------------------------------------------------------
# Extractor registry
# ---------------------------------------------------------------------------

def load_extractor(source_id: str):
    """
    Attempt to import scripts/extractors/<source_id>.py.
    Returns the module if found, None otherwise.

    Extractor contract:
        def extract(raw_path: Path, source: dict) -> list[dict]:
            ...
    Each returned dict maps to CandidateRecord fields (unknown keys ignored).
    """
    module_name = f"extractors.{source_id}"
    spec_path = EXTRACTORS_DIR / f"{source_id}.py"
    if not spec_path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location(module_name, spec_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as exc:
        log.error(f"Failed to load extractor '{source_id}': {exc}")
        return None


def run_extractor(mod, raw_path: Path, source: dict) -> list[CandidateRecord]:
    now = datetime.now(timezone.utc).isoformat()
    try:
        raw_records = mod.extract(raw_path, source)
    except Exception as exc:
        log.error(f"  Extractor {source['source_id']} raised: {exc}")
        return []

    candidates = []
    for r in raw_records:
        c = CandidateRecord(
            source_id=source["source_id"],
            raw_path=str(raw_path),
            extracted_at=now,
            **{k: v for k, v in r.items() if k in QUEUE_FIELDS},
        )
        candidates.append(c)
    return candidates


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------

def load_manifest(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parseable_rows(
    manifest: list[dict],
    parsed: set[tuple[str, str]],
    source_id_filter: Optional[str],
    reparse: bool,
) -> list[dict]:
    """
    Return manifest rows that should be parsed this run.
    Skips: error rows, unchanged-marker rows, already-parsed (unless --reparse).
    """
    rows = []
    for row in manifest:
        if row.get("error"):
            continue
        if row.get("local_path") in ("", "unchanged"):
            continue
        if source_id_filter and row["source_id"] != source_id_filter:
            continue
        key = (row["source_id"], row["content_hash"])
        if not reparse and key in parsed:
            continue
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Parse raw fetched files into candidate records.")
    parser.add_argument("--source", help="Parse only this source_id.")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing.")
    parser.add_argument("--reparse", help="Re-parse this source_id even if already in parse_state.")
    args = parser.parse_args()

    # sys.path must include the scripts/ dir so extractor imports resolve
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    if not MANIFEST_PATH.exists():
        log.warning(f"Manifest not found at {MANIFEST_PATH}. Run fetch.py first.")
        return

    manifest = load_manifest(MANIFEST_PATH)
    parsed = load_parse_state(PARSE_STATE_PATH)

    source_filter = args.source or args.reparse
    reparse = bool(args.reparse)
    targets = parseable_rows(manifest, parsed, source_filter, reparse)

    if not targets:
        log.info("No unprocessed manifest rows found.")
        return

    log.info(f"Parsing {len(targets)} manifest row(s). dry_run={args.dry_run}")
    total_candidates = 0

    for row in targets:
        sid = row["source_id"]
        raw_path = REPO_ROOT / row["local_path"]

        mod = load_extractor(sid)
        if mod is None:
            log.info(f"  {sid}: no extractor found — skipping. (Add scripts/extractors/{sid}.py to enable.)")
            continue

        if args.dry_run:
            log.info(f"  [dry-run] would parse {sid}: {raw_path.name}")
            continue

        log.info(f"  Parsing {sid}: {raw_path.name}")
        candidates = run_extractor(mod, raw_path, row)
        log.info(f"    -> {len(candidates)} candidate(s) extracted")

        append_queue(QUEUE_PATH, candidates)
        append_parse_state(PARSE_STATE_PATH, {
            "source_id": sid,
            "content_hash": row["content_hash"],
            "raw_path": row["local_path"],
            "parsed_at": datetime.now(timezone.utc).isoformat(),
            "candidate_count": len(candidates),
        })
        total_candidates += len(candidates)

    log.info(f"Done. {total_candidates} total candidate(s) queued at {QUEUE_PATH}")


if __name__ == "__main__":
    main()
