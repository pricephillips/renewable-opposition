"""Move complete review rows into the seed CSVs (pipeline step 4 -> 5).

Promotion is automatic: build-data.yml runs this before every build, so nobody
promotes anything by hand. A row is promoted as soon as it is complete, and
review_status only ever holds a row back:

  rejected   never promoted
  promoted   already in a seed; skipped, so re-running is a no-op
  awaiting_review
             drafted by an agent or person and not yet reviewed by someone
             else (docs/AGENT_REVIEW.md): held and listed until a reviewer
             sets it to confirmed
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

Queue rows say how their source was seen in `access` (resolutions.ACCESS).
A row whose access is blank or unknown, or `archived` with no archived_url,
is reported and not promoted, and so is any row whose access is `snippet`,
whatever its review_status: the source has to be opened or archived first.

Restriction candidates are scored by the rules published Sabin rows use, never
by a typed number. `mechanisms` is a semicolon-separated list in the
build_sabin_seeds.MECHANISM_TYPE vocabulary, and `mechanism_detail` holds
their values (distances, dBA and hours, acreage, caps). For each technology
the row names, restriction_severity and driving_type run on
mechanism_detail plus description and set severity_score, severity_basis and
restriction_type. A typed severity_score that disagrees with the computed
one is reported as a conflict and the row is not promoted. An unknown
mechanism stops the run with an error, before anything is written.

Restriction status. A restriction candidate needs a status, one of active,
extended, pending, lifted or expired; a blank or other status stops its
promotion and is listed. A lifted or expired instrument is no longer in force
and is not published (as for Sabin rows); it stays in the queue, listed.

Evidence. `source_kind` says what source_url is (classify.SOURCE_KINDS). A
restriction whose access is opened or archived and whose source_kind is
instrument, minutes or official_copy (the instrument, its minutes, or an
official copy of either) publishes with that URL as its primary source
(primary_source_url, _access, _archived_url, verdict confirmed), so it is
evidence_level primary_source and verification verified. Any other restriction
publishes as unverified: a news article or tracker locates an instrument but
does not verify it. A contested project carries source_kind and source_access,
and is verified when its source is news or an official record that was read.

Re-sync. A queue row corrected after promotion would leave its seed rows
stale, so every run recomputes the seed rows of every row whose review_status
is promoted, by the same rules as a first promotion, and reports each field
that changed. Seed rows are linked to their queue row by queue_id (assigned on
promotion; older rows are matched once by source, state and jurisdiction or
project name). Each seed row keeps its published id: pinned_id, set on
promotion to the id the build gives the row, is what the build uses, so a
corrected description or source URL never renumbers the record. A technology
the queue row no longer lists drops its seed row; a new one adds a row.

Contested-project severity: a typed severity_score is kept; otherwise it is
scored by build_sabin_seeds.project_severity from the outcome its status maps to.

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
from build_sabin_seeds import (  # noqa: E402
    MECHANISM_TYPE, OUTCOME, RESTRICTION_STATUS, RESTRICTION_TECH, driving_type, finalize_outcome,
    project_severity, restriction_severity, text_about,
)
from build_seed_outputs import REQUIRED, normalize_row, record_id  # noqa: E402
from classify import INSTRUMENT_KINDS, SOURCE_KINDS  # noqa: E402
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
QUEUE_COMMON = ["state", "technology", "severity_score", "description", "source_url"]
# Per entity: queue column -> seed column. Only columns the seed already has,
# so a promoted row never adds a column to a seed.
QUEUE_SPECIFIC = {
    "restriction": {"jurisdiction_type": "jurisdiction_type", "restriction_type": "restriction_type",
                    "status": "status", "adopted_date": "date_enacted_iso",
                    "mechanism_detail": "long_description"},
    "contested_project": {"project_name": "project_name", "county": "county",
                          "municipality": "municipality", "opposition_type": "opposition_type",
                          "first_event_date": "event_date_text", "status": "status",
                          "opposition_groups": "opposition_groups", "group_sources": "group_sources"},
    "case": {"project_name": "project_name", "court_level": "court_level",
             "docket_number": "docket_number"},
}
NEVER = {"rejected", "promoted"}
# Drafted rows waiting for a reviewer other than their drafter.
AWAITING = "awaiting_review"
# Statuses a restriction candidate may carry; blank stops promotion. Lifted and
# expired instruments are not in force and are not published.
QUEUE_RESTRICTION_STATUS = ("active", "extended", "pending", "lifted", "expired")
NOT_IN_FORCE = {"lifted", "expired"}
# Seed columns a promotion may add (beyond the seed's own): the link to the
# queue row, the pinned id, and the evidence for the verification field.
EVIDENCE_COLUMNS = ["queue_id", "pinned_id", "source_kind", "source_access", "primary_source_url",
                    "primary_source_access", "primary_source_archived_url", "primary_source_verdict"]
_PROMOTED_ON = re.compile(r"promoted automatically from \S+ on (\d{4}-\d{2}-\d{2})")
_URL = re.compile(r"^https?://[^\s/]+\.[^\s]+$")


def provenance(row: dict, kind: str, auto_on: str | None = None) -> str:
    """The reviewer_notes a promoted row carries, plus a line saying whether a
    person confirmed it. auto_on: on a re-sync, the date of the original
    automatic promotion ('' when a person confirmed it), so the notes do not
    change with the calendar."""
    notes = [n for n in [(row.get("reviewer_notes") or "").strip()] if n]
    if auto_on is None:
        auto_on = "" if (row.get("review_status") or "").strip() == "confirmed" else date.today().isoformat()
    if auto_on:
        notes.append(f"promoted automatically from {kind} on {auto_on}: "
                     "required fields complete, not reviewed by hand")
    return "; ".join(notes)


def queue_id(row: dict, taken: set[str] | None = None) -> str:
    """A key for a queue row, assigned once on promotion and stored, so later
    corrections never change it. Two rows from one source and place (three
    ordinances reported in one article) get distinct keys: the technology is
    part of the hash, and a remaining collision with a key in `taken` gets a
    numeric suffix."""
    raw = "|".join((row.get(k) or "").strip().lower() for k in
                   ("source_id", "entity_type", "state", "county", "municipality", "project_name", "technology",
                    "extracted_at"))
    base = "q_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    qid, n = base, 1
    while taken and qid in taken:
        n += 1
        qid = f"{base}-{n}"
    return qid


def evidence(row: dict) -> dict:
    """Seed columns that carry how the queue row's source was seen."""
    kind, access = (row.get("source_kind") or "").strip(), (row.get("access") or "").strip()
    out = {"source_kind": kind}
    if row["entity_type"] == "restriction":
        if kind in INSTRUMENT_KINDS and is_read(access):
            out.update(primary_source_url=row.get("source_url", ""), primary_source_access=access,
                       primary_source_archived_url=row.get("archived_url", ""),
                       primary_source_verdict="confirmed")
    else:
        out["source_access"] = access
    return {k: v for k, v in out.items() if v}


