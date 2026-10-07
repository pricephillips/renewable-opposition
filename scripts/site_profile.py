"""Descriptive site profile: everything the repo records about one county.

No scoring and no prediction. For a county it lists, with the evidence behind
each item:

  1. In the county      published restrictions, contested projects and cases
                        whose county_fips_all includes it (county-level
                        instruments, multi-county projects, and town-level
                        instruments placed by coordinates or by the Census
                        place index).
     Local knowledge   rows of data/review/local_knowledge.csv whose
                        county_fips is the county, printed as they are and
                        labelled "reported, not verified". Hand-edited and
                        never published; --no-local leaves it out (and does
                        not read the file) for profiles that leave THG.
  2. Adjacent counties  the same, for every county sharing a boundary,
                        across state lines (data/geo/counties_2024.topojson).
  3. Within a radius    optional (--radius): records outside 1 and 2 whose
                        coordinates, or county centroid, fall within N miles.
  4. Not published      rows the build held back that concern the county:
                        Sabin rows set aside (lifted, duplicate, unplaceable),
                        QC quarantine, coverage gaps, case candidates, and
                        data/review/queue.csv candidates of any entity type
                        still pending review (matched by county name, town
                        via the place index, or "<Name> County" in the text).
                        Pending candidates in adjacent counties are listed
                        there too, one line each.
  5. Text mentions      any row in the data or review files whose text names
                        "<County> County" in the state but that 1 to 4 did
                        not place, so an unplaced record still surfaces.
  6. Flags and context  moratoria past their end date, pending instruments,
                        report-only evidence, same-name counties elsewhere,
                        one "Evidence still to read" flag counting the items
                        shown whose source was seen only as search-index
                        text (access snippet),
                        and whether the state has any contested-project
                        coverage at all, so an empty section reads as
                        "nothing recorded", never "nothing happened". The
                        state line counts unplaced rows (nothing to match)
                        apart from ambiguous ones (a town name shared by
                        several counties), since only the second could be
                        settled by a reviewer override.

Usage
  python scripts/site_profile.py --state KS --county Cherokee
  python scripts/site_profile.py --fips 20021 --radius 50
  python scripts/site_profile.py --sites sites.csv --out profiles.md
  python scripts/site_profile.py --state KS --county Cherokee --no-local
      sites.csv columns: name, state, county, fips (any one of county or fips),
      optional lat, lon, notes. --json writes structured output instead.

Every record line prints its primary source on the "Source" line when one is
attached, labelled "located, not yet read" when only search-index text was
seen, and the compiled source (Sabin, Moratorium Nation) as "Compiled from".
A contested project's outcome prints its resolution URL and access the same way.
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
# Hand-edited, unverified, never published: read here and nowhere else.
LOCAL_KNOWLEDGE = REVIEW / "local_knowledge.csv"
LOCAL_FIELDS = ["county_fips", "state", "county", "topic", "claim", "source_type", "source_note",
                "date_reported", "reporter"]
LOCAL_SOURCE_TYPES = ("local_contact", "meeting_attended", "document_seen")
LOCAL_TOPICS = ("restriction", "project", "litigation", "sentiment", "other")

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
    def __init__(self, local: bool = True, root: Path | None = None) -> None:
        """root: a directory holding a data/ tree laid out like this repo's;
        default the repository itself."""
        if root is None:
            processed, review = PROCESSED, REVIEW
            local_path, lookup, place_index, snapshots = LOCAL_KNOWLEDGE, FIPS_LOOKUP, PLACE_INDEX, SNAPSHOTS
        else:
            processed, review = root / "data" / "processed", root / "data" / "review"
            local_path = review / LOCAL_KNOWLEDGE.name
            lookup, place_index = root / "data" / FIPS_LOOKUP.name, root / "data" / PLACE_INDEX.name
            snapshots = root / "data" / "snapshots" / SNAPSHOTS.name
        self.restrictions = _csv(processed / "restrictions.csv")
        self.projects = _csv(processed / "contested_projects.csv")
        self.cases = _csv(processed / "cases.csv")
        self.quarantine = _json(processed / "quarantine.json", [])
        self.held = _csv(review / "sabin_restrictions_review.csv")
        self.gaps = _csv(review / "coverage_gaps.csv")
        self.candidates = _csv(review / "cases_candidates.csv")
        # Review-queue candidates nobody has decided on yet: shown, never published.
        self.queue = [r for r in _csv(review / "queue.csv") if r.get("review_status") == "pending"]
        # None, not [], when left out, so the profile omits the section.
        self.local = _csv(local_path) if local else None
        raw = _json(lookup, {})
        self.lookup = {k.lower(): str(v) for k, v in raw.items() if not k.startswith("_")}
        self.places = {k: v for k, v in _json(place_index, {}).items() if not k.startswith("_")}
        snaps = _csv(snapshots)
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


def concerns(d: Data, row: dict, fips: str, name: str, st: str, *fields: str) -> bool:
    """Whether a held-back row names this county: the county's own name in a
    field, a town the place index puts in this county alone, or "<Name>
    County" in the text. Rows of other states never match."""
    if (row.get("state") or "").upper() != st:
        return False
    phrase, bare = county_phrase(name), name.lower()
    for f in fields:
        v = (row.get(f) or "").strip()
        if not v:
            continue
        if COUNTY_SUFFIX.sub("", v).lower() == bare or phrase.search(v):
            return True
        if d.places.get(f"{classify.place_key(v)}|{st}") == [fips]:
            return True
    return False


