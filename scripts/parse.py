"""
parse.py
--------
Parser layer for the renewable-opposition pipeline.

Responsibilities:
  1. Read data/raw/manifest.csv (written by fetch.py).
  2. For each unprocessed raw file, dispatch to a source-specific extractor.
  3. Each extractor returns a list of CandidateRecord dicts.
  4. Drop candidates the repository already holds (dedupe below), then
     append the rest to data/review/queue.csv for human confirmation.
  5. Track which manifest rows have been parsed in data/raw/parse_state.csv
     so re-runs are idempotent (skip already-parsed files).

Dedupe (lesson from pricephillips/data-center-map, whose harvester checked
new URLs against the cleaned feed only and re-promoted the same articles
every night: 4,099 duplicate rows in four days). A candidate is checked
against EVERY file that could already hold it, the review queue (any
review_status) and the three seeds:
  - the same entity_type and the same source document (common.normalize_url
    of source_url) is a duplicate and is dropped, logged with what it
    duplicates; so is a second copy inside one batch;
  - the same entity_type, state and name (project_name, or municipality or
    county) under a different URL is kept, with "possible duplicate of ..."
    prepended to reviewer_notes, because new coverage of a known record is
    for a reviewer to merge or reject, not for the parser to decide.
Nothing is read from data/processed/ and nothing is written outside
data/review/ and parse_state.csv.

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
import importlib.util
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SEED_DIR, normalize_url, read_csv  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "data" / "raw" / "manifest.csv"
PARSE_STATE_PATH = REPO_ROOT / "data" / "raw" / "parse_state.csv"
QUEUE_PATH = REPO_ROOT / "data" / "review" / "queue.csv"
EXTRACTORS_DIR = Path(__file__).resolve().parent / "extractors"
# Read only, for dedupe: the seeds a promoted candidate would land in.
SEED_PATHS = {
    "restriction": SEED_DIR / "restrictions_seed.csv",
    "contested_project": SEED_DIR / "contested_projects_seed.csv",
    "case": SEED_DIR / "cases_seed.csv",
}

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
    review_status starts as 'pending'. promote_reviewed.py promotes the row on
    the next data build once its seed's required fields are filled; 'rejected'
    keeps it out.
    """
    # Provenance
    source_id: str = ""
    raw_path: str = ""
    extracted_at: str = ""

    # Classification
    entity_type: str = "unknown"          # restriction | contested_project | case | unknown
    review_status: str = "pending"        # pending | confirmed | rejected | promoted
    reviewer_notes: str = ""

    # Jurisdiction
    state: str = ""
    county: str = ""
    municipality: str = ""
    jurisdiction_type: str = ""

    # Project / restriction shared
    project_name: str = ""
    technology: str = ""                  # solar | wind | battery | offshore_wind | mixed
    severity_score: str = ""             # 1-4; restrictions: computed on promotion, a typed one must agree
    description: str = ""
    source_url: str = ""

    # Restriction-specific
    restriction_type: str = ""           # computed on promotion (driving_type); a typed value is ignored
    mechanisms: str = ""                 # ;-separated, build_sabin_seeds.MECHANISM_TYPE vocabulary
    mechanism_detail: str = ""           # the mechanisms' values: distances, dBA and hours, acreage, caps
    adopted_date: str = ""
    effective_date: str = ""

    # Contested project-specific
    opposition_type: str = ""            # public_hearing | petition | permit_denial | campaign | settlement
    first_event_date: str = ""
    status: str = ""
    opposition_groups: str = ""          # ;-separated group names; each needs a source in group_sources
    group_sources: str = ""              # ;-separated URLs (news articles) that name the groups

    # Case-specific
    court_level: str = ""               # state_trial | state_appellate | federal_district | agency
    filing_date: str = ""
    docket_number: str = ""

    # Evidence
    evidence_text: str = ""             # verbatim excerpt that triggered extraction
    access: str = ""                    # opened | archived | snippet (resolutions.ACCESS); set by the extractor
    archived_url: str = ""              # the Internet Archive copy read, when access is archived
    source_kind: str = ""               # what source_url is (classify.SOURCE_KINDS): instrument | minutes |
                                        # official_copy | court_record | news | tracker | other
    queue_id: str = ""                  # set by promote_reviewed.py on promotion; links the row to its seed rows


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
        writer = csv.DictWriter(f, fieldnames=PARSE_STATE_FIELDS, lineterminator="\n")
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
        writer = csv.DictWriter(f, fieldnames=QUEUE_FIELDS, lineterminator="\n")
        if write_header:
            writer.writeheader()
        for c in candidates:
            writer.writerow(asdict(c))


