"""One row per county: what the published data holds there, counted by instrument.

data/processed/county_summary.csv / .json lists every county and county
equivalent in the 2024 Census boundaries (data/geo/), including the ones with
nothing published, so a reader can tell "nothing recorded" from "not in the
file". A consumer that needs only per-county figures (a choropleth, a coverage
table, a join to other county data) reads this one small file instead of the
three entity files.

A record counts in every county its county_fips_all lists (the counties it
touches), not only the one county_fips the map paints, so a multi-county
instrument counts in each of its counties. Counting follows
scripts/headline_metrics.py: an instrument once however many technology rows
it has, and restrictions that also cover data centers apart from the
renewables-only figure, never summed into it. A case counts where its project
is. Siting standards count jurisdiction and technology pairs (NREL's
ordinances), not feature rows.

`coverage` says how the county stands: `record` (anything published),
`negative_check` (nothing published, and a documented "checked, nothing
found" row in data/review/negative_checks.csv) or `none` (neither: nobody has
looked, which is not evidence that nothing happened).
"""
from __future__ import annotations

from collections import defaultdict

FIELDS = [
    "county_fips", "state", "county", "coverage",
    "restrictions_renewables", "restrictions_renewables_severe", "restrictions_renewables_verified",
    "restrictions_multi_sector", "contested_projects", "projects_blocked", "projects_advanced",
    "projects_pending", "projects_matched_to_plant", "cases", "siting_standard_jurisdictions",
    "negative_check_on",
]


def _fips(row: dict) -> list[str]:
    return [f for f in str(row.get("county_fips_all") or "").split(";") if f]


def _instruments(rows: list[dict]) -> dict[str, dict]:
    """instrument_id -> merged row: highest severity, any verified row, every county."""
    out: dict[str, dict] = {}
    for r in rows:
        iid = r.get("instrument_id") or r.get("id")
        cur = out.setdefault(iid, {**r, "_fips": set(), "_sev": 0, "_verified": False})
        cur["_fips"].update(_fips(r))
        try:
            cur["_sev"] = max(cur["_sev"], int(r.get("severity_score") or 0))
        except ValueError:
            pass
        cur["_verified"] = cur["_verified"] or r.get("verification") == "verified"
    return out


def build(datasets: dict[str, list[dict]], standards: list[dict], checks: list[dict],
          counties: list[str], county_name, county_state) -> list[dict]:
    """county_name(fips) and county_state(fips) name each county."""
    tally: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    for inst in _instruments(datasets.get("restrictions", [])).values():
        multi = inst.get("scope") == "multi_sector_data_centers"
        for f in inst["_fips"]:
            t = tally[f]
            if multi:
                t["restrictions_multi_sector"] += 1
                continue
            t["restrictions_renewables"] += 1
            t["restrictions_renewables_severe"] += inst["_sev"] >= 3
            t["restrictions_renewables_verified"] += inst["_verified"]
    projects = _instruments(datasets.get("contested_projects", []))
    where: dict[str, set[str]] = defaultdict(set)
    for inst in projects.values():
        outcome = str(inst.get("outcome") or "")
        if inst.get("source_record_id"):
            where[inst["source_record_id"]] |= inst["_fips"]
        for f in inst["_fips"]:
            t = tally[f]
            t["contested_projects"] += 1
            t["projects_blocked"] += outcome.startswith("blocked")
            t["projects_advanced"] += outcome.startswith("advanced")
            t["projects_pending"] += outcome == "pending"
            t["projects_matched_to_plant"] += bool(inst.get("facility_match"))
    for case in _instruments(datasets.get("cases", [])).values():
        for f in where.get(case.get("source_record_id") or "", set()):
            tally[f]["cases"] += 1
    pairs: dict[str, set] = defaultdict(set)
    for s in standards:
        for f in _fips(s):
            pairs[f].add((s.get("jurisdiction"), s.get("technology")))
    for f, p in pairs.items():
        tally[f]["siting_standard_jurisdictions"] = len(p)
    newest: dict[str, str] = {}
    for c in checks:
        f = c.get("county_fips") or ""
        newest[f] = max(newest.get(f, ""), c.get("checked_on") or "")

    out = []
    for f in sorted(counties):
        t = tally.get(f, {})
        row = {k: t.get(k, 0) for k in FIELDS[4:-1]}
        published = any(row[k] for k in ("restrictions_renewables", "restrictions_multi_sector",
                                          "contested_projects", "siting_standard_jurisdictions"))
        coverage = "record" if published else ("negative_check" if newest.get(f) else "none")
        out.append({"county_fips": f, "state": county_state(f), "county": county_name(f),
                    "coverage": coverage, **row, "negative_check_on": newest.get(f, "")})
    return out
