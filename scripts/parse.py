"""
parse.py
--------
Parser layer for the renewable-opposition pipeline.

Responsibilities:
  1. Read data/raw/manifest.csv (written by fetch.py).
  2. For each unprocessed raw file, dispatch to a source-specific extractor.
  3. Each extractor returns a list of CandidateRecord dicts.
  4. Drop candidates the repository already holds (dedupe below), then
     append the rest to data/review/queue.csv as leads for triage.
  5. Track which manifest rows have been parsed in data/raw/parse_state.csv
     so re-runs are idempotent (skip already-parsed files). A raw file whose
     extractor raised is recorded with its error and tried again on the next
     run, up to MAX_ATTEMPTS times; after that it is skipped and reported, so
     one bad file does not fail every weekly run.

Leads. Every candidate an extractor finds enters the queue with review_status
'lead' and access 'snippet' (parse.py sets both, whatever the extractor
returned): machine-harvested, not yet triaged, its source not yet read.
Before queueing, sanitize() blanks any value outside the vocabulary the
promotion and the build accept (state code, technology, status, mechanisms,
source_kind) and every machine-typed severity_score, and says so in
reviewer_notes, so no extractor bug can publish a row or stop the build. promote_reviewed.py never promotes
a lead, the county reports and the public dashboard count only 'pending' rows,
so a lead changes nothing anyone reads until a reviewer triages it: 'pending'
once it is on topic and placed (it then counts as a candidate awaiting review
for its county), 'rejected' otherwise. Each lead gets its queue_id here, from
its source document, so two leads from one raw file never share a key.

Dedupe (lesson from pricephillips/data-center-map, whose harvester checked
new URLs against the cleaned feed only and re-promoted the same articles
every night: 4,099 duplicate rows in four days). A candidate is checked
against EVERY file that could already hold it, the review queue (any
review_status), the three seeds and the review files that cite evidence:
  - the same entity_type and the same source document (common.normalize_url
    of source_url, click-tracking parameters removed) is a duplicate and is
    dropped, logged with what it duplicates; so is a second copy inside one
    batch;
  - a source document already cited anywhere else (a seed's primary source,
    ordinance, group or case source; an outcome resolution, restriction
    source, group candidate, place override or case candidate) is dropped
    whatever the entity: someone has already read it against a record;
  - a news candidate whose headline is already queued (syndication: one
    story on many mastheads) is dropped;
  - the same entity_type, state and name (a project's or case's own
    project_name; a restriction's municipality or county, with a technology
    in common) under a different URL is kept, with "possible duplicate of
    <that row's id>" prepended to reviewer_notes, because new coverage of a
    known record is for a reviewer to merge or reject, not for the parser to
    decide.
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
import hashlib
import importlib.util
import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_sabin_seeds import MECHANISM_TYPE, OUTCOME, RESTRICTION_TECH  # noqa: E402
from classify import SOURCE_KINDS  # noqa: E402
from common import (REVIEW_DIR, SEED_DIR, STATE_CODES, normalize_url, read_csv, strip_tracking,  # noqa: E402
                    technology_tokens)

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
# Read only, for dedupe: review files whose URL columns cite evidence someone
# has read against a record. (file, URL column)
CITED_PATHS = [
    (REVIEW_DIR / "outcome_resolutions.csv", "evidence_url"),
    (REVIEW_DIR / "restriction_sources.csv", "primary_source_url"),
    (REVIEW_DIR / "group_candidates.csv", "group_source_url"),
    (REVIEW_DIR / "place_overrides.csv", "evidence_url"),
    (REVIEW_DIR / "status_resolutions.csv", "evidence_url"),
    (REVIEW_DIR / "cases_candidates.csv", "case_source_url"),
]
# Seed columns, other than source_url, that cite a source document.
SEED_CITED_COLUMNS = ("primary_source_url", "ordinance_url", "group_sources", "case_source_url")
LEAD = "lead"
ENTITY_TYPES = ("restriction", "contested_project", "case")
# promote_reviewed.QUEUE_RESTRICTION_STATUS (tests/test_intake_framework.py keeps them equal).
RESTRICTION_STATUS = ("active", "extended", "pending", "lifted", "expired")
# A raw file whose extractor keeps raising is skipped after this many tries.
MAX_ATTEMPTS = 3

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
    review_status starts as 'lead': harvested by a machine, not yet triaged.
    promote_reviewed.py never promotes a lead. A reviewer sets 'pending' once
    the lead is on topic and placed (promote_reviewed.py then promotes it on
    the next data build once its seed's required fields are filled and its
    source was opened), or 'rejected' to keep it out.
    """
    # Provenance
    source_id: str = ""
    raw_path: str = ""
    extracted_at: str = ""

    # Classification
    entity_type: str = "unknown"          # restriction | contested_project | case | unknown
    review_status: str = LEAD             # lead | pending | confirmed | awaiting_review | rejected | promoted
    reviewer_notes: str = ""

    # Jurisdiction
    state: str = ""
    county: str = ""
    municipality: str = ""
    jurisdiction_type: str = ""

    # Project / restriction shared
    project_name: str = ""
    technology: str = ""                  # ;-separated common.TECH_ORDER tokens: solar;wind;battery_storage
    severity_score: str = ""             # 1-4; restrictions: computed on promotion, a typed one must agree
    description: str = ""
    source_url: str = ""

    # Restriction-specific
    restriction_type: str = ""           # computed on promotion (driving_type); a typed value is ignored
    mechanisms: str = ""                 # ;-separated, build_sabin_seeds.MECHANISM_TYPE vocabulary
    mechanism_detail: str = ""           # the mechanisms' values: distances, dBA and hours, acreage, caps
    adopted_date: str = ""
    effective_date: str = ""
    end_date: str = ""                   # YYYY[-MM[-DD]]: the date the instrument runs to (a moratorium's
                                         # term) or, when lifted or expired, the date it stopped applying

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
    queue_id: str = ""                  # set by parse.py when queued (promote_reviewed.py for hand-added
                                        # rows); links the row to its seed rows once promoted


