"""Descriptive site profile: everything the repo records about one county.

No scoring and no prediction. For a county it lists, with the evidence behind
each item:

  0. State framework    the state's siting law (data/processed/state_policies.csv):
                        who decides and above what size, any local opt-out
                        power, state setback standards and other state rules,
                        each with its verification label; rows still held for
                        review (data/processed/state_policies_held.csv) are shown
                        as not verified, with the reason.
  1. In the county      published restrictions, contested projects and cases
                        whose county_fips_all includes it (county-level
                        instruments, multi-county projects, and town-level
                        instruments placed by coordinates or by the Census
                        place index).
     Local knowledge   rows of the local-knowledge file whose county_fips is
                        the county, printed as they are and labelled
                        "reported, not verified". Hand-edited, never
                        published and kept outside the repository: the path
                        is $RO_LOCAL_KNOWLEDGE, default
                        ~/.renewable-opposition/local_knowledge.csv.
                        --no-local leaves it out (and does not read the
                        file) for profiles that leave THG.
  2. Adjacent counties  the same, for every county sharing a boundary,
                        across state lines (data/geo/counties_2024.topojson).
     Local siting standards
                        NREL's siting ordinance features (setbacks, height,
                        noise, shadow flicker, lot size, prohibitions and the
                        rest; data/processed/siting_standards.csv) for the
                        county and its neighbors, one line per jurisdiction
                        and technology, each labelled unverified unless a
                        reviewer confirmed it against the ordinance.
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
  python scripts/site_profile.py --fips 19113 --verified-only
      sites.csv columns: name, state, county, fips (any one of county or fips),
      optional lat, lon, notes. --json writes structured output instead.

Every restriction line says, in plain words, how it stands under the evidence
standard (classify.verification): verified against the instrument or its
minutes, instrument located but not yet read, or not verified. Every
contested-project line says whether a news article or court record that was
read backs it. --verified-only leaves out restrictions that are not verified
from the county and adjacent sections and states how many it left out; it
also leaves out siting standards that are not verified and state framework
rows still held for review, and counts them.

An empty county section prints the newest matching row of
data/review/negative_checks.csv instead of "Nothing published": "Checked
<sources> on <date>: none found", flagged stale after 12 months. Every county
a profile is run for is recorded in data/review/profile_requests.csv (county
code and date only), which feeds the build's negative-check worklist.

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
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import classify  # noqa: E402
import geo  # noqa: E402
import group_registry  # noqa: E402
import negative_checks  # noqa: E402
import state_policies  # noqa: E402
from sync_data_center_map import evidence_label  # noqa: E402
from common import STATE_NAMES  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
REVIEW = ROOT / "data" / "review"
FIPS_LOOKUP = ROOT / "data" / "county_fips_lookup.json"
PLACE_INDEX = ROOT / "data" / "place_county_index.json"
SNAPSHOTS = ROOT / "data" / "snapshots" / "manifest.csv"
# Local data center events from pricephillips/data-center-map (scripts/sync_data_center_map.py).
DC_EVENTS = ROOT / "data" / "reference" / "data_center_events.csv"
# Every county a profile is run for: county code and date, never who asked or why.
PROFILE_REQUESTS = REVIEW / "profile_requests.csv"
# Hand-edited, unverified, never published: read here and nowhere else. It
# holds reports from local contacts, so it lives outside this public
# repository; .gitignore and the precommit "private" gate keep it out.
LOCAL_KNOWLEDGE_ENV = "RO_LOCAL_KNOWLEDGE"
LOCAL_KNOWLEDGE_DEFAULT = Path("~/.renewable-opposition/local_knowledge.csv")


def local_knowledge_path() -> Path:
    """$RO_LOCAL_KNOWLEDGE, or ~/.renewable-opposition/local_knowledge.csv."""
    return Path(os.environ.get(LOCAL_KNOWLEDGE_ENV) or LOCAL_KNOWLEDGE_DEFAULT).expanduser()
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
            lookup, place_index, snapshots = FIPS_LOOKUP, PLACE_INDEX, SNAPSHOTS
            dc_events = DC_EVENTS
        else:
            dc_events = root / "data" / "reference" / DC_EVENTS.name
            processed, review = root / "data" / "processed", root / "data" / "review"
            lookup, place_index = root / "data" / FIPS_LOOKUP.name, root / "data" / PLACE_INDEX.name
            snapshots = root / "data" / "snapshots" / SNAPSHOTS.name
        self.policies = _csv(processed / "state_policies.csv")
        self.policies_held = _csv(processed / state_policies.HELD_PATH.name)
        self.standards = _csv(processed / "siting_standards.csv")
        self.restrictions = _csv(processed / "restrictions.csv")
        self.projects = _csv(processed / "contested_projects.csv")
        self.cases = _csv(processed / "cases.csv")
        self.quarantine = _json(processed / "quarantine.json", [])
        self.held = _csv(review / "sabin_restrictions_review.csv")
        self.gaps = _csv(review / "coverage_gaps.csv")
        self.candidates = _csv(review / "cases_candidates.csv")
        # Review-queue candidates nobody has decided on yet: shown, never published.
        self.queue = [r for r in _csv(review / "queue.csv") if r.get("review_status") == "pending"]
        self.dc_events = _csv(dc_events)
        # "Checked, nothing found" rows (never published), by county.
        self.checks: dict[str, list[dict]] = {}
        for r in _csv(review / negative_checks.CHECKS_PATH.name):
            self.checks.setdefault(r.get("county_fips", "").strip().zfill(5), []).append(r)
        # None, not [], when left out, so the profile omits the section.
        self.local = _csv(local_knowledge_path()) if local else None
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


def _verification(r: dict) -> str:
    return r.get("verification") or "unverified"


def profile(d: Data, fips: str, name: str, st: str, *, site: str = "", lat=None, lon=None,
            radius: float = 0.0, notes: str = "", verified_only: bool = False) -> dict:
    neighbors = geo.neighbors(fips)
    origin = (lat, lon) if lat is not None and lon is not None else geo.centroid(fips)
    today = date.today().isoformat()
    shown: set[str] = set()

    def take(rows, test):
        out = [r for r in rows if test(r)]
        shown.update(r["id"] for r in out)
        return out

    # --verified-only: restrictions not verified against the instrument are
    # left out of the county and adjacent sections, and counted.
    left_out: dict[str, set[str]] = {"located": set(), "unverified": set()}

    def keep(r: dict) -> bool:
        v = _verification(r)
        if verified_only and v != "verified":
            left_out.setdefault(v, set()).add(r.get("instrument_id") or r["id"])
            return False
        return True

    here = {"restrictions": [r for r in take(d.restrictions, lambda r: fips in fips_set(r)) if keep(r)],
            "contested_projects": take(d.projects, lambda r: fips in fips_set(r))}
    local = None if d.local is None else [r for r in d.local if r["county_fips"].strip().zfill(5) == fips]
    pending = pending_for(d, fips, name, st)
    queued = {id(r) for r in pending}
    near = {}
    for nb in neighbors:
        rs = [r for r in take(d.restrictions, lambda r, nb=nb: nb in fips_set(r) and r["id"] not in shown)
              if keep(r)]
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
    # One case linked to two records is one case row per record; list it once.
    cases = list({(c["case_name"], c["court"], c.get("docket_number", "")): c
                  for c in d.cases if c.get("source_record_id") in linked}.values())

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
    # A promoted candidate is a published case (listed under Cases), not held back.
    candidates = [r for r in d.candidates if r.get("review_status") != "promoted"
                  and (r.get("source_record_id") in linked | held_ids
                  or names_county(r, "project_name") or phrase.search(r.get("litigation_context", ""))
                  and r.get("state", "").upper() == st)]

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

    def checked(f: str, scope: str) -> list[dict]:
        return sorted((c for c in d.checks.get(f, []) if negative_checks.covers(c, scope)),
                      key=lambda c: c.get("checked_on", ""), reverse=True)

    checks = {"restrictions": [] if here["restrictions"] else checked(fips, "restrictions"),
              "projects": [] if here["contested_projects"] else checked(fips, "projects")}
    neighbor_checks = {nb: sorted(d.checks[nb], key=lambda c: c.get("checked_on", ""), reverse=True)
                       for nb in neighbors if nb not in near and d.checks.get(nb)}
    for c in checks["restrictions"] + checks["projects"]:
        if negative_checks.is_stale(c):
            flags.append(f"The negative check of {c['checked_on']} is more than 12 months old (stale); "
                         "search again before relying on it")

    framework = state_policies.framework(getattr(d, "policies", []), st)
    held_policies = [] if verified_only else [r for r in getattr(d, "policies_held", []) if r.get("state") == st]
    standards, standards_left_out = local_standards(d, fips, neighbors, verified_only)

    flags = list(dict.fromkeys(flags))  # a flag raised per technology row of one instrument shows once
    return {"site": site or f"{name}, {st}", "notes": notes, "state": st, "county": name, "fips": fips,
            "neighbors": [{"fips": n, "name": geo.name(n), "state": state_of(d, n)} for n in neighbors],
            "in_county": here, "local_knowledge": local, "adjacent": near, "within_radius": radius_rows, "radius_mi": radius,
            "cases": cases, "not_published": {"held_back": held, "coverage_gaps": gaps,
                                              "quarantined": quarantined, "case_candidates": candidates,
                                              "pending_review": pending},
            "text_mentions": mentions, "flags": flags, "state_context": context,
            "data_center_activity": dc_activity(d, fips, neighbors),
            "verified_only": verified_only, "negative_checks": checks, "neighbor_checks": neighbor_checks,
            "left_out": {k: len(v) for k, v in left_out.items()},
            "state_framework": framework, "state_framework_held": held_policies,
            "state_framework_held_left_out": (sum(1 for r in getattr(d, "policies_held", []) if r.get("state") == st)
                                              if verified_only else 0),
            "local_standards": standards, "local_standards_left_out": standards_left_out}


def local_standards(d: Data, fips: str, neighbors: list[str], verified_only: bool) -> tuple[dict, int]:
    """{county fips: [siting_standards rows]} for the county and each neighbor
    with any, and how many unverified rows --verified-only left out."""
    out: dict[str, list[dict]] = {}
    left = 0
    for f in [fips, *neighbors]:
        rows = [r for r in getattr(d, "standards", []) if f in fips_set(r)]
        if verified_only:
            left += sum(1 for r in rows if r.get("verification") != "verified")
            rows = [r for r in rows if r.get("verification") == "verified"]
        if rows:
            out[f] = rows
    return out, left


def dc_activity(d: Data, fips: str, neighbors: list[str]) -> dict[str, list[dict]]:
    """data-center-map events in the county and in each neighbor, newest first."""
    out: dict[str, list[dict]] = {}
    for f in [fips, *neighbors]:
        rows = [e for e in getattr(d, "dc_events", []) if f in fips_set({"county_fips": e.get("county_fips")})]
        if rows:
            out[f] = sorted(rows, key=lambda e: e.get("date", ""), reverse=True)
    return out


DC_EVIDENCE_WORDS = {"verified": "verified: a source is the instrument or official minutes",
                     "reported": "reported"}


def _dc_lines(events: list[dict], indent: str = "") -> list[str]:
    out = []
    for e in events:
        urls = [u.strip() for u in (e.get("source_urls") or "").split(";") if u.strip()]
        out.append(f"{indent}- {e.get('date') or 'date n/a'}, {e.get('event_type') or 'type n/a'}, "
                   f"status {e.get('status') or 'n/a'} ({DC_EVIDENCE_WORDS[evidence_label(urls)]}): "
                   f"{e.get('summary')}")
        groups = f" Groups: {e['opposition_groups']}." if e.get("opposition_groups") else ""
        out.append(f"{indent}  Sources: {'; '.join(urls) or 'none'}.{groups} From data-center-map, "
                   f"{e.get('dc_row_ref')}")
    return out


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


# The evidence standard in plain words (classify.verification).
VERIFICATION_WORDS = {
    "restrictions": {
        "verified": "verified against the instrument or the minutes that adopted it",
        "located": "instrument located but not yet read, so not verified",
        "unverified": "not verified: no instrument or minutes read, only a news article or compiled tracker",
    },
    "contested_projects": {
        "verified": "verified: backed by a news article or court record that was read",
        "unverified": "not verified: rests on a compiled report or tracker only",
    },
}


def verification_words(entity: str, r: dict) -> str:
    return VERIFICATION_WORDS[entity].get(_verification(r), VERIFICATION_WORDS[entity]["unverified"])


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
                   f"scope {r.get('scope', '')}; {verification_words('restrictions', r)}")
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
                   f"finality {r.get('finality_evidence')}; evidence {r['evidence_level']}; "
                   f"{verification_words('contested_projects', r)}")
        out.append(f"{indent}  {r['description'][:280]}")
        if r.get("resolution_url"):
            out.append(f"{indent}  Outcome source: " + _seen(r["resolution_url"], r.get("resolution_access", ""),
                                                            r.get("resolution_archived_url", "")))
        if r.get("opposition_groups"):
            out.append(f"{indent}  Groups: {_groups(r.get('opposition_groups'), r.get('group_sources'))}")
        out.append(f"{indent}  {_source_line(r)}")
    return out


def _groups(names: str, sources: str) -> str:
    """'A, B (sources: url1; url2)': the group names on a record and the
    sources that name them."""
    gs = [g.strip() for g in (names or "").split(";") if g.strip()]
    us = [u.strip() for u in (sources or "").split(";") if u.strip()]
    return ", ".join(gs) + (f" (sources: {'; '.join(us)})" if us else "")


def groups_nearby(p: dict) -> list[dict]:
    """Every sourced group named on a record the profile shows, once each:
    name, where (county or neighbor), and its sources."""
    seen: dict[str, dict] = {}
    blocks = [("in the county", p["in_county"]["contested_projects"])]
    blocks += [(f"{g['name']}, {g['state']}", g["contested_projects"]) for g in p["adjacent"].values()]
    blocks += [("within the radius", [r for r in p["within_radius"] if r["id"].startswith("con_")])]
    for f, events in (p.get("data_center_activity") or {}).items():
        where_ = "in the county" if f == p["fips"] else f"{geo.name(f)} ({f})"
        blocks.append((f"{where_}, data center activity",
                       [{"opposition_groups": e.get("opposition_groups"), "group_sources": e.get("source_urls")}
                        for e in events]))
    for where_, rows in blocks:
        for r in rows:
            us = [u.strip() for u in (r.get("group_sources") or "").split(";") if u.strip()]
            for g in [g.strip() for g in (r.get("opposition_groups") or "").split(";")
                      if g.strip() and not group_registry.is_generic(g)]:
                e = seen.setdefault(group_registry.key(g), {"name": g, "where": [], "sources": []})
                if where_ not in e["where"]:
                    e["where"].append(where_)
                e["sources"] += [u for u in us if u not in e["sources"]]
    return list(seen.values())


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


POLICY_WORDS = {
    "siting_authority": "Who decides", "local_preemption": "State preemption of local rules",
    "local_opt_out": "Local opt-out power", "state_setback_standard": "State setback standard",
    "state_moratorium": "State moratorium or ban", "other": "Other state rule",
}
WHO_WORDS = {"state_board": "a state board", "local_government": "local government",
             "hybrid": "state and local government (hybrid)"}


def _threshold(value: str) -> str:
    parts = [p.split(":") for p in (value or "").split(";") if ":" in p]
    return ", ".join(f"{t.replace('_', ' ')} {mw} MW" for t, mw in parts)


def framework_lines(p: dict) -> list[str]:
    out = []
    for r in p.get("state_framework") or []:
        head = POLICY_WORDS.get(r["policy_type"], r["policy_type"])
        who = ""
        if r.get("who_decides"):
            who = WHO_WORDS.get(r["who_decides"], r["who_decides"])
            if r.get("state_body"):
                who += f" ({r['state_body']})"
            if r.get("threshold_mw"):
                who += f", threshold {_threshold(r['threshold_mw'])}"
            who += ". "
        out.append(f"- **{head}** ({r.get('technology', '').replace(';', ', ')}): {who}{r.get('summary', '')}")
        out.append(f"  {r.get('statute_citation') or 'statute not cited'}, {r.get('source_url', '')}: verified "
                   f"against the statute ({r.get('reviewer', 'reviewer not named')}, {r.get('reviewed_on', '')}, "
                   f"{ACCESS_LABEL.get(r.get('review_access', ''), r.get('review_access', ''))})"
                   + (f". Amendments: {r['amendments_note']}" if r.get("amendments_note") else ""))
    for r in p.get("state_framework_held") or []:
        out.append(f"- Not verified, held for review: {POLICY_WORDS.get(r['policy_type'], r['policy_type'])} "
                   f"({r.get('statute_citation') or 'no citation'}): {r.get('reason')}")
    return out


QUALITATIVE = re.compile(r"Districts|Decommissioning|Lighting|Signage|Color|Soil|Climbing|Repowering|Screening|"
                         r"Fencing|Glare|Visual", re.I)


def _feature(r: dict) -> str:
    if QUALITATIVE.search(r.get("feature", "")) or not r.get("value"):
        return r.get("feature", "")
    extra = f", at least {r['min_setback_ft']} ft" if r.get("min_setback_ft") else ""
    return f"{r['feature']} {r['value']} {r.get('units', '')}".strip() + extra


def standards_lines(p: dict) -> list[str]:
    out = []
    for f, rows in (p.get("local_standards") or {}).items():
        where = "In the county" if f == p["fips"] else f"{geo.name(f)} ({f})"
        groups: dict[tuple[str, str, str], list[dict]] = {}
        for r in rows:
            groups.setdefault((r["jurisdiction"], r["jurisdiction_type"], r["technology"]), []).append(r)
        out.append(f"- {where}:")
        for (jur, jtype, tech), rs in sorted(groups.items()):
            rs.sort(key=lambda r: (r.get("restricting") != "yes", r["feature"]))
            unverified = sum(1 for r in rs if r.get("verification") != "verified")
            label = ("all unverified: NREL's reading, not checked against the ordinance" if unverified == len(rs)
                     else f"{len(rs) - unverified} verified against the ordinance, {unverified} unverified")
            year = sorted({r["ordinance_year"] for r in rs if r.get("ordinance_year")})
            out.append(f"  - **{jur}** ({jtype}, {tech}{', ordinance year ' + '/'.join(year) if year else ''}; "
                       f"{label}): " + "; ".join(_feature(r) for r in rs))
            urls = sorted({u for r in rs for u in (r.get("ordinance_url") or "").split()})
            if urls:
                out.append(f"    Ordinance as cited by NREL: {'; '.join(urls[:3])}"
                           + (f"; and {len(urls) - 3} more" if len(urls) > 3 else ""))
    return out


NREL_ATTRIBUTION = ("Source: NREL, U.S. Wind and U.S. Solar Siting Regulation and Zoning Ordinances (2025), "
                    "doi.org/10.25984/3363758 and doi.org/10.25984/3363739, licensed CC BY 4.0. NREL compiled "
                    "them with large language models and asks that they be validated.")


def checked_line(c: dict) -> str:
    """'Checked <sources> on <date>: none found', flagged when stale."""
    srcs = "; ".join(negative_checks.sources(c))
    stale = " (stale: more than 12 months old)" if negative_checks.is_stale(c) else ""
    return f"Checked {srcs} on {c.get('checked_on')}: none found{stale}"


def record_request(fips: str, today: str | None = None) -> None:
    """Append the county code and today's date to PROFILE_REQUESTS, once per
    county per day. Nothing about who asked or why."""
    today = today or date.today().isoformat()
    if any(r.get("county_fips") == fips and r.get("date") == today for r in _csv(PROFILE_REQUESTS)):
        return
    new = not PROFILE_REQUESTS.exists()
    with open(PROFILE_REQUESTS, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=negative_checks.REQUEST_FIELDS, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerow({"county_fips": fips, "date": today})


def render(p: dict) -> str:
    L = [f"## {p['site']}", "",
         f"{p['county']}, {p['state']} (FIPS {p['fips']}). Data as of {p['state_context']['data_as_of']}.", ""]
    if p["notes"]:
        L += [f"Local knowledge supplied: {p['notes']}", ""]
    L.append(f"### State framework ({p['state']})")
    fl = framework_lines(p)
    L += fl or [f"- No state siting law row is published for {p['state']} yet."]
    if p.get("state_framework_held_left_out"):
        L.append(f"- Verified only: {p['state_framework_held_left_out']} row(s) still held for review were left out.")
    L.append("")
    here = p["in_county"]
    if p.get("verified_only"):
        lo = p.get("left_out", {})
        n = sum(lo.values())
        L += [f"Verified only: {n} restriction instrument(s) not verified against the instrument were left "
              f"out of the county and adjacent sections ({lo.get('located', 0)} located but not yet read, "
              f"{lo.get('unverified', 0)} unverified).", ""]
    L.append(f"### In the county: {len(_instruments(here['restrictions']))} restriction instrument(s), "
             f"{len(here['contested_projects'])} contested project(s)")
    L += _restriction_lines(here["restrictions"]) + _project_lines(here["contested_projects"])
    nc = p.get("negative_checks") or {}
    for scope, entity in (("restrictions", "restrictions"), ("projects", "contested_projects")):
        if not here[entity]:
            L += [f"- {scope.capitalize()}: {checked_line(c)}" for c in nc.get(scope, [])[:1]]
    if not here["restrictions"] and not here["contested_projects"] and not any(nc.values()):
        L.append("- Nothing published for this county.")
    L.append("")
    if p["local_knowledge"] is not None:
        L.append(f"### Local knowledge on file: {len(p['local_knowledge'])} item(s)")
        L.append("From the local-knowledge file outside the repository, as entered. Not checked "
                 "against a source and not part of the published data.")
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
    for nb, cs in (p.get("neighbor_checks") or {}).items():
        L.append(f"- {geo.name(nb)} ({nb}), nothing published: {checked_line(cs[0])}")
    for nb, g in p["adjacent"].items():
        L.append(f"- {g['name']}, {g['state']} ({nb})")
        L += _restriction_lines(g["restrictions"], "  ") + _project_lines(g["contested_projects"], "  ")
        L += _pending_lines(g.get("pending", []), "  ", short=True)
    L.append("")
    ls = p.get("local_standards") or {}
    n_here = len(ls.get(p["fips"], []))
    L.append(f"### Local siting standards (NREL): {n_here} feature(s) in the county, "
             f"{sum(len(v) for k, v in ls.items() if k != p['fips'])} in adjacent counties")
    L.append(NREL_ATTRIBUTION)
    L += standards_lines(p) or ["- None recorded for the county or its neighbors."]
    if p.get("verified_only") and p.get("local_standards_left_out"):
        L.append(f"- Verified only: {p['local_standards_left_out']} unverified feature(s) were left out.")
    L.append("")
    if p["radius_mi"]:
        L.append(f"### Within {p['radius_mi']:g} miles (beyond the county and its neighbors)")
        rs = [r for r in p["within_radius"] if r["id"].startswith("res_")]
        ps = [r for r in p["within_radius"] if r["id"].startswith("con_")]
        L += _restriction_lines(rs) + _project_lines(ps) or ["- Nothing."]
        L.append("")
    dca = p.get("data_center_activity") or {}
    L.append(f"### Data center activity (data-center-map): {sum(len(v) for v in dca.values())} event(s)")
    L.append("Local data center events the same governments acted on, from pricephillips/data-center-map. "
             "Not renewable restrictions and not counted above.")
    for f, events in dca.items():
        L.append(f"- {'In the county' if f == p['fips'] else geo.name(f) + ' (' + f + ')'}:")
        L += _dc_lines(events, "  ")
    if not dca:
        L.append("- None recorded for the county or its neighbors.")
    L.append("")
    nearby = groups_nearby(p)
    def few(us: list[str]) -> str:
        return "; ".join(us[:3]) + (f"; and {len(us) - 3} more on the record" if len(us) > 3 else "")

    L.append("Groups active nearby: " + ("; ".join(
        f"{g['name']} ({', '.join(g['where'])}; sources: {few(g['sources'])})" for g in nearby)
        if nearby else "none with a source on the records shown."))
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
         "Held back | Flags | Siting standards here | State framework rows |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for p in profiles:
        h = p["in_county"]
        inst = _instruments(h["restrictions"])
        severe = sum(1 for g in inst if g[0]["severity_score"] in ("3", "4"))
        adj = sum(len(g["restrictions"]) + len(g["contested_projects"]) for g in p["adjacent"].values())
        held = sum(len(v) for v in p["not_published"].values())
        L.append(f"| {p['site']} | {p['county']}, {p['state']} ({p['fips']}) | {len(inst)} | {severe} | "
                 f"{len(h['contested_projects'])} | {adj} | {held} | {len(p['flags'])} | "
                 f"{len((p.get('local_standards') or {}).get(p['fips'], []))} | "
                 f"{len(p.get('state_framework') or [])} |")
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
    a.add_argument("--verified-only", action="store_true",
                   help="leave out restrictions not verified against the instrument (in the county and "
                        "adjacent sections) and say how many were left out")
    a.add_argument("--no-local", action="store_true",
                   help="omit local knowledge ($RO_LOCAL_KNOWLEDGE) and do not read it")
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
        record_request(fips)
        lat = float(s["lat"]) if s.get("lat") else None
        lon = float(s["lon"]) if s.get("lon") else None
        profiles.append(profile(d, fips, name, st, site=s.get("name", ""), lat=lat, lon=lon,
                                radius=x.radius, notes=s.get("notes", ""), verified_only=x.verified_only))
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
