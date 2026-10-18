#!/usr/bin/env python3
"""Packets that carry a reading from one agent to the next (docs/AGENTS.md).

The agents that verify a record never pass each other free text. Each step
reads and writes a JSON packet, and this module builds, checks and reconciles
them, so the rules in docs/AGENT_REVIEW.md hold whatever an agent wrote:

  card     What the drafter gets: the published record of one item, where to
           start looking (the worklist's located_url and search_query), and
           what earlier attempts left in the review file and the log.
  draft    What the drafter returns: the document it read, how it was seen,
           the operative text quoted, a field-by-field comparison with the
           record, and its conclusion (a verdict for an instrument, the
           outcome the document supports for a project, or the status an
           instrument has today).
  blind    What the second reader gets: the card without the earlier
           attempts, plus the drafter's source URL and archived copy. Never
           the drafter's conclusion, quote, comparison or note.
  review   What the second reader returns: a packet of the draft's shape,
           from its own reading.

The packet files live under .packets/<run>/<queue>/<slug>.<kind>.json, which
is not committed (docs/AGENTS.md). The lane hook keeps a blind reviewer away
from every *.draft.json.

Packet fields (draft and review)
  packet         draft | review
  queue, key     restriction + instrument_id, outcome + source_record_id, or
                 status + instrument_id (is the instrument still in force?)
  agent          who read it: agent:<role>-<n> (Claude Code, YYYY-MM-DD)
  date           YYYY-MM-DD of the reading
  result         read | not_read (no copy could be opened) |
                 nothing_found (no document could be found at all)
  source_url     the document read
  access         opened | archived (with archived_url); a reading is never
                 snippet: search-index text is not a reading
  archived_url   the Internet Archive copy read, when access is archived
  source_kind    restriction and status: instrument | minutes | official_copy (a news
                 article locates an instrument and never verifies it);
                 outcome: those, court_record, news, or inventory (an
                 EIA-860M, USWTDB or USPVDB entry read in the file itself)
  document       what the document is, in words (title, body, date)
  relation       restriction and status: how the document stands to the record's
                 instrument: is (the instrument or an official copy),
                 adopts (the minutes that adopted it), amends, extends,
                 repeals, or other (a different instrument of the same body,
                 which neither confirms nor contradicts the record: a lead)
  quote          the operative text, verbatim
  fields         [{field, record, document, agrees}]: each field of the
                 record checked against the document
  verdict        restriction: confirmed | contradicts
  outcome        outcome: the contested_projects outcome the document supports
  status         status: active | extended | pending | lifted | expired, as
                 the document shows the instrument today (resolutions.py,
                 RESOLVED_STATUSES); a repeal (relation repeals) is lifted
  end_date       status: YYYY[-MM[-DD]] the instrument stopped applying
                 (required for lifted and expired, and not after the
                 reading), or a full YYYY-MM-DD current end date for an
                 active or extended instrument
  evidence_date  outcome and status: YYYY[-MM[-DD]] of the event the document
                 records (for a status, the code's currency date, the meeting
                 or the repeal)
  note           what the document says, in the reader's words, for the
                 review file; no em dash (quote the source in `quote`)
  attempts       [{url, result}]: every URL tried that could not be read,
                 with what it returned (HTTP status, challenge, egress block)

Blind cards for rows that are not reconciled by code (blind-row): the
independent second reading of a lead's triage or of a case's court record,
and the claim check of a drafted queue row or a held negative check. Each
carries the row's own columns or claimed values and the source, and never a
note, a drafter or a reviewer; `expect` gives the shape of the review packet.

Subcommands
  card QUEUE KEY                       print the card for one item
  blind CARD DRAFT                     print the blind card
  blind-row lead QUEUE_ID              a lead as parse.py queued it, for an independent triage
  blind-row queue_row QUEUE_ID         a drafted queue row's claims, without its notes
  blind-row negative_check FIPS        the county's held negative check, without note or drafter
  blind-row case SOURCE_RECORD_ID --draft DRAFT
                                       a case candidate and the court records the draft read
  check PACKET...                      check packets of any queue; exit 1 on any error
  reconcile CARD DRAFT REVIEW          compare the two readings; print JSON
  reconcile CARD DRAFT REVIEW --row    print the review-file row to append
                                       (exit 1 unless both readings agree and
                                       the file has no row for the key yet)
  reconcile CARD DRAFT REVIEW --log    print the verification_log.csv line

Writes nothing. The record-editor appends what --row and --log print:

  python scripts/review_packets.py reconcile C D R --row >> data/review/restriction_sources.csv
  (status_resolutions.csv for the status queue, outcome_resolutions.csv for outcome)
  python scripts/review_packets.py reconcile C D R --log >> data/review/verification_log.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify import EVENT_KINDS, INSTRUMENT_KINDS  # noqa: E402
from common import PROCESSED_DIR, REVIEW_DIR, read_csv  # noqa: E402
from resolutions import (  # noqa: E402
    NOT_IN_FORCE, OUTCOME_FIELDS, OUTCOME_PATH, RESOLVED_STATUSES, RESTRICTION_FIELDS, RESTRICTION_PATH,
    STATUS_FIELDS, STATUS_PATH, VERDICTS, access_error,
)
from verification_batch import LOG, LOG_FIELDS  # noqa: E402

QUEUE_PATH = REVIEW_DIR / "queue.csv"
CANDIDATES_PATH = REVIEW_DIR / "cases_candidates.csv"
NEGATIVE_PATH = REVIEW_DIR / "negative_checks.csv"

OUTCOMES = {"blocked_confirmed", "blocked_unverified", "restricted_conditional", "advanced_confirmed",
            "advanced_unverified", "pending"}
RESULTS = ("read", "not_read", "nothing_found")
RELATIONS = ("is", "adopts", "amends", "extends", "repeals", "other")
LOG_FOR_RESULT = {"read": "written", "not_read": "not_read", "nothing_found": "nothing_found"}
EMDASH = "—"
_URL = re.compile(r"^https?://[^\s/]+\.[^\s]+$")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PARTIAL = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
_AGENT = re.compile(r"^agent:[a-z0-9]+(?:-[a-z0-9]+)* \(Claude Code, \d{4}-\d{2}-\d{2}\)$")
MIN_QUOTE = 20

QUEUES = {
    "restriction": {
        "key": "instrument_id",
        "records": PROCESSED_DIR / "restrictions.csv",
        "worklist": REVIEW_DIR / "restriction_worklist.csv",
        "review_file": RESTRICTION_PATH,
        "review_fields": RESTRICTION_FIELDS,
        # Columns of the published rows the card carries (one value per column,
        # technology rows joined).
        "record": ["instrument_id", "state", "jurisdiction", "jurisdiction_type", "technology",
                   "restriction_type", "status", "date_enacted_iso", "current_end_date_iso", "date_text",
                   "mechanisms", "severity_score", "severity_basis", "scope", "description",
                   "long_description", "legal_basis", "source", "source_url", "primary_source_url",
                   "primary_source_access", "evidence_level", "verification", "currency", "status_as_of"],
        "work": ["tier", "flags", "county_impact", "located_url", "search_query"],
        "kinds": INSTRUMENT_KINDS,
    },
    # Whether an instrument is still in force today: the same records, read for
    # the instrument's current standing (the body's current code, or the
    # minutes that extended, amended or repealed it) rather than its terms.
    "status": {
        "key": "instrument_id",
        "records": PROCESSED_DIR / "restrictions.csv",
        "worklist": REVIEW_DIR / "restriction_worklist.csv",
        "review_file": STATUS_PATH,
        "review_fields": STATUS_FIELDS,
        "record": ["instrument_id", "state", "jurisdiction", "jurisdiction_type", "technology",
                   "restriction_type", "status", "date_enacted_iso", "current_end_date_iso", "date_text",
                   "mechanisms", "severity_score", "description", "legal_basis", "source", "source_url",
                   "primary_source_url", "verification", "currency", "status_as_of"],
        "work": ["tier", "flags", "county_impact", "located_url", "search_query"],
        "kinds": INSTRUMENT_KINDS,
    },
    "outcome": {
        "key": "source_record_id",
        "records": PROCESSED_DIR / "contested_projects.csv",
        "worklist": REVIEW_DIR / "outcome_worklist.csv",
        "review_file": OUTCOME_PATH,
        "review_fields": OUTCOME_FIELDS,
        "record": ["source_record_id", "state", "county", "municipality", "project_name", "technology",
                   "capacity_mw", "outcome", "finality_evidence", "status", "has_litigation",
                   "opposition_type", "event_date_text", "description", "long_description", "source",
                   "source_url", "facility_name", "facility_status", "facility_note", "facility_conflict"],
        "work": ["tier", "what_would_confirm", "decision_language", "recheck", "located_url", "search_query"],
        # A federal plant inventory entry (EIA-860M, USWTDB, USPVDB) read in the
        # file itself shows what became of a plant (README, "Federal plant
        # inventories"); outcome_resolutions.csv has no source_kind column.
        "kinds": EVENT_KINDS + ("inventory",),
    },
}


# The field that carries each queue's conclusion.
CONCLUSION = {"restriction": "verdict", "outcome": "outcome", "status": "status"}


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def slug(key: str) -> str:
    """A file name for a key: instrument ids carry ':' and '/'."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", key).strip("_") or "item"


