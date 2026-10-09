"""Match contested projects to the federal plant inventories.

data/reference/facilities.csv (scripts/fetch_facilities.py) lists every solar,
wind, battery storage and geothermal plant that EIA-860M, the U.S. Wind
Turbine Database or the U.S. Large-Scale Solar PV Database records as built,
under construction, planned, cancelled or retired. This module finds the
plant, if any, that each contested project became.

Names are compared on their distinctive words: lower case, punctuation gone,
and the generic words of plant names (solar, wind, farm, project, energy,
center, LLC, phase numbers and the rest, NAME_NOISE) dropped, so "Ripley Road
Solar Project" is {ripley, road} and EIA's "Ripley" is {ripley}. A plant is a
candidate only in the project's state and only when the two share a
technology.

  strong    the distinctive words are the same and the plant lies in one of
            the project's counties (or the project names no county); or one
            set contains the other, the plant lies in one of the project's
            counties and the capacities agree (within 20 percent of a figure
            or range the record gives). The strong candidates must all be one
            plant (an EIA plant id, or one USWTDB or USPVDB entry); several
            different plants make the match `possible`.
  possible  the same distinctive words in another county, or one set
            containing the other within the project's county.

Only a strong match is published on the project row (the facility_* columns).
It never changes an outcome: the inventories say what became of a plant, not
whether opposition had anything to do with it, and an outcome changes only
through a reviewed row in data/review/outcome_resolutions.csv. Instead every
strong and possible match goes to data/review/facility_matches.csv, conflicts
first (a project published as blocked whose plant is operating, a pending one
whose plant is built or cancelled), with a drafted evidence note a reviewer
can check and copy into outcome_resolutions.csv.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from common import REVIEW_DIR, ROOT, read_csv

FACILITIES_PATH = ROOT / "data" / "reference" / "facilities.csv"
WORKLIST_PATH = REVIEW_DIR / "facility_matches.csv"

NAME_NOISE = set("""
solar wind farm farms project projects energy energies center centre park facility facilities power
plant plants llc inc lp ltd co company corp the pv photovoltaic generating generation station storage
battery batteries bess and of renewable renewables array system systems turbine turbines proposed
development complex hybrid garden gardens community csg phase site repower repowering parks
i ii iii iv v vi a b c 1 2 3 4 5 6 one two three utility scale mw
""".split())

STATUS_RANK = ["operating", "under_construction", "planned", "canceled_or_postponed", "retired"]
STATUS_WORDS = {"operating": "operating", "under_construction": "under construction",
                "planned": "planned, not under construction", "canceled_or_postponed":
                "cancelled or indefinitely postponed", "retired": "retired"}
SOURCE_LABELS = {"eia860m": "EIA-860M", "uswtdb": "USWTDB", "uspvdb": "USPVDB"}

PUBLISHED = ["facility_match", "facility_ids", "facility_name", "facility_status",
             "facility_capacity_mw", "facility_year", "facility_latitude", "facility_longitude",
             "facility_note", "facility_conflict"]
WORKLIST_FIELDS = [
    "priority", "match", "conflict", "source_record_id", "id", "state", "county", "project_name",
    "technology", "capacity_mw", "outcome", "finality_evidence", "facility_ids", "facility_name",
    "facility_operator", "facility_county_fips", "facility_status", "facility_capacity_mw",
    "facility_year", "matched_on", "draft_outcome", "draft_evidence_url", "draft_evidence_date",
    "draft_evidence_note",
]
EVIDENCE_URLS = {"eia860m": "https://www.eia.gov/electricity/data/eia860m/",
                 "uswtdb": "https://energy.usgs.gov/uswtdb/",
                 "uspvdb": "https://energy.usgs.gov/uspvdb/"}


def core(name: str) -> frozenset[str]:
    """The distinctive words of a plant or project name."""
    text = (name or "").lower().replace("&", " and ").replace("’", "'")
    text = re.sub(r"\(.*?\)", " ", text)
    words = re.findall(r"[a-z0-9]+", text.replace("'", ""))
    return frozenset(w for w in words if w not in NAME_NOISE)


def capacities(text: str) -> list[tuple[float, float]]:
    """(low, high) MW ranges a free-text capacity gives: '160', '35-40 MW',
    '1.2 GW'. A text in other units ('22 turbines', '4,700 acres') gives none."""
    t = (text or "").lower().replace(",", "")
    if re.search(r"turbine|acre|home|panel|household|module|mwh", t):
        return []
    out = []
    for m in re.finditer(r"(\d*\.?\d+)(?:\s*(?:-|to|–)\s*(\d*\.?\d+))?\s*(gw|mw|kw)?", t):
        lo = float(m.group(1))
        hi = float(m.group(2)) if m.group(2) else lo
        f = {"gw": 1000.0, "mw": 1.0, "kw": 0.001}[m.group(3) or "mw"]
        if lo > 0:
            out.append((lo * f, hi * f))
    return out


def capacity_agrees(text: str, mw: str) -> bool:
    try:
        cap = float(mw)
    except (TypeError, ValueError):
        return False
    return any(lo * 0.8 <= cap <= hi * 1.2 for lo, hi in capacities(text))


def capacity_differs(text: str, mw: str) -> bool:
    """Both sizes known and far apart: the plant is under a third or over
    three times every figure the record gives. The record's figure is
    sometimes a turbine count typed as megawatts, so a closer gap is not
    enough to rule a plant out."""
    try:
        cap = float(mw)
    except (TypeError, ValueError):
        return False
    given = capacities(text)
    return bool(given) and not any(lo / 3 <= cap <= hi * 3 for lo, hi in given)


def techs(value: str) -> set[str]:
    return {t.strip() for t in re.split(r"[;,]", value or "") if t.strip()}


def load(path: Path | None = None) -> dict[str, list[dict]]:
    """State -> facility rows, each with its name core. Empty without the file."""
    by_state: dict[str, list[dict]] = defaultdict(list)
    for f in read_csv(path or FACILITIES_PATH):
        f["_core"] = core(f["name"])
        f["_tech"] = techs(f["technology"])
        by_state[f["state"]].append(f)
    return by_state


def identity(f: dict) -> str:
    """One plant across sources: its EIA id when it has one."""
    return f"eia:{f['eia_plant_id']}" if f.get("eia_plant_id") else f["facility_id"]


def candidates(project: dict, by_state: dict[str, list[dict]]) -> list[dict]:
    """[{plant, rows, match, matched_on}] for one project, strongest first."""
    pcore = core(project.get("project_name") or "")
    ptech = techs(project.get("technology") or "")
    if not pcore or not ptech:
        return []
    counties = {c for c in (project.get("county_fips_all") or "").split(";") if c}
    cap_text = project.get("capacity_mw") or ""
    plants: dict[str, dict] = {}
    for f in by_state.get(project.get("state") or "", []):
        fcore = f["_core"]
        if not fcore or not (ptech & f["_tech"]):
            continue
        if fcore == pcore:
            rel = "name"
        elif (fcore < pcore or pcore < fcore) and any(len(w) >= 4 for w in fcore & pcore):
            rel = "part of the name"
        else:
            continue
        in_county = f["county_fips"] in counties
        cap_ok = capacity_agrees(cap_text, f["capacity_mw"])
        cap_off = capacity_differs(cap_text, f["capacity_mw"])
        if cap_off:
            level = "possible"
        elif rel == "name" and (in_county or not counties):
            level = "strong"
        elif rel == "part of the name" and in_county and cap_ok:
            level = "strong"
        elif rel == "name" or in_county:
            level = "possible"
        else:
            continue
        on = [rel] + (["county"] if in_county else []) + (["capacity"] if cap_ok else []) \
            + (["a different capacity"] if cap_off else [])
        p = plants.setdefault(identity(f), {"plant": identity(f), "rows": [], "match": "possible", "on": set()})
        p["rows"].append(f)
        p["on"].update(on)
        if level == "strong":
            p["match"] = "strong"
    out = sorted(plants.values(), key=lambda p: (p["match"] != "strong", p["plant"]))
    strong = [p for p in out if p["match"] == "strong"]
    # A USWTDB or USPVDB entry with no EIA id whose name is the EIA plant's is
    # the same plant (often a later phase recorded apart): fold it in.
    eia = [p for p in strong if p["plant"].startswith("eia:")]
    if len(eia) == 1:
        for p in [p for p in strong if not p["plant"].startswith("eia:")]:
            if {r["_core"] for r in p["rows"]} <= {r["_core"] for r in eia[0]["rows"]}:
                eia[0]["rows"] += p["rows"]
                eia[0]["on"] |= p["on"]
                out.remove(p)
                strong.remove(p)
    if len(strong) > 1:
        for p in strong:
            p["match"] = "possible"
            p["on"].add(f"one of {len(strong)} plants")
    for p in out:
        order = ["name", "part of the name", "county", "capacity", "a different capacity"]
        p["matched_on"] = " and ".join([w for w in order if w in p["on"]] +
                                       sorted(w for w in p["on"] if w not in order))
    return out


def status_of(rows: list[dict]) -> str:
    return min((r["status"] for r in rows), key=STATUS_RANK.index)


def conflict(outcome: str, status: str) -> str:
    outcome = outcome or ""
    built = status in ("operating", "under_construction")
    if outcome.startswith("blocked") and built:
        return f"outcome {outcome}, but the plant is {STATUS_WORDS[status]}"
    if outcome.startswith("advanced") and status == "canceled_or_postponed":
        return f"outcome {outcome}, but the plant is {STATUS_WORDS[status]}"
    if outcome in ("pending", "needs_review") and (built or status == "canceled_or_postponed"):
        return f"outcome {outcome}, but the plant is {STATUS_WORDS[status]}"
    return ""


def _primary(rows: list[dict]) -> dict:
    """The row a note quotes: EIA first, at the plant's own status."""
    status = status_of(rows)
    return sorted(rows, key=lambda r: (r["status"] != status, r["source"] != "eia860m", r["facility_id"]))[0]


