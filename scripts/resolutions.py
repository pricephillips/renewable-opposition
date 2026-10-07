"""Reviewer evidence applied at build time. Pure apart from reading two CSVs.

The seeds hold what a source said. These two hand-edited review files hold
what a reviewer later established from a primary document, and
build_seed_outputs.py lays them over the seed rows on every build, so a
confirmation reaches the published data without re-running any importer.

Every row of all three files (and of data/review/queue.csv) says how its
evidence was seen, in `access`:
  opened     the page or document itself was read
  archived   an Internet Archive copy was read; its URL goes in archived_url
  snippet    only search-index text was seen
A blank or unknown access, or archived with no archived_url, stops the build.
Only opened or archived evidence upgrades a record: a snippet row is kept and
its URL attached, but it never makes a restriction primary_source or an
outcome *_confirmed.

data/review/outcome_resolutions.csv      contested projects, keyed on source_record_id
  outcome          the outcome the evidence supports; any value in the
                   contested_projects vocabulary (qc_gate.VOCAB). A reviewer
                   may confirm (blocked_unverified -> blocked_confirmed) or
                   correct (pending -> advanced_confirmed) an outcome.
  evidence_url     required: the document that shows it (withdrawal letter,
                   permit denial, commissioning notice, minutes, news report)
  evidence_date    YYYY[-MM[-DD]] of the event the document records
  evidence_note    one line: what the document says
  reviewer         who checked it
  access, archived_url  how the document was seen (above)
  -> opened or archived: outcome, finality_evidence = "resolution: <evidence_url>",
     severity_score (build_sabin_seeds.project_severity), resolution_date
  -> snippet: outcome and severity_score unchanged, so an *_unverified outcome
     stays unverified; finality_evidence = "lead: <evidence_url>" unless a
     court ruling already confirms it
  -> either way: resolution_url, resolution_access, resolution_archived_url

data/review/restriction_sources.csv      restrictions, keyed on instrument_id
  primary_source_url  required: the ordinance, resolution or minutes
  verdict             confirmed | contradicts. "contradicts" means the primary
                      source disagrees with the record (repealed, never
                      adopted, a different technology): the rows are marked
                      for qc_gate to hold back.
  checked_on, note, reviewer
  access, archived_url  how the document was seen (above)
  -> primary_source_url, primary_source_checked_on, primary_source_verdict,
     primary_source_access, primary_source_archived_url on every row of the
     instrument. classify.evidence_level becomes primary_source only for a
     confirmed one whose access is opened or archived; with snippet the
     source is "located, not yet read" and the level does not change.

data/review/place_overrides.csv          restrictions and contested projects, keyed on instrument_id
  county_fips      required: the 2024 county the evidence places the record in
  evidence_url     required: the ordinance, minutes or news story that names the
                   town (or project) together with its county
  evidence_note    one line: what the document says
  reviewer, checked_on
  access, archived_url  how the document was seen (above). Any value places
                   the record, since placement is low-stakes; it is carried
                   through as placement_access (with placement_url) so the
                   site profile can say how the county was established.
  -> county_fips_all = county_fips, county_fips_method = "override" on every
     row of the instrument. Applied last, after classify.county_fips_all, for
     records the code cannot place (a town name shared by several counties,
     a jurisdiction name that matches nothing). county_fips, the code the map
     paints, is never changed.

A resolution naming a record that does not exist, or missing its evidence URL,
is an error: build_seed_outputs refuses to build, as it does for a broken seed.
So is an override whose county_fips is not a 2024 county.
"""
from __future__ import annotations

import re
from pathlib import Path

from common import REVIEW_DIR, read_csv

OUTCOME_PATH = REVIEW_DIR / "outcome_resolutions.csv"
RESTRICTION_PATH = REVIEW_DIR / "restriction_sources.csv"
PLACE_OVERRIDE_PATH = REVIEW_DIR / "place_overrides.csv"

OUTCOME_FIELDS = ["source_record_id", "project_name", "outcome", "evidence_url",
                  "evidence_date", "evidence_note", "reviewer", "access", "archived_url"]
RESTRICTION_FIELDS = ["instrument_id", "jurisdiction", "state", "primary_source_url",
                      "verdict", "checked_on", "note", "reviewer", "access", "archived_url"]
PLACE_OVERRIDE_FIELDS = ["instrument_id", "county_fips", "evidence_url", "evidence_note",
                         "reviewer", "checked_on", "access", "archived_url"]
VERDICTS = {"confirmed", "contradicts"}
ACCESS = ("opened", "archived", "snippet")
# How a source must have been seen before it can upgrade a record.
READ_ACCESS = {"opened", "archived"}
_URL = re.compile(r"^https?://[^\s/]+\.[^\s]+$")
_ISO = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def _load(path: Path) -> list[tuple[int, dict]]:
    if not path.exists():
        return []
    return [(i, r) for i, r in enumerate(read_csv(path), start=2)
            if any(_s(v) for v in r.values())]


def access_error(row: dict) -> str:
    """'' when the row's access (and archived_url) are valid, else why not."""
    access, archived = _s(row.get("access")), _s(row.get("archived_url"))
    if access not in ACCESS:
        return (f"access {access!r} must be one of {', '.join(ACCESS)} "
                "(opened: the page was read; archived: an Internet Archive copy was read; "
                "snippet: only search-index text was seen)")
    if access == "archived" and not _URL.match(archived):
        return "access is archived, so archived_url must be the http(s) URL of the copy read"
    if archived and not _URL.match(archived):
        return f"archived_url {archived!r} must be http(s)"
    return ""