CASE_FIELDS = [
    "state", "project_name", "technology", "court_level", "severity_score",
    "description", "case_name", "court", "docket_number", "case_status",
    "linked_entity", "source_record_id", "case_id", "source", "source_url",
    "case_source_url", "reviewer_notes",
]


def case_id(case_name: str, court: str, docket: str) -> str:
    raw = f"{case_name}|{court}|{docket}".lower()
    return "case_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def queue_to_seed(row: dict, auto_on: str | None = None) -> dict:
    etype = row["entity_type"]
    out = {k: row[k] for k in QUEUE_COMMON if row.get(k)}
    out.update({dst: row[src] for src, dst in QUEUE_SPECIFIC[etype].items() if row.get(src)})
    out["source"] = f"review queue: {row.get('source_id', '')}".strip()
    out.update(evidence(row))
    notes = provenance(row, "data/review/queue.csv", auto_on)
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
        # Scored by the Sabin rule (build_sabin_seeds.project_severity) when no
        # severity is typed; a queue row records no litigation of its own.
        if not out.get("severity_score"):
            out["severity_score"] = project_severity(out["outcome"], False)
    if etype == "case":
        out["case_id"] = case_id(row.get("project_name", ""), row.get("court_level", ""), row.get("docket_number", ""))
        # cases_seed.csv has no filing-date column; keep the date in the notes.
        filed = f"filed {row['filing_date']}" if row.get("filing_date") else ""
        out["reviewer_notes"] = "; ".join(filter(None, [filed, notes]))
    elif notes:
        out["notes"] = notes
    return out


class PromotionError(Exception):
    """A queue row that must stop the whole run (an unknown mechanism)."""


def mechanism_list(row: dict) -> list[str]:
    return [m.strip() for m in (row.get("mechanisms") or "").split(";") if m.strip()]


def score_restriction(row: dict, auto_on: str | None = None) -> tuple[list[dict], list[str]]:
    """One scored seed row per technology, or ([], problems). Raises
    PromotionError on a mechanism outside MECHANISM_TYPE."""
    mechanisms = mechanism_list(row)
    unknown = [m for m in mechanisms if m not in MECHANISM_TYPE]
    if unknown:
        raise PromotionError(f"unknown mechanism(s) {unknown}; use the build_sabin_seeds.MECHANISM_TYPE "
                             "vocabulary, separated by semicolons")
    if not mechanisms:
        return [], ["mechanisms is blank; list every mechanism the instrument uses"]
    status = (row.get("status") or "").strip()
    if status not in QUEUE_RESTRICTION_STATUS:
        return [], [f"status {status!r} must be one of {', '.join(QUEUE_RESTRICTION_STATUS)}; "
                    "a blank status stops promotion"]
    if status in NOT_IN_FORCE:
        return [], [f"status {status}: the instrument is no longer in force, so it is not published"]
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
        seed = queue_to_seed(row, auto_on)
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
        "reviewer_notes": provenance(row, "data/review/cases_candidates.csv"),
    }


