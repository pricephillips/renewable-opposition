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
applies it and the item drops off these lists once its access is opened or
archived. A row seen only as search-index text (access snippet) stays on the
list, with its URL in located_url, because the source still has to be read.
Nothing here edits a record.

Ranking
  Outcomes      blocked_unverified, then advanced_unverified, then needs_review,
                then pending. A blocked or advanced claim is what a reader
                quotes, so it is checked first. Inside a tier, litigated projects
                first, then the oldest event (an old pending project has most
                likely been decided since).
  Restrictions  compiled_flagged (Moratorium Nation [VERIFY] tags), then
                compiled_record, then report_citation (Sabin). Inside a tier,
                renewables_only before multi-sector, higher severity first,
                then active before extended before pending. NREL rows are
                compiled_flagged, so they come first, most severe first.

flags (restrictions) says why an item needs a closer look: an NREL row whose
values disagree with a Sabin, Moratorium Nation or queue row for the same
jurisdiction (conflicts_with), and an NREL row whose features the accuracy
sample contradicted or could not check (data/review/nrel_sample_review.csv).

Currency and age (adapted from pricephillips/data-center-map
stale_pending_audit.py and status_resolution.py; copied in spirit, not
imported). A record goes wrong by sitting still, so each list also says how
long an item has been in its current state and whether its own text already
reports the decision:
  Restrictions  an instrument past its own end date with no confirmed
                extension (classify.currency lapsed_unconfirmed) is listed
                first of all, whatever its tier, and stays listed even after
                a primary-source check made before the end date, because the
                question is new: was it extended? A pending instrument whose
                status_as_of is more than STALE_PENDING_DAYS old is flagged
                stale: a vote follows a proposal within weeks to months, so
                an old "pending" has most likely been decided.
  County impact (restrictions; after data-center-map's label_moving rank):
                re-verifying some instruments would change what a county
                shows, and those come first within their group. county_impact
                is sole_severe when the instrument is the only severe
                renewables-only instrument in one of its counties (settling
                it moves the county between severe and not), sole_record when
                it is the only restriction of any kind there, else blank.
  Sibling source (restrictions): when another instrument for the same
                jurisdiction and technology (any source family) is verified
                against a primary source, that document almost certainly
                covers this one too. Its URL goes in located_url when the
                row has none, and flags says which instrument holds it. A
                lead for the reviewer: the row stays unverified until someone
                reads the document against it.
  Outcomes      age_days counts from the latest date in event_date_text (the
                end of its precision, so "2023" is measured from 2023-12-31).
                A pending project older than STALE_OUTCOME_DAYS is flagged
                recheck=overdue. decision_language lists the words in the
                row's own text that state a completed decision (approved,
                denied, withdrawn) when no word in the text says the step was
                not final (proposed, hearing, appeal, lawsuit); such a row is
                cheap to settle and sorts first within its tier. Both are
                leads for a reviewer; neither changes a record.

Usage
  python scripts/verification_worklist.py
