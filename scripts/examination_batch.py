#!/usr/bin/env python3
"""The next counties for a county-check sweep (/sweep-counties), in waves.

data/review/examination_worklist.csv ranks every county nobody has examined
(build_database.py). A sweep takes counties from its top and runs the
/examine-county steps on them a wave at a time. A county the examiner drafted
something for stays on the worklist until the draft is reviewed, and one it
could not finish stays there for good, so without a record of attempts the
next sweep would pick the same counties again. data/review/examination_log.csv
is that record: the record-editor appends one line per county examined. A
county attempted in the last SKIP_DAYS days is skipped, as is one whose
negative check is drafted and waiting for review (`drafted_by` on the
worklist: review it, do not examine it again).

examination_log.csv columns
  date        YYYY-MM-DD of the examination
  county_fips five-digit county FIPS
  state, county
  run         the sweep's run name (<date>-sweep)
  result      restrictions    restrictions drafted (queue rows awaiting review)
              negative_check  a complete negative check drafted
              leads           leads only: the check could not be completed
              not_read        the county's sources could not be opened
  drafted_by  the examiner's signature
  note        the examiner's summary; no em dash

With --by-activity the batch is ordered instead by the solar, wind and
storage megawatts of the county's active or suspended interconnection
requests (data/reference/queue_projects.csv), worklist rank breaking ties: a
county where projects are being proposed is where a rule matters to a
client. --active-only also leaves out counties with no such request; they stay
on the worklist and the county record score covers them with its prior.

Writes nothing.

Usage
  python scripts/examination_batch.py                       the next 20 counties, waves of 5
  python scripts/examination_batch.py --counties 30 --wave-size 6 --state VT --state NH
  python scripts/examination_batch.py --today 2026-10-17 --csv
  python scripts/examination_batch.py --by-activity --active-only --counties 40
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import REVIEW_DIR, ROOT, read_csv  # noqa: E402

WORKLIST = REVIEW_DIR / "examination_worklist.csv"
LOG = REVIEW_DIR / "examination_log.csv"
QUEUE = ROOT / "data" / "reference" / "queue_projects.csv"
ACTIVE = ("active", "suspended")
LOG_FIELDS = ["date", "county_fips", "state", "county", "run", "result", "drafted_by", "note"]
RESULTS = ("restrictions", "negative_check", "leads", "not_read")
SKIP_DAYS = 60
DEFAULT_COUNTIES = 20
DEFAULT_WAVE = 5
OUT_FIELDS = ["wave", "rank", "county_fips", "state", "county", "who_decides", "census_local_governments",
              "neighbors_with_restrictions", "active_queue_mw", "last_attempt"]


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def attempts(log: list[dict]) -> dict[str, date]:
    """county_fips -> the latest date it was examined (bad dates ignored)."""
    out: dict[str, date] = {}
    for r in log:
        try:
            when = date.fromisoformat(_s(r.get("date")))
        except ValueError:
            continue
        fips = _s(r.get("county_fips"))
        if fips and (fips not in out or when > out[fips]):
            out[fips] = when
    return out


def activity(queue: list[dict]) -> dict[str, float]:
    """county_fips -> solar, wind and storage MW of its active or suspended
    interconnection requests."""
    out: dict[str, float] = {}
    for q in queue:
        fips = _s(q.get("county_fips"))
        if not fips or _s(q.get("status")) not in ACTIVE:
            continue
        mw = 0.0
        for k in ("solar_mw", "wind_mw", "storage_mw"):
            try:
                mw += float(_s(q.get(k)) or 0)
            except ValueError:
                pass
        out[fips] = out.get(fips, 0.0) + mw
    return out


def pick(worklist: list[dict], log: list[dict], today: date, n: int = DEFAULT_COUNTIES,
         wave_size: int = DEFAULT_WAVE, states: tuple[str, ...] = (), skip_days: int = SKIP_DAYS,
         mw: dict[str, float] | None = None, active_only: bool = False) -> list[dict]:
    """The next n counties in worklist rank (or, given mw, most active
    interconnection megawatts first), none attempted in the last skip_days
    days, none with a held draft, numbered into waves."""
    last = attempts(log)
    since = today - timedelta(days=skip_days)
    wanted = {s.upper() for s in states}

    def rank(r: dict) -> int:
        try:
            return int(_s(r.get("rank")))
        except ValueError:
            return 10**9

    out: list[dict] = []
    seen: set[str] = set()
    order = (lambda r: (-(mw or {}).get(_s(r.get("county_fips")), 0.0), rank(r))) if mw is not None else rank
    for r in sorted(worklist, key=order):
        if len(out) >= n:
            break
        fips = _s(r.get("county_fips"))
        if not fips or fips in seen or (wanted and _s(r.get("state")).upper() not in wanted):
            continue
        if _s(r.get("drafted_by")):
            continue
        if active_only and not (mw or {}).get(fips):
            continue
        prior = last.get(fips)
        if prior is not None and since < prior <= today:
            continue
        seen.add(fips)
        row = {c: _s(r.get(c)) for c in OUT_FIELDS if c in r}
        row["wave"] = str(len(out) // max(wave_size, 1) + 1)
        row["last_attempt"] = prior.isoformat() if prior else ""
        row["active_queue_mw"] = f"{(mw or {}).get(fips, 0.0):.0f}" if mw is not None else ""
        out.append(row)
    return out


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--counties", type=int, default=DEFAULT_COUNTIES)
    a.add_argument("--wave-size", type=int, default=DEFAULT_WAVE)
    a.add_argument("--state", action="append", default=[], help="only this state (repeatable)")
    a.add_argument("--skip-days", type=int, default=SKIP_DAYS)
    a.add_argument("--today", default="")
    a.add_argument("--csv", action="store_true", help="print CSV instead of one line per county")
    a.add_argument("--by-activity", action="store_true",
                   help="order by active interconnection MW in the county, worklist rank breaking ties")
    a.add_argument("--active-only", action="store_true",
                   help="with --by-activity, leave out counties with no active request")
    x = a.parse_args(argv)
    today = date.fromisoformat(x.today) if x.today else date.today()
    mw = activity(read_csv(QUEUE)) if x.by_activity else None
    batch = pick(read_csv(WORKLIST), read_csv(LOG), today, x.counties, x.wave_size, tuple(x.state), x.skip_days,
                 mw, x.active_only)
    if x.csv:
        w = csv.DictWriter(sys.stdout, fieldnames=OUT_FIELDS, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(batch)
        return 0
    for b in batch:
        again = f"; last attempted {b['last_attempt']}" if b["last_attempt"] else ""
        print(f"wave {b['wave']}: {b['county_fips']} {b.get('county', '')}, {b.get('state', '')} "
              f"(rank {b.get('rank', '')}; {b.get('who_decides', '')}; "
              f"local governments: {b.get('census_local_governments', '')}"
              f"{'; active queue MW: ' + b['active_queue_mw'] if b.get('active_queue_mw') else ''}{again})")
    if not batch:
        print("Nothing to examine: every worklist county was attempted in the last "
              f"{x.skip_days} days or has a draft waiting for review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
