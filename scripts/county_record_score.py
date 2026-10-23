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
  combined     evidence weight x record points + (1 - weight) x profile
               points; the profile points are the mean record points of all
               counties in the same resemblance decile (no record counts as
               zero).

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
    "county_fips", "state", "county", "tier", "combined", "combined_pct_us", "state_rank", "state_n",
    "basis", "evidence_weight", "record_points", "instrument_points", "zoning_points", "blocked_points",
    "approval_credit", "top_instrument", "instruments", "verified_instruments", "projects_blocked",
    "projects_advanced", "plants_built", "profile_score", "profile_decile", "profile_points",
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
                                    "verified": False, "year": ""})
        cur["fips"].update(_fips(r))
        if _s(r.get("technology")):
            cur["techs"].add(_s(r["technology"]))
        sev = _int(r.get("severity_score"))
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
                                 "year": _s(c.get("drafting_since"))[:4]}
    return out


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


def record(insts: list[dict], zoning: dict | None, outcomes: list[str], cfg: dict) -> dict:
    """The record points of one county from its instruments, its zoning
    transition (or None) and its contested projects' outcomes."""
    cp = cfg["projects"]
    scored = sorted(((instrument_points(i, cfg), i) for i in insts + ([zoning] if zoning else [])),
                    key=lambda t: (-t[0], t[1]["id"]))
    base = stack([p for p, _ in scored], cfg)
    inst_pts = stack([p for p, i in scored if i is not zoning], cfg)
    blocked = min(cp["blocked_cap"], sum(max(0, cp["points"].get(o, 0)) for o in outcomes))
    credit = min(cp["approval_cap"], -sum(min(0, cp["points"].get(o, 0)) for o in outcomes),
                 cp["approval_max_share_of_instruments"] * base)
    # A moratorium or ban in force county-wide outweighs earlier approvals.
    floor = max([p for p, i in scored if i["severity"] == 4 and i["currency"] == "in_force"
                 and is_county_wide(i, cfg)], default=0.0)
    total = max(floor, base + blocked - credit)
    top = scored[0][1] if scored else None
    return {"record_points": round(total, 2), "instrument_points": round(inst_pts, 2),
            "zoning_points": round(base - inst_pts, 2), "blocked_points": round(blocked, 2),
            "approval_credit": round(base + blocked - total, 2) if credit else 0.0,
            "top_instrument": (f"{top['id']} ({top['restriction_type']}, severity {top['severity']}, "
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

    rows = []
    for s in summary_rows:
        f = _s(s["county_fips"])
        if f.startswith("72"):
            continue
        insts = by_county.get(f, [])
        contested = outcomes.get(f, [])
        advanced = sum(1 for o in contested if o.startswith("advanced"))
        built = uncontested_builds(built_years.get(f, []), insts, zoning.get(f), advanced)
        rec = record(insts, zoning.get(f), contested + ["built"] * built, cfg)
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
    # unexamined county above one that approved its projects.
    by_dec: dict[int, list[float]] = defaultdict(list)
    for r in rows:
        if r["profile_decile"] != "":
            by_dec[r["profile_decile"]].append(r["record_points"])
    dec_mean = {d: sum(v) / len(v) for d, v in by_dec.items()}
    for r in rows:
        r["profile_points"] = round(dec_mean.get(r["profile_decile"], 0.0), 2)
        w = r["evidence_weight"]
        r["combined"] = round(w * r["record_points"] + (1 - w) * r["profile_points"], 2)
        r["tier"] = tier(r["combined"], cfg) if r["basis"] != "profile_only" else "no_record"
    combined = [r["combined"] for r in rows]
    by_state: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        r["combined_pct_us"] = pct(combined, r["combined"])
        by_state[r["state"]].append(r)
    for st_rows in by_state.values():
        for r in st_rows:
            r["state_rank"] = 1 + sum(1 for x in st_rows if x["combined"] > r["combined"])
            r["state_n"] = len(st_rows)
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