# Queue fields matched against a county: its county, its town, and its text.
QUEUE_PLACE_FIELDS = ("county", "municipality", "project_name", "description")


def pending_for(d: Data, fips: str, name: str, st: str) -> list[dict]:
    return [r for r in d.queue if concerns(d, r, fips, name, st, *QUEUE_PLACE_FIELDS)]


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
    local = None if d.local is None else [r for r in d.local if r["county_fips"].strip().zfill(5) == fips]
    pending = pending_for(d, fips, name, st)
    queued = {id(r) for r in pending}
    near = {}
    for nb in neighbors:
        rs = take(d.restrictions, lambda r, nb=nb: nb in fips_set(r) and r["id"] not in shown)
        ps = take(d.projects, lambda r, nb=nb: nb in fips_set(r) and r["id"] not in shown)
        nb_name, nb_state = geo.name(nb), state_of(d, nb)
        qs = [r for r in pending_for(d, nb, nb_name, nb_state) if id(r) not in queued]
        queued.update(id(r) for r in qs)
        if rs or ps or qs:
            near[nb] = {"name": nb_name, "state": nb_state,
                        "restrictions": rs, "contested_projects": ps, "pending": qs}
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
        return concerns(d, row, fips, name, st, *fields)

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
            flags.append(f"{label}: evidence is a report citation only; "
                         + ("a primary source is located but not yet read" if r.get("primary_source_url")
                            else "no primary source attached"))
    if held:
        flags.append(f"{len(held)} Sabin row(s) for this county were held back from publication; see Not published")
    unread = still_to_read(here, near, radius_rows, pending)
    if unread:
        flags.append(f"Evidence still to read: {len(unread)} item(s) shown here rest on a source located but not "
                     "yet read (only search-index text was seen): " + "; ".join(unread))
    twins = sorted({r["state"] for r in d.restrictions + d.projects
                    if r.get("state", "").upper() != st and fips not in fips_set(r)
                    and any(geo.name(f).lower() == bare for f in fips_set(r))})
    if twins:
        flags.append(f"Same county name has records in {', '.join(twins)}; do not mix them up")

    state_rows = [r for r in d.restrictions if r["state"] == st]
    unplaced = [r for r in state_rows + [p for p in d.projects if p["state"] == st] if not fips_set(r)]
    context = {
        "restriction_instruments": len({r["instrument_id"] for r in state_rows}),
        "severe_instruments": len({r["instrument_id"] for r in state_rows if r["severity_score"] in ("3", "4")}),
        "contested_projects": sum(1 for r in d.projects if r["state"] == st),
        "cases": sum(1 for r in d.cases if r["state"] == st),
        "unplaced_rows": sum(1 for r in unplaced if r.get("county_fips_method") != "place_ambiguous"),
        "ambiguous_rows": sum(1 for r in unplaced if r.get("county_fips_method") == "place_ambiguous"),
        "place_index": bool(d.places),
        "data_as_of": d.as_of,
    }
    if context["contested_projects"] == 0:
        flags.append(f"No contested projects are recorded anywhere in {st}: project-level opposition "
                     "is a coverage gap there, not evidence of none")

    return {"site": site or f"{name}, {st}", "notes": notes, "state": st, "county": name, "fips": fips,
            "neighbors": [{"fips": n, "name": geo.name(n), "state": state_of(d, n)} for n in neighbors],
            "in_county": here, "local_knowledge": local, "adjacent": near, "within_radius": radius_rows, "radius_mi": radius,
            "cases": cases, "not_published": {"held_back": held, "coverage_gaps": gaps,
                                              "quarantined": quarantined, "case_candidates": candidates,
                                              "pending_review": pending},
            "text_mentions": mentions, "flags": flags, "state_context": context}


