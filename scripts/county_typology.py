#!/usr/bin/env python3
"""One category per county, read off what the published data holds there.

data/processed/county_summary.csv counts what each county has; this module
says what kind of county that makes it, so a reader can group the 3,144
counties (and the county equivalents outside the coverage universe) without
re-deriving the rules each time. It is descriptive only: every value is a
count or a label computed from published rows, never a score, a forecast or
a guess. The county restriction model's scores (data/model/) are not read:
config/county_model_registration.json keeps them off every page and report
until Price decides otherwise.

Reads   data/processed/county_summary.csv     the per-county counts and coverage
        data/processed/restrictions.csv       currency, type, severity, technology by instrument
        data/processed/state_policies.csv     each state's verified siting law
        data/reference/county_covariates.csv  population and density (ACS)
        data/geo/ (via geo.neighbors)         which counties share a border
Writes  data/processed/county_typology.csv

`category` takes the first rule a county meets, in this order (CATEGORIES).
Every restriction instrument placed in the county decides its category,
including one that also covers data centers (a moratorium on wind, solar and
data centers is a moratorium on wind and solar). The headline figures count
those apart to keep national totals comparable; here `multi_sector` says how
many of the county's instruments also cover data centers.

  moratorium_in_force          a moratorium whose currency is in_force
  severe_rules_in_force        an instrument in force with a severity of 3 or
                               more (an outright ban, or terms likely to act
                               as one)
  rules_in_force               an instrument in force, less severe
  restriction_pending          an instrument still pending (proposed, not
                               adopted)
  restrictions_status_unknown  instruments, none known to be in force: the
                               source does not say whether they still are
                               (every NREL ordinance, until a reviewer settles
                               it) or they are past their end date with no
                               confirmed extension
  contested_projects_only      no restriction, at least one contested project
  siting_standards_only        only NREL siting standards (rules that set
                               standards but no restriction)
  checked_none_found           nothing published and a documented negative check
  not_examined                 nothing published and no documented negative
                               check (a county a sweep attempted without
                               finishing stays here), which is not evidence
                               that nothing happened

The other columns are counts and context a reader can filter on:
`neighbors_with_rules_in_force` counts adjacent counties whose own category is
one of the three in-force ones; `state_siting_authority` and
`state_limits_local` are classify.state_context for a county-level instrument,
per technology, collapsed to one value when every technology agrees.

Usage
  python scripts/county_typology.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import classify  # noqa: E402
import geo  # noqa: E402
from common import PROCESSED_DIR, ROOT, read_csv, write_csv  # noqa: E402

OUT = PROCESSED_DIR / "county_typology.csv"
SUMMARY = PROCESSED_DIR / "county_summary.csv"
RESTRICTIONS = PROCESSED_DIR / "restrictions.csv"
POLICIES = PROCESSED_DIR / "state_policies.csv"
COVARIATES = ROOT / "data" / "reference" / "county_covariates.csv"

CATEGORIES = [
    "moratorium_in_force", "severe_rules_in_force", "rules_in_force", "restriction_pending",
    "restrictions_status_unknown", "contested_projects_only",
    "siting_standards_only", "checked_none_found", "not_examined",
]
IN_FORCE = {"moratorium_in_force", "severe_rules_in_force", "rules_in_force"}
TECHS = ["solar", "wind", "battery_storage"]
SEVERE = classify.SEVERE_SCORE if hasattr(classify, "SEVERE_SCORE") else 3

FIELDS = [
    "county_fips", "state", "county", "in_coverage_universe", "category",
    "restrictions_renewables", "in_force", "severe_in_force", "moratoria_in_force", "pending",
    "status_unknown", "multi_sector", "technologies_in_force", "latest_enacted_year",
    "contested_projects", "projects_blocked", "projects_advanced", "projects_pending",
    "siting_standard_jurisdictions", "negative_check_grade",
    "neighbors", "neighbors_with_rules_in_force",
    "state_siting_authority", "state_limits_local",
    "population", "pop_density_sqmi",
]


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def _int(v) -> int:
    try:
        return int(float(_s(v) or 0))
    except ValueError:
        return 0


def _fips(row: dict) -> list[str]:
    return [f for f in _s(row.get("county_fips_all")).split(";") if f]


def instruments(rows: list[dict]) -> dict[str, dict]:
    """instrument_id -> one merged instrument: every county and technology it
    touches, its highest severity, whether any of its rows is a moratorium,
    and the first non-blank currency, type and scope (rows of one instrument
    agree on currency and scope; a few differ on type by technology)."""
    out: dict[str, dict] = {}
    for r in rows:
        iid = _s(r.get("instrument_id")) or _s(r.get("id"))
        cur = out.setdefault(iid, {"fips": set(), "techs": set(), "severity": 0, "currency": "",
                                    "restriction_type": "", "moratorium": False, "scope": "", "year": ""})
        cur["fips"].update(_fips(r))
        if _s(r.get("technology")):
            cur["techs"].add(_s(r["technology"]))
        cur["severity"] = max(cur["severity"], _int(r.get("severity_score")))
        cur["moratorium"] = cur["moratorium"] or _s(r.get("restriction_type")) == "moratorium"
        for field in ("currency", "restriction_type", "scope"):
            cur[field] = cur[field] or _s(r.get(field))
        year = _s(r.get("date_enacted_iso"))[:4]
        if year.isdigit():
            cur["year"] = max(cur["year"], year)
    return out


def tally(insts: dict[str, dict]) -> dict[str, dict]:
    """county_fips -> the restriction counts the categories are read from."""
    out: dict[str, dict] = defaultdict(lambda: {"in_force": 0, "severe_in_force": 0, "moratoria_in_force": 0,
                                                 "pending": 0, "status_unknown": 0, "multi_sector": 0,
                                                 "techs": set(), "year": ""})
    for inst in insts.values():
        for f in inst["fips"]:
            t = out[f]
            t["multi_sector"] += inst["scope"] == "multi_sector_data_centers"
            currency = inst["currency"]
            if currency == "in_force":
                t["in_force"] += 1
                t["severe_in_force"] += inst["severity"] >= SEVERE
                t["moratoria_in_force"] += inst["moratorium"]
                t["techs"] |= inst["techs"]
            elif currency == "pending":
                t["pending"] += 1
            else:
                t["status_unknown"] += 1
            if inst["year"]:
                t["year"] = max(t["year"], inst["year"])
    return out


def category(summary: dict, t: dict) -> str:
    """The first rule in CATEGORIES the county meets (module docstring)."""
    if t["moratoria_in_force"]:
        return "moratorium_in_force"
    if t["severe_in_force"]:
        return "severe_rules_in_force"
    if t["in_force"]:
        return "rules_in_force"
    if t["pending"]:
        return "restriction_pending"
    if t["status_unknown"]:
        return "restrictions_status_unknown"
    if _int(summary.get("contested_projects")):
        return "contested_projects_only"
    if _int(summary.get("siting_standard_jurisdictions")):
        return "siting_standards_only"
    if _s(summary.get("coverage")) == "negative_check":
        return "checked_none_found"
    return "not_examined"


def _collapse(by_tech: dict[str, str]) -> str:
    """{"solar": "hybrid", "wind": "hybrid"} -> "hybrid"; differing values keep
    their technology ("solar:hybrid;wind:local_government"); blanks drop out."""
    kept = {t: v for t, v in by_tech.items() if v}
    if not kept:
        return ""
    values = set(kept.values())
    if len(values) == 1 and len(kept) == len(by_tech):
        return values.pop()
    return ";".join(f"{t}:{v}" for t, v in kept.items())


def state_context(state: str, policies_by_state: dict[str, list[dict]]) -> tuple[str, str]:
    """(siting authority, limits local) for a county-level instrument in the
    state, from classify.state_context per technology."""
    policies = policies_by_state.get(state, [])
    who, limits = {}, {}
    for tech in TECHS:
        ctx = classify.state_context({"technology": tech, "jurisdiction_type": "County"}, policies)
        who[tech] = ctx.get("state_siting_authority", "")
        limits[tech] = ctx.get("state_limits_local", "")
    return _collapse(who), _collapse(limits)


def build(summary_rows: list[dict], restriction_rows: list[dict], policy_rows: list[dict],
          covariate_rows: list[dict], neighbors) -> list[dict]:
    """neighbors(fips) -> adjacent county FIPS. Pure apart from that callable."""
    t_by = tally(instruments(restriction_rows))
    empty = tally({})["__none__"]
    policies_by_state: dict[str, list[dict]] = defaultdict(list)
    for p in policy_rows:
        policies_by_state[_s(p.get("state"))].append(p)
    cov = {_s(c.get("county_fips")): c for c in covariate_rows}
    states_seen: dict[str, tuple[str, str]] = {}

    rows = []
    for s in summary_rows:
        fips = _s(s.get("county_fips"))
        t = t_by.get(fips, empty)
        state = _s(s.get("state"))
        if state not in states_seen:
            states_seen[state] = state_context(state, policies_by_state)
        who, limits = states_seen[state]
        c = cov.get(fips, {})
        rows.append({
            "county_fips": fips, "state": state, "county": _s(s.get("county")),
            "in_coverage_universe": "no" if fips.startswith("72") else "yes",
            "category": category(s, t),
            "restrictions_renewables": _int(s.get("restrictions_renewables")),
            "in_force": t["in_force"], "severe_in_force": t["severe_in_force"],
            "moratoria_in_force": t["moratoria_in_force"], "pending": t["pending"],
            "status_unknown": t["status_unknown"], "multi_sector": t["multi_sector"],
            "technologies_in_force": ";".join(x for x in TECHS if x in t["techs"]),
            "latest_enacted_year": t["year"],
            "contested_projects": _int(s.get("contested_projects")),
            "projects_blocked": _int(s.get("projects_blocked")),
            "projects_advanced": _int(s.get("projects_advanced")),
            "projects_pending": _int(s.get("projects_pending")),
            "siting_standard_jurisdictions": _int(s.get("siting_standard_jurisdictions")),
            "negative_check_grade": _s(s.get("negative_check_grade")),
            "state_siting_authority": who, "state_limits_local": limits,
            "population": _s(c.get("population")), "pop_density_sqmi": _s(c.get("pop_density_sqmi")),
        })
    by_fips = {r["county_fips"]: r for r in rows}
    for r in rows:
        adj = [f for f in neighbors(r["county_fips"]) if f in by_fips]
        r["neighbors"] = len(adj)
        r["neighbors_with_rules_in_force"] = sum(1 for f in adj if by_fips[f]["category"] in IN_FORCE)
    return rows


def main() -> int:
    rows = build(read_csv(SUMMARY), read_csv(RESTRICTIONS), read_csv(POLICIES), read_csv(COVARIATES),
                 geo.neighbors)
    write_csv(OUT, rows, FIELDS)
    universe = [r for r in rows if r["in_coverage_universe"] == "yes"]
    counts = {c: sum(1 for r in universe if r["category"] == c) for c in CATEGORIES}
    print(f"Wrote data/processed/county_typology.csv ({len(rows)} counties; "
          + ", ".join(f"{c} {n}" for c, n in counts.items()) + ")")
    return 0


if __name__ == "__main__":
    sys.exit(main())