QUEUE_FIELDS = list(CandidateRecord.__dataclass_fields__.keys())


# ---------------------------------------------------------------------------
# Parse state — tracks which (source_id, content_hash) pairs are done
# ---------------------------------------------------------------------------

PARSE_STATE_FIELDS = ["source_id", "content_hash", "raw_path", "parsed_at", "candidate_count", "error"]


def load_parse_state(path: Path) -> set[tuple[str, str]]:
    """Return set of (source_id, content_hash) already parsed."""
    if not path.exists():
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {(r["source_id"], r["content_hash"]) for r in csv.DictReader(f) if not r.get("error")}


def load_parse_failures(path: Path) -> dict[tuple[str, str], int]:
    """How many times each (source_id, content_hash) failed to parse."""
    out: dict[tuple[str, str], int] = {}
    if path.exists():
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("error"):
                    key = (r["source_id"], r["content_hash"])
                    out[key] = out.get(key, 0) + 1
    return out


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
    if not write_header:
        with open(path, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f), [])
        if header != QUEUE_FIELDS:
            # A field added to CandidateRecord since the file was written: bring
            # the file to the current columns first, so appended rows line up.
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            unknown = sorted(set(header) - set(QUEUE_FIELDS))
            if unknown:
                raise SystemExit(f"{path}: columns {unknown} are not CandidateRecord fields")
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=QUEUE_FIELDS, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=QUEUE_FIELDS, lineterminator="\n")
        if write_header:
            writer.writeheader()
        for c in candidates:
            writer.writerow(asdict(c))


# ---------------------------------------------------------------------------
# Dedupe against the queue and the seeds
# ---------------------------------------------------------------------------