# ── Cards ────────────────────────────────────────────────────────────────────

def _join(rows: list[dict], col: str) -> str:
    vals = list(dict.fromkeys(_s(r.get(col)) for r in rows if _s(r.get(col))))
    return "; ".join(vals)


def build_card(queue: str, key: str, records: list[dict], worklist: list[dict],
               review_rows: list[dict], log_rows: list[dict]) -> dict:
    spec = QUEUES[queue]
    kcol = spec["key"]
    mine = [r for r in records if _s(r.get(kcol)) == key]
    if not mine:
        raise ValueError(f"no published {queue} record has {kcol} {key!r}")
    record = {c: _join(mine, c) for c in spec["record"] if _join(mine, c)}
    work = next((w for w in worklist if _s(w.get(kcol)) == key), {})
    return {
        "packet": "card",
        "queue": queue,
        "key": key,
        "slug": slug(key),
        "record": record,
        "rows": len(mine),
        "worklist": {c: _s(work.get(c)) for c in spec["work"] if _s(work.get(c))},
        "prior": {
            "review_rows": [{k: v for k, v in r.items() if _s(v)} for r in review_rows
                            if _s(r.get(kcol)) == key],
            "log": [r for r in log_rows if _s(r.get("queue")) == queue and _s(r.get("key")) == key],
        },
        "review_file": str(spec["review_file"].relative_to(spec["review_file"].parents[2])),
        "source_kinds": list(spec["kinds"]),
    }


