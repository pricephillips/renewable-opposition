"""One row per Ohio county for checking local opt-outs under Ohio SB 52 (2021).

SB 52 (Ohio Rev. Code 303.58 and 303.62) lets a board of county commissioners
declare all or part of the unincorporated county a restricted area where
utility-scale wind (5 MW or more) and solar (50 MW or more) facilities are
prohibited, and veto individual projects before the Ohio Power Siting Board.
Townships can ask for a referendum on a county's resolution. This worklist
says, for every county, what the data already holds and whether anyone has
checked the county's resolutions.

Columns
  priority                 order to check: counties whose records already
                           name an SB 52 action or a restricted area first,
                           then counties with a contested project, then
                           counties with any other record, then the rest
  county_fips, county
  restriction_instruments  published restriction instruments placed in the
                           county: instrument_id, type, severity,
                           verification, source
  sb52_records             of those, the ones whose text names SB 52, a
                           restricted area, 303.58 or a county resolution
  contested_projects       published contested projects in the county
  siting_standards         NREL siting standard features in the county
  pending_queue            review-queue candidates still pending for it
  negative_check           the newest data/review/negative_checks.csv row for
                           it (date and scope)
  first_pass               checked_on of the first pass, from the negative
                           check or the queue row it produced
  next_step                what to search: the county commission's
                           resolutions and minutes, and the Power Siting
                           Board's record of restricted areas

It reads only data/processed/ and data/review/; nothing here publishes.

Usage
  python scripts/ohio_sb52_worklist.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geo  # noqa: E402
from common import PROCESSED_DIR, REVIEW_DIR, ROOT, read_csv, write_csv  # noqa: E402

OUT_PATH = REVIEW_DIR / "ohio_sb52_worklist.csv"
FIELDS = ["priority", "county_fips", "county", "restriction_instruments", "sb52_records", "contested_projects",
          "siting_standards", "pending_queue", "negative_check", "first_pass", "next_step"]
SB52 = re.compile(r"\bS\.?\s?B\.?\s?52\b|restricted area|303\.58|303\.62|unincorporated (?:area|territory)",
                  re.I)
NEXT = ("Search the {county} County Board of Commissioners resolutions and minutes since 2021-10-11 for a "
        "restricted-area resolution or a project veto under Ohio Rev. Code 303.58 or 303.62, and the Ohio "
        "Power Siting Board's case record for the county. Queue what you find (data/review/queue.csv) or "
        "record a negative_checks row.")


def _fips(row: dict) -> set[str]:
    return {f for f in (row.get("county_fips_all") or "").split(";") if f}


def build(restrictions: list[dict], projects: list[dict], standards: list[dict], queue: list[dict],
          checks: list[dict], counties: list[str]) -> list[dict]:
    rows = []
    for fips in counties:
        name = geo.name(fips) or fips
        rs = [r for r in restrictions if fips in _fips(r)]
        inst: dict[str, dict] = {}
        for r in rs:
            inst.setdefault(r.get("instrument_id") or r["id"], r)
        sb52 = [i for i, r in inst.items()
                if SB52.search(" ".join(r.get(k, "") for k in ("description", "long_description", "notes")))]
        ps = [p for p in projects if fips in _fips(p)]
        st = [s for s in standards if fips in _fips(s)]
        qs = [q for q in queue if q.get("state") == "OH" and q.get("review_status") in ("pending", "awaiting_review", "confirmed", "")
              and (q.get("county", "").lower().replace(" county", "") == name.lower()
                   or f"{name} County".lower() in (q.get("description", "") + q.get("reviewer_notes", "")).lower())]
        cs = sorted((c for c in checks if c.get("county_fips", "").zfill(5) == fips),
                    key=lambda c: c.get("checked_on", ""), reverse=True)
        first = cs[0]["checked_on"] if cs else next((q.get("extracted_at", "") for q in qs if q.get("extracted_at")),
                                                    "")
        tier = 0 if sb52 else 1 if ps else 2 if inst or st else 3
        rows.append({
            "_tier": tier, "county_fips": fips, "county": name,
            "restriction_instruments": "; ".join(
                f"{i} ({r.get('restriction_type')}, severity {r.get('severity_score')}, {r.get('verification')}, "
                f"{(r.get('source') or '')[:40]})" for i, r in sorted(inst.items())),
            "sb52_records": "; ".join(sorted(sb52)),
            "contested_projects": "; ".join(sorted({p.get("project_name", "") for p in ps})),
            "siting_standards": f"{len(st)} NREL feature(s)" if st else "",
            "pending_queue": "; ".join(q.get("queue_id") or q.get("description", "")[:60] for q in qs),
            "negative_check": f"{cs[0]['checked_on']} ({cs[0].get('scope')})" if cs else "",
            "first_pass": first,
            "next_step": "" if first else NEXT.format(county=name),
        })
    rows.sort(key=lambda r: (r["_tier"], -len(r["contested_projects"].split("; ")) if r["contested_projects"] else 0,
                             r["county"]))
    for i, r in enumerate(rows, 1):
        r["priority"] = i
        r.pop("_tier")
    return rows


def main() -> int:
    counties = [f for f in geo.all_counties() if f.startswith("39")]
    rows = build(read_csv(PROCESSED_DIR / "restrictions.csv"), read_csv(PROCESSED_DIR / "contested_projects.csv"),
                 read_csv(PROCESSED_DIR / "siting_standards.csv"), read_csv(REVIEW_DIR / "queue.csv"),
                 read_csv(REVIEW_DIR / "negative_checks.csv"), counties)
    write_csv(OUT_PATH, rows, FIELDS)
    done = sum(1 for r in rows if r["first_pass"])
    print(f"Wrote {OUT_PATH.relative_to(ROOT)}: {len(rows)} Ohio counties, {done} with a first pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
