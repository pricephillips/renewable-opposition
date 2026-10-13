"""County report: everything the repo records about one county, in the shape
of pricephillips/data-center-map's location report. No scoring and no
prediction.

The report follows config/county_report.json: a title block, then these
sections in order, each with a lead sentence, a table whose rows carry their
own source, and a plain sentence where it is empty. Terms are defined in
parentheses on their first use and bare afterwards.

  Summary               what is on record, in sentences: restriction
                        instruments and how many are verified, contested
                        projects, cases, adjacent counties, who decides
                        siting in the state, what is held back, and any
                        notes or local reports supplied.
  State siting law      data/processed/state_policies.csv for the state: who
                        decides and above what size, preemption, opt-out
                        powers, setbacks and other rules, each verified
                        against the statute; rows still held for review
                        (state_policies_held.csv) shown as not verified.
  Restrictions on record
                        published instruments whose county_fips_all includes
                        the county (county-level instruments, multi-county
                        projects, town-level instruments placed by
                        coordinates or the Census place index), one row per
                        instrument with its severity and basis, status,
                        verification under the evidence standard, and source
                        with how it was seen.
  Contested projects on record
                        the same for project-level opposition, with outcome,
                        finality, groups, the federal plant inventory where
                        matched, and the outcome source.
  Cases linked to those records
                        litigation linked to the records shown, once each.
  Adjacent counties     one row per county sharing a boundary, across state
                        lines (data/geo/counties_2024.topojson): counts, and
                        its newest negative check when nothing is published;
                        then the records themselves and each pending
                        review-queue candidate, one line each.
  Local siting standards
                        NREL's ordinance features for the county and its
                        neighbors (data/processed/siting_standards.csv), one
                        row per jurisdiction and technology, unverified until
                        a reviewer checks it against the ordinance.
  Within the radius     optional (--radius): records outside the county and
                        its neighbors within N miles of the site.
  Data center activity  data-center-map events for the county and its
                        neighbors: context only, never counted.
  Opposition groups active nearby
                        every sourced group on a record shown.
  Held back from publication
                        rows the build set aside that name the county: Sabin
                        rows held back, QC quarantine, coverage gaps, case
                        candidates, and pending review-queue candidates.
  Named in records placed elsewhere
                        optional: records placed in another county whose text
                        names this one.
  Flags                 moratoria past their end date, pending instruments,
                        report-only evidence, same-name counties, evidence
                        still to read, stale checks, and a state with no
                        contested-project coverage.
  Sources and method    the descriptive notice, the evidence standard, the
                        commit, every repository file read with the first
                        twelve characters of its hash, and the state context.

Local reports (the local-knowledge file, $RO_LOCAL_KNOWLEDGE, default
~/.renewable-opposition/local_knowledge.csv) have no section of their own.
Each row prints inside the section its topic concerns (restriction, project
or litigation; sentiment and other in the Summary), labelled reported and
not verified. A county with none says nothing about them. The file is
hand-edited, never published and kept outside the repository; --no-local
leaves it out and does not read it, and the report never names it.

Usage
  python scripts/site_profile.py --state KS --county Cherokee
  python scripts/site_profile.py --fips 20021 --radius 50
  python scripts/site_profile.py --sites sites.csv --out deliverables/county_reports/sites.md
  python scripts/site_profile.py --state KS --county Cherokee --no-local
  python scripts/site_profile.py --fips 19113 --verified-only
      sites.csv columns: name, state, county, fips (any one of county or fips),
      optional lat, lon, notes. --json writes structured output instead.

Every restriction row says, in plain words, how it stands under the evidence
standard (classify.verification): verified against the instrument or its
minutes, instrument located but not yet read, or not verified. Every
contested-project row says whether a news article or court record that was
read backs it. --verified-only leaves out restrictions that are not verified
from the county and adjacent sections and states how many it left out; it
also leaves out siting standards that are not verified and state law rows
still held for review, and counts them.

An empty section prints the newest matching row of
data/review/negative_checks.csv instead of a bare "nothing on record":
"Checked <sources> on <date>: none found", flagged stale after 12 months.
Every county a report is run for is recorded in
data/review/profile_requests.csv (county code and date only), which feeds the
build's negative-check worklist.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import math
import os
import re
import subprocess
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
        # Every repository file the profile reads, for the report's Sources
        # and method section. The local-knowledge file is never listed.
        self.root = root or ROOT
        self.files: list[Path] = []

        def read(path: Path, kind=_csv, default=None):
            if path.exists():
                self.files.append(path)
            return kind(path) if default is None else kind(path, default)

        self.policies = read(processed / "state_policies.csv")
        self.policies_held = read(processed / state_policies.HELD_PATH.name)
        self.standards = read(processed / "siting_standards.csv")
        self.restrictions = read(processed / "restrictions.csv")
        self.projects = read(processed / "contested_projects.csv")
        self.cases = read(processed / "cases.csv")
        self.quarantine = read(processed / "quarantine.json", _json, [])
        self.held = read(review / "sabin_restrictions_review.csv")
        self.gaps = read(review / "coverage_gaps.csv")
        self.candidates = read(review / "cases_candidates.csv")
        # Review-queue candidates nobody has decided on yet: shown, never published.
        self.queue = [r for r in read(review / "queue.csv") if r.get("review_status") == "pending"]
        self.dc_events = read(dc_events)
        # "Checked, nothing found" rows (never published), by county.
        self.checks: dict[str, list[dict]] = {}
        for r in negative_checks.counted(read(review / negative_checks.CHECKS_PATH.name)):
            self.checks.setdefault(r.get("county_fips", "").strip().zfill(5), []).append(r)
        # None, not [], when left out, so nothing about local reports is read or printed.
        self.local = _csv(local_knowledge_path()) if local else None
        raw = read(lookup, _json, {})
        self.lookup = {k.lower(): str(v) for k, v in raw.items() if not k.startswith("_")}
        self.places = {k: v for k, v in read(place_index, _json, {}).items() if not k.startswith("_")}
        if geo.TOPOJSON.exists():
            self.files.append(geo.TOPOJSON)
        snaps = read(snapshots)
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
    concerns_of = {r["source_record_id"]: _label(r) for g in (here, *near.values())
                   for k in ("restrictions", "contested_projects") for r in g[k] if r.get("source_record_id")}
    for c in cases:
        c["_concerns"] = concerns_of.get(c.get("source_record_id"), "")
    report = {"title": f"{site or name + ', ' + STATE_NAMES.get(st, st)}: county report", "fips": fips,
              "county_name": name, "state_name": STATE_NAMES.get(st, st), "as_of": d.as_of,
              "generated": today, "commit": commit_label(d.files), "files": source_files(d)}
    return {"site": site or f"{name}, {st}", "notes": notes, "state": st, "county": name, "fips": fips,
            "report": report,
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


def source_files(d: Data) -> list[dict]:
    """Each repository file the profile read, with the first twelve characters
    of its SHA-256, as the report's Sources and method section prints them."""
    out = []
    for path in d.files:
        try:
            rel = str(path.relative_to(d.root))
        except ValueError:
            rel = path.name
        out.append({"path": rel, "sha": hashlib.sha256(path.read_bytes()).hexdigest()[:12]})
    return out