def note(rows: list[dict], matched_on: str) -> str:
    """One sentence per source, in the style of the hand-written resolutions."""
    parts = []
    for r in sorted(rows, key=lambda r: (r["source"] != "eia860m", r["facility_id"])):
        when = ""
        if r["year"]:
            when = (f", expected {r['month'] + '/' if r['month'] else ''}{r['year']}"
                    if r["status"] in ("planned", "under_construction")
                    else f", since {r['month'] + '/' if r['month'] else ''}{r['year']}")
        who = f", entity {r['operator']}" if r.get("operator") else ""
        detail = f" {r['status_detail']}" if r["source"] == "eia860m" and r["status_detail"] else ""
        cap = f", {r['capacity_mw']} MW" if r["capacity_mw"] else ""
        # EIA and USPVDB give a bare name ("Charles"); USWTDB the full one.
        # Louisiana parishes and Alaska boroughs keep their bare name.
        suffix = (r["county"] and r["source"] != "uswtdb" and r["state"] not in ("LA", "AK")
                  and "county" not in r["county"].lower())
        place = f"{r['state']}, {r['county']}" + (" County" if suffix else "")
        ident = f"plant ID {r['plant_id']}" if r["source"] == "eia860m" else f"entry {r['plant_id']}"
        parts.append(f"{r['release']}: {ident} '{r['name']}' ({place}{who}, {r['technology']}{cap}), "
                     f"{STATUS_WORDS[r['status']]}{when}.{detail and ' Status' + detail + '.'}")
    return (" ".join(parts) + f" Matched on {matched_on}. The inventory records the plant's status "
            "only; it says nothing about the opposition or its effect.")