def blind_card(card: dict, draft: dict) -> dict:
    """The card a second reader gets: no earlier attempts (they live in
    data/review/), and of the draft only the document's address."""
    if _s(draft.get("result")) != "read":
        raise ValueError("the draft read nothing, so there is nothing to read a second time; log it as "
                         f"{LOG_FOR_RESULT.get(_s(draft.get('result')), 'not_read')}")
    if (card.get("queue"), card.get("key")) != (draft.get("queue"), draft.get("key")):
        raise ValueError("the card and the draft are for different items")
    return {
        "packet": "blind",
        "queue": card["queue"],
        "key": card["key"],
        "slug": card.get("slug") or slug(card["key"]),
        "record": card.get("record", {}),
        "worklist": {k: v for k, v in card.get("worklist", {}).items() if k != "located_url"},
        "source_url": _s(draft.get("source_url")),
        "archived_url": _s(draft.get("archived_url")),
        "source_kinds": card.get("source_kinds", []),
    }


_ATTEMPTS = [{"url": "", "result": ""}]
EXPECT = {
    "lead": {"result": "read | not_read", "decision": "pending | rejected | duplicate", "on_topic": "true | false",
             "placed": "true | false", "duplicate_of": "", "access": "opened | archived | snippet",
             "archived_url": "", "source_kind": "", "set": {"<column>": "<the value the source states>"},
             "quote": "", "note": "", "attempts": _ATTEMPTS},
    "case": {"result": "read | not_read | nothing_found",
             "cases": [{"case_name": "", "court": "", "court_level": "", "docket_number": "", "case_status": "",
                        "case_source_url": "", "access": "opened | archived", "archived_url": "", "document": "",
                        "quote": ""}],
             "fields": [{"field": "", "record": "", "document": "", "agrees": "true | false"}],
             "note": "", "attempts": _ATTEMPTS},
    "claim": {"result": "read | not_read", "verdict": "confirmed | contradicts | unverifiable",
              "fields": [{"field": "", "claimed": "", "document": "", "agrees": "true | false"}],
              "source_url": "", "access": "opened | archived", "archived_url": "", "quote": "", "note": "",
              "attempts": _ATTEMPTS},
}
# Never in a blind card: who drafted or reviewed a row, and what they wrote.
HIDDEN = {"reviewer_notes", "note", "drafted_by", "reviewer", "review_status", "raw_path"}
CASE_RECORD = ("state", "project_name", "technology", "source_record_id", "linked_entity", "outcome",
               "event_date_text", "litigation_context")


def _blind(queue: str, key: str, body: dict, expect: str) -> dict:
    return {"packet": "blind", "queue": queue, "key": key, "slug": slug(key), **body,
            "expect": {"packet": "review", "queue": queue, "key": key, "agent": "", "date": "",
                       **EXPECT[expect]}}


def blind_row(kind: str, key: str, queue_rows: list[dict], candidate_rows: list[dict],
              negative_rows: list[dict], draft: dict | None = None) -> dict:
    if kind in ("lead", "queue_row"):
        row = next((r for r in queue_rows if _s(r.get("queue_id")) == key), None)
        if row is None:
            raise ValueError(f"no queue row has queue_id {key!r}")
        status = _s(row.get("review_status"))
        if kind == "lead":
            if status != "lead":
                raise ValueError(f"{key} is {status}, not an untriaged lead")
            # A harvested lead (parse.py sets raw_path) carries parse.py's notes on
            # how it was found and placed; no reviewer has written in them yet. A
            # hand-queued lead's notes were written by whoever read it first, so
            # they stay out of the second reader's card.
            harvested = bool(_s(row.get("raw_path")))
            record = {k: v for k, v in row.items() if _s(v) and k != "raw_path"
                      and (harvested or k != "reviewer_notes")}
            body = {"record": record, "source_url": _s(row.get("source_url"))}
            if not harvested and _s(row.get("reviewer_notes")):
                body["notes_withheld"] = "queued by hand: its notes record an earlier reading and are left out"
            return _blind("lead", key, body, "lead")
        claim = {k: v for k, v in row.items() if _s(v) and k not in HIDDEN}
        return _blind("queue_row", key, {"claim": claim, "source_url": _s(row.get("source_url")),
                                         "archived_url": _s(row.get("archived_url"))}, "claim")
    if kind == "negative_check":
        held = [r for r in negative_rows if _s(r.get("county_fips")) == key
                and _s(r.get("drafted_by")) and not _s(r.get("reviewer"))]
        if not held:
            raise ValueError(f"no held negative check (drafted, not reviewed) for county {key}")
        row = max(held, key=lambda r: _s(r.get("checked_on")))
        claim = {k: v for k, v in row.items() if _s(v) and k not in HIDDEN}
        return _blind("negative_check", key, {"claim": claim}, "claim")
    if kind == "case":
        rows = [r for r in candidate_rows if _s(r.get("source_record_id")) == key]
        if not rows:
            raise ValueError(f"no case candidate has source_record_id {key!r}")
        if not draft or (_s(draft.get("queue")), _s(draft.get("key"))) != ("case", key):
            raise ValueError("a case's blind card needs the case-researcher's draft for the same key (--draft)")
        urls = [_s(c.get("case_source_url")) for c in draft.get("cases") or [] if _s(c.get("case_source_url"))]
        if not urls:
            raise ValueError("the draft names no court record, so there is nothing to read a second time")
        record = {c: _s(rows[0].get(c)) for c in CASE_RECORD if _s(rows[0].get(c))}
        return _blind("case", key, {"record": record, "source_urls": urls}, "case")
    raise ValueError(f"blind-row kind {kind!r} must be lead, queue_row, negative_check or case")