def missing(entity: str, row: dict) -> list[str]:
    gaps = [f for f in REQUIRED[entity] if not str(row.get(f) or "").strip()]
    if "source_url" not in gaps and not _URL.match(str(row.get("source_url")).strip()):
        gaps.append("source_url (not http(s))")
    return gaps


def seed_rows_for(row: dict, auto_on: str | None = None) -> tuple[list[dict], list[str]]:
    """The seed rows a queue row produces now, or ([], problems). Raises
    PromotionError on an unknown mechanism."""
    etype = row.get("entity_type", "")
    if etype not in SEED_FOR:
        return [], [f"entity_type {etype!r} cannot be promoted"]
    bad = access_error(row)
    if bad:
        return [], [bad]
    if not is_read(row.get("access", "")):
        return [], ["access is snippet (only search-index text was seen); the source has to be opened "
                    "or archived first, then set access to opened or archived"]
    kind = (row.get("source_kind") or "").strip()
    if kind and kind not in SOURCE_KINDS:
        return [], [f"source_kind {kind!r} must be one of {', '.join(SOURCE_KINDS)}"]
    if etype == "restriction":
        rows, why = score_restriction(row, auto_on)
        if why:
            return [], why
    else:
        rows = [queue_to_seed(row, auto_on)]
    gaps = sorted({g for r in rows for g in missing(SEED_FOR[etype][0], r)})
    if gaps:
        return [], [f"missing {', '.join(gaps)}"]
    return rows, []


def pin(entity: str, seed: dict) -> str:
    """The id the build gives this seed row (build_seed_outputs.record_id)."""
    return record_id(entity, normalize_row({k: "" if v is None else str(v) for k, v in seed.items()}))


def _jurisdiction(row: dict) -> str:
    return (row.get("municipality") or row.get("county") or "").strip()


def linked(entity: str, qrow: dict, seeds: list[dict]) -> list[dict]:
    """The seed rows a promoted queue row produced: by queue_id, or for a row
    promoted before queue_id existed, by source, state and jurisdiction (or
    project name) among rows not yet linked."""
    qid = qrow.get("queue_id", "")
    hits = [r for r in seeds if qid and r.get("queue_id") == qid]
    if hits:
        return hits
    source = f"review queue: {qrow.get('source_id', '')}".strip()
    key = qrow.get("project_name", "").strip() if entity != "restrictions" else _jurisdiction(qrow)
    return [r for r in seeds if not r.get("queue_id") and r.get("source") == source
            and r.get("state") == qrow.get("state")
            and (r.get("project_name") if entity != "restrictions" else r.get("jurisdiction")) == key]


def _short(v) -> str:
    v = "" if v is None else str(v)
    return v if len(v) <= 90 else v[:87] + "..."