def _label(r: dict) -> str:
    return r.get("jurisdiction") or r.get("project_name") or r.get("municipality") or r.get("county") or ""


def still_to_read(here: dict, near: dict, radius_rows: list[dict], pending: list[dict]) -> list[str]:
    """One entry per item the profile shows whose source was seen only as
    search-index text: a primary source, an outcome resolution, a placement,
    or a pending review-queue candidate."""
    out, seen = [], set()
    groups = [here, *near.values()]
    restrictions = [r for g in groups for r in g["restrictions"]] + [r for r in radius_rows
                                                                    if r["id"].startswith("res_")]
    projects = [r for g in groups for r in g["contested_projects"]] + [r for r in radius_rows
                                                                      if r["id"].startswith("con_")]
    for r in restrictions + projects:
        iid = r.get("instrument_id") or r["id"]
        for field, what in (("primary_source_access", "primary source"),
                            ("resolution_access", "outcome source"),
                            ("placement_access", "county placement")):
            if r.get(field) == "snippet" and (iid, field) not in seen:
                seen.add((iid, field))
                out.append(f"{_label(r)} {what}")
    for r in pending + [r for g in near.values() for r in g.get("pending", [])]:
        if r.get("access") == "snippet":
            out.append(f"{_label(r)} pending {r.get('entity_type') or 'candidate'}")
    return out


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


ACCESS_LABEL = {"snippet": "located, not yet read", "opened": "opened", "archived": "archived copy read"}


def _seen(url: str, access: str, archived: str = "") -> str:
    """A reviewer's source URL with how it was seen."""
    label = ACCESS_LABEL.get(access, f"access {access or 'not recorded'}")
    return f"{url} ({label}{': ' + archived if archived and access == 'archived' else ''})"


def _compiled(r: dict) -> str:
    """The compiled source a record came from, or '' when its source_url is
    the document itself (a promoted review-queue row)."""
    iid = r.get("instrument_id") or ""
    name = ("Moratorium Nation" if iid.startswith("mn:") else "Sabin Center report" if iid.startswith("sabin:")
            else "")
    return f"{name}, {r.get('source_url', '')}" if name else ""


def _source_line(r: dict) -> str:
    """'Source: <primary> (access). Compiled from <name>, <url>' or the
    compiled source alone when no primary source is attached."""
    compiled = _compiled(r)
    if r.get("primary_source_url"):
        line = "Source: " + _seen(r["primary_source_url"], r.get("primary_source_access", ""),
                                  r.get("primary_source_archived_url", ""))
        if r.get("primary_source_verdict") == "contradicts":
            line += ", which a reviewer reads as contradicting the record"
        return line + (f". Compiled from {compiled}" if compiled else "")
    if compiled:
        return f"Source: no primary source attached. Compiled from {compiled}"
    return f"Source: {r.get('source_url', '')}"


def _placed(r: dict) -> str:
    how = r.get("county_fips_method") or ""
    if not how or how == "name":
        return ""
    if how == "override" and r.get("placement_access"):
        return f", placed by override ({ACCESS_LABEL.get(r['placement_access'], r['placement_access'])})"
    return f", placed by {how}"


def _restriction_lines(rows: list[dict], indent: str = "") -> list[str]:
    out = []
    for g in _instruments(rows):
        r = g[0]
        techs = ", ".join(sorted({x["technology"] for x in g}))
        when = r.get("date_enacted_iso") or r.get("date_text") or "date n/a"
        dist = f", {r['_miles']} mi" if "_miles" in r else ""
        how = _placed(r)
        out.append(f"{indent}- **{r['jurisdiction']}** ({r['jurisdiction_type']}{dist}{how}): "
                   f"{r['restriction_type']}, severity {r['severity_score']}, {techs}; "
                   f"status {r.get('status') or 'n/a'}; {when}; evidence {r['evidence_level']}; "
                   f"scope {r.get('scope', '')}")
        out.append(f"{indent}  {r['description'][:280]}")
        basis = r.get("severity_basis") or (
            "Moratorium Nation rule: active or extended moratorium scores 4, pending 2"
            if (r.get("instrument_id") or "").startswith("mn:") else "n/a")
        out.append(f"{indent}  Severity basis: {basis}. {_source_line(r)}")
    return out