# ── Checks ───────────────────────────────────────────────────────────────────

# Queues whose packets blind-row cards ask for (EXPECT) and that reconcile does
# not compare: the record-editor applies them from both readings.
ROW_QUEUES = ("lead", "queue_row", "negative_check", "case")
CLAIM_VERDICTS = ("confirmed", "contradicts", "unverifiable")
LEAD_DECISIONS = ("pending", "rejected", "duplicate")
# What a triage judged from the headline alone may correct (lead-triager).
HEADLINE_COLUMNS = {"state", "county", "municipality", "entity_type", "technology"}


def _note_errors(item: dict, where: str = "") -> list[str]:
    note = _s(item.get("note"))
    if not note:
        return [f"{where}note is required: what the document says, or what was searched"]
    if EMDASH in note:
        return [f"{where}note has an em dash; use a comma, colon or parentheses (quote the source in `quote`)"]
    return []


def _attempt_errors(item: dict, where: str = "") -> tuple[list[str], list]:
    attempts = item.get("attempts") or []
    if not isinstance(attempts, list) or any(
            not isinstance(a, dict) or not _s(a.get("url")) or not _s(a.get("result")) for a in attempts):
        return [f"{where}attempts must be a list of {{url, result}}"], []
    return [], attempts


def _reading_errors(item: dict, where: str = "") -> list[str]:
    """A document that was read: its http(s) address and how it was seen."""
    errors = []
    if not _URL.match(_s(item.get("source_url"))):
        errors.append(f"{where}source_url must be the http(s) address of the document read")
    if _s(item.get("access")) == "snippet":
        errors.append(f"{where}access snippet is not a reading: search-index text never verifies anything; "
                      "use result not_read and list the attempts")
    else:
        bad = access_error(item)
        if bad:
            errors.append(where + bad)
    return errors


def _check_claim(p: dict) -> list[str]:
    """A claim check of a drafted queue row or a held negative check."""
    errors = _note_errors(p)
    errs, attempts = _attempt_errors(p)
    errors += errs
    result, verdict = _s(p.get("result")), _s(p.get("verdict"))
    if result not in ("read", "not_read"):
        return errors + [f"result {result!r} must be read or not_read"]
    if verdict not in CLAIM_VERDICTS:
        return errors + [f"verdict {verdict!r} must be one of {', '.join(CLAIM_VERDICTS)}"]
    if result == "not_read":
        if verdict != "unverifiable":
            errors.append(f"verdict {verdict} but nothing was read; a source that cannot be read is unverifiable")
        if not attempts:
            errors.append("result not_read needs attempts: every URL tried and what it returned")
        return errors
    errors += _reading_errors(p)
    if verdict == "unverifiable":
        return errors
    if len(_s(p.get("quote"))) < MIN_QUOTE:
        errors.append("quote is required: the operative text, verbatim")
    fields = p.get("fields") or []
    if not isinstance(fields, list) or not fields or any(
            not isinstance(f, dict) or not _s(f.get("field")) or not isinstance(f.get("agrees"), bool)
            for f in fields):
        return errors + ["fields must list at least one {field, claimed, document, agrees (true or false)}"]
    disagreements = [_s(f.get("field")) for f in fields if f.get("agrees") is False]
    if verdict == "confirmed" and disagreements:
        errors.append(f"verdict confirmed but fields disagree ({', '.join(disagreements)}): that is contradicts")
    elif verdict == "contradicts" and not disagreements:
        errors.append("verdict contradicts names no field that disagrees")
    return errors