def url_key(url: str) -> str:
    """Source identity for dedupe: normalize_url without click tracking, with
    http folded into https and a leading www. dropped (the same article is
    linked both ways). Only for comparison: published source ids still hash
    common.normalize_url."""
    key = normalize_url(strip_tracking(url))
    key = re.sub(r"^http://", "https://", key)
    return re.sub(r"^https://www\.", "https://", key)


def _name_key(entity: str, state: str, *names: str) -> tuple:
    # A project or a case goes by its own name (the first given) only: an
    # unnamed one falling back to its county would share a name with every
    # other unnamed project there.
    if entity in ("contested_project", "case"):
        names = names[:1]
    name = next((n for n in names if (n or "").strip()), "")
    return (entity, (state or "").strip().upper(), " ".join(name.lower().split()))


def _name_keys(key: tuple, technology: str, held: bool) -> list[tuple]:
    """A restriction's name keys by technology (a county's solar ordinance is
    not its wind ordinance): a held row registers one per technology it covers
    plus one without, a candidate looks up its own technologies', or the one
    without when it names none. Any other entity has the one name key."""
    if key[0] != "restriction":
        return [key]
    try:
        tokens = [key + (t,) for t in technology_tokens(technology)]
    except ValueError:
        tokens = []
    return (tokens + [key + ("",)]) if held else (tokens or [key + ("",)])


def _queue_where(source_id: str, queue_id: str) -> str:
    """A queue row as a reviewer finds it: its source and its queue_id."""
    return f"queue row from {source_id}".strip() + (f" ({queue_id})" if queue_id else "")


def headline_key(text: str) -> str:
    """A news headline folded for comparison: lowercase words only."""
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").lower()))[:200]


def _urls(value: str) -> list[str]:
    return [u for u in re.split(r"[;\s]+", value or "") if u.startswith(("http://", "https://"))]


class Known:
    """What the repository already holds, keyed for dedupe: by source document
    (entity, normalized URL), by any other citation of a document (URL alone),
    by news headline, and by name (entity, state, name). Each value says where
    it was seen, for the log and the reviewer note."""

    def __init__(self, queue_rows: list[dict], seeds: dict[str, list[dict]],
                 cited: list[tuple[str, str]] | None = None):
        self.by_url: dict[tuple, str] = {}
        self.by_name: dict[tuple, str] = {}
        self.cited: dict[str, str] = {}
        self.headlines: dict[str, str] = {}
        for r in queue_rows:
            where = _queue_where(r.get("source_id", ""), r.get("queue_id", ""))
            self.add(r.get("entity_type", ""), r.get("source_url", ""), r.get("state", ""),
                     (r.get("project_name"), r.get("municipality"), r.get("county")), where,
                     r.get("technology", ""))
            if (r.get("source_kind") or "").strip() == "news" and headline_key(r.get("evidence_text", "")):
                self.headlines.setdefault(headline_key(r["evidence_text"]), where)
        for entity, rows in seeds.items():
            for r in rows:
                # The row's own id, never its shared citation ('source').
                rid = next((r[c] for c in ("pinned_id", "case_id", "source_record_id", "nrel_id",
                                           "moratorium_id", "queue_id", "source_url") if r.get(c)), "")
                where = f"seed {rid}".strip()
                self.add(entity, r.get("source_url", ""), r.get("state", ""),
                         (r.get("project_name"), r.get("jurisdiction"), r.get("municipality"), r.get("county")), where,
                         r.get("technology", ""))
                for col in ("source_url",) + SEED_CITED_COLUMNS:
                    for u in _urls(r.get(col, "")):
                        self.cited.setdefault(url_key(u), f"{col} of {where}")
        for url, where in cited or []:
            self.cited.setdefault(url_key(url), where)

    def add(self, entity: str, url: str, state: str, names, where: str, technology: str = "") -> None:
        if (url or "").strip():
            self.by_url.setdefault((entity, url_key(url)), where)
        key = _name_key(entity, state, *names)
        if key[1] and key[2]:
            for k in _name_keys(key, technology, held=True):
                self.by_name.setdefault(k, where)