def commit_label(files: list[Path]) -> str:
    """The repository commit the report was built at, noting uncommitted
    changes to the files it read; 'not available' outside a git checkout."""
    try:
        run = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True,  # noqa: E731
                                        check=True).stdout.strip()
        sha = run("rev-parse", "--short=12", "HEAD")
        inside = [str(f) for f in files if ROOT in f.parents]
        dirty = run("status", "--porcelain", "--", *inside) if inside else ""
        return sha + (" (with uncommitted changes to the files read)" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "not available"


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
#
# The report's shape follows pricephillips/data-center-map's location report
# (templates/manifest.json, configs/definitions.json, scripts/
# build_report_templates.py): a title block, a Summary in plain sentences,
# one section per entity with a lead sentence and a table, each table row
# carrying its own source, a plain sentence where a section is empty, and a
# closing "Sources and method" section naming the files read, their hashes
# and the commit. Terms are defined on first use from config/county_report.json.

REPORT_CONFIG = ROOT / "config" / "county_report.json"
DIGIT = re.compile(r"\d")
ENTITY_TOPICS = {"restrictions": ("restriction",), "projects": ("project",), "cases": ("litigation",)}


def load_report_config(path: Path = REPORT_CONFIG) -> dict:
    """Section order, terms and notices. A definition or notice with a digit
    is refused: every digit in a report comes from a record."""
    cfg = json.loads(path.read_text(encoding="utf-8"))
    for key, t in cfg["terms"].items():
        if DIGIT.search(t["term"]) or DIGIT.search(t["definition"]):
            raise SystemExit(f"{path.name}: term {key} carries a digit; numbers come from the records")
    for key, text in cfg.get("notices", {}).items():
        if DIGIT.search(text):
            raise SystemExit(f"{path.name}: notice {key} carries a digit")
    return cfg


class Definer:
    """define(key): 'term (definition)' the first time, 'term' after. Sections
    render in the configured order, so "first" follows that order."""

    def __init__(self, cfg: dict) -> None:
        self.terms = cfg["terms"]
        self.used: list[str] = []

    def __call__(self, key: str, n: int | None = None) -> str:
        """With n, the term is pluralised for that count, before the definition."""
        t = self.terms[key]
        term = t["term"] + ("s" if n is not None and n != 1 else "")
        if key in self.used:
            return term
        self.used.append(key)
        return f"{term} ({t['definition']})"


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


def _source_text(r: dict) -> str:
    """'<primary> (access). Compiled from <name>, <url>', or the compiled
    source alone when no primary source is attached."""
    compiled = _compiled(r)
    if r.get("primary_source_url"):
        text = _seen(r["primary_source_url"], r.get("primary_source_access", ""),
                     r.get("primary_source_archived_url", ""))
        if r.get("primary_source_verdict") == "contradicts":
            text += ", which a reviewer reads as contradicting the record"
        return text + (f". Compiled from {compiled}" if compiled else "")
    if compiled:
        return f"No primary source attached. Compiled from {compiled}"
    return r.get("source_url", "")


def _placed(r: dict) -> str:
    how = r.get("county_fips_method") or ""
    if not how or how == "name":
        return ""
    if how == "override" and r.get("placement_access"):
        return f"; placed by override ({ACCESS_LABEL.get(r['placement_access'], r['placement_access'])})"
    return f"; placed by {how}"


def _cell(v) -> str:
    return re.sub(r"\s+", " ", str(v if v is not None else "")).replace("|", "\\|").strip()


def _table(headers: list[str], rows: list[list]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows]
    return out


RESTRICTION_HEADERS = ["Date", "Jurisdiction", "Instrument", "Technology", "Severity", "Status",
                       "Verification", "What it does", "Source"]
PROJECT_HEADERS = ["Date", "Project", "Technology", "Outcome", "Severity", "Verification", "What happened",
                   "Groups", "Source"]


def _restriction_row(g: list[dict]) -> list[str]:
    r = g[0]
    techs = ", ".join(sorted({x["technology"] for x in g}))
    when = r.get("date_enacted_iso") or r.get("date_text") or "date n/a"
    basis = r.get("severity_basis") or (
        "Moratorium Nation rule: active or extended moratorium scores 4, pending 2"
        if (r.get("instrument_id") or "").startswith("mn:") else "n/a")
    return [when, f"{r['jurisdiction']} ({r['jurisdiction_type']}{_placed(r)})",
            f"{r['restriction_type']}; scope {r.get('scope') or 'n/a'}", techs,
            f"{r['severity_score']} ({basis})", r.get("status") or "n/a",
            f"{verification_words('restrictions', r)}; evidence {r['evidence_level']}",
            r["description"][:280], _source_text(r)]


def _restriction_rows(rows: list[dict], prefix=None) -> list[list[str]]:
    return [([prefix(g[0])] if prefix else []) + _restriction_row(g) for g in _instruments(rows)]


def _finality(r: dict) -> str:
    return (r.get("finality_evidence") or "none").split(":")[0]


def _project_row(r: dict) -> list[str]:
    tech = r["technology"] + (f", {r['capacity_mw']} MW" if r.get("capacity_mw") else "")
    what = r["description"][:280]
    if r.get("facility_match"):
        what += f" Federal plant inventory: {r.get('facility_status') or 'status n/a'}."
        if r.get("facility_conflict"):
            what += f" Contradicts the published outcome: {r['facility_conflict']}."
    source = _source_text(r)
    if r.get("resolution_url"):
        source = ("Outcome: " + _seen(r["resolution_url"], r.get("resolution_access", ""),
                                      r.get("resolution_archived_url", "")) + ". " + source)
    return [r.get("event_date_text") or "date n/a", f"{r['project_name']} ({r.get('county') or 'county n/a'}{_placed(r)})",
            tech, f"{r['outcome']}; litigation {r.get('has_litigation') or 'n/a'}; finality {_finality(r)}",
            r["severity_score"], f"{verification_words('contested_projects', r)}; evidence {r['evidence_level']}",
            what, _groups(r.get("opposition_groups"), r.get("group_sources")) or "none named", source]


def _project_rows(rows: list[dict], prefix=None) -> list[list[str]]:
    return [([prefix(r)] if prefix else []) + _project_row(r) for r in rows]


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


def _who_decides(p: dict) -> str:
    """One sentence on who sites projects in the state, from the siting_authority rows."""
    rows = [r for r in p.get("state_framework") or [] if r.get("policy_type") == "siting_authority"]
    if not rows:
        return f"No state siting law row is published for {p['state']} yet."
    parts = []
    for r in rows:
        who = WHO_WORDS.get(r.get("who_decides"), r.get("who_decides") or "not recorded")
        if r.get("state_body"):
            who += f" ({r['state_body']})"
        if r.get("threshold_mw"):
            who += f", above {_threshold(r['threshold_mw'])}"
        parts.append(f"{who} for {r.get('technology', '').replace(';', ', ') or 'all technologies'}")
    return "Who decides siting in the state: " + "; ".join(parts) + "."


QUALITATIVE = re.compile(r"Districts|Decommissioning|Lighting|Signage|Color|Soil|Climbing|Repowering|Screening|"
                         r"Fencing|Glare|Visual", re.I)


def _feature(r: dict) -> str:
    if QUALITATIVE.search(r.get("feature", "")) or not r.get("value"):
        return r.get("feature", "")
    extra = f", at least {r['min_setback_ft']} ft" if r.get("min_setback_ft") else ""
    return f"{r['feature']} {r['value']} {r.get('units', '')}".strip() + extra


def standards_rows(p: dict) -> list[list[str]]:
    out = []
    for f, rows in (p.get("local_standards") or {}).items():
        where = "This county" if f == p["fips"] else f"{geo.name(f)} ({f})"
        groups: dict[tuple[str, str, str], list[dict]] = {}
        for r in rows:
            groups.setdefault((r["jurisdiction"], r["jurisdiction_type"], r["technology"]), []).append(r)
        for (jur, jtype, tech), rs in sorted(groups.items()):
            rs.sort(key=lambda r: (r.get("restricting") != "yes", r["feature"]))
            unverified = sum(1 for r in rs if r.get("verification") != "verified")
            label = ("all unverified: NREL's reading, not checked against the ordinance" if unverified == len(rs)
                     else f"{len(rs) - unverified} verified against the ordinance, {unverified} unverified")
            year = "/".join(sorted({r["ordinance_year"] for r in rs if r.get("ordinance_year")})) or "n/a"
            urls = sorted({u for r in rs for u in (r.get("ordinance_url") or "").split()})
            cited = "; ".join(urls[:3]) + (f"; and {len(urls) - 3} more" if len(urls) > 3 else "")
            out.append([where, f"{jur} ({jtype})", tech, year, label, "; ".join(_feature(r) for r in rs),
                        cited or "not cited"])
    return out


NREL_ATTRIBUTION = ("Source: NREL, U.S. Wind and U.S. Solar Siting Regulation and Zoning Ordinances (2025), "
                    "doi.org/10.25984/3363758 and doi.org/10.25984/3363739, licensed CC BY 4.0. NREL compiled "
                    "them with large language models and asks that they be validated.")

DC_EVIDENCE_WORDS = {"verified": "verified: a source is the instrument or official minutes",
                     "reported": "reported"}


def _dc_row(where: str, e: dict) -> list[str]:
    urls = [u.strip() for u in (e.get("source_urls") or "").split(";") if u.strip()]
    return [e.get("date") or "date n/a", where, e.get("event_type") or "type n/a", e.get("status") or "n/a",
            DC_EVIDENCE_WORDS[evidence_label(urls)], e.get("summary") or "", e.get("opposition_groups") or "",
            ("; ".join(urls) or "none") + f". From data-center-map, {e.get('dc_row_ref')}"]


def checked_line(c: dict) -> str:
    """'Checked <sources> on <date>: none found', with the check's evidence
    grade and the independence classes behind it, flagged when stale."""
    srcs = "; ".join(negative_checks.sources(c))
    stale = " (stale: more than 12 months old)" if negative_checks.is_stale(c) else ""
    classes = ", ".join(negative_checks.independence_classes(c))
    return (f"Checked {srcs} on {c.get('checked_on')}: none found{stale}. "
            f"Evidence grade {negative_checks.grade(c)} ({classes})")


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


# ── Local reports: inside the section each concerns, never a section of their own

def local_rows(p: dict, topics: tuple[str, ...] | None) -> list[dict]:
    """The county's local reports on these topics; topics None means every
    topic no entity section claims (sentiment, other, blank)."""
    claimed = {t for ts in ENTITY_TOPICS.values() for t in ts}
    rows = p.get("local_knowledge") or []
    if topics is None:
        return [r for r in rows if (r.get("topic") or "") not in claimed]
    return [r for r in rows if (r.get("topic") or "") in topics]


def _local_block(p: dict, define: Definer, topics: tuple[str, ...] | None) -> list[str]:
    rows = local_rows(p, topics)
    if not rows:
        return []
    out = ["", f"Reported locally, not verified and not published ({define('local_report')}):"]
    for r in rows:
        src = r.get("source_type") or "source not given"
        if r.get("source_note"):
            src += f", {r['source_note']}"
        out.append(f"- Reported, not verified ({r.get('topic') or 'no topic'}): {r['claim']} Source: {src}. "
                   f"Reported {r.get('date_reported') or 'undated'} by {r.get('reporter') or 'unnamed'}.")
    return out


# ── Sections ─────────────────────────────────────────────────────────────────

def _place(p: dict) -> str:
    return f"{p['county']}, {STATE_NAMES.get(p['state'], p['state'])}"


def _by_verification(rows: list[dict]) -> dict[str, int]:
    out: dict[str, set] = {"verified": set(), "located": set(), "unverified": set()}
    for r in rows:
        out.setdefault(_verification(r), set()).add(r.get("instrument_id") or r["id"])
    return {k: len(v) for k, v in out.items()}


def sec_summary(p: dict, define: Definer) -> list[str]:
    here, place = p["in_county"], _place(p)
    L = []
    inst = _instruments(here["restrictions"])
    nc = p.get("negative_checks") or {}
    if inst:
        v = _by_verification(here["restrictions"])
        severe = sum(1 for g in inst if g[0]["severity_score"] in ("3", "4"))
        L.append(f"{place} has {len(inst)} {define('restriction_instrument', len(inst))} on record: "
                 f"{v['verified']} verified against the instrument, {v['located']} located but not yet read, "
                 f"{v['unverified']} not verified. Instruments scoring 3 or 4 on the {define('severity')} scale: "
                 f"{severe}.")
    else:
        line = f"No {define('restriction_instrument')} is on record for {place}."
        if nc.get("restrictions"):
            c = nc["restrictions"][0]
            line += f" A {define('negative_check')} on {c.get('checked_on')} found none: {checked_line(c)}."
        else:
            line += " No one has recorded a search of the county's codes and minutes, so this is a gap in coverage."
        L.append(line)
    projects = here["contested_projects"]
    if projects:
        backed = sum(1 for r in projects if _verification(r) == "verified")
        L.append(f"{len(projects)} {define('contested_project', len(projects))} on record, {backed} backed by a news "
                 f"article or court record that was read. Cases linked to the records shown: {len(p['cases'])}.")
    else:
        line = f"No {define('contested_project')} is on record for {place}."
        if nc.get("projects"):
            c = nc["projects"][0]
            line += f" A {define('negative_check')} on {c.get('checked_on')} found none: {checked_line(c)}."
        L.append(line + f" Cases linked to the records shown: {len(p['cases'])}.")
    nbrs = p["neighbors"]
    adj = p["adjacent"]
    L.append(f"Adjacent counties: {len(nbrs)}. With a restriction instrument on record: "
             f"{sum(1 for g in adj.values() if g['restrictions'])}. With a contested project on record: "
             f"{sum(1 for g in adj.values() if g['contested_projects'])}. With a negative check and nothing on "
             f"record: {len(p.get('neighbor_checks') or {})}.")
    L.append(_who_decides(p))
    np_ = p["not_published"]
    held = sum(len(v) for v in np_.values())
    if held:
        L.append(f"Rows held back from publication that name the county: {held}, of which "
                 f"{len(np_.get('pending_review', []))} are {define('pending_candidate', 2)} (see Held back from "
                 "publication).")
    unread = [f for f in p["flags"] if f.startswith("Evidence still to read")]
    if unread:
        L.append(unread[0].split(":")[0] + ": " + unread[0].split(":", 1)[1].split("(")[0].strip() + ".")
    if p.get("verified_only"):
        lo = p.get("left_out", {})
        L.append(f"Verified only: {sum(lo.values())} restriction instrument(s) not verified against the instrument "
                 f"were left out of the county and adjacent sections ({lo.get('located', 0)} located but not yet "
                 f"read, {lo.get('unverified', 0)} unverified).")
    if p["notes"]:
        L.append(f"Notes supplied with the request: {p['notes']}")
    local = p.get("local_knowledge") or []
    if local:
        L.append(f"{len(local)} {define('local_report', len(local))} on file; each appears in the section it concerns, "
                 "labelled reported and not verified.")
    return L + _local_block(p, define, None)


def sec_framework(p: dict, define: Definer) -> list[str]:
    fl = framework_lines(p)
    L = ([f"The state's siting law for {p['state']} as recorded, each row verified against the statute unless "
          "marked held for review:"] + fl if fl
         else [f"No state siting law row is published for {p['state']} yet."])
    if p.get("state_framework_held_left_out"):
        L.append(f"Verified only: {p['state_framework_held_left_out']} row(s) still held for review were left out.")
    return L


def sec_restrictions(p: dict, define: Definer) -> list[str]:
    here, place = p["in_county"], _place(p)
    nc = (p.get("negative_checks") or {}).get("restrictions") or []
    if here["restrictions"]:
        L = [f"Each {define('restriction_instrument')} the published data places in {place}, with its "
             f"{define('severity')}, its {define('verification')} and its source:", ""]
        L += _table(RESTRICTION_HEADERS, _restriction_rows(here["restrictions"]))
    elif nc:
        L = [f"No {define('restriction_instrument')} is on record for {place}. {checked_line(nc[0])}."]
    else:
        L = [f"No {define('restriction_instrument')} is on record for {place}, and no {define('negative_check')} "
             "says that anyone looked."]
    return L + _local_block(p, define, ENTITY_TOPICS["restrictions"])


def sec_projects(p: dict, define: Definer) -> list[str]:
    here, place = p["in_county"], _place(p)
    nc = (p.get("negative_checks") or {}).get("projects") or []
    if here["contested_projects"]:
        L = [f"Each {define('contested_project')} the published data places in {place}, with its outcome, its "
             f"{define('severity')} (how hard opposition hit the project), its {define('verification')} and its "
             "source:", ""]
        L += _table(PROJECT_HEADERS, _project_rows(here["contested_projects"]))
    elif nc:
        L = [f"No {define('contested_project')} is on record for {place}. {checked_line(nc[0])}."]
    else:
        L = [f"No {define('contested_project')} is on record for {place}."]
    return L + _local_block(p, define, ENTITY_TOPICS["projects"])


def sec_cases(p: dict, define: Definer) -> list[str]:
    if p["cases"]:
        L = ["Court cases and formal proceedings linked to the records above, each with the record it concerns:",
             ""]
        L += _table(["Case", "Court", "Docket", "Status", "Evidence", "Concerns"],
                    [[c["case_name"], c["court"], c.get("docket_number") or "", c.get("case_status") or "status blank",
                      c["evidence_level"], c.get("_concerns") or c.get("source_record_id") or ""] for c in p["cases"]])
    else:
        L = ["No case is linked to the records above."]
    return L + _local_block(p, define, ENTITY_TOPICS["cases"])


def sec_neighbors(p: dict, define: Definer) -> list[str]:
    adj, checks = p["adjacent"], p.get("neighbor_checks") or {}
    L = [f"Counties that share a boundary with {p['county']}, across state lines:", ""]
    rows = []
    for n in p["neighbors"]:
        g = adj.get(n["fips"], {})
        c = checks.get(n["fips"])
        rows.append([n["name"], n["state"], n["fips"], len(_instruments(g.get("restrictions", []))),
                     len(g.get("contested_projects", [])), len(g.get("pending", [])),
                     checked_line(c[0]) if c else ""])
    L += _table(["County", "State", "FIPS", "Restriction instruments", "Contested projects", "Pending candidates",
                 "Checked, none found"], rows)
    rs, ps, pend = [], [], []
    for nb, g in adj.items():
        label = f"{g['name']}, {g['state']} ({nb})"
        rs += _restriction_rows(g["restrictions"], prefix=lambda r, label=label: label)
        ps += _project_rows(g["contested_projects"], prefix=lambda r, label=label: label)
        pend += [f"- {label}: " + line[2:] for line in _pending_lines(g.get("pending", []), short=True)]
    if rs:
        L += ["", "Restriction instruments in adjacent counties:", ""] + _table(["County"] + RESTRICTION_HEADERS, rs)
    if ps:
        L += ["", "Contested projects in adjacent counties:", ""] + _table(["County"] + PROJECT_HEADERS, ps)
    if pend:
        L += ["", f"Each {define('pending_candidate')} in an adjacent county, one line each:"] + pend
    if not adj and not checks:
        L += ["", "Nothing is published in any adjacent county, and no adjacent county has a negative check."]
    return L


def sec_standards(p: dict, define: Definer) -> list[str]:
    ls = p.get("local_standards") or {}
    n_here = len(ls.get(p["fips"], []))
    n_adj = sum(len(v) for k, v in ls.items() if k != p["fips"])
    L = [f"Each {define('siting_standard')} NREL records for the county and its neighbors: "
         f"{n_here} feature(s) in the county, {n_adj} in adjacent counties. {NREL_ATTRIBUTION}", ""]
    rows = standards_rows(p)
    L += _table(["County", "Jurisdiction", "Technology", "Ordinance year", "Verification", "Features",
                 "Ordinance as cited by NREL"], rows) if rows else ["None recorded for the county or its neighbors."]
    if p.get("verified_only") and p.get("local_standards_left_out"):
        L.append(f"Verified only: {p['local_standards_left_out']} unverified feature(s) were left out.")
    return L


def sec_radius(p: dict, define: Definer) -> list[str] | None:
    if not p["radius_mi"]:
        return None
    rs = [r for r in p["within_radius"] if r["id"].startswith("res_")]
    ps = [r for r in p["within_radius"] if r["id"].startswith("con_")]
    if not rs and not ps:
        return [f"Nothing within {p['radius_mi']:g} miles beyond the county and its neighbors."]
    L = [f"Records within {p['radius_mi']:g} miles of the site that the county and adjacent sections do not "
         "show, by distance:"]
    miles_of = lambda r: f"{r['_miles']} mi"  # noqa: E731
    if rs:
        L += ["", "Restriction instruments:", ""] + _table(["Distance"] + RESTRICTION_HEADERS,
                                                            _restriction_rows(rs, prefix=miles_of))
    if ps:
        L += ["", "Contested projects:", ""] + _table(["Distance"] + PROJECT_HEADERS, _project_rows(ps, prefix=miles_of))
    return L


def sec_data_centers(p: dict, define: Definer) -> list[str]:
    dca = p.get("data_center_activity") or {}
    n = sum(len(v) for v in dca.values())
    L = [f"Each {define('data_center_event')} the same governments acted on, from pricephillips/data-center-map: "
         f"{n} event(s). Not renewable restrictions and not counted above.", ""]
    rows = [_dc_row("This county" if f == p["fips"] else f"{geo.name(f)} ({f})", e)
            for f, events in dca.items() for e in events]
    L += _table(["Date", "County", "Event", "Status", "Evidence", "Summary", "Groups", "Sources"], rows) if rows \
        else ["None recorded for the county or its neighbors."]
    return L


def sec_groups(p: dict, define: Definer) -> list[str]:
    nearby = groups_nearby(p)

    def few(us: list[str]) -> str:
        return "; ".join(us[:3]) + (f"; and {len(us) - 3} more on the record" if len(us) > 3 else "")

    return ["Groups active nearby: " + ("; ".join(
        f"{g['name']} ({', '.join(g['where'])}; sources: {few(g['sources'])})" for g in nearby)
        if nearby else "none with a source on the records shown.")]


def sec_held(p: dict, define: Definer) -> list[str]:
    np_ = p["not_published"]
    L = []
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
    if not L:
        return ["Nothing is held back for this county."]
    return [f"Rows the build set aside that name the county. A {define('pending_candidate')} is listed here "
            "with its mechanisms and how its source was seen."] + L


def sec_mentions(p: dict, define: Definer) -> list[str] | None:
    if not p["text_mentions"]:
        return None
    L = ["Records placed in another county whose text names this one:"]
    for r in p["text_mentions"]:
        label = r.get("jurisdiction") or r.get("project_name")
        L.append(f"- {label} ({r['id']}, county_fips_all {r.get('county_fips_all') or 'blank'}): "
                 f"{r['description'][:200]}")
    return L


def sec_flags(p: dict, define: Definer) -> list[str]:
    return [f"- {f}" for f in p["flags"]] or ["None."]


def sec_sources(p: dict, define: Definer) -> list[str]:
    cfg = load_report_config()
    rpt, s = p["report"], p["state_context"]
    L = [cfg["notices"]["descriptive"] + " " + cfg["notices"]["empty"], "",
         cfg["notices"]["evidence"] + " Verification labels follow the evidence standard in README.md "
         "(Counting and verification).", "",
         f"Every figure in this report was read from the files below at commit {rpt['commit']}, with data as of "
         f"{rpt['as_of']}. Reports from local contacts are read from a file outside the repository and are not "
         "listed.", ""]
    L += _table(["File", "Hash (first twelve characters)"], [[f["path"], f["sha"]] for f in rpt["files"]])
    L += ["", f"State context ({p['state']}): {s['restriction_instruments']} restriction instruments "
          f"({s['severe_instruments']} severe), {s['contested_projects']} contested projects, {s['cases']} cases. "
          f"{s['unplaced_rows']} {p['state']} row(s) are unplaced (no county, town or coordinates "
          f"the build could match) and {s['ambiguous_rows']} are ambiguous (a town name shared by "
          "several counties, left unplaced rather than guessed)"
          + ("" if s["place_index"] else "; the Census place index is not built, so run "
             "scripts/build_place_index.py to place town-level records") + "."]
    return L


SECTIONS = {
    "summary": sec_summary, "framework": sec_framework, "restrictions": sec_restrictions,
    "projects": sec_projects, "cases": sec_cases, "neighbors": sec_neighbors, "standards": sec_standards,
    "radius": sec_radius, "data_centers": sec_data_centers, "groups": sec_groups, "held": sec_held,
    "mentions": sec_mentions, "flags": sec_flags, "sources": sec_sources,
}


def render(p: dict, level: int = 1) -> str:
    """The county report as markdown: a title block, then the sections of
    config/county_report.json in order, at heading level `level` + 1."""
    cfg = load_report_config()
    define = Definer(cfg)
    rpt = p["report"]
    h = "#" * level
    L = [f"{h} {rpt['title']}", "",
         f"{_place(p)} (FIPS {p['fips']}). Data as of {rpt['as_of']}. Commit {rpt['commit']}. "
         f"Generated {rpt['generated']} by scripts/site_profile.py.", ""]
    for s in cfg["sections"]:
        body = SECTIONS[s["id"]](p, define)
        if body is None:
            if not s.get("optional"):
                raise SystemExit(f"section {s['id']} is not optional and rendered nothing")
            continue
        L += [f"{h}# {s['heading']}", ""] + body + [""]
    return "\n".join(L)


def summary(profiles: list[dict]) -> str:
    """The overview table of a multi-site run."""
    rows = []
    for p in profiles:
        h = p["in_county"]
        inst = _instruments(h["restrictions"])
        severe = sum(1 for g in inst if g[0]["severity_score"] in ("3", "4"))
        adj = sum(len(g["restrictions"]) + len(g["contested_projects"]) for g in p["adjacent"].values())
        held = sum(len(v) for v in p["not_published"].values())
        rows.append([p["site"], f"{p['county']}, {p['state']} ({p['fips']})", len(inst), severe,
                     len(h["contested_projects"]), adj, held, len(p["flags"]),
                     len((p.get("local_standards") or {}).get(p["fips"], [])), len(p.get("state_framework") or [])])
    return "\n".join(_table(["Site", "County", "Restriction instruments", "Severe", "Contested projects",
                             "Adjacent records", "Held back", "Flags", "Siting standards", "State law rows"],
                            rows)) + "\n"


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--state")
    a.add_argument("--county")
    a.add_argument("--fips")
    a.add_argument("--lat", type=float)
    a.add_argument("--lon", type=float)
    a.add_argument("--radius", type=float, default=0.0, help="miles; 0 (default) skips the radius section")
    a.add_argument("--name", default="")
    a.add_argument("--notes", default="", help="notes to print in the report's Summary")
    a.add_argument("--sites", help="CSV with name,state,county,fips,lat,lon,notes")
    a.add_argument("--out", help="write here instead of stdout")
    a.add_argument("--json", action="store_true")
    a.add_argument("--verified-only", action="store_true",
                   help="leave out restrictions not verified against the instrument (in the county and "
                        "adjacent sections) and say how many were left out")
    a.add_argument("--no-local", action="store_true",
                   help="omit local reports ($RO_LOCAL_KNOWLEDGE) and do not read the file")
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
        if len(profiles) == 1:
            text = render(profiles[0])
        else:
            head = (f"# County reports\n\nDescriptive only: what the published and held-back data record. "
                    f"Generated {date.today().isoformat()} by scripts/site_profile.py.\n\n")
            text = head + summary(profiles) + "\n" + "\n".join(render(p, level=2) for p in profiles)
    if x.out:
        Path(x.out).write_text(text, encoding="utf-8")
        print(f"Wrote {x.out} ({len(profiles)} site(s))")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