def _check_lead(item: dict, where: str = "") -> list[str]:
    """One lead's triage: a draft batch item (read true or false) or a
    blind-row review (result read or not_read)."""
    errors = _note_errors(item, where)
    errs, _ = _attempt_errors(item, where)
    errors += errs
    decision = _s(item.get("decision"))
    if decision not in LEAD_DECISIONS:
        return errors + [f"{where}decision {decision!r} must be one of {', '.join(LEAD_DECISIONS)}"]
    on_topic, placed = item.get("on_topic"), item.get("placed")
    if not isinstance(on_topic, bool) or not isinstance(placed, bool):
        return errors + [f"{where}on_topic and placed must be true or false"]
    if decision == "pending" and not (on_topic and placed):
        errors.append(f"{where}decision pending needs a lead that is on topic and placed")
    if decision == "rejected" and on_topic and placed:
        errors.append(f"{where}decision rejected, but the lead is on topic and placed: say which it is not")
    if decision == "duplicate" and not _s(item.get("duplicate_of")):
        errors.append(f"{where}decision duplicate needs duplicate_of: the queue_id or record it repeats")
    read = item.get("read") is True or _s(item.get("result")) == "read"
    access = _s(item.get("access"))
    bad = access_error(item)
    if bad:
        errors.append(where + bad)
    elif read and access == "snippet":
        errors.append(f"{where}read, but access snippet: a source that was read is opened or archived")
    elif not read and access in ("opened", "archived"):
        errors.append(f"{where}access {access} for a source that was not read")
    if item.get("set"):
        if not isinstance(item["set"], dict):
            return errors + [f"{where}set must map each column to change to the value the source states"]
        beyond = sorted(set(item["set"]) - HEADLINE_COLUMNS)
        if not read and beyond:
            errors.append(f"{where}set {', '.join(beyond)} from a source that was not read: a headline "
                          f"supports only {', '.join(sorted(HEADLINE_COLUMNS))}")
        if not _s(item.get("quote")) or (read and len(_s(item.get("quote"))) < MIN_QUOTE):
            errors.append(f"{where}set needs quote: the sentences each value rests on, verbatim")
    return errors


def _check_case(p: dict) -> list[str]:
    """A case-researcher's reading or its blind second reading."""
    errors = _note_errors(p)
    errs, attempts = _attempt_errors(p)
    errors += errs
    result = _s(p.get("result"))
    if result not in RESULTS:
        return errors + [f"result {result!r} must be one of {', '.join(RESULTS)}"]
    cases = p.get("cases") or []
    if result != "read":
        if cases:
            errors.append(f"cases are named but the result is {result}; a case needs a court record that was read")
        if result == "not_read" and not attempts:
            errors.append("result not_read needs attempts: every URL tried and what it returned")
        return errors
    if not isinstance(cases, list) or not cases:
        return errors + ["result read needs cases: each case the court record names"]
    for i, c in enumerate(cases, start=1):
        where = f"cases[{i}]: "
        if not isinstance(c, dict):
            errors.append(f"{where}must be an object")
            continue
        missing = [f for f in ("case_name", "court", "court_level") if not _s(c.get(f))]
        if missing:
            errors.append(f"{where}missing {', '.join(missing)}")
        errors += _reading_errors({**c, "source_url": c.get("case_source_url")}, where)
        if len(_s(c.get("quote"))) < MIN_QUOTE:
            errors.append(f"{where}quote is required: the lines that name the case, court and disposition")
    return errors


