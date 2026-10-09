"""Neighbor watch: counties next to a new restriction that nobody has checked.

A county that adopts a moratorium or siting rules is often followed by its
neighbors. For every published restriction instrument enacted in the last
WINDOW_MONTHS months (date_enacted_iso; an extension counts only through that
date, since no separate extension date is recorded), this lists each adjacent
county (geo.neighbors, across state lines) that has no published restriction
and no data/review/negative_checks.csv row covering restrictions.

Output: data/review/adjacency_worklist.csv, one row per (neighbor, triggering
instrument), newest trigger first, with a suggested search query. A worklist
only: nothing here is published or changes a record.

Usage
  python scripts/adjacency_worklist.py           run by the Build dashboard data workflow
  python scripts/adjacency_worklist.py --today 2026-10-09
"""
from __future__ import annotations

import argparse
import calendar
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geo  # noqa: E402
import negative_checks  # noqa: E402
from build_seed_outputs import fips_states, load_fips_lookup  # noqa: E402
from common import PROCESSED_DIR, REVIEW_DIR, STATE_NAMES, read_csv, write_csv  # noqa: E402

RESTRICTIONS = PROCESSED_DIR / "restrictions.csv"
OUT = REVIEW_DIR / "adjacency_worklist.csv"
WINDOW_MONTHS = 18
FIELDS = ["county_fips", "state", "county", "trigger_instrument_id", "trigger_jurisdiction", "trigger_state",
          "trigger_type", "trigger_status", "trigger_date", "trigger_technologies", "suggested_query"]


def months_before(d: date, n: int) -> date:
    y, m = divmod(d.year * 12 + d.month - 1 - n, 12)
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def latest_day(iso: str) -> date | None:
    """The last day a partial date can mean: '2025' -> 2025-12-31,
    '2025-06' -> 2025-06-30. None when it is not YYYY[-MM[-DD]]."""
    parts = (iso or "").strip().split("-")
    try:
        if len(parts) == 1:
            return date(int(parts[0]), 12, 31)
        y, m = int(parts[0]), int(parts[1])
        if len(parts) == 2:
            return date(y, m, calendar.monthrange(y, m)[1])
        return date(y, m, int(parts[2]))
    except (ValueError, IndexError):
        return None


def fips_of(row: dict) -> set[str]:
    return {f for f in (row.get("county_fips_all") or "").split(";") if f}


def build(restrictions: list[dict], checks: list[dict], today: date, neighbors, name_of, state_of) -> list[dict]:
    cutoff = months_before(today, WINDOW_MONTHS)
    restricted = set().union(*(fips_of(r) for r in restrictions)) if restrictions else set()
    checked = {c.get("county_fips", "").strip() for c in checks if negative_checks.covers(c, "restrictions")}
    instruments: dict[str, list[dict]] = {}
    for r in restrictions:
        instruments.setdefault(r.get("instrument_id") or r.get("id"), []).append(r)
    out, seen = [], set()
    for iid, rows in instruments.items():
        r = rows[0]
        when = latest_day(r.get("date_enacted_iso", ""))
        if when is None or not cutoff <= when <= today:
            continue
        techs = ";".join(sorted({x.get("technology", "") for x in rows}))
        for home in sorted(set().union(*(fips_of(x) for x in rows))):
            for nb in neighbors(home):
                if nb in restricted or nb in checked or (nb, iid) in seen:
                    continue
                seen.add((nb, iid))
                st, county = state_of(nb), name_of(nb)
                out.append({
                    "county_fips": nb, "state": st, "county": county, "trigger_instrument_id": iid,
                    "trigger_jurisdiction": r.get("jurisdiction", ""), "trigger_state": r.get("state", ""),
                    "trigger_type": r.get("restriction_type", ""), "trigger_status": r.get("status", ""),
                    "trigger_date": r.get("date_enacted_iso", ""), "trigger_technologies": techs,
                    "suggested_query": f'"{county} County" {STATE_NAMES.get(st, st)} moratorium OR ordinance '
                                       'solar OR wind OR "battery storage"'})
    return sorted(out, key=lambda x: (x["trigger_date"], x["county_fips"]), reverse=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--today", help="YYYY-MM-DD; default today")
    a = ap.parse_args(argv)
    today = date.fromisoformat(a.today) if a.today else date.today()
    states = fips_states(load_fips_lookup())
    rows = build(read_csv(RESTRICTIONS), negative_checks.load(), today, geo.neighbors, geo.name,
                 lambda f: states.get(f, ""))
    write_csv(OUT, rows, FIELDS)
    print(f"Wrote data/review/adjacency_worklist.csv ({len(rows)} neighbor(s) to check, "
          f"{len({r['county_fips'] for r in rows})} counties)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