def load_cited(paths: list[tuple[Path, str]]) -> list[tuple[str, str]]:
    """(url, where) for every URL a review file cites as evidence."""
    out = []
    for path, column in paths:
        for i, r in enumerate(read_csv(path), start=2):
            out += [(u, f"{path.name} row {i}") for u in _urls(r.get(column, ""))]
    return out


def load_known(queue_path: Path, seed_paths: dict[str, Path],
               cited_paths: list[tuple[Path, str]] | None = None) -> Known:
    return Known(read_csv(queue_path), {e: read_csv(p) for e, p in seed_paths.items()},
                 load_cited(cited_paths or []))


def dedupe(candidates: list[CandidateRecord], known: Known) -> tuple[list[CandidateRecord], list[str]]:
    """(candidates to queue, one line per candidate dropped). A candidate
    whose source document is already queued or seeded for the same entity, or
    cited as evidence anywhere, or whose news headline is already queued, is
    dropped; one that only shares a name is kept and noted."""
    kept, dropped = [], []
    for c in candidates:
        label = c.project_name or c.municipality or c.county or c.source_url
        if c.source_url.strip():
            ukey = url_key(c.source_url)
            key = (c.entity_type, ukey)
            if key in known.by_url:
                dropped.append(f"{c.entity_type} {label!r}: same source document as {known.by_url[key]}")
                continue
            if ukey in known.cited:
                dropped.append(f"{c.entity_type} {label!r}: source document already cited as {known.cited[ukey]}")
                continue
        hkey = headline_key(c.evidence_text) if c.source_kind == "news" else ""
        if hkey and hkey in known.headlines:
            dropped.append(f"{c.entity_type} {label!r}: same headline as {known.headlines[hkey]}")
            continue
        where = _queue_where(c.source_id, c.queue_id)
        if c.source_url.strip():
            known.by_url[(c.entity_type, url_key(c.source_url))] = where
        if hkey:
            known.headlines[hkey] = where
        key = _name_key(c.entity_type, c.state, c.project_name, c.municipality, c.county)
        if key[1] and key[2]:
            hit = next((known.by_name[k] for k in _name_keys(key, c.technology, held=False) if k in known.by_name), "")
            if hit:
                note = f"possible duplicate of {hit} (same name under another URL)"
                c.reviewer_notes = "; ".join(x for x in (note, c.reviewer_notes) if x)
            for k in _name_keys(key, c.technology, held=True):
                known.by_name.setdefault(k, where)
        kept.append(c)
    return kept, dropped


def _undash(value: str) -> str:
    """Em dash, or a spaced en dash, to a comma; an en dash in a range to a hyphen."""
    value = re.sub(r"\s*\u2014\s*", ", ", value)
    value = re.sub(r"\s+\u2013\s+", ", ", value)
    return value.replace("\u2013", "-")