def resync(entity: str, where: str, qrow: dict, seeds: list[dict]) -> tuple[list[str], list[str]]:
    """Recompute the seed rows of a promoted queue row in place in seeds.
    Returns (changes, problems)."""
    old = linked(entity, qrow, seeds)
    if not old:
        return [], [f"{where}: review_status is promoted but no seed row is linked to it"]
    m = _PROMOTED_ON.search(" ".join((r.get("notes") or r.get("reviewer_notes") or "") for r in old))
    try:
        fresh, why = seed_rows_for(qrow, m.group(1) if m else "")
    except PromotionError as exc:
        return [], [f"{where}: {exc}"]
    if why:
        return [], [f"{where} (promoted) was not re-synced: {w}" for w in why]
    qid = qrow.get("queue_id") or queue_id(qrow)
    qrow["queue_id"] = qid
    managed = set(EVIDENCE_COLUMNS) | set(QUEUE_COMMON) | {"source", "notes", "reviewer_notes", "outcome",
                                                         "finality_evidence", "severity_basis", "mechanisms",
                                                         "jurisdiction"}
    for spec in QUEUE_SPECIFIC.values():
        managed |= set(spec.values())
    by_tech = {r.get("technology", ""): r for r in old}
    changes = []
    for f in fresh:
        f["queue_id"] = qid
        prev = by_tech.pop(f.get("technology", ""), None) if entity != "cases" else (old[0] if old else None)
        if prev is None:
            f["pinned_id"] = pin(entity, f)
            seeds.append(f)
            changes.append(f"{where} -> {f['pinned_id']}: added a row for {f.get('technology')}")
            continue
        pinned = prev.get("pinned_id") or pin(entity, prev)
        new = dict(prev)
        for k in managed:
            if k in new or k in f:
                new[k] = f.get(k, "")
        new["pinned_id"], new["queue_id"] = pinned, qid
        for k in sorted(set(prev) | set(new)):
            a, b = "" if prev.get(k) is None else str(prev.get(k)), "" if new.get(k) is None else str(new.get(k))
            if a != b:
                label = "linked" if k in ("pinned_id", "queue_id") and not a else "changed"
                changes.append(f"{where} -> {pinned} ({new.get('technology')}): {k} {label}: "
                               f"{_short(a)!r} -> {_short(b)!r}")
        seeds[seeds.index(prev)] = new
    for gone in by_tech.values() if entity != "cases" else []:
        seeds.remove(gone)
        changes.append(f"{where} -> {gone.get('pinned_id') or pin(entity, gone)}: removed the "
                       f"{gone.get('technology')} row; the queue row no longer lists it")
    return changes, []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    seeds: dict[str, list[dict]] = {}
    headers: dict[str, list[str]] = {}
    for etype, (_, path) in SEED_FOR.items():
        seeds[etype] = read_csv(path)
        headers[etype] = list(seeds[etype][0].keys()) if seeds[etype] else []
    added: dict[str, int] = {k: 0 for k in SEED_FOR}
    problems: list[str] = []
    changes: list[str] = []

    queue = read_csv(QUEUE_PATH) if QUEUE_PATH.exists() else []
    errors: list[str] = []
    taken = {r.get("queue_id") for r in queue if r.get("queue_id")}
    resync_rows = []
    for i, row in enumerate(queue, start=2):
        where = f"queue.csv row {i}"
        status = (row.get("review_status") or "").strip()
        if status == "promoted":
            resync_rows.append((where, row))
            continue
        if status in NEVER:
            continue
        if status == AWAITING:
            problems.append(f"{where}: awaiting review by someone other than its drafter (docs/AGENT_REVIEW.md); "
                            "set review_status to confirmed once reviewed")
            continue
        try:
            seed_rows, why = seed_rows_for(row)
        except PromotionError as exc:
            errors.append(f"{where}: {exc}")
            continue
        if why:
            problems += [f"{where}: {w}" for w in why]
            continue
        etype = row["entity_type"]
        qid = row.get("queue_id") or queue_id(row, taken)
        taken.add(qid)
        for r in seed_rows:
            r["queue_id"] = qid
            r["pinned_id"] = pin(SEED_FOR[etype][0], r)
        known = {r.get("case_id") for r in seeds[etype] if r.get("case_id")}
        fresh = [r for r in seed_rows if not r.get("case_id") or r["case_id"] not in known]
        seeds[etype].extend(fresh)
        added[etype] += len(fresh)
        row["queue_id"] = qid
        row["review_status"] = "promoted"
    for where, row in resync_rows:
        etype = row.get("entity_type", "")
        if etype not in SEED_FOR:
            problems.append(f"{where}: entity_type {etype!r} cannot be re-synced")
            continue
        ch, why = resync(SEED_FOR[etype][0], where, row, seeds[etype])
        changes += ch
        problems += why
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        print(f"{len(errors)} error(s); nothing promoted.", file=sys.stderr)
        return 1

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
        case = candidate_to_case(row)
        if case["case_id"] not in {r.get("case_id") for r in seeds["case"]}:
            seeds["case"].append(case)
            added["case"] += 1
        row["review_status"] = "promoted"

    for p in problems:
        print(p)
    if waiting:
        print(f"{waiting} case candidate(s) still await docket research (no case fields yet)")
    total = sum(added.values())
    print(f"{total} row(s) to promote: " + ", ".join(f"{k}={v}" for k, v in added.items()))
    print(f"Re-sync of promoted queue rows: {len(changes)} field change(s)")
    for c in changes:
        print(f"  {c}")
    if args.dry_run or not (total or changes):
        return 0

    for etype, rows in seeds.items():
        _, path = SEED_FOR[etype]
        if rows == read_csv(path):
            continue
        fields = CASE_FIELDS if etype == "case" else headers[etype] or None
        write_csv(path, rows, fields)
        print(f"Wrote {path.name} ({added[etype]} row(s) added)")
    if queue:
        write_csv(QUEUE_PATH, queue, list(dict.fromkeys(list(queue[0].keys()) + ["queue_id"])))
    if candidates:
        write_csv(CANDIDATES_PATH, candidates, list(candidates[0].keys()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
