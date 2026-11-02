"""County record score: how restrictive a county is, read from its own record.

The county restriction model (scripts/county_restriction_model.py) scores
resemblance: how closely a county's population, income, queue and neighbours
match counties that enacted a severe restriction. It never reads the
county's own instruments or projects, by design, so a small county with a
moratorium in force can score low and a large one with permissive rules and
approved projects high. This score reads the record itself, compares every
county on one rubric, and keeps the resemblance score only as the prior for
counties the record says nothing about. Everything it weighs is in
config/county_record_score.json; read it first. In short:

  instruments  each restriction instrument placed in the county: severity
               points (4: 40, 3: 30, 2: 12, 1: 4) x currency (in force 1,
               status unknown 0.85, pending 0.3) x jurisdiction (county-wide
               1, a city or township 0.5) x technology breadth. The largest
               counts fully, the rest at a quarter, capped.
  zoning       a listed county moving from no zoning to zoning, in a state
               where an unzoned county has no permit over these projects,
               counts as a county-wide severity 3 instrument; one whose
               second reading confirmed every claim counts as verified.
  projects     blocked projects add points; approved ones take points off,
               at most half the instrument points, and never below a
               severity 4 county-wide instrument in force.
  build-out    utility-scale plants built since 2020 (EIA-860M), after the
               county's latest rule in force, count as uncontested
               approvals, inside the same limits.
  no zoning    in a state whose counties cannot zone (config no_county_zoning),
               a county with no record has evidence too: its government
               cannot restrict. Counties that zone anyway by local act are
               listed as exceptions.
  preemption   a state law that overrides local rules (config
               state_preemption, one rule per verified state_policies row)
               caps the severity a local instrument counts at, technology by
               technology: 1 where a state permit replaces local approval, 2
               where statute caps local rules or a state body may set them
               aside. Each rule names the governments it binds and the
               project size it reaches (read for reference_project_mw). The
               same cap bounds the prior of a county with no record.
               combined_local and tier_local are the score as if every local
               instrument bound.
  combined     evidence weight x record points + (1 - weight) x profile
               points; the profile points are the mean record points of all
               counties in the same resemblance decile (no record counts as
               zero).
  deciles      combined_normal is the combined score's rank turned into a
               standard normal score, and combined_decile its tenth of U.S.
               counties. Ties are broken by the resemblance score, then by
               FIPS, so the ten deciles hold the same number of counties
               even though many counties share a combined score. Points and
               tiers are unchanged; these two columns only order counties.

Reads   data/processed/restrictions.csv, contested_projects.csv, county_summary.csv
        data/reference/facilities.csv
        data/model/county_restriction_scores.csv (has_severe, queue run)
        config/county_record_score.json
Writes  data/model/county_record_scores.csv   one row per county
        data/model/county_record_report.md    the rubric's results

Internal, like the rest of data/model/: no page, county report or headline
figure reads these until Price decides otherwise.

Usage
  python scripts/county_record_score.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from statistics import NormalDist
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROCESSED_DIR, ROOT, read_csv, write_csv  # noqa: E402

CONFIG_PATH = ROOT / "config" / "county_record_score.json"
RESTRICTIONS_PATH = PROCESSED_DIR / "restrictions.csv"
PROJECTS_PATH = PROCESSED_DIR / "contested_projects.csv"
SUMMARY_PATH = PROCESSED_DIR / "county_summary.csv"
FACILITIES_PATH = ROOT / "data" / "reference" / "facilities.csv"
PROFILE_PATH = ROOT / "data" / "model" / "county_restriction_scores.csv"
PROFILE_COLUMN = "has_severe__queue"
SCORES_PATH = ROOT / "data" / "model" / "county_record_scores.csv"
REPORT_PATH = ROOT / "data" / "model" / "county_record_report.md"

FIELDS = [
    "county_fips", "state", "county", "tier", "combined", "combined_pct_us", "combined_normal", "combined_decile",
    "state_rank", "state_n",
    "tier_local", "combined_local",
    "basis", "evidence_weight", "record_points", "local_points", "preemption_points", "preemption_rules",
    "instrument_points", "zoning_points", "blocked_points",
    "approval_credit", "top_instrument", "instruments", "verified_instruments", "projects_blocked",
    "projects_advanced", "plants_built", "profile_score", "profile_decile", "profile_points", "profile_cap",
]


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def _int(v) -> int:
    try:
        return int(float(_s(v) or 0))
    except ValueError:
        return 0


def _fips(row: dict) -> list[str]:
    return [f for f in _s(row.get("county_fips_all") or row.get("county_fips")).split(";") if f]


# ── Instruments ─────────────────────────────────────────────────────────────

def instruments(rows: list[dict]) -> dict[str, dict]:
    """instrument_id -> one instrument: counties, technologies, highest
    severity, first non-blank currency and jurisdiction type, verified if any
    row is."""
    out: dict[str, dict] = {}
    for r in rows:
        iid = _s(r.get("instrument_id")) or _s(r.get("id"))
        cur = out.setdefault(iid, {"id": iid, "fips": set(), "techs": set(), "severity": 0, "currency": "",
                                    "jurisdiction_type": "", "restriction_type": "", "jurisdiction": "",
                                    "verified": False, "year": "", "tech_severity": {}})
        cur["fips"].update(_fips(r))
        if _s(r.get("technology")):
            cur["techs"].add(_s(r["technology"]))
        sev = _int(r.get("severity_score"))
        tech = _s(r.get("technology"))
        cur["tech_severity"][tech] = max(sev, cur["tech_severity"].get(tech, 0))
        if sev > cur["severity"]:
            cur["severity"], cur["restriction_type"] = sev, _s(r.get("restriction_type"))
        for field in ("currency", "jurisdiction_type", "jurisdiction"):
            cur[field] = cur[field] or _s(r.get(field))
        cur["verified"] = cur["verified"] or _s(r.get("verification")) == "verified"
        year = _s(r.get("date_enacted_iso"))[:4]
        if year.isdigit():
            cur["year"] = max(cur["year"], year)
    return out


def is_county_wide(inst: dict, cfg: dict) -> bool:
    return inst["jurisdiction_type"] in cfg["instruments"]["jurisdiction"]["county_types"]


def instrument_points(inst: dict, cfg: dict) -> float:
    c = cfg["instruments"]
    base = c["severity_points"].get(str(inst["severity"]), 0)
    currency = c["currency"].get(inst["currency"] or "unknown", 0.0)
    where = c["jurisdiction"]["county"] if is_county_wide(inst, cfg) else c["jurisdiction"]["other"]
    techs = len(inst["techs"] & set(c["breadth_technologies"]))
    breadth = 1 + c["breadth_per_extra_technology"] * max(0, techs - 1)
    return base * currency * where * breadth


def zoning_instruments(cfg: dict, as_of: str) -> dict[str, dict]:
    """county_fips -> a county-wide instrument for a listed zoning transition
    that still counts on as_of (YYYY-MM-DD)."""
    z = cfg["zoning_transition"]
    out = {}
    for c in z["counties"]:
        if c["state"] not in z["states"]:
            raise ValueError(f"zoning transition for {c['county_fips']} in {c['state']}, not a listed state")
        adopted = _s(c.get("adopted_on"))
        if adopted:
            until = f"{int(adopted[:4]) + z['counts_for_years_after_adoption']}{adopted[4:]}"
            if as_of > until:
                continue
        out[c["county_fips"]] = {"id": f"zoning:{c['county_fips']}", "fips": {c["county_fips"]},
                                 "techs": set(c["technologies"]), "severity": z["severity"],
                                 "currency": "in_force", "jurisdiction_type": "County",
                                 "restriction_type": "zoning_transition", "jurisdiction": c["county"],
                                 "verified": _s((c.get("second_reading") or {}).get("verdict")) == "confirmed",
                                 "year": _s(c.get("drafting_since"))[:4],
                                 "tech_severity": {t: z["severity"] for t in c["technologies"]}}
    return out


# ── State preemption ────────────────────────────────────────────────────────

def preemption_rules(cfg: dict, state: str, as_of: str) -> list[dict]:
    """The state_preemption rules of a state in effect on as_of (YYYY-MM-DD)."""
    return [r for r in (cfg.get("state_preemption") or {}).get("rules", [])
            if r["policy_id"].split("-")[0] == state and (not r["effective"] or r["effective"] <= as_of)
            and (not r["expires"] or as_of <= r["expires"])]


def reaches(rule: dict, tech: str, county_wide: bool, cfg: dict) -> bool:
    """Whether a rule reaches a local instrument on tech: the rule covers the
    technology, binds this kind of government, and applies to a project of
    the reference size."""
    sp = cfg["state_preemption"]
    if tech not in rule["technologies"]:
        return False
    if rule["binds"] == "county" and not county_wide or rule["binds"] == "non_county" and county_wide:
        return False
    least = rule["technologies"][tech]
    if isinstance(least, dict):
        return sp["reference_project_mw"] * sp["reference_storage_hours"] >= least["mwh"]
    return least is None or sp["reference_project_mw"] >= least


def ceiling(tech: str, county_wide: bool, rules: list[dict], cfg: dict) -> tuple[int | None, list[str]]:
    """The lowest ceiling the rules put on a local instrument on tech, and the
    rules that set it; (None, []) when no rule reaches it."""
    caps = [(cfg["state_preemption"]["ceilings"][r["mechanism"]], r["policy_id"])
            for r in rules if reaches(r, tech, county_wide, cfg)]
    if not caps:
        return None, []
    low = min(c for c, _ in caps)
    return low, sorted({p for c, p in caps if c == low})


def preempted(inst: dict, rules: list[dict], cfg: dict) -> dict:
    """The instrument with its severity capped technology by technology, or
    the instrument itself when no rule lowers it."""
    county_wide = is_county_wide(inst, cfg)
    severity, by = 0, set()
    for tech, sev in (inst.get("tech_severity") or {"": inst["severity"]}).items():
        cap, ids = ceiling(tech, county_wide, rules, cfg)
        if cap is not None and cap < sev:
            by.update(ids)
            sev = cap
        severity = max(severity, sev)
    if severity >= inst["severity"]:
        return inst
    return {**inst, "severity": severity, "local_severity": inst["severity"], "preempted_by": sorted(by)}


def prior_cap(rules: list[dict], cfg: dict) -> float | None:
    """The points of one county-wide instrument in force on solar, wind and
    battery storage at the highest county ceiling the rules set on them, when
    a rule reaches every one of the three; None otherwise."""
    techs = cfg["instruments"]["breadth_technologies"]
    caps = [ceiling(t, True, rules, cfg)[0] for t in techs]
    if None in caps or not cfg["state_preemption"].get("cap_prior"):
        return None
    return instrument_points({"severity": max(caps), "currency": "in_force", "jurisdiction_type": "County",
                              "techs": set(techs)}, cfg)


def plants(facility_rows: list[dict], cfg: dict) -> dict[str, list[int]]:
    """county_fips -> years of the build-out plants placed in it."""
    b = cfg["build_out"]
    out: dict[str, list[int]] = defaultdict(list)
    for p in facility_rows:
        if p.get("source") != b["source"] or p.get("status") not in b["statuses"]:
            continue
        if not set(_s(p.get("technology")).split(";")) & set(b["technologies"]):
            continue
        year = _s(p.get("year"))[:4]
        try:
            mw = float(p.get("capacity_mw") or 0)
        except ValueError:
            continue
        if mw >= b["min_mw"] and year.isdigit() and int(year) >= b["since_year"] and _s(p.get("county_fips")):
            out[p["county_fips"]].append(int(year))
    return out


def uncontested_builds(years: list[int], insts: list[dict], zoning: dict | None, advanced: int) -> int:
    """Plants no earlier than the county's latest instrument in force, less
    the contested projects that advanced (assumed to be among them)."""
    rules = [i for i in insts + ([zoning] if zoning else []) if i["currency"] == "in_force" and i["year"]]
    latest = max((int(i["year"]) for i in rules), default=0)
    return max(0, sum(1 for y in years if y >= latest) - advanced)


# ── Score ───────────────────────────────────────────────────────────────────

def stack(points: list[float], cfg: dict) -> float:
    """The largest in full, the rest at others_weight, capped."""
    ci = cfg["instruments"]
    pts = sorted(points, reverse=True)
    return min(ci["cap"], pts[0] + ci["others_weight"] * sum(pts[1:])) if pts else 0.0


def record(insts: list[dict], zoning: dict | None, outcomes: list[str], cfg: dict, rules: list[dict] = ()) -> dict:
    """The record points of one county from its instruments, its zoning
    transition (or None) and its contested projects' outcomes, with each
    instrument capped by the state preemption rules in effect there.
    local_points is the same score with no cap."""
    capped = [preempted(i, list(rules), cfg) for i in insts]
    capped_zoning = preempted(zoning, list(rules), cfg) if zoning else None
    out = _record(capped, capped_zoning, outcomes, cfg)
    local = _record(insts, zoning, outcomes, cfg)["record_points"] if rules else out["record_points"]
    by = sorted({p for i in capped + [capped_zoning] if i for p in i.get("preempted_by", [])})
    return {**out, "local_points": local, "preemption_points": round(local - out["record_points"], 2),
            "preemption_rules": ";".join(by)}


def _record(insts: list[dict], zoning: dict | None, outcomes: list[str], cfg: dict) -> dict:
    cp = cfg["projects"]
    scored = sorted(((instrument_points(i, cfg), i) for i in insts + ([zoning] if zoning else [])),
                    key=lambda t: (-t[0], t[1]["id"]))
    base = stack([p for p, _ in scored], cfg)
    inst_pts = stack([p for p, i in scored if i["restriction_type"] != "zoning_transition"], cfg)
    blocked = min(cp["blocked_cap"], sum(max(0, cp["points"].get(o, 0)) for o in outcomes))
    credit = min(cp["approval_cap"], -sum(min(0, cp["points"].get(o, 0)) for o in outcomes),
                 cp["approval_max_share_of_instruments"] * base)
    # A moratorium or ban in force county-wide outweighs earlier approvals.
    floor = max([p for p, i in scored if i["severity"] == 4 and i["currency"] == "in_force"
                 and is_county_wide(i, cfg)], default=0.0)
    total = max(floor, base + blocked - credit)
    top = scored[0][1] if scored else None
    cap = (f" capped from {top['local_severity']} by {';'.join(top['preempted_by'])}"
           if top and "local_severity" in top else "")
    return {"record_points": round(total, 2), "instrument_points": round(inst_pts, 2),
            "zoning_points": round(base - inst_pts, 2), "blocked_points": round(blocked, 2),
            "approval_credit": round(base + blocked - total, 2) if credit else 0.0,
            "top_instrument": (f"{top['id']} ({top['restriction_type']}, severity {top['severity']}{cap}, "
                               f"{top['currency']}, {top['jurisdiction']})") if top else ""}


def tier(points: float, cfg: dict) -> str:
    for t in cfg["tiers"]:
        if points >= t["min"]:
            return t["name"]
    return cfg["tiers"][-1]["name"]


def deciles(values: dict[str, float]) -> dict[str, int]:
    """fips -> decile 1 to 10 of value (ties broken by FIPS)."""
    order = sorted(values, key=lambda f: (values[f], f))
    n = len(order)
    return {f: min(10, 1 + (10 * i) // n) for i, f in enumerate(order)}


def normal_scores(rows: list[dict]) -> None:
    """Set combined_normal and combined_decile on each row, by rank.

    The combined score is skewed (most counties have no record and take one
    of a few prior values), so cutting it at its own deciles gives uneven
    groups. Ranking first, with ties broken by the resemblance score and then
    FIPS, gives every county its own place; the place becomes a standard
    normal score (Blom, (rank - 3/8) / (n + 1/4)) and a decile of equal size.
    """
    def key(r):
        p = r.get("profile_score")
        return (r["combined"], float(p) if p != "" else -1.0, r["county_fips"])
    order = sorted(rows, key=key)
    n = len(order)
    nd = NormalDist()
    for i, r in enumerate(order):
        r["combined_normal"] = round(nd.inv_cdf((i + 1 - 0.375) / (n + 0.25)), 3) + 0.0
        r["combined_decile"] = 1 + (10 * i) // n


def pct(values: list[float], v: float) -> float:
    """Mid-rank percentile of v among values."""
    below = sum(1 for x in values if x < v)
    same = sum(1 for x in values if x == v)
    return round(100 * (below + 0.5 * same) / len(values), 1)


def build(restriction_rows: list[dict], project_rows: list[dict], summary_rows: list[dict],
          profile_rows: list[dict], cfg: dict, as_of: str, facility_rows: list[dict] = ()) -> list[dict]:
    by_county: dict[str, list[dict]] = defaultdict(list)
    for inst in instruments(restriction_rows).values():
        for f in inst["fips"]:
            by_county[f].append(inst)
    outcomes: dict[str, list[str]] = defaultdict(list)
    for p in project_rows:
        for f in _fips(p):
            outcomes[f].append(_s(p.get("outcome")))
    zoning = zoning_instruments(cfg, as_of)
    built_years = plants(list(facility_rows), cfg)
    profile = {_s(r["county_fips"]): float(r[PROFILE_COLUMN]) for r in profile_rows
               if _s(r.get(PROFILE_COLUMN))}
    pdec = deciles(profile)
    ew = cfg["evidence_weight"]
    rules_by_state: dict[str, list[dict]] = {}

    rows = []
    for s in summary_rows:
        f = _s(s["county_fips"])
        if f.startswith("72"):
            continue
        st = _s(s.get("state"))
        rules = rules_by_state.setdefault(st, preemption_rules(cfg, st, as_of))
        insts = by_county.get(f, [])
        contested = outcomes.get(f, [])
        advanced = sum(1 for o in contested if o.startswith("advanced"))
        built = uncontested_builds(built_years.get(f, []), insts, zoning.get(f), advanced)
        rec = record(insts, zoning.get(f), contested + ["built"] * built, cfg, rules)
        verified = sum(1 for i in insts if i["verified"])
        confirmed = any(o.endswith("_confirmed") for o in contested) or bool(zoning.get(f, {}).get("verified"))
        has_record = bool(insts) or bool(contested) or f in zoning
        if has_record:
            basis = "record"
            weight = ew["verified_record"] if (verified or confirmed) else ew["unverified_record"]
        elif _s(s.get("coverage")) == "negative_check":
            basis, weight = "negative_check", ew["negative_check"]
        elif built:
            basis, weight = "build_out", ew["build_out"]
        elif (_s(s.get("state")) in cfg["no_county_zoning"]["states"]
              and f not in cfg["no_county_zoning"].get("except_counties", {})):
            basis, weight = "no_county_zoning", ew["no_county_zoning"]
        else:
            basis, weight = "profile_only", ew["none"]
        rows.append({"county_fips": f, "state": _s(s.get("state")), "county": _s(s.get("county")),
                     "basis": basis, "evidence_weight": weight, **rec,
                     "instruments": len(insts), "verified_instruments": verified,
                     "projects_blocked": sum(1 for o in outcomes.get(f, []) if o.startswith("blocked")),
                     "projects_advanced": advanced, "plants_built": built,
                     "profile_score": profile.get(f, ""), "profile_decile": pdec.get(f, "")})

    # Profile points: the mean record points of every county in the same
    # resemblance decile, a county with no record counting as zero. Most
    # counties have never been examined, so this is a floor, as every count
    # here is; averaging only counties with a record would put every
    # unexamined county above one that approved its projects. The mean is of
    # points with no state preemption cap (local_points), so a cap in one
    # state never moves another state's prior; profile_cap applies the
    # county's own state's cap afterwards.
    by_dec: dict[int, list[float]] = defaultdict(list)
    for r in rows:
        if r["profile_decile"] != "":
            by_dec[r["profile_decile"]].append(r["local_points"])
    dec_mean = {d: sum(v) / len(v) for d, v in by_dec.items()}
    caps = {st: prior_cap(rules, cfg) for st, rules in rules_by_state.items()} if rules_by_state else {}
    for r in rows:
        cap = caps.get(r["state"])
        r["profile_cap"] = "" if cap is None else round(cap, 2)
        r["profile_points"] = round(min(dec_mean.get(r["profile_decile"], 0.0), cap if cap is not None else 1e9), 2)
        w = r["evidence_weight"]
        r["combined"] = round(w * r["record_points"] + (1 - w) * r["profile_points"], 2)
        r["tier"] = tier(r["combined"], cfg) if r["basis"] != "profile_only" else "no_record"
    normal_scores(rows)
    combined = [r["combined"] for r in rows]
    by_state: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        r["combined_pct_us"] = pct(combined, r["combined"])
        by_state[r["state"]].append(r)
    for st_rows in by_state.values():
        for r in st_rows:
            r["state_rank"] = 1 + sum(1 for x in st_rows if x["combined"] > r["combined"])
            r["state_n"] = len(st_rows)
    # The same rubric with no state preemption: what each county would score
    # if every local instrument bound.
    if (cfg.get("state_preemption") or {}).get("rules"):
        local_cfg = {**cfg, "state_preemption": {**cfg["state_preemption"], "rules": [], "cap_prior": False}}
        local = {r["county_fips"]: r for r in build(restriction_rows, project_rows, summary_rows, profile_rows,
                                                    local_cfg, as_of, facility_rows)}
    else:
        local = {r["county_fips"]: r for r in rows}
    for r in rows:
        r["combined_local"], r["tier_local"] = local[r["county_fips"]]["combined"], local[r["county_fips"]]["tier"]
    return rows


# ── Report ──────────────────────────────────────────────────────────────────

def report(rows: list[dict], cfg: dict) -> str:
    by = {r["county_fips"]: r for r in rows}
    tiers = [t["name"] for t in cfg["tiers"]] + ["no_record"]
    L = ["# County record score", "",
         "Written by `scripts/county_record_score.py` from `config/county_record_score.json` "
         f"(version {cfg['version']}). Do not edit by hand.", "",
         "**What the score is.** How restrictive a county is for wind, solar and battery storage, on one "
         "rubric, read from its own record: the restriction instruments placed in it, a listed move from no "
         "zoning to zoning, and the outcomes of its contested projects. A county with no record is scored on "
         "its resemblance score (`data/model/county_restriction_scores.csv`) as a prior. Internal: no page, "
         "county report or headline figure reads it.", "",
         "## Counties by tier", "", "| Tier | Counties | Meaning |", "|---|---:|---|"]
    labels = {t["name"]: t["label"] for t in cfg["tiers"]}
    labels["no_record"] = "No record and no negative check: scored on the profile prior alone"
    for t in tiers:
        L.append(f"| {t} | {sum(1 for r in rows if r['tier'] == t)} | {labels[t]} |")
    L += ["", "## Reference counties", "",
          "| County | Tier | Combined (U.S. percentile) | Record points | Instruments | Zoning | Blocked | "
          "Approval credit | Resemblance score (decile) | Top instrument |",
          "|---|---|---|---:|---:|---:|---:|---:|---|---|"]
    for f in cfg["reference_counties"]["fips"]:
        r = by.get(f)
        if not r:
            continue
        L.append(f"| {r['county']}, {r['state']} | {r['tier']} | {r['combined']} ({r['combined_pct_us']}) "
                 f"| {r['record_points']} | {r['instrument_points']} | {r['zoning_points']} | {r['blocked_points']} "
                 f"| {r['approval_credit']} | {r['profile_score']} ({r['profile_decile']}) | {r['top_instrument']} |")
    L += preemption_report(rows, cfg)
    L += ["", "## Combined score by decile", "",
          "Deciles of U.S. counties ranked by combined score, ties broken by resemblance score. "
          "`combined_normal` is the same rank as a standard normal score.", "",
          "| Decile | Counties | Combined score (lowest to highest) | Normal score (lowest to highest) |",
          "|---:|---:|---|---|"]
    for d in range(1, 11):
        ds = [r for r in rows if r["combined_decile"] == d]
        if ds:
            L.append(f"| {d} | {len(ds)} | {min(r['combined'] for r in ds)} to {max(r['combined'] for r in ds)} "
                     f"| {min(r['combined_normal'] for r in ds)} to {max(r['combined_normal'] for r in ds)} |")
    L += ["", "## Highest combined scores", "", "| County | Tier | Combined | Top instrument |", "|---|---|---:|---|"]
    for r in sorted(rows, key=lambda r: (-r["combined"], r["county_fips"]))[:15]:
        L.append(f"| {r['county']}, {r['state']} | {r['tier']} | {r['combined']} | {r['top_instrument']} |")
    L += ["## Build-out", "",
          f"{sum(1 for r in rows if r['plants_built'])} counties have at least one uncontested plant counted as an "
          f"approval ({sum(r['plants_built'] for r in rows)} plants); for "
          f"{sum(1 for r in rows if r['basis'] == 'build_out')} of them it is the only evidence on record.", ""]
    rec = [r for r in rows if r["basis"] == "record"]
    L += ["", "## Record against resemblance", "",
          f"{len(rec)} counties have a record. Of those in the top three resemblance deciles, "
          f"{sum(1 for r in rec if r['profile_decile'] != '' and r['profile_decile'] >= 8 and r['tier'] in ('open', 'regulated'))} "
          "are open or regulated on their record; of those in the bottom three, "
          f"{sum(1 for r in rec if r['profile_decile'] != '' and r['profile_decile'] <= 3 and r['tier'] in ('closed', 'severe'))} "
          "are closed or severe. These are the counties where the two scores disagree most.", ""]
    return "\n".join(L) + "\n"


def preemption_report(rows: list[dict], cfg: dict) -> list[str]:
    sp = cfg.get("state_preemption") or {}
    if not sp.get("rules"):
        return []
    tiers = [t["name"] for t in cfg["tiers"]] + ["no_record"]
    L = ["", "## State preemption", "",
         "Each rule in `state_preemption` caps the severity a local instrument counts at (1 where a state permit "
         "replaces local approval, 2 where statute caps local rules or a state body may set them aside), for the "
         f"governments it binds and a project of {sp['reference_project_mw']} MW. `tier_local` and "
         "`combined_local` are the score with no cap.", "",
         "| Rule | Mechanism | Ceiling | Binds | Technologies (smallest project reached) | Counties capped | "
         "Points removed |", "|---|---|---:|---|---|---:|---:|"]
    for rule in sp["rules"]:
        hit = [r for r in rows if rule["policy_id"] in r["preemption_rules"].split(";")]
        techs = ", ".join(f"{t} ({'any' if v is None else str(v['mwh']) + ' MWh' if isinstance(v, dict) else str(v) + ' MW'})"
                          for t, v in rule["technologies"].items())
        L.append(f"| {rule['policy_id']} | {rule['mechanism']} | {sp['ceilings'][rule['mechanism']]} | {rule['binds']} "
                 f"| {techs} | {len(hit)} | {round(sum(r['preemption_points'] for r in hit), 2)} |")
    moved = [r for r in rows if r["tier"] != r["tier_local"]]
    L += ["", f"{sum(1 for r in rows if r['preemption_points'])} counties have record points removed and "
          f"{sum(1 for r in rows if r['profile_cap'] != '' and r['basis'] != 'record')} without a record have their "
          f"prior capped; {len(moved)} change tier.", "",
          "| Tier with no cap | " + " | ".join(tiers) + " |", "|---|" + "---:|" * len(tiers)]
    for a in tiers:
        L.append(f"| {a} | " + " | ".join(str(sum(1 for r in rows if r["tier_local"] == a and r["tier"] == b))
                                          for b in tiers) + " |")
    L += ["", "Rows are the tier with no cap, columns the tier scored.", "",
          "### Largest reductions", "",
          "| County | Tier (no cap to scored) | Combined (no cap to scored) | Record points removed | Rules |",
          "|---|---|---|---:|---|"]
    for r in sorted(rows, key=lambda r: (r["combined"] - r["combined_local"], r["county_fips"]))[:20]:
        if r["combined_local"] == r["combined"]:
            break
        L.append(f"| {r['county']}, {r['state']} | {r['tier_local']} to {r['tier']} | {r['combined_local']} to "
                 f"{r['combined']} | {r['preemption_points']} | {r['preemption_rules'] or 'prior cap'} |")
    ex = {k: v for k, v in sp.get("partial_exemptions", {}).items() if not k.startswith("_")}
    if ex:
        L += ["", "### Partial exemptions", "",
              "The cap still applies in these counties; a site inside the exempt area is not covered by it.", ""]
        L += [f"- {v}" for v in ex.values()]
    na = {k: v for k, v in sp.get("not_applied", {}).items() if not k.startswith("_")}
    if na:
        L += ["", "### Read and not applied", ""] + [f"- {k}: {v}" for k, v in na.items()]
    return L


def main() -> int:
    import datetime as dt
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    rows = build(read_csv(RESTRICTIONS_PATH), read_csv(PROJECTS_PATH), read_csv(SUMMARY_PATH),
                 read_csv(PROFILE_PATH), cfg, dt.date.today().isoformat(), read_csv(FACILITIES_PATH))
    write_csv(SCORES_PATH, rows, FIELDS)
    REPORT_PATH.write_text(report(rows, cfg), encoding="utf-8")
    counts = {t: sum(1 for r in rows if r["tier"] == t) for t in [x["name"] for x in cfg["tiers"]] + ["no_record"]}
    print(f"Wrote {SCORES_PATH.relative_to(ROOT)} ({len(rows)} counties; "
          + ", ".join(f"{t} {n}" for t, n in counts.items()) + f") and {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