"""
from __future__ import annotations

import calendar
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    PROCESSED_DIR, REVIEW_DIR, STATE_NAMES, jurisdiction_key, jurisdiction_kind, read_csv, write_csv,
)

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
# How long a "pending" may sit before the list says to look again. The
# data-center-map thresholds: a moratorium vote follows its proposal within
# 120 days; anything else defaults to a year.
STALE_PENDING_DAYS = 120
STALE_OUTCOME_DAYS = 365
LAPSED = "lapsed_unconfirmed"
IMPACT_RANK = {"sole_severe": 0, "sole_record": 1, "": 2}
SEVERE = 3
# A completed decision stated in the past tense, and the words that mean the
# step was not final (or that the decision is being contested).
DECISION = re.compile(
    r"\b(approved|adopted|enacted|denied|rejected|withdrawn|withdrew|cancell?ed|abandoned|dismissed|granted|"
    r"upheld|overturned|unanimously (approved|adopted|voted|rejected|denied)|voted (down|to approve|to deny|"
    r"to reject))\b", re.I)
NOT_FINAL = re.compile(
    r"\b(initial|first reading|preliminary|tentative(ly)?|consider(s|ing)?|weigh(s|ing)?|to vote|will vote|"
    r"set to|plans? to|propos(e|es|ed|al)|draft(s|ing)?|move[sd]? toward|towards?|hearing|could|may|seeks?|"
    r"push(es)? for|calls? for|urge[sd]?|asks?|appeal(s|ed|ing)?|pending|lawsuit|sue[sd]?|suit|"
    r"challeng(e|es|ed|ing)|petition(s|ed)?|intervene[sd]?|remand(s|ed)?)\b", re.I)
_DATE_TOKEN = re.compile(r"\b(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?\b")
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
           "october", "november", "december"]
_MONTH_YEAR = re.compile(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{4})\b", re.I)
# "May 2024" or "May 7" is a date, not the modal verb NOT_FINAL looks for.
_MAY_DATE = re.compile(r"\bMay\s+(?=\d)")
STATUS_ORDER = {"active": 0, "extended": 1, "pending": 2}
TECH_WORDS = {"solar": "solar", "wind": "wind", "battery_storage": "battery storage"}

OUTCOME_FIELDS = ["priority", "tier", "source_record_id", "state", "county", "municipality",
                  "project_name", "technology", "outcome", "event_date_text", "age_days", "recheck",
                  "decision_language", "has_litigation",
                  "what_would_confirm", "located_url", "search_query", "facility_status",
                  "facility_conflict"]
RESTRICTION_FIELDS = ["priority", "tier", "instrument_id", "state", "jurisdiction",
                      "jurisdiction_type", "scope", "county_impact", "technologies", "status", "currency",
                      "status_as_of",
                      "severity_score", "date_enacted_iso", "current_end_date_iso", "legal_basis",
                      "located_url", "search_query", "flags"]


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def _year(text: str) -> int:
    m = re.search(r"(19|20)\d{2}", text or "")
    return int(m.group(0)) if m else 9999


def _techs(value: str) -> list[str]:
    return [t for t in _s(value).split(";") if t]


def _state_name(code: str) -> str:
    return STATE_NAMES.get(code, code)


def latest_date(text: str) -> date | None:
    """The latest date named in free text, at the end of its precision:
    "2023" -> 2023-12-31, "2021-04" -> 2021-04-30, "June 2023" -> 2023-06-30.
    None when the text names no year."""
    found: list[date] = []
    text = text or ""
    for name, y in _MONTH_YEAR.findall(text):
        mm = _MONTHS.index(name.lower()) + 1
        found.append(date(int(y), mm, calendar.monthrange(int(y), mm)[1]))
    # A year already read as part of "June 2023" is not also a bare year.
    for y, m, d in _DATE_TOKEN.findall(_MONTH_YEAR.sub(" ", text)):
        y = int(y)
        if not 1900 <= y <= 2100:
            continue
        mm = int(m) if m else 12
        if not 1 <= mm <= 12:
            continue
        try:
            dd = int(d) if d else calendar.monthrange(y, mm)[1]
            found.append(date(y, mm, dd))
        except ValueError:
            continue
    return max(found) if found else None


def age_days(text: str, today: date) -> int | None:
    when = latest_date(text)
    return (today - when).days if when else None


def decision_language(text: str) -> str:
    """The decision words a text states, or "" when it also says the step was
    not final (or when it states none)."""
    text = _MAY_DATE.sub(" ", text or "")
    if NOT_FINAL.search(text):
        return ""
    words = sorted({m.group(0).lower() for m in DECISION.finditer(text or "")})
    return "; ".join(words)


def _row_text(row: dict) -> str:
    return " ".join(_s(row.get(f)) for f in ("description", "long_description", "notes"))


def outcome_rows(projects: list[dict], resolved: set[str], located: dict[str, str] | None = None,
                 today: date | None = None) -> list[dict]:
    today = today or date.today()
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
        age = age_days(_s(p.get("event_date_text")), today)
        overdue = outcome == "pending" and age is not None and age > STALE_OUTCOME_DAYS
        rows.append({
            "tier": outcome, "source_record_id": rid, "state": p.get("state"),
            "county": p.get("county"), "municipality": p.get("municipality"),
            "project_name": name, "technology": p.get("technology"), "outcome": outcome,
            "event_date_text": p.get("event_date_text"),
            "age_days": "" if age is None else age,
            "recheck": f"overdue: pending {age} days, past {STALE_OUTCOME_DAYS}" if overdue else "",
            "decision_language": decision_language(_row_text(p)) if outcome in ("pending", "needs_review") else "",
            "has_litigation": p.get("has_litigation"),
            "what_would_confirm": WHAT_CONFIRMS[outcome], "located_url": (located or {}).get(rid, ""),
            "search_query": query,
            "facility_status": p.get("facility_status") or "",
            "facility_conflict": p.get("facility_conflict") or "",
        })
    # A plant inventory that contradicts the outcome goes first: its drafted
    # evidence note is in data/review/facility_matches.csv.
    rows.sort(key=lambda r: (not r["facility_conflict"], OUTCOME_TIERS.index(r["tier"]),
                             not r["decision_language"], _s(r["has_litigation"]) != "yes",
                             _year(_s(r["event_date_text"])), r["state"], r["project_name"]))
    for i, r in enumerate(rows, 1):
        r["priority"] = i
    return rows


def _fips(row: dict) -> list[str]:
    return [f for f in _s(row.get("county_fips_all") or row.get("county_fips")).split(";") if f]


def _severity(row: dict) -> int:
    try:
        return int(row.get("severity_score") or 0)
    except (TypeError, ValueError):
        return 0


def county_impacts(restrictions: list[dict]) -> dict[str, str]:
    """instrument_id -> sole_severe | sole_record | "" over every published
    renewables-only restriction (the map's figure), by county_fips_all."""
    per_county: dict[str, set[str]] = {}
    severe_per_county: dict[str, set[str]] = {}
    severity: dict[str, int] = {}
    counties: dict[str, set[str]] = {}
    for r in restrictions:
        iid = _s(r.get("instrument_id"))
        if not iid or _s(r.get("scope")) != "renewables_only":
            continue
        severity[iid] = max(severity.get(iid, 0), _severity(r))
        for f in _fips(r):
            counties.setdefault(iid, set()).add(f)
            per_county.setdefault(f, set()).add(iid)
    for iid, sev in severity.items():
        if sev >= SEVERE:
            for f in counties.get(iid, ()):
                severe_per_county.setdefault(f, set()).add(iid)
    out: dict[str, str] = {}
    for iid, fs in counties.items():
        if severity[iid] >= SEVERE and any(len(severe_per_county.get(f, ())) == 1 for f in fs):
            out[iid] = "sole_severe"
        elif any(len(per_county.get(f, ())) == 1 for f in fs):
            out[iid] = "sole_record"
        else:
            out[iid] = ""
    return out


def _place_key(row: dict) -> tuple | None:
    try:
        return (jurisdiction_key(_s(row.get("state")), jurisdiction_kind(_s(row.get("jurisdiction_type"))),
                                 _s(row.get("jurisdiction"))), _s(row.get("technology")))
    except ValueError:
        return None


def sibling_sources(restrictions: list[dict]) -> dict[str, tuple[str, str]]:
    """instrument_id -> (sibling instrument_id, its primary_source_url) for
    every unverified instrument that shares jurisdiction and technology with a
    verified one from another instrument."""
    held: dict[tuple, tuple[str, str]] = {}
    for r in restrictions:
        key = _place_key(r)
        if key and _s(r.get("verification")) == "verified" and _s(r.get("primary_source_url")):
            held.setdefault(key, (_s(r.get("instrument_id")), _s(r.get("primary_source_url"))))
    out: dict[str, tuple[str, str]] = {}
    for r in restrictions:
        key, iid = _place_key(r), _s(r.get("instrument_id"))
        if key in held and held[key][0] != iid and _s(r.get("verification")) != "verified":
            out.setdefault(iid, held[key])
    return out


def restriction_rows(restrictions: list[dict], checked: set[str],
                     located: dict[str, str] | None = None, sample: dict[str, list[str]] | None = None,
                     today: date | None = None) -> list[dict]:
    today = today or date.today()
    impact = county_impacts(restrictions)
    siblings = sibling_sources(restrictions)
    inst: dict[str, dict] = {}
    for r in restrictions:
        iid = _s(r.get("instrument_id"))
        lapsed = _s(r.get("currency")) == LAPSED
        # A lapsed instrument is listed whatever its evidence and whether or
        # not it was checked before: the question (was it extended?) is new.
        if not iid or (not lapsed and (iid in checked or _s(r.get("evidence_level")) not in EVIDENCE_TIERS)):
            continue
        cur = inst.setdefault(iid, {**r, "_techs": set()})
        cur["_techs"].update(_techs(r.get("technology")))
    rows = []
    for iid, r in inst.items():
        techs = sorted(r["_techs"])
        currency, as_of = _s(r.get("currency")), _s(r.get("status_as_of"))
        age = age_days(as_of, today) if as_of else None
        stale = _s(r.get("status")) == "pending" and age is not None and age > STALE_PENDING_DAYS
        sibling = siblings.get(iid)
        located_url = (located or {}).get(iid, "") or (sibling[1] if sibling else "")
        currency_flags = [
            f"end date {_s(r.get('current_end_date_iso'))} passed with no confirmed extension" if currency == LAPSED
            else "",
            f"pending {age} days (since {as_of}), past {STALE_PENDING_DAYS}" if stale else "",
            f"primary source held by {sibling[0]} (same jurisdiction and technology)" if sibling else "",
        ]
        place = _s(r.get("jurisdiction")) or _s(r.get("county"))
        query = " ".join(x for x in (f'"{place}"' if place else "", _state_name(_s(r.get("state"))),
                                     " OR ".join(TECH_WORDS.get(t, t) for t in techs),
                                     _s(r.get("restriction_type")) or "ordinance") if x)
        rows.append({
            "tier": r.get("evidence_level"), "instrument_id": iid, "state": r.get("state"),
            "jurisdiction": place, "jurisdiction_type": r.get("jurisdiction_type"),
            "scope": r.get("scope"), "county_impact": impact.get(iid, ""),
            "technologies": ";".join(techs), "status": r.get("status"),
            "currency": currency, "status_as_of": as_of,
            "severity_score": r.get("severity_score"),
            "date_enacted_iso": r.get("date_enacted_iso"),
            "current_end_date_iso": r.get("current_end_date_iso"),
            "legal_basis": r.get("legal_basis"), "located_url": located_url,
            "search_query": query,
            "flags": "; ".join(x for x in (
                *currency_flags,
                f"values conflict with {r['conflicts_with']}" if _s(r.get("conflicts_with")) else "",
                *(sample or {}).get(iid, [])) if x),
        })
    rows.sort(key=lambda r: (r["currency"] != LAPSED,
                             EVIDENCE_TIERS.index(r["tier"]) if r["tier"] in EVIDENCE_TIERS else len(EVIDENCE_TIERS),
                             _s(r["scope"]) != "renewables_only",
                             IMPACT_RANK.get(r["county_impact"], 2),
                             -int(r["severity_score"] or 0),
                             STATUS_ORDER.get(_s(r["status"]), 9), r["state"], r["jurisdiction"]))
    for i, r in enumerate(rows, 1):
        r["priority"] = i
    return rows


def split_by_access(rows: list[dict], key: str, url: str) -> tuple[set[str], dict[str, str]]:
    """(keys whose source was opened or archived, key -> URL of the ones seen
    only as search-index text). A read source settles the item; a snippet is
    a located lead that still has to be read."""
    read, leads = set(), {}
    for r in rows:
        if _s(r.get("access")) in ("opened", "archived"):
            read.add(_s(r.get(key)))
        else:
            leads[_s(r.get(key))] = _s(r.get(url))
    return read, leads


def main() -> int:
    projects = json.loads((PROCESSED_DIR / "contested_projects.json").read_text(encoding="utf-8"))
    restrictions = json.loads((PROCESSED_DIR / "restrictions.json").read_text(encoding="utf-8"))
    resolved, lead_outcomes = split_by_access(read_csv(REVIEW_DIR / "outcome_resolutions.csv"),
                                              "source_record_id", "evidence_url")
    checked, lead_sources = split_by_access(read_csv(REVIEW_DIR / "restriction_sources.csv"),
                                            "instrument_id", "primary_source_url")
    sample: dict[str, list[str]] = {}
    for r in read_csv(REVIEW_DIR / "nrel_sample_review.csv"):
        if r.get("verdict") in ("contradicts", "unverifiable"):
            sample.setdefault(_s(r.get("instrument_id")), []).append(
                f"NREL sample: {r['feature']} {r['verdict']}")
    outcomes = outcome_rows(projects, resolved, lead_outcomes)
    restr = restriction_rows(restrictions, checked, lead_sources, sample)
    write_csv(OUTCOME_WORKLIST, outcomes, OUTCOME_FIELDS)
    write_csv(RESTRICTION_WORKLIST, restr, RESTRICTION_FIELDS)
    print(f"verification_worklist: {len(outcomes)} outcomes, {len(restr)} restriction instruments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
