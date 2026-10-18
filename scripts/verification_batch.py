#!/usr/bin/env python3
"""The next batch for the daily verification routine (docs/VERIFICATION_ROUTINE.md).

Reads the two ranked worklists that verification_worklist.py builds and the
routine's own log, and prints the next items to read: the restriction
instruments whose source is already located first, then the rest in worklist
order, and the top outcome items. An item attempted in the last SKIP_DAYS days
(any outcome in data/review/verification_log.csv) is skipped, so a source that
blocked the agent yesterday does not take today's slot again; after SKIP_DAYS
it comes back, since a blocked host is sometimes reachable later.

Adapted from pricephillips/data-center-map docs/research_routine.md ("Take the
first 25 rows ... skipping fips attempted in the last 14 days"); copied in
spirit, not imported.

With --statuses N it also picks the next N instruments whose status nobody
has settled (currency unknown or lapsed_unconfirmed in
data/processed/restrictions.csv, and no row in
data/review/status_resolutions.csv) for /check-status. As in the other
queues, an instrument whose source is already located comes first; then a
county's only severe record, a county's only record, higher severity, and
worklist order.

Writes nothing. The routine records each attempt in verification_log.csv by
hand (hand-edited, declared in config/layers.json).

Usage
  python scripts/verification_batch.py                       20 restrictions, 5 outcomes
  python scripts/verification_batch.py --restrictions 10 --outcomes 0
  python scripts/verification_batch.py --today 2026-10-14 --csv
  python scripts/verification_batch.py --restrictions 0 --outcomes 0 --statuses 20
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROCESSED_DIR, REVIEW_DIR, read_csv  # noqa: E402

RESTRICTION_WORKLIST = REVIEW_DIR / "restriction_worklist.csv"
OUTCOME_WORKLIST = REVIEW_DIR / "outcome_worklist.csv"
LOG = REVIEW_DIR / "verification_log.csv"
RESTRICTIONS = PROCESSED_DIR / "restrictions.csv"
STATUS_RESOLUTIONS = REVIEW_DIR / "status_resolutions.csv"
UNSETTLED = ("unknown", "lapsed_unconfirmed")
IMPACT_ORDER = {"sole_severe": 0, "sole_record": 1}
LOG_FIELDS = ["date", "queue", "key", "outcome", "note"]
LOG_OUTCOMES = ("written", "not_read", "disputed", "nothing_found")
QUEUES = {"restriction": "instrument_id", "outcome": "source_record_id", "status": "instrument_id"}
SKIP_DAYS = 14
DEFAULT_RESTRICTIONS = 20
DEFAULT_OUTCOMES = 5
OUT_FIELDS = ["queue", "key", "state", "place", "what", "located_url", "search_query"]


def recent_keys(log: list[dict], today: date, days: int = SKIP_DAYS) -> set[tuple[str, str]]:
    """(queue, key) pairs attempted within `days` days before `today`."""
    since = today - timedelta(days=days)
    out = set()
    for r in log:
        try:
            when = date.fromisoformat((r.get("date") or "").strip())
        except ValueError:
            continue
        if since < when <= today:
            out.add(((r.get("queue") or "").strip(), (r.get("key") or "").strip()))
    return out


def _rank(rows: list[dict]) -> list[dict]:
    """Worklist order, with rows whose source is already located first."""
    def key(r: dict) -> tuple[int, int]:
        try:
            p = int(r.get("priority") or 0)
        except ValueError:
            p = 0
        return (0 if (r.get("located_url") or "").strip() else 1, p)
    return sorted(rows, key=key)


def status_rows(published: list[dict], worklist: list[dict], settled: list[dict]) -> list[dict]:
    """One row per instrument whose status nobody has settled, ranked
    (module docstring), in the shape pick() takes: priority is the rank."""
    done = {(r.get("instrument_id") or "").strip() for r in settled}
    work = {(w.get("instrument_id") or "").strip(): w for w in worklist}
    merged: dict[str, dict] = {}
    for r in published:
        iid = (r.get("instrument_id") or "").strip()
        if not iid or iid in done or (r.get("currency") or "").strip() not in UNSETTLED:
            continue
        cur = merged.setdefault(iid, {"instrument_id": iid, "state": r.get("state", ""),
                                      "jurisdiction": r.get("jurisdiction", ""), "techs": [], "severity": 0,
                                      "legal_basis": r.get("legal_basis", "") or r.get("date_text", "")})
        tech = (r.get("technology") or "").strip()
        if tech and tech not in cur["techs"]:
            cur["techs"].append(tech)
        try:
            cur["severity"] = max(cur["severity"], int(r.get("severity_score") or 0))
        except ValueError:
            pass

    def key(m: dict) -> tuple:
        w = work.get(m["instrument_id"], {})
        try:
            prio = int(w.get("priority") or 10**9)
        except ValueError:
            prio = 10**9
        return (IMPACT_ORDER.get((w.get("county_impact") or "").strip(), 2), -m["severity"], prio,
                m["instrument_id"])

    out = []
    for rank, m in enumerate(sorted(merged.values(), key=key), 1):
        w = work.get(m["instrument_id"], {})
        out.append({"priority": str(rank), "instrument_id": m["instrument_id"], "state": m["state"],
                    "jurisdiction": m["jurisdiction"], "technologies": ";".join(m["techs"]),
                    "tier": f"severity {m['severity']}; {w.get('county_impact') or 'other records in county'}",
                    "legal_basis": m["legal_basis"], "located_url": w.get("located_url", ""),
                    "search_query": w.get("search_query", "")})
    return out


def pick(restrictions: list[dict], outcomes: list[dict], log: list[dict], today: date,
         n_restrictions: int = DEFAULT_RESTRICTIONS, n_outcomes: int = DEFAULT_OUTCOMES,
         statuses: list[dict] | None = None, n_statuses: int = 0) -> list[dict]:
    """The next batch: n_restrictions instruments, then n_outcomes projects,
    then n_statuses unsettled statuses (rows from status_rows), none attempted
    in the last SKIP_DAYS days and none twice."""
    skip = recent_keys(log, today)
    out: list[dict] = []
    for queue, rows, n in (("restriction", restrictions, n_restrictions), ("outcome", outcomes, n_outcomes),
                           ("status", statuses or [], n_statuses)):
        field, seen = QUEUES[queue], set()
        for r in _rank(rows):
            if len([o for o in out if o["queue"] == queue]) >= n:
                break
            k = (r.get(field) or "").strip()
            if not k or k in seen or (queue, k) in skip:
                continue
            seen.add(k)
            if queue in ("restriction", "status"):
                place = r.get("jurisdiction", "")
                what = f"{r.get('technologies', '')} {r.get('tier', '')}; {r.get('legal_basis', '')}".strip()
            else:
                place = r.get("project_name") or r.get("county", "")
                what = f"{r.get('outcome', '')}; {r.get('what_would_confirm', '')}".strip()
            out.append({"queue": queue, "key": k, "state": r.get("state", ""), "place": place,
                        "what": what, "located_url": r.get("located_url", ""),
                        "search_query": r.get("search_query", "")})
    return out


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--restrictions", type=int, default=DEFAULT_RESTRICTIONS)
    a.add_argument("--outcomes", type=int, default=DEFAULT_OUTCOMES)
    a.add_argument("--statuses", type=int, default=0, help="instruments whose status nobody has settled")
    a.add_argument("--today", default="")
    a.add_argument("--csv", action="store_true", help="print CSV instead of one line per item")
    x = a.parse_args(argv)
    today = date.fromisoformat(x.today) if x.today else date.today()
    work = read_csv(RESTRICTION_WORKLIST)
    statuses = status_rows(read_csv(RESTRICTIONS), work, read_csv(STATUS_RESOLUTIONS)) if x.statuses else []
    batch = pick(work, read_csv(OUTCOME_WORKLIST), read_csv(LOG), today,
                 x.restrictions, x.outcomes, statuses, x.statuses)
    if x.csv:
        w = csv.DictWriter(sys.stdout, fieldnames=OUT_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(batch)
    else:
        for i, b in enumerate(batch, 1):
            print(f"{i}. [{b['queue']}] {b['key']} ({b['state']}, {b['place']}): {b['what']}")
            print(f"   located: {b['located_url'] or 'none'}; search: {b['search_query']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