def check_packet(p: dict, today: date | None = None) -> tuple[list[str], list[str]]:
    """(errors, warnings) for a draft or review packet."""
    today = today or date.today()
    errors: list[str] = []
    warnings: list[str] = []
    kind, queue, key = _s(p.get("packet")), _s(p.get("queue")), _s(p.get("key"))
    if kind not in ("draft", "review"):
        errors.append(f"packet {kind!r} must be draft or review")
    if queue not in QUEUES and queue not in ROW_QUEUES:
        return errors + [f"queue {queue!r} must be one of {', '.join([*QUEUES, *ROW_QUEUES])}"], warnings
    batch = queue == "lead" and "leads" in p
    if not key and not batch:
        errors.append("key is required")
    agent = _s(p.get("agent"))
    if not agent:
        errors.append("agent is required: who read it")
    elif agent.startswith("agent:") and not _AGENT.match(agent):
        errors.append(f"agent {agent!r} must read agent:<role>-<n> (Claude Code, YYYY-MM-DD)")
    when = _s(p.get("date"))
    if not _DAY.match(when):
        errors.append(f"date {when!r} must be YYYY-MM-DD")
    elif date.fromisoformat(when) > today:
        errors.append(f"date {when} is after today")
    if queue in ROW_QUEUES:
        if batch:
            leads = p.get("leads")
            if not isinstance(leads, list) or not leads:
                return errors + ["leads must list at least one triaged lead"], warnings
            for i, item in enumerate(leads, start=1):
                if not isinstance(item, dict):
                    errors.append(f"leads[{i}]: must be an object")
                    continue
                where = f"leads[{i}] {_s(item.get('queue_id')) or '(no queue_id)'}: "
                if not _s(item.get("queue_id")):
                    errors.append(f"{where}queue_id is required")
                errors += _check_lead(item, where)
        elif queue == "lead":
            errors += _check_lead(p)
        elif queue == "case":
            errors += _check_case(p)
        else:
            errors += _check_claim(p)
        return errors, warnings
    result = _s(p.get("result"))
    if result not in RESULTS:
        return errors + [f"result {result!r} must be one of {', '.join(RESULTS)}"], warnings
    errors += _note_errors(p)
    errs, attempts = _attempt_errors(p)
    errors += errs
    conclusion = CONCLUSION[queue]

    if result != "read":
        if _s(p.get(conclusion)):
            errors.append(f"{conclusion} is set but nothing was read; a conclusion needs a reading")
        if _s(p.get("access")) in ("opened", "archived"):
            errors.append(f"access {p.get('access')} with result {result}: say read, or say how it failed")
        if result == "not_read" and not attempts:
            errors.append("result not_read needs attempts: every URL tried and what it returned")
        return errors, warnings

    errors += _reading_errors(p)
    kind_of = _s(p.get("source_kind"))
    if kind_of not in QUEUES[queue]["kinds"]:
        why = ("a news article or tracker locates an instrument but never verifies it"
               if queue in ("restriction", "status") else
               "an outcome rests on an official record, a court record, news or a plant inventory")
        errors.append(f"source_kind {kind_of!r} must be one of {', '.join(QUEUES[queue]['kinds'])}: {why}")
    if len(_s(p.get("quote"))) < MIN_QUOTE:
        errors.append("quote is required: the operative text, verbatim")
    if not _s(p.get("document")):
        errors.append("document is required: what was read (title, body, date)")
    fields = p.get("fields") or []
    if not isinstance(fields, list) or not fields or any(
            not isinstance(f, dict) or not _s(f.get("field")) or not isinstance(f.get("agrees"), bool)
            for f in fields):
        errors.append("fields must list at least one {field, record, document, agrees (true or false)}")
        fields = []
    disagreements = [_s(f.get("field")) for f in fields if f.get("agrees") is False]

    if queue in ("restriction", "status"):
        relation = _s(p.get("relation"))
        if relation not in RELATIONS:
            errors.append(f"relation {relation!r} must be one of {', '.join(RELATIONS)}: is the document the "
                          "record's instrument, the minutes that adopted it, or one that amends, extends or "
                          "repeals it?")
        elif relation == "other":
            errors.append("relation other: a different instrument neither confirms nor contradicts the record; "
                          "put it in leads, keep looking for the record's own instrument, and if it cannot be "
                          "found return nothing_found")
    if queue == "status":
        status, end, ev = _s(p.get("status")), _s(p.get("end_date")), _s(p.get("evidence_date"))
        if status not in RESOLVED_STATUSES:
            errors.append(f"status {status!r} must be one of {', '.join(RESOLVED_STATUSES)}")
        elif status in NOT_IN_FORCE and not end:
            errors.append(f"status {status} needs end_date: the date the instrument stopped applying")
        elif _s(p.get("relation")) == "repeals" and status != "lifted":
            errors.append(f"relation repeals with status {status}: a repealed instrument is lifted")
        if end and not _PARTIAL.match(end):
            errors.append(f"end_date {end!r} must be YYYY[-MM[-DD]]")
        elif end and status in RESOLVED_STATUSES and status not in NOT_IN_FORCE and not _DAY.match(end):
            errors.append(f"end_date {end!r}: an {status} instrument's end date must be a full YYYY-MM-DD "
                          "(or blank when the document gives none), so the build can tell when it passes")
        elif end and status in NOT_IN_FORCE and _DAY.match(when) and end > when[: len(end)]:
            errors.append(f"end_date {end} is after the reading ({when}): an instrument that still applies "
                          "is active until then, with that end_date")
        if not _PARTIAL.match(ev):
            errors.append(f"evidence_date {ev!r} must be YYYY[-MM[-DD]]: the date of the document that shows "
                          "the status (the code's currency date, the meeting, the repeal)")
    elif queue == "restriction":
        verdict = _s(p.get("verdict"))
        if verdict not in VERDICTS:
            errors.append(f"verdict {verdict!r} must be one of {', '.join(sorted(VERDICTS))}")
        elif verdict == "confirmed" and disagreements:
            errors.append(f"verdict confirmed but fields disagree ({', '.join(disagreements)}): that is contradicts")
        elif verdict == "contradicts" and not disagreements:
            errors.append("verdict contradicts names no field that disagrees")
    else:
        outcome = _s(p.get("outcome"))
        if outcome not in OUTCOMES:
            errors.append(f"outcome {outcome!r} must be one of {', '.join(sorted(OUTCOMES))}")
        elif outcome.endswith("_unverified"):
            warnings.append(f"outcome {outcome} from a document that was read: is it {outcome[:-11]}_confirmed?")
        ev = _s(p.get("evidence_date"))
        if not _PARTIAL.match(ev):
            errors.append(f"evidence_date {ev!r} must be YYYY[-MM[-DD]]: the date of the event the document records")
    return errors, warnings