def stamp(rows: list[dict], by_state: dict[str, list[dict]]) -> list[dict]:
    """Publish strong matches on the project rows; return the worklist."""
    work = []
    for row in rows:
        for k in PUBLISHED:
            row.pop(k, None)
        found = candidates(row, by_state)
        for p in found:
            status = status_of(p["rows"])
            prim = _primary(p["rows"])
            clash = conflict(row.get("outcome"), status)
            text = note(p["rows"], p["matched_on"])
            if p["match"] == "strong":
                row.update({
                    "facility_match": "strong",
                    "facility_ids": ";".join(sorted(r["facility_id"] for r in p["rows"])),
                    "facility_name": prim["name"], "facility_status": status,
                    "facility_capacity_mw": prim["capacity_mw"] or None, "facility_year": prim["year"] or None,
                    "facility_latitude": float(prim["latitude"]) if prim["latitude"] else None,
                    "facility_longitude": float(prim["longitude"]) if prim["longitude"] else None,
                    "facility_note": text, "facility_conflict": clash or None,
                })
            draft = ""
            if status in ("operating", "under_construction"):
                draft = "advanced_confirmed"
            elif status == "canceled_or_postponed":
                draft = "blocked_confirmed"
            work.append({
                "match": p["match"], "conflict": clash,
                "source_record_id": row.get("source_record_id"), "id": row.get("id"),
                "state": row.get("state"), "county": row.get("county"),
                "project_name": row.get("project_name"), "technology": row.get("technology"),
                "capacity_mw": row.get("capacity_mw"), "outcome": row.get("outcome"),
                "finality_evidence": row.get("finality_evidence"),
                "facility_ids": ";".join(sorted(r["facility_id"] for r in p["rows"])),
                "facility_name": prim["name"], "facility_operator": prim.get("operator"),
                "facility_county_fips": prim["county_fips"], "facility_status": status,
                "facility_capacity_mw": prim["capacity_mw"], "facility_year": prim["year"],
                "matched_on": p["matched_on"],
                "draft_outcome": draft if draft and draft != row.get("outcome") else "",
                "draft_evidence_url": EVIDENCE_URLS[prim["source"]],
                "draft_evidence_date": (f"{prim['year']}-{int(prim['month']):02d}" if prim["month"] else prim["year"])
                if status in ("operating", "under_construction") else "",
                "draft_evidence_note": text,
            })

    def rank(w: dict):
        resolved = (w["finality_evidence"] or "").startswith(("resolution:", "court_ruling:"))
        return (not w["conflict"], w["match"] != "strong", resolved, not w["draft_outcome"],
                w["state"] or "", w["project_name"] or "")
    work.sort(key=rank)
    for i, w in enumerate(work, start=1):
        w["priority"] = i
    return work
