"""Descriptive site profile: everything the repo records about one county.

No scoring and no prediction. For a county it lists, with the evidence behind
each item:

  1. In the county      published restrictions, contested projects and cases
                        whose county_fips_all includes it (county-level
                        instruments, multi-county projects, and town-level
                        instruments placed by coordinates or by the Census
                        place index).
  2. Adjacent counties  the same, for every county sharing a boundary,
                        across state lines (data/geo/counties_2024.topojson).
  3. Within a radius    optional (--radius): records outside 1 and 2 whose
                        coordinates, or county centroid, fall within N miles.
  4. Not published      rows the build held back that concern the county:
                        Sabin rows set aside (lifted, duplicate, unplaceable),
                        QC quarantine, coverage gaps and case candidates.
  5. Text mentions      any row in the data or review files whose text names
                        "<County> County" in the state but that 1 to 4 did
                        not place, so an unplaced record still surfaces.
  6. Flags and context  moratoria past their end date, pending instruments,
                        report-only evidence, same-name counties elsewhere,
                        and whether the state has any contested-project
                        coverage at all, so an empty section reads as
                        "nothing recorded", never "nothing happened".

Usage
  python scripts/site_profile.py --state KS --county Cherokee
  python scripts/site_profile.py --fips 20021 --radius 50
  python scripts/site_profile.py --sites sites.csv --out profiles.md
      sites.csv columns: name, state, county, fips (any one of county or fips),
      optional lat, lon, notes. --json writes structured output instead.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import math
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import classify  # noqa: E402
import geo  # noqa: E402
from common import STATE_NAMES  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
REVIEW = ROOT / "data" / "review"
FIPS_LOOKUP = ROOT / "data" / "county_fips_lookup.json"
PLACE_INDEX = ROOT / "data" / "place_county_index.json"
SNAPSHOTS = ROOT / "data" / "snapshots" / "manifest.csv"

IN_FORCE = {"active", "extended", "unknown", "pending", ""}
COUNTY_SUFFIX = re.compile(r"\s+(?:county|co\.?|parish|borough|census area|city and borough)$", re.I)


# ── Loading ──────────────────────────────────────────────────────────────────

def _csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{k: (v or "") for k, v in r.items()} for r in csv.DictReader(f)]


def _json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


class Data:
    def __init__(self) -> None:
        self.restrictions = _csv(PROCESSED / "restrictions.csv")
        self.projects = _csv(PROCESSED / "contested_projects.csv")
        self.cases = _csv(PROCESSED / "cases.csv")
        self.quarantine = _json(PROCESSED / "quarantine.json", [])
        self.held = _csv(REVIEW / "sabin_restrictions_review.csv")
        self.gaps = _csv(REVIEW / "coverage_gaps.csv")
        self.candidates = _csv(REVIEW / "cases_candidates.csv")
        raw = _json(FIPS_LOOKUP, {})
        self.lookup = {k.lower(): str(v) for k, v in raw.items() if not k.startswith("_")}
        self.places = {k: v for k, v in _json(PLACE_INDEX, {}).items() if not k.startswith("_")}
        snaps = _csv(SNAPSHOTS)
        self.as_of = max((r["date"] for r in snaps if r.get("date")), default="unknown")
        for r in self.restrictions + self.projects:
            if "county_fips_all" not in r:  # data built before county_fips_all existed
                r["county_fips_all"] = r.get("county_fips", "")


def fips_set(row: dict) -> set[str]:
    return {f for f in (row.get("county_fips_all") or row.get("county_fips") or "").split(";") if f}


# ── Resolving the site ───────────────────────────────────────────────────────

def resolve(d: Data, state: str = "", county: str = "", fips: str = "") -> tuple[str, str, str]:
    """(fips, county name, state code), or SystemExit with suggestions."""
    if fips:
        fips = fips.strip().zfill(5)
        if not geo.known(fips):
            raise SystemExit(f"FIPS {fips} is not a 2024 county")
        st = next((c for c, n in STATE_NAMES.items()
                   if any(v == fips and k.endswith("|" + n.lower()) for k, v in d.lookup.items())), state.upper())
        return fips, geo.name(fips), st
    st = state.strip().upper()
    if st not in STATE_NAMES:
        raise SystemExit(f"Unknown state {state!r}; use the two-letter code")
    name = COUNTY_SUFFIX.sub("", county.strip())
    found = classify.lookup_county(name, STATE_NAMES[st].lower(), d.lookup)
    if not found or not geo.known(found):
        pool = sorted({k.split("|")[0] for k in d.lookup if k.endswith("|" + STATE_NAMES[st].lower())})
        near = difflib.get_close_matches(name.lower(), pool, n=4, cutoff=0.6)
        hint = f" Did you mean: {', '.join(near)}?" if near else ""
        why = "is not a 2024 county (Connecticut uses planning regions)" if found else "was not found"
        raise SystemExit(f"{county!r}, {st} {why}.{hint}")
    return found, geo.name(found) or name, st


def miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2)
    return 7917.6 * math.asin(math.sqrt(h))


def where(row: dict) -> tuple[float, float] | None:
    try:
        return float(row["latitude"]), float(row["longitude"])
    except (KeyError, ValueError, TypeError):
        pass
    for f in sorted(fips_set(row)):
        c = geo.centroid(f)
        if c:
            return c
    return None


# ── Profiling ────────────────────────────────────────────────────────────────

def county_phrase(name: str) -> re.Pattern:
    return re.compile(rf"\b{re.escape(name)}\s+(?:County|Counties|Parish)\b", re.I)


def profile(d: Data, fips: str, name: str, st: str, *, site: str = "", lat=None, lon=None,
            radius: float = 0.0, notes: str = "") -> dict:
    neighbors = geo.neighbors(fips)
    origin = (lat, lon) if lat is not None and lon is not None else geo.centroid(fips)
    today = date.today().isoformat()
    shown: set[str] = set()

    def take(rows, test):
        out = [r for r in rows if test(r)]
        shown.update(r["id"] for r in out)
        return out

    here = {"restrictions": take(d.restrictions, lambda r: fips in fips_set(r)),
            "contested_projects": take(d.projects, lambda r: fips in fips_set(r))}
    near = {}
    for nb in neighbors:
        rs = take(d.restrictions, lambda r, nb=nb: nb in fips_set(r) and r["id"] not in shown)
        ps = take(d.projects, lambda r, nb=nb: nb in fips_set(r) and r["id"] not in shown)
        if rs or ps:
            near[nb] = {"name": geo.name(nb), "state": state_of(d, nb),
                        "restrictions": rs, "contested_projects": ps}
    radius_rows = []
    if radius and origin:
        for r in d.restrictions + d.projects:
            if r["id"] in shown:
                continue
            pt = where(r)
            if pt and miles(origin, pt) <= radius:
                radius_rows.append({**r, "_miles": round(miles(origin, pt), 1)})
                shown.add(r["id"])
        radius_rows.sort(key=lambda r: r["_miles"])

    linked = {r["source_record_id"] for g in (here, *near.values())
              for k in ("restrictions", "contested_projects") for r in g[k] if r.get("source_record_id")}
    cases = [c for c in d.cases if c.get("source_record_id") in linked]

    # Not published: anything the build set aside that names this county or one of its towns.
    phrase = county_phrase(name)
    bare = name.lower()

    def names_county(row: dict, *fields: str) -> bool:
        if (row.get("state") or "").upper() != st:
            return False
        for f in fields:
            v = (row.get(f) or "").strip()
            if not v:
                continue
            if COUNTY_SUFFIX.sub("", v).lower() == bare or phrase.search(v):
                return True
            key = f"{classify.place_key(v)}|{st}"
            if d.places.get(key) == [fips]:
                return True
        return False

    held = [r for r in d.held if names_county(r, "jurisdiction")]
    gaps = [r for r in d.gaps if names_county(r, "jurisdiction")]
    quarantined = [r for r in d.quarantine
                   if fips in fips_set(r) or names_county(r, "jurisdiction", "county")]
    held_ids = {r.get("source_record_id") for r in held} | {r.get("id") for r in gaps}
    candidates = [r for r in d.candidates
                  if r.get("source_record_id") in linked | held_ids
                  or names_county(r, "project_name") or phrase.search(r.get("litigation_context", ""))
                  and r.get("state", "").upper() == st]

    # Text mentions the placement missed.
    mentions = []
    for r in d.restrictions + d.projects:
        if r["id"] in shown or r.get("state", "").upper() != st:
            continue
        text = " ".join(r.get(k, "") for k in ("description", "long_description", "jurisdiction", "county"))
        if phrase.search(text):
            mentions.append(r)

    flags = []
    for r in here["restrictions"]:
        end = r.get("current_end_date_iso", "")
        if end and end < today and r.get("status") in ("active", "extended"):
            flags.append(f"{r['jurisdiction']} {r['restriction_type']}: end date {end} has passed "
                         f"but status is still {r['status']}; check whether it lapsed or was extended")
        if r.get("status") == "pending":
            flags.append(f"{r['jurisdiction']} {r['restriction_type']}: pending, not yet in force")
        if r.get("needs_verification") == "yes":
            flags.append(f"{r['jurisdiction']} {r['restriction_type']}: source marks it needs verification")
    for r in here["restrictions"] + here["contested_projects"]:
        if r.get("evidence_level") == "report_citation":
            label = r.get("jurisdiction") or r.get("project_name")
            flags.append(f"{label}: evidence is a report citation only; no primary source attached")
    if held:
        flags.append(f"{len(held)} Sabin row(s) for this county were held back from publication; see Not published")
    twins = sorted({r["state"] for r in d.restrictions + d.projects
                    if r.get("state", "").upper() != st and fips not in fips_set(r)
                    and any(geo.name(f).lower() == bare for f in fips_set(r))})
    if twins:
        flags.append(f"Same county name has records in {', '.join(twins)}; do not mix them up")

    state_rows = [r for r in d.restrictions if r["state"] == st]
    context = {
        "restriction_instruments": len({r["instrument_id"] for r in state_rows}),
        "severe_instruments": len({r["instrument_id"] for r in state_rows if r["severity_score"] in ("3", "4")}),
        "contested_projects": sum(1 for r in d.projects if r["state"] == st),
        "cases": sum(1 for r in d.cases if r["state"] == st),
        "unplaced_rows": sum(1 for r in state_rows + [p for p in d.projects if p["state"] == st]
                             if not fips_set(r)),
        "place_index": bool(d.places),
        "data_as_of": d.as_of,
    }
    if context["contested_projects"] == 0:
        flags.append(f"No contested projects are recorded anywhere in {st}: project-level opposition "
                     "is a coverage gap there, not evidence of none")

    return {"site": site or f"{name}, {st}", "notes": notes, "state": st, "county": name, "fips": fips,
            "neighbors": [{"fips": n, "name": geo.name(n), "state": state_of(d, n)} for n in neighbors],
            "in_county": here, "adjacent": near, "within_radius": radius_rows, "radius_mi": radius,
            "cases": cases, "not_published": {"held_back": held, "coverage_gaps": gaps,
                                              "quarantined": quarantined, "case_candidates": candidates},
            "text_mentions": mentions, "flags": flags, "state_context": context}


def state_of(d: Data, fips: str) -> str:
    for code, nm in STATE_NAMES.items():
        if any(v == fips and k.endswith("|" + nm.lower()) for k, v in d.lookup.items()):
            return code
    return ""


# ── Rendering ────────────────────────────────────────────────────────────────

def _instruments(rows: list[dict]) -> list[list[dict]]:
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(r.get("instrument_id") or r["id"], []).append(r)
    return sorted(groups.values(), key=lambda g: -int(g[0].get("severity_score") or 0))


def _restriction_lines(rows: list[dict], indent: str = "") -> list[str]:
    out = []
    for g in _instruments(rows):
        r = g[0]
        techs = ", ".join(sorted({x["technology"] for x in g}))
        when = r.get("date_enacted_iso") or r.get("date_text") or "date n/a"
        dist = f", {r['_miles']} mi" if "_miles" in r else ""
        how = r.get("county_fips_method") or ""
        how = f", placed by {how}" if how and how != "name" else ""
        out.append(f"{indent}- **{r['jurisdiction']}** ({r['jurisdiction_type']}{dist}{how}): "
                   f"{r['restriction_type']}, severity {r['severity_score']}, {techs}; "
                   f"status {r.get('status') or 'n/a'}; {when}; evidence {r['evidence_level']}; "
                   f"scope {r.get('scope', '')}")
        out.append(f"{indent}  {r['description'][:280]}")
        basis = r.get("severity_basis") or (
            "Moratorium Nation rule: active or extended moratorium scores 4, pending 2"
            if (r.get("instrument_id") or "").startswith("mn:") else "n/a")
        out.append(f"{indent}  Severity basis: {basis}. Source: {r['source_url']}")
    return out


def _project_lines(rows: list[dict], indent: str = "") -> list[str]:
    out = []
    for r in rows:
        dist = f", {r['_miles']} mi" if "_miles" in r else ""
        out.append(f"{indent}- **{r['project_name']}** ({r['technology']}, {r.get('capacity_mw') or 'size n/a'}"
                   f"{dist}; {r.get('county', '')}): outcome {r['outcome']}, severity {r['severity_score']}, "
                   f"litigation {r.get('has_litigation') or 'n/a'}, {r.get('event_date_text') or 'date n/a'}; "
                   f"finality {r.get('finality_evidence')}; evidence {r['evidence_level']}")
        out.append(f"{indent}  {r['description'][:280]}")
    return out


def render(p: dict) -> str:
    L = [f"## {p['site']}", "",
         f"{p['county']}, {p['state']} (FIPS {p['fips']}). Data as of {p['state_context']['data_as_of']}.", ""]
    if p["notes"]:
        L += [f"Local knowledge supplied: {p['notes']}", ""]
    here = p["in_county"]
    L.append(f"### In the county: {len(_instruments(here['restrictions']))} restriction instrument(s), "
             f"{len(here['contested_projects'])} contested project(s)")
    L += _restriction_lines(here["restrictions"]) + _project_lines(here["contested_projects"])
    if not here["restrictions"] and not here["contested_projects"]:
        L.append("- Nothing published for this county.")
    L.append("")
    nb_names = ", ".join(f"{n['name']} {n['state']}" for n in p["neighbors"])
    L.append(f"### Adjacent counties ({nb_names})")
    if not p["adjacent"]:
        L.append("- Nothing published in any adjacent county.")
    for nb, g in p["adjacent"].items():
        L.append(f"- {g['name']}, {g['state']} ({nb})")
        L += _restriction_lines(g["restrictions"], "  ") + _project_lines(g["contested_projects"], "  ")
    L.append("")
    if p["radius_mi"]:
        L.append(f"### Within {p['radius_mi']:g} miles (beyond the county and its neighbors)")
        rs = [r for r in p["within_radius"] if r["id"].startswith("res_")]
        ps = [r for r in p["within_radius"] if r["id"].startswith("con_")]
        L += _restriction_lines(rs) + _project_lines(ps) or ["- Nothing."]
        L.append("")
    L.append(f"### Cases linked to the records above: {len(p['cases'])}")
    for c in p["cases"]:
        L.append(f"- {c['case_name']}, {c['court']} {c.get('docket_number', '')}: "
                 f"{c.get('case_status') or 'status blank'} ({c['evidence_level']})")
    L.append("")
    np_ = p["not_published"]
    L.append("### Not published (held back by the build)")
    for r in np_["held_back"]:
        L.append(f"- Sabin {r['source_record_id']}, {r['jurisdiction']}: {r['technology']} {r['mechanisms']}, "
                 f"status {r['status']}. Held back: {r['reason']}.")
        L.append(f"  {r.get('long_description') or r.get('description')}")
    for r in np_["coverage_gaps"]:
        L.append(f"- Coverage gap: {r['jurisdiction']} {r['technologies']} ({r['status']}, {r['date']}) "
                 f"is missing from {r['missing_from']}.")
    for r in np_["quarantined"]:
        why = "; ".join(i.get("detail", i.get("code", "")) for i in r.get("qc_issues", []))
        L.append(f"- Quarantined by QC: {r.get('jurisdiction') or r.get('project_name')} "
                 f"{r.get('technology', '')}: {why}")
    for r in np_["case_candidates"]:
        L.append(f"- Case candidate: {r['project_name']} ({r.get('review_status') or 'unreviewed'}); "
                 "no court record confirmed yet")
    if not any(np_.values()):
        L.append("- Nothing held back for this county.")
    L.append("")
    if p["text_mentions"]:
        L.append("### Named in the text of records placed elsewhere")
        for r in p["text_mentions"]:
            label = r.get("jurisdiction") or r.get("project_name")
            L.append(f"- {label} ({r['id']}, county_fips_all {r.get('county_fips_all') or 'blank'}): "
                     f"{r['description'][:200]}")
        L.append("")
    L.append("### Flags")
    L += [f"- {f}" for f in p["flags"]] or ["- None."]
    s = p["state_context"]
    L += ["", f"State context ({p['state']}): {s['restriction_instruments']} restriction instruments "
          f"({s['severe_instruments']} severe), {s['contested_projects']} contested projects, {s['cases']} cases. "
          f"{s['unplaced_rows']} {p['state']} row(s) could not be placed in any county"
          + ("" if s["place_index"] else " (the Census place index is not built; run "
             "scripts/build_place_index.py to place town-level records)") + ".", ""]
    return "\n".join(L)


def summary(profiles: list[dict]) -> str:
    L = ["| Site | County | Restrictions here | Severe here | Projects here | Adjacent records | "
         "Held back | Flags |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for p in profiles:
        h = p["in_county"]
        inst = _instruments(h["restrictions"])
        severe = sum(1 for g in inst if g[0]["severity_score"] in ("3", "4"))
        adj = sum(len(g["restrictions"]) + len(g["contested_projects"]) for g in p["adjacent"].values())
        held = sum(len(v) for v in p["not_published"].values())
        L.append(f"| {p['site']} | {p['county']}, {p['state']} ({p['fips']}) | {len(inst)} | {severe} | "
                 f"{len(h['contested_projects'])} | {adj} | {held} | {len(p['flags'])} |")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--state")
    a.add_argument("--county")
    a.add_argument("--fips")
    a.add_argument("--lat", type=float)
    a.add_argument("--lon", type=float)
    a.add_argument("--radius", type=float, default=0.0, help="miles; 0 (default) skips the radius section")
    a.add_argument("--name", default="")
    a.add_argument("--notes", default="", help="local knowledge to print beside the data")
    a.add_argument("--sites", help="CSV with name,state,county,fips,lat,lon,notes")
    a.add_argument("--out", help="write here instead of stdout")
    a.add_argument("--json", action="store_true")
    x = a.parse_args(argv)
    d = Data()
    specs = _csv(Path(x.sites)) if x.sites else [{
        "name": x.name, "state": x.state or "", "county": x.county or "", "fips": x.fips or "",
        "lat": "" if x.lat is None else str(x.lat), "lon": "" if x.lon is None else str(x.lon),
        "notes": x.notes}]
    if not x.sites and not (x.fips or (x.state and x.county)):
        a.error("give --fips, or --state and --county, or --sites")
    profiles = []
    for s in specs:
        fips, name, st = resolve(d, s.get("state", ""), s.get("county", ""), s.get("fips", ""))
        lat = float(s["lat"]) if s.get("lat") else None
        lon = float(s["lon"]) if s.get("lon") else None
        profiles.append(profile(d, fips, name, st, site=s.get("name", ""), lat=lat, lon=lon,
                                radius=x.radius, notes=s.get("notes", "")))
    if x.json:
        text = json.dumps(profiles, indent=2, default=str)
    else:
        head = (f"# Site profiles\n\nDescriptive only: what the published and held-back data record. "
                f"Generated {date.today().isoformat()} by scripts/site_profile.py.\n\n")
        text = head + (summary(profiles) + "\n" if len(profiles) > 1 else "") + "\n".join(map(render, profiles))
    if x.out:
        Path(x.out).write_text(text, encoding="utf-8")
        print(f"Wrote {x.out} ({len(profiles)} site(s))")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