def sanitize(c: CandidateRecord) -> bool:
    """Hold a machine candidate to the lead contract, in place: review_status
    lead and access snippet always; every value outside the vocabulary the
    promotion and the build accept is blanked, every machine-typed severity
    dropped, em and en dashes replaced (county reports refuse them), and each
    change named in reviewer_notes. False when the row cannot be a candidate
    at all (an unknown entity_type)."""
    if c.entity_type not in ENTITY_TYPES:
        return False
    fixed = []
    for name in QUEUE_FIELDS:
        value = getattr(c, name)
        if isinstance(value, str) and ("\u2014" in value or "\u2013" in value):
            setattr(c, name, _undash(value))
    c.review_status, c.access, c.archived_url = LEAD, "snippet", ""
    state = c.state.strip().upper()
    if state and state not in STATE_CODES:
        fixed.append(f"state {c.state!r}")
        state = ""
    c.state = state
    if c.technology.strip():
        try:
            tokens = technology_tokens(c.technology)
        except ValueError:
            tokens = []
        kept = [t for t in tokens if t in RESTRICTION_TECH] if c.entity_type == "restriction" else tokens
        if not kept or kept != tokens:
            fixed.append(f"technology {c.technology!r}")
        c.technology = ";".join(kept)
    if c.source_kind and c.source_kind not in SOURCE_KINDS:
        fixed.append(f"source_kind {c.source_kind!r}")
        c.source_kind = ""
    allowed = {"restriction": RESTRICTION_STATUS, "contested_project": tuple(OUTCOME)}.get(c.entity_type, ())
    if c.status and c.status not in allowed:
        fixed.append(f"status {c.status!r}")
        c.status = ""
    if c.mechanisms.strip():
        tokens = [t.strip() for t in c.mechanisms.split(";") if t.strip()]
        if any(t not in MECHANISM_TYPE for t in tokens):
            fixed.append(f"mechanisms {c.mechanisms!r}")
            c.mechanisms = ""
    if c.severity_score.strip():
        fixed.append(f"severity_score {c.severity_score!r}")
        c.severity_score = ""
    if c.source_url and not re.match(r"^https?://[^\s/]+\.[^\s]+$", c.source_url.strip()):
        fixed.append(f"source_url {c.source_url!r}")
        c.source_url = ""
    if fixed:
        note = "intake blanked values outside the vocabulary: " + ", ".join(fixed)
        c.reviewer_notes = "; ".join(x for x in (c.reviewer_notes, note) if x)
    return True


def assign_queue_ids(candidates: list[CandidateRecord], taken: set[str]) -> None:
    """Give each lead a queue_id from its source, source document and place,
    unique within the queue (a numeric suffix settles a collision). The
    promotion trail and the seeds key on it, so two leads from one raw file
    must never share one."""
    for c in candidates:
        if c.queue_id:
            taken.add(c.queue_id)
            continue
        raw = "|".join((v or "").strip().lower() for v in (
            c.source_id, c.entity_type, url_key(c.source_url) if c.source_url.strip() else "",
            c.state, c.county, c.municipality, c.project_name, c.technology, c.evidence_text[:200]))
        base = "q_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
        qid, n = base, 1
        while qid in taken:
            n += 1
            qid = f"{base}-{n}"
        c.queue_id = qid
        taken.add(qid)


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


# Set by parse.py itself; an extractor that returns one of these is ignored on that key.
OWN_FIELDS = ("source_id", "raw_path", "extracted_at", "queue_id")