def _project_lines(rows: list[dict], indent: str = "") -> list[str]:
    out = []
    for r in rows:
        dist = f", {r['_miles']} mi" if "_miles" in r else ""
        out.append(f"{indent}- **{r['project_name']}** ({r['technology']}, {r.get('capacity_mw') or 'size n/a'}"
                   f"{dist}{_placed(r)}; {r.get('county', '')}): outcome {r['outcome']}, "
                   f"severity {r['severity_score']}, "
                   f"litigation {r.get('has_litigation') or 'n/a'}, {r.get('event_date_text') or 'date n/a'}; "
                   f"finality {r.get('finality_evidence')}; evidence {r['evidence_level']}")
        out.append(f"{indent}  {r['description'][:280]}")
        if r.get("resolution_url"):
            out.append(f"{indent}  Outcome source: " + _seen(r["resolution_url"], r.get("resolution_access", ""),
                                                            r.get("resolution_archived_url", "")))
        out.append(f"{indent}  {_source_line(r)}")
    return out


def _mechanisms(r: dict) -> str:
    mech = r.get("mechanisms") or r.get("restriction_type") or r.get("opposition_type") or ""
    detail = r.get("mechanism_detail") or ""
    return " ".join(x for x in (f"Mechanisms: {mech}." if mech else "No mechanisms recorded.",
                                 f"Values: {detail}" if detail else "") if x)


def _adopted(r: dict) -> str:
    return r.get("adopted_date") or r.get("first_event_date") or r.get("filing_date") or "date n/a"


def _pending_lines(rows: list[dict], indent: str = "", short: bool = False) -> list[str]:
    out = []
    for r in rows:
        head = (f"{indent}- Pending review, not published: {r.get('entity_type') or 'candidate'}, "
                f"{_label(r)}, {r.get('technology') or 'technology n/a'}")
        access = ACCESS_LABEL.get(r.get("access", ""), f"access {r.get('access') or 'not recorded'}")
        if short:
            out.append(f"{head}; {r.get('mechanisms') or r.get('restriction_type') or 'mechanisms n/a'}; "
                       f"{_adopted(r)}; source {access}")
            continue
        out.append(f"{head}; adopted {_adopted(r)}; source {r.get('source_url') or 'n/a'} ({access}).")
        out.append(f"{indent}  {_mechanisms(r)}")
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
    if p["local_knowledge"] is not None:
        L.append(f"### Local knowledge on file: {len(p['local_knowledge'])} item(s)")
        L.append("From data/review/local_knowledge.csv, as entered. Not checked against a source "
                 "and not part of the published data.")
        for r in p["local_knowledge"]:
            L.append(f"- Reported, not verified ({r['topic'] or 'no topic'}): {r['claim']}")
            L.append(f"  Source: {r['source_type'] or 'not given'}"
                     + (f", {r['source_note']}" if r["source_note"] else "")
                     + f". Reported {r['date_reported'] or 'undated'} by {r['reporter'] or 'unnamed'}.")
        if not p["local_knowledge"]:
            L.append("- Nothing on file for this county.")
        L.append("")
    nb_names = ", ".join(f"{n['name']} {n['state']}" for n in p["neighbors"])
    L.append(f"### Adjacent counties ({nb_names})")
    if not p["adjacent"]:
        L.append("- Nothing published in any adjacent county.")
    for nb, g in p["adjacent"].items():
        L.append(f"- {g['name']}, {g['state']} ({nb})")
        L += _restriction_lines(g["restrictions"], "  ") + _project_lines(g["contested_projects"], "  ")
        L += _pending_lines(g.get("pending", []), "  ", short=True)
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
    L += _pending_lines(np_.get("pending_review", []))
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
          f"{s['unplaced_rows']} {p['state']} row(s) are unplaced (no county, town or coordinates "
          f"the build could match) and {s['ambiguous_rows']} are ambiguous (a town name shared by "
          "several counties, left unplaced rather than guessed)"
          + ("" if s["place_index"] else "; the Census place index is not built, so run "
             "scripts/build_place_index.py to place town-level records") + ".", ""]
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
    a.add_argument("--no-local", action="store_true",
                   help="omit local knowledge (data/review/local_knowledge.csv) and do not read it")
    x = a.parse_args(argv)
    d = Data(local=not x.no_local)
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