def _dates_agree(a: str, b: str) -> bool:
    return not a or not b or a.startswith(b) or b.startswith(a)


# ── Reconcile ────────────────────────────────────────────────────────────────

def _one_line(text: str) -> str:
    return re.sub(r"\s+", " ", _s(text))


def _attempts(p: dict) -> str:
    return "; ".join(f"{_s(a.get('url'))} ({_s(a.get('result'))})" for a in p.get("attempts") or [])


def reconcile(card: dict, draft: dict, review: dict, existing: list[dict] | None = None,
              today: date | None = None) -> dict:
    """Compare two readings. Returns {result, differences, errors, row, log}.
    result is written, not_read, nothing_found, disputed or invalid."""
    today = today or date.today()
    queue, key = _s(card.get("queue")), _s(card.get("key"))
    errors = []
    for name, p in (("draft", draft), ("review", review)):
        if _s(p.get("packet")) != name:
            errors.append(f"{name}: packet is {p.get('packet')!r}, expected {name}")
        if (_s(p.get("queue")), _s(p.get("key"))) != (queue, key):
            errors.append(f"{name}: for {p.get('queue')} {p.get('key')}, not {queue} {key}")
        errs, _ = check_packet(p, today)
        errors += [f"{name}: {e}" for e in errs]
    if _s(draft.get("agent")).lower() == _s(review.get("agent")).lower():
        errors.append("the drafter reviewed its own reading; the second reading must be another agent's")
    out = {"queue": queue, "key": key, "differences": [], "errors": errors, "row": None, "log": None}
    if errors:
        out["result"] = "invalid"
        return out

    spec = QUEUES[queue]
    conclusion = CONCLUSION[queue]
    d_res, r_res = _s(draft.get("result")), _s(review.get("result"))
    if d_res != "read":
        out["result"] = LOG_FOR_RESULT[d_res]
        note = f"{draft['agent']}: {_one_line(draft.get('note'))}"
        if _attempts(draft):
            note += f" Tried: {_attempts(draft)}."
    elif r_res != "read":
        out["result"] = "not_read"
        note = (f"{draft['agent']} read {draft['source_url']} ({draft['access']}); the second reading "
                f"({review['agent']}) could not. Tried: {_attempts(review) or 'none listed'}.")
    else:
        diffs = []
        if _s(draft.get(conclusion)) != _s(review.get(conclusion)):
            diffs.append(f"{conclusion}: draft {draft.get(conclusion)}, review {review.get(conclusion)}")
        if queue in ("restriction", "status") and _s(draft.get("relation")) != _s(review.get("relation")):
            diffs.append(f"relation: draft {draft.get('relation')}, review {review.get('relation')}")
        if queue == "status" and not _dates_agree(_s(draft.get("end_date")), _s(review.get("end_date"))):
            diffs.append(f"end_date: draft {draft.get('end_date')}, review {review.get('end_date')}")
        if queue == "outcome" and not _dates_agree(_s(draft.get("evidence_date")), _s(review.get("evidence_date"))):
            diffs.append(f"evidence_date: draft {draft.get('evidence_date')}, review {review.get('evidence_date')}")
        rf = {_s(f.get("field")): f for f in review.get("fields") or []}
        for f in draft.get("fields") or []:
            other = rf.get(_s(f.get("field")))
            if other is not None and bool(other.get("agrees")) != bool(f.get("agrees")):
                diffs.append(f"{f.get('field')}: draft reads {f.get('document')!r}, review reads "
                             f"{other.get('document')!r}")
        unchecked = sorted({_s(f.get("field")) for f in draft.get("fields") or []} - set(rf))
        if unchecked:
            out["unchecked_by_review"] = unchecked
        if _s(review.get("source_url")) not in (_s(draft.get("source_url")), _s(draft.get("archived_url"))):
            out["review_document"] = _s(review.get("source_url"))
        out["differences"] = diffs
        if diffs:
            out["result"] = "disputed"
            note = (f"{draft['agent']}: {_one_line(draft.get('note'))} {review['agent']}: "
                    f"{_one_line(review.get('note'))} Differ on: {'; '.join(diffs)}.")
        else:
            out["result"] = "written"
            signed = f"{draft['agent']} + {review['agent']}"
            text = (f"{_one_line(draft.get('note'))} Quoted: \"{_one_line(draft.get('quote'))}\" "
                    f"Second reading ({review['agent']}, {review.get('access')}): {_one_line(review.get('note'))}")
            checked_on = max(_s(draft.get("date")), _s(review.get("date")))
            record = card.get("record", {})
            if queue == "restriction":
                row = {"instrument_id": key, "jurisdiction": record.get("jurisdiction", ""),
                       "state": record.get("state", ""), "primary_source_url": draft["source_url"],
                       "verdict": draft["verdict"], "checked_on": checked_on, "note": text, "reviewer": signed,
                       "access": draft["access"], "archived_url": _s(draft.get("archived_url"))}
            elif queue == "status":
                # Of two end dates that agree, the more precise one.
                end = max(_s(draft.get("end_date")), _s(review.get("end_date")), key=len)
                row = {"instrument_id": key, "jurisdiction": record.get("jurisdiction", ""),
                       "state": record.get("state", ""), "status": draft["status"], "end_date": end,
                       "evidence_url": draft["source_url"], "evidence_date": draft["evidence_date"],
                       "checked_on": checked_on, "note": text, "reviewer": signed, "access": draft["access"],
                       "archived_url": _s(draft.get("archived_url"))}
            else:
                row = {"source_record_id": key, "project_name": record.get("project_name", ""),
                       "outcome": draft["outcome"], "evidence_url": draft["source_url"],
                       "evidence_date": draft["evidence_date"], "evidence_note": text, "reviewer": signed,
                       "access": draft["access"], "archived_url": _s(draft.get("archived_url"))}
            out["row"] = {c: row.get(c, "") for c in spec["review_fields"]}
            held = [r for r in existing or [] if _s(r.get(spec["key"])) == key]
            if held:
                out["existing"] = held
            note = f"{conclusion} {draft[conclusion]}: {draft['source_url']} ({draft['access']}); signed {signed}."
    out["log"] = {"date": today.isoformat(), "queue": queue, "key": key, "outcome": out["result"],
                  "note": _one_line(note)}
    return out