def run_extractor(mod, raw_path: Path, source: dict, rel_path: str = "") -> Optional[list[CandidateRecord]]:
    """The extractor's candidates, or None when it raised (the raw file is then
    not marked parsed, so the next run tries it again)."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        raw_records = mod.extract(raw_path, source)
    except Exception as exc:
        log.error(f"  Extractor {source['source_id']} raised on {raw_path.name}: {type(exc).__name__}: {exc}")
        return None

    candidates = []
    for r in raw_records:
        clash = [k for k in OWN_FIELDS if k in r]
        if clash:
            log.warning(f"  Extractor {source['source_id']} returned {clash}; parse.py sets those itself")
        c = CandidateRecord(
            source_id=source["source_id"],
            raw_path=rel_path or str(raw_path),
            extracted_at=now,
            **{k: ("" if v is None else str(v)) for k, v in r.items() if k in QUEUE_FIELDS and k not in OWN_FIELDS},
        )
        if not sanitize(c):
            log.warning(f"  Extractor {source['source_id']} returned entity_type {c.entity_type!r}; row dropped")
            continue
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
    failures: Optional[dict] = None,
) -> list[dict]:
    """
    Return manifest rows that should be parsed this run.
    Skips: error rows, unchanged-marker rows, already-parsed (unless --reparse),
    and files whose extractor already failed MAX_ATTEMPTS times (unless --reparse).
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
        if not reparse and (failures or {}).get(key, 0) >= MAX_ATTEMPTS:
            log.warning(f"  {row['source_id']}: {row['local_path']} failed {MAX_ATTEMPTS} times; skipped "
                        f"(fix the extractor, then --reparse {row['source_id']})")
            continue
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
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
        return 0

    manifest = load_manifest(MANIFEST_PATH)
    parsed = load_parse_state(PARSE_STATE_PATH)

    source_filter = args.source or args.reparse
    reparse = bool(args.reparse)
    targets = parseable_rows(manifest, parsed, source_filter, reparse, load_parse_failures(PARSE_STATE_PATH))

    if not targets:
        log.info("No unprocessed manifest rows found.")
        return 0

    log.info(f"Parsing {len(targets)} manifest row(s). dry_run={args.dry_run}")
    known = load_known(QUEUE_PATH, SEED_PATHS, CITED_PATHS)
    taken = {r.get("queue_id") for r in read_csv(QUEUE_PATH) if r.get("queue_id")}
    per_source: dict[str, list[int]] = {}
    failed = []
    no_extractor: dict[str, int] = {}
    done: set[tuple[str, str]] = set()

    for row in targets:
        sid = row["source_id"]
        raw_path = REPO_ROOT / row["local_path"]

        mod = load_extractor(sid)
        if mod is None:
            no_extractor[sid] = no_extractor.get(sid, 0) + 1
            continue
        # Identical responses to two requests (two clients with no matters)
        # are one stored file: parse it once per run, and when it fails,
        # record one failed attempt, not one per request.
        key = (sid, row["content_hash"])
        if key in done:
            continue
        done.add(key)

        if args.dry_run:
            log.info(f"  [dry-run] would parse {sid}: {raw_path.name}")
            continue

        log.info(f"  Parsing {sid}: {raw_path.name}")
        candidates = run_extractor(mod, raw_path, row, rel_path=row["local_path"])
        if candidates is None:
            failed.append(f"{sid}: {row['local_path']}")
            append_parse_state(PARSE_STATE_PATH, {
                "source_id": sid, "content_hash": row["content_hash"], "raw_path": row["local_path"],
                "parsed_at": datetime.now(timezone.utc).isoformat(), "candidate_count": "",
                "error": "extractor raised (see the run log)",
            })
            continue
        assign_queue_ids(candidates, taken)     # first, so a note can name an in-batch row
        candidates, dropped = dedupe(candidates, known)
        for line in dropped:
            log.info(f"    dropped {line}")
        log.info(f"    -> {len(candidates)} lead(s) queued, {len(dropped)} already held")

        append_queue(QUEUE_PATH, candidates)
        append_parse_state(PARSE_STATE_PATH, {
            "source_id": sid,
            "content_hash": row["content_hash"],
            "raw_path": row["local_path"],
            "parsed_at": datetime.now(timezone.utc).isoformat(),
            "candidate_count": len(candidates),
        })
        counts = per_source.setdefault(sid, [0, 0, 0])
        counts[0] += 1
        counts[1] += len(candidates)
        counts[2] += len(dropped)

    for sid, n in sorted(no_extractor.items()):
        log.info(f"  {sid}: {n} raw file(s), no extractor (add scripts/extractors/{sid}.py to parse them)")
    for sid, (files, queued, held) in per_source.items():
        print(f"{sid}: {files} raw file(s) parsed, {queued} lead(s) queued, {held} already held")
    for f in failed:
        print(f"{f}: extractor raised; recorded, retried next run (up to {MAX_ATTEMPTS} tries)", file=sys.stderr)
    log.info(f"Done. {sum(v[1] for v in per_source.values())} total lead(s) queued at {QUEUE_PATH}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