def is_read(access: str) -> bool:
    return _s(access) in READ_ACCESS


def apply_outcomes(rows: list[dict], allowed: set[str], path: Path | None = None) -> list[str]:
    from build_sabin_seeds import project_severity

    path = path or OUTCOME_PATH
    errors: list[str] = []
    by_rid: dict[str, list[dict]] = {}
    for r in rows:
        by_rid.setdefault(_s(r.get("source_record_id")), []).append(r)
    seen: set[str] = set()
    for i, res in _load(path):
        where = f"{path.name}: row {i}"
        rid, outcome, url = _s(res.get("source_record_id")), _s(res.get("outcome")), _s(res.get("evidence_url"))
        date = _s(res.get("evidence_date"))
        if rid in seen:
            errors.append(f"{where}: {rid} is resolved twice")
            continue
        seen.add(rid)
        if rid not in by_rid or not rid:
            errors.append(f"{where}: no contested project has source_record_id {rid!r}")
            continue
        if outcome not in allowed:
            errors.append(f"{where}: outcome {outcome!r} is not in the vocabulary")
            continue
        if not _URL.match(url):
            errors.append(f"{where}: evidence_url is required and must be http(s)")
            continue
        if date and not _ISO.match(date):
            errors.append(f"{where}: evidence_date {date!r} is not YYYY[-MM[-DD]]")
            continue
        bad = access_error(res)
        if bad:
            errors.append(f"{where}: {bad}")
            continue
        access = _s(res.get("access"))
        for row in by_rid[rid]:
            row["resolution_url"] = url
            row["resolution_access"] = access
            row["resolution_archived_url"] = _s(res.get("archived_url"))
            if not is_read(access):
                # Located, not read: the outcome stays where the source left it.
                if not _s(row.get("finality_evidence")).startswith("court_ruling"):
                    row["finality_evidence"] = f"lead: {url}"
                continue
            litigated = _s(row.get("has_litigation")) == "yes"
            row["outcome"] = outcome
            row["finality_evidence"] = f"resolution: {url}"
            row["severity_score"] = project_severity(outcome, litigated)
            row["resolution_date"] = date
    return errors


def apply_restriction_sources(rows: list[dict], path: Path | None = None) -> list[str]:
    path = path or RESTRICTION_PATH
    errors: list[str] = []
    by_iid: dict[str, list[dict]] = {}
    for r in rows:
        by_iid.setdefault(_s(r.get("instrument_id")), []).append(r)
    seen: set[str] = set()
    for i, res in _load(path):
        where = f"{path.name}: row {i}"
        iid, url, verdict = _s(res.get("instrument_id")), _s(res.get("primary_source_url")), \
            _s(res.get("verdict"))
        if iid in seen:
            errors.append(f"{where}: {iid} is listed twice")
            continue
        seen.add(iid)
        if iid not in by_iid or not iid:
            errors.append(f"{where}: no restriction has instrument_id {iid!r}")
            continue
        if not _URL.match(url):
            errors.append(f"{where}: primary_source_url is required and must be http(s)")
            continue
        if verdict not in VERDICTS:
            errors.append(f"{where}: verdict {verdict!r} is not one of {sorted(VERDICTS)}")
            continue
        bad = access_error(res)
        if bad:
            errors.append(f"{where}: {bad}")
            continue
        for row in by_iid[iid]:
            row["primary_source_url"] = url
            row["primary_source_verdict"] = verdict
            row["primary_source_checked_on"] = _s(res.get("checked_on"))
            row["primary_source_access"] = _s(res.get("access"))
            row["primary_source_archived_url"] = _s(res.get("archived_url"))
    return errors


def apply_place_overrides(datasets: dict[str, list[dict]], known, path: Path | None = None) -> list[str]:
    """Lay reviewer counties over county_fips_all. ``known(fips) -> bool`` says
    whether a code is a 2024 county (geo.known); injected to keep this free of
    the geometry file."""
    path = path or PLACE_OVERRIDE_PATH
    errors: list[str] = []
    by_iid: dict[str, list[dict]] = {}
    for entity in ("restrictions", "contested_projects"):
        for r in datasets.get(entity, []):
            by_iid.setdefault(_s(r.get("instrument_id")), []).append(r)
    seen: set[str] = set()
    for i, ov in _load(path):
        where = f"{path.name}: row {i}"
        iid, fips, url = _s(ov.get("instrument_id")), _s(ov.get("county_fips")), _s(ov.get("evidence_url"))
        checked = _s(ov.get("checked_on"))
        if iid in seen:
            errors.append(f"{where}: {iid} is listed twice")
            continue
        seen.add(iid)
        if iid not in by_iid or not iid:
            errors.append(f"{where}: no restriction or contested project has instrument_id {iid!r}")
            continue
        if not _URL.match(url):
            errors.append(f"{where}: evidence_url is required and must be http(s)")
            continue
        if not (re.fullmatch(r"\d{5}", fips) and known(fips)):
            errors.append(f"{where}: county_fips {fips!r} is not a 2024 county")
            continue
        if checked and not _ISO.match(checked):
            errors.append(f"{where}: checked_on {checked!r} is not YYYY[-MM[-DD]]")
            continue
        bad = access_error(ov)
        if bad:
            errors.append(f"{where}: {bad}")
            continue
        for row in by_iid[iid]:
            row["county_fips_all"] = fips
            row["county_fips_method"] = "override"
            row["placement_url"] = url
            row["placement_access"] = _s(ov.get("access"))
    return errors
