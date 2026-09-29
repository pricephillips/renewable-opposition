#!/usr/bin/env python3
"""Ranked worklists of what to verify next, rebuilt from data/processed/.

Writes
  data/review/outcome_worklist.csv       contested projects whose outcome is not
                                         confirmed, most consequential first
  data/review/restriction_worklist.csv   restriction instruments with no primary
                                         source, weakest evidence first

Each row says what evidence would settle it and gives a search query to start
from. A reviewer records the answer in data/review/outcome_resolutions.csv or
data/review/restriction_sources.csv (see resolutions.py); the next build
applies it and the item drops off these lists. Nothing here edits a record.

Ranking
  Outcomes      blocked_unverified, then advanced_unverified, then needs_review,
                then pending. A blocked or advanced claim is what a reader
                quotes, so it is checked first. Inside a tier, litigated projects
                first, then the oldest event (an old pending project has most
                likely been decided since).
  Restrictions  compiled_flagged (Moratorium Nation [VERIFY] tags), then
                compiled_record, then report_citation (Sabin). Inside a tier,
                renewables_only before multi-sector, higher severity first,
                then active before extended before pending.

Usage
  python scripts/verification_worklist.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROCESSED_DIR, REVIEW_DIR, STATE_NAMES, read_csv, write_csv  # noqa: E402

OUTCOME_WORKLIST = REVIEW_DIR / "outcome_worklist.csv"
RESTRICTION_WORKLIST = REVIEW_DIR / "restriction_worklist.csv"

OUTCOME_TIERS = ("blocked_unverified", "advanced_unverified", "needs_review", "pending")
WHAT_CONFIRMS = {
    "blocked_unverified": "Withdrawal or cancellation notice, permit or zoning denial, "
                          "or interconnection queue withdrawal",
    "advanced_unverified": "Permit or zoning approval, construction start, or commercial "
                           "operation (EIA-860, utility or developer announcement)",
    "needs_review": "The project's current status from county records or recent coverage",
    "pending": "Any decision since the event date: approval, denial or withdrawal",
}
EVIDENCE_TIERS = ("compiled_flagged", "compiled_record", "report_citation")
STATUS_ORDER = {"active": 0, "extended": 1, "pending": 2}
TECH_WORDS = {"solar": "solar", "wind": "wind", "battery_storage": "battery storage"}

OUTCOME_FIELDS = ["priority", "tier", "source_record_id", "state", "county", "municipality",
                  "project_name", "technology", "outcome", "event_date_text", "has_litigation",
                  "what_would_confirm", "search_query"]
RESTRICTION_FIELDS = ["priority", "tier", "instrument_id", "state", "jurisdiction",
                      "jurisdiction_type", "scope", "technologies", "status", "severity_score",
                      "date_enacted_iso", "current_end_date_iso", "legal_basis", "search_query"]


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def _year(text: str) -> int:
    m = re.search(r"(19|20)\d{2}", text or "")
    return int(m.group(0)) if m else 9999


def _techs(value: str) -> list[str]:
    return [t for t in _s(value).split(";") if t]


def _state_name(code: str) -> str:
    return STATE_NAMES.get(code, code)


def outcome_rows(projects: list[dict], resolved: set[str]) -> list[dict]:
    seen, rows = set(), []
    for p in projects:
        rid, outcome = _s(p.get("source_record_id")), _s(p.get("outcome"))
        if outcome not in OUTCOME_TIERS or rid in resolved or rid in seen:
            continue
        seen.add(rid)
        tech = " ".join(TECH_WORDS.get(t, t) for t in _techs(p.get("technology")))
        place = _s(p.get("municipality")) or _s(p.get("county"))
        name = _s(p.get("project_name"))
        query = " ".join(x for x in (f'"{name}"' if name else "", tech, place,
                                     _state_name(_s(p.get("state")))) if x)
        rows.append({
            "tier": outcome, "source_record_id": rid, "state": p.get("state"),
            "county": p.get("county"), "municipality": p.get("municipality"),
            "project_name": name, "technology": p.get("technology"), "outcome": outcome,
            "event_date_text": p.get("event_date_text"),
            "has_litigation": p.get("has_litigation"),
            "what_would_confirm": WHAT_CONFIRMS[outcome], "search_query": query,
        })
    rows.sort(key=lambda r: (OUTCOME_TIERS.index(r["tier"]),
                             _s(r["has_litigation"]) != "yes",
                             _year(_s(r["event_date_text"])), r["state"], r["project_name"]))
    for i, r in enumerate(rows, 1):
        r["priority"] = i
    return rows


def restriction_rows(restrictions: list[dict], checked: set[str]) -> list[dict]:
    inst: dict[str, dict] = {}
    for r in restrictions:
        iid = _s(r.get("instrument_id"))
        if not iid or iid in checked or _s(r.get("evidence_level")) not in EVIDENCE_TIERS:
            continue
        cur = inst.setdefault(iid, {**r, "_techs": set()})
        cur["_techs"].update(_techs(r.get("technology")))
    rows = []
    for iid, r in inst.items():
        techs = sorted(r["_techs"])
        place = _s(r.get("jurisdiction")) or _s(r.get("county"))
        query = " ".join(x for x in (f'"{place}"' if place else "", _state_name(_s(r.get("state"))),
                                     " OR ".join(TECH_WORDS.get(t, t) for t in techs),
                                     _s(r.get("restriction_type")) or "ordinance") if x)
        rows.append({
            "tier": r.get("evidence_level"), "instrument_id": iid, "state": r.get("state"),
            "jurisdiction": place, "jurisdiction_type": r.get("jurisdiction_type"),
            "scope": r.get("scope"), "technologies": ";".join(techs), "status": r.get("status"),
            "severity_score": r.get("severity_score"),
            "date_enacted_iso": r.get("date_enacted_iso"),
            "current_end_date_iso": r.get("current_end_date_iso"),
            "legal_basis": r.get("legal_basis"), "search_query": query,
        })
    rows.sort(key=lambda r: (EVIDENCE_TIERS.index(r["tier"]),
                             _s(r["scope"]) != "renewables_only",
                             -int(r["severity_score"] or 0),
                             STATUS_ORDER.get(_s(r["status"]), 9), r["state"], r["jurisdiction"]))
    for i, r in enumerate(rows, 1):
        r["priority"] = i
    return rows


def main() -> int:
    projects = json.loads((PROCESSED_DIR / "contested_projects.json").read_text(encoding="utf-8"))
    restrictions = json.loads((PROCESSED_DIR / "restrictions.json").read_text(encoding="utf-8"))
    resolved = {_s(r.get("source_record_id")) for r in read_csv(REVIEW_DIR / "outcome_resolutions.csv")} \
        if (REVIEW_DIR / "outcome_resolutions.csv").exists() else set()
    checked = {_s(r.get("instrument_id")) for r in read_csv(REVIEW_DIR / "restriction_sources.csv")} \
        if (REVIEW_DIR / "restriction_sources.csv").exists() else set()
    outcomes = outcome_rows(projects, resolved)
    restr = restriction_rows(restrictions, checked)
    write_csv(OUTCOME_WORKLIST, outcomes, OUTCOME_FIELDS)
    write_csv(RESTRICTION_WORKLIST, restr, RESTRICTION_FIELDS)
    print(f"verification_worklist: {len(outcomes)} outcomes, {len(restr)} restriction instruments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