# ---------------------------------------------------------------------------
# Dedupe against the queue and the seeds
# ---------------------------------------------------------------------------

def _name_key(entity: str, state: str, *names: str) -> tuple:
    name = next((n for n in names if (n or "").strip()), "")
    return (entity, (state or "").strip().upper(), " ".join(name.lower().split()))


class Known:
    """What the repository already holds, keyed for dedupe: by source document
    (entity, normalized URL) and by name (entity, state, name). Each value
    says where it was seen, for the log and the reviewer note."""

    def __init__(self, queue_rows: list[dict], seeds: dict[str, list[dict]]):
        self.by_url: dict[tuple, str] = {}
        self.by_name: dict[tuple, str] = {}
        for r in queue_rows:
            where = f"queue row from {r.get('source_id', '')}".strip()
            self.add(r.get("entity_type", ""), r.get("source_url", ""), r.get("state", ""),
                     (r.get("project_name"), r.get("municipality"), r.get("county")), where)
        for entity, rows in seeds.items():
            for r in rows:
                where = f"seed {r.get('pinned_id') or r.get('id') or r.get('source', '')}".strip()
                self.add(entity, r.get("source_url", ""), r.get("state", ""),
                         (r.get("project_name"), r.get("jurisdiction"), r.get("municipality"), r.get("county")), where)

    def add(self, entity: str, url: str, state: str, names, where: str) -> None:
        if (url or "").strip():
            self.by_url.setdefault((entity, normalize_url(url)), where)
        key = _name_key(entity, state, *names)
        if key[1] and key[2]:
            self.by_name.setdefault(key, where)


def load_known(queue_path: Path, seed_paths: dict[str, Path]) -> Known:
    return Known(read_csv(queue_path), {e: read_csv(p) for e, p in seed_paths.items()})


def dedupe(candidates: list[CandidateRecord], known: Known) -> tuple[list[CandidateRecord], list[str]]:
    """(candidates to queue, one line per candidate dropped). A candidate
    whose source document is already queued or seeded for the same entity is
    dropped; one that only shares a name is kept and noted."""
    kept, dropped = [], []
    for c in candidates:
        label = c.project_name or c.municipality or c.county or c.source_url
        if c.source_url.strip():
            key = (c.entity_type, normalize_url(c.source_url))
            if key in known.by_url:
                dropped.append(f"{c.entity_type} {label!r}: same source document as {known.by_url[key]}")
                continue
            known.by_url[key] = f"queue row from {c.source_id}"
        key = _name_key(c.entity_type, c.state, c.project_name, c.municipality, c.county)
        if key[1] and key[2]:
            if key in known.by_name:
                note = f"possible duplicate of {known.by_name[key]} (same name under another URL)"
                c.reviewer_notes = "; ".join(x for x in (note, c.reviewer_notes) if x)
            else:
                known.by_name[key] = f"queue row from {c.source_id}"
        kept.append(c)
    return kept, dropped


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
    known = load_known(QUEUE_PATH, SEED_PATHS)

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
        candidates, dropped = dedupe(candidates, known)
        for line in dropped:
            log.info(f"    dropped {line}")
        log.info(f"    -> {len(candidates)} candidate(s) queued, {len(dropped)} already held")

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