def csv_line(row: dict, fields: list[str]) -> str:
    buf = io.StringIO()
    csv.DictWriter(buf, fieldnames=fields, lineterminator="\n").writerow(row)
    return buf.getvalue()


def _header(path: Path, default: list[str]) -> list[str]:
    if path.exists():
        with path.open(newline="", encoding="utf-8-sig") as f:
            head = next(csv.reader(f), None)
        if head:
            return head
    return default


# ── CLI ──────────────────────────────────────────────────────────────────────

def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("card")
    c.add_argument("queue", choices=sorted(QUEUES))
    c.add_argument("key")
    b = sub.add_parser("blind")
    b.add_argument("card")
    b.add_argument("draft")
    br = sub.add_parser("blind-row")
    br.add_argument("kind", choices=("lead", "queue_row", "negative_check", "case"))
    br.add_argument("key")
    br.add_argument("--draft", default="")
    k = sub.add_parser("check")
    k.add_argument("packets", nargs="+")
    k.add_argument("--today", default="")
    r = sub.add_parser("reconcile")
    r.add_argument("card")
    r.add_argument("draft")
    r.add_argument("review")
    r.add_argument("--today", default="")
    out = r.add_mutually_exclusive_group()
    out.add_argument("--row", action="store_true")
    out.add_argument("--log", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "card":
        spec = QUEUES[a.queue]
        try:
            card = build_card(a.queue, a.key, read_csv(spec["records"]), read_csv(spec["worklist"]),
                              read_csv(spec["review_file"]), read_csv(LOG))
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1
        print(json.dumps(card, indent=2, ensure_ascii=False))
        return 0
    if a.cmd == "blind":
        try:
            print(json.dumps(blind_card(_load(a.card), _load(a.draft)), indent=2, ensure_ascii=False))
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1
        return 0
    if a.cmd == "blind-row":
        try:
            card = blind_row(a.kind, a.key, read_csv(QUEUE_PATH), read_csv(CANDIDATES_PATH), read_csv(NEGATIVE_PATH),
                             _load(a.draft) if a.draft else None)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1
        print(json.dumps(card, indent=2, ensure_ascii=False))
        return 0
    today = date.fromisoformat(a.today) if a.today else date.today()
    if a.cmd == "check":
        bad = 0
        for path in a.packets:
            errors, warnings = check_packet(_load(path), today)
            for e in errors:
                print(f"{path}: error: {e}")
            for w in warnings:
                print(f"{path}: warning: {w}")
            bad += bool(errors)
            if not errors:
                print(f"{path}: ok")
        return 1 if bad else 0

    card = _load(a.card)
    queue = _s(card.get("queue"))
    if queue not in QUEUES:
        print(f"{a.card}: not a card (queue {queue!r})", file=sys.stderr)
        return 1
    spec = QUEUES[queue]
    res = reconcile(card, _load(a.draft), _load(a.review), read_csv(spec["review_file"]), today)
    if a.row:
        if res["result"] != "written":
            print(f"no row: the readings are {res['result']}; "
                  + "; ".join(res["errors"] or res["differences"] or [res["log"]["note"]]), file=sys.stderr)
            return 1
        if res.get("existing"):
            print(f"{spec['review_file'].name} already has a row for {res['key']}; edit that row in place "
                  "with the values from `reconcile` (without --row) instead of appending a second", file=sys.stderr)
            return 1
        sys.stdout.write(csv_line(res["row"], _header(spec["review_file"], spec["review_fields"])))
        return 0
    if a.log:
        if res["result"] == "invalid":
            print("; ".join(res["errors"]), file=sys.stderr)
            return 1
        sys.stdout.write(csv_line(res["log"], _header(LOG, LOG_FIELDS)))
        return 0
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res["result"] != "invalid" else 1


if __name__ == "__main__":
    sys.exit(main())
