"""Descriptive site profile: what the processed data says about one location.

Usage:
  python scripts/site_profile.py --state PA --county "Adams" [--lat 39.8 --lon -77.2] [--radius 25] [--name "Site A"]

Reports restrictions, contested projects and cases in the county, nearby
(within --radius miles, when coordinates are given), and statewide. No scoring
or prediction: it lists what is recorded and how well each record is evidenced.
"""
import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "data" / "processed"

STATE_NAMES = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas", "CA": "california", "CO": "colorado",
    "CT": "connecticut", "DE": "delaware", "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
    "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas", "KY": "kentucky", "LA": "louisiana",
    "ME": "maine", "MD": "maryland", "MA": "massachusetts", "MI": "michigan", "MN": "minnesota",
    "MS": "mississippi", "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico", "NY": "new york", "NC": "north carolina",
    "ND": "north dakota", "OH": "ohio", "OK": "oklahoma", "OR": "oregon", "PA": "pennsylvania",
    "RI": "rhode island", "SC": "south carolina", "SD": "south dakota", "TN": "tennessee", "TX": "texas",
    "UT": "utah", "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west virginia",
    "WI": "wisconsin", "WY": "wyoming",
}


def load(name):
    with open(P / f"{name}.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def miles(a, b, c, d):
    r = 3958.8
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = math.radians(c - a), math.radians(d - b)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def fips_for(state, county):
    lookup = json.load(open(ROOT / "data" / "county_fips_lookup.json"))
    key = f"{county.lower().strip()}|{STATE_NAMES[state]}"
    return lookup.get(key) or lookup.get(key.replace(" county|", "|"))


def profile(state, county, lat=None, lon=None, radius=25.0):
    state = state.upper()
    fips = fips_for(state, county)
    res, con, cas = load("restrictions"), load("contested_projects"), load("cases")
    out = {"state": state, "county": county, "county_fips": fips, "radius_mi": radius}

    def place(r):
        if fips and r.get("county_fips") == fips:
            return "county", None
        if lat is not None and r.get("latitude") and r.get("longitude"):
            d = miles(lat, lon, float(r["latitude"]), float(r["longitude"]))
            if d <= radius:
                return "nearby", round(d, 1)
        if r.get("state") == state and (r.get("jurisdiction_type") or "").lower() == "state":
            return "statewide", None
        return None, None

    groups = {"restrictions": [], "contested_projects": [], "cases": []}
    for r in res:
        where, d = place(r)
        if where:
            groups["restrictions"].append({**r, "_where": where, "_miles": d})
    for r in con:
        if fips and r.get("county_fips") == fips:
            groups["contested_projects"].append({**r, "_where": "county", "_miles": None})
    linked = {r["source_record_id"] for g in ("restrictions", "contested_projects") for r in groups[g]}
    groups["cases"] = [r for r in cas if r["source_record_id"] in linked]
    # same-state context, so an empty county reads against something
    out["state_context"] = {
        "restriction_instruments": len({r["instrument_id"] for r in res if r["state"] == state}),
        "severe_instruments": len({r["instrument_id"] for r in res if r["state"] == state and r["severity_score"] in ("3", "4")}),
        "contested_projects": sum(1 for r in con if r["state"] == state),
        "rows_without_county_fips": sum(1 for r in res + con if r["state"] == state and not r.get("county_fips")),
    }
    out.update(groups)
    return out


def report(p, name):
    L = [f"## {name}: {p['county']}, {p['state']} (FIPS {p['county_fips'] or 'NOT FOUND'})", ""]
    rs = p["restrictions"]
    inst = {}
    for r in rs:
        inst.setdefault(r["instrument_id"], []).append(r)
    L.append(f"**Restrictions:** {len(inst)} instruments ({len(rs)} rows)")
    for iid, rows in sorted(inst.items(), key=lambda kv: (-int(kv[1][0]["severity_score"] or 0))):
        r = rows[0]
        techs = ", ".join(sorted({x["technology"] for x in rows}))
        where = r["_where"] + (f", {r['_miles']} mi" if r["_miles"] is not None else "")
        L.append(f"- [{where}] {r['jurisdiction']} ({r['jurisdiction_type']}): {r['restriction_type']}, "
                 f"severity {r['severity_score']}, {techs}, status {r['status'] or 'n/a'}, "
                 f"enacted {r['date_enacted_iso'] or r['date_text'] or 'n/a'}; evidence {r['evidence_level']}; scope {r['scope']}")
        L.append(f"    {r['description'][:300]}")
        L.append(f"    basis: {r['severity_basis'] or 'n/a'} | source: {r['source_url']}")
    L.append("")
    L.append(f"**Contested projects:** {len(p['contested_projects'])}")
    for r in p["contested_projects"]:
        L.append(f"- {r['project_name']} ({r['technology']}, {r['capacity_mw'] or '? MW'}): outcome {r['outcome']}, "
                 f"severity {r['severity_score']}, litigation {r['has_litigation']}, {r['event_date_text']}; "
                 f"finality {r['finality_evidence']}; evidence {r['evidence_level']}")
        L.append(f"    {r['description'][:300]}")
    L.append("")
    L.append(f"**Cases:** {len(p['cases'])}")
    for r in p["cases"]:
        L.append(f"- {r['case_name']}, {r['court']} {r['docket_number']}: {r['case_status'] or 'blank'}")
    s = p["state_context"]
    L += ["", f"State context ({p['state']}): {s['restriction_instruments']} restriction instruments "
          f"({s['severe_instruments']} severe), {s['contested_projects']} contested projects, "
          f"{s['rows_without_county_fips']} rows lack a county FIPS (may be missed by the county match).", ""]
    return "\n".join(L)


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--state", required=True)
    a.add_argument("--county", required=True)
    a.add_argument("--lat", type=float)
    a.add_argument("--lon", type=float)
    a.add_argument("--radius", type=float, default=25.0)
    a.add_argument("--name", default="Site")
    a.add_argument("--json", action="store_true")
    x = a.parse_args()
    p = profile(x.state, x.county, x.lat, x.lon, x.radius)
    print(json.dumps(p, indent=2, default=str) if x.json else report(p, x.name))
