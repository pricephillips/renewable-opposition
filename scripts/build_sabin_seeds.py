"""Build seed rows from the Sabin Center's "Opposition to Renewable Energy
Facilities in the United States".

The current input is the September 2026 edition (6th edition, data through
2025-12-31), extracted by scripts/extract_sabin_edition.py into
data/renewable_opposition_records_2026-09.csv. The June 2025 extraction
(data/renewable_opposition_records.csv) is still read, through the edition
crosswalk (data/review/sabin_edition_crosswalk.csv, scripts/sabin_crosswalk.py):

  matched 2026 entry      published under its 2025 REC- id, so its
                          instrument_id (sabin:<REC id>), its published id
                          (pinned_id, the id the 2025 row had) and every review
                          row attached to it carry over. Its fields come from
                          the 2026 entry; opposition_type, which the 2026
                          edition does not record, and a blank capacity or
                          area are carried from the 2025 record and noted.
  new 2026 entry          published under its own id (S26R-/S26P-).
  2026 entry that is a candidate in an ambiguous crosswalk row
                          held (sabin_edition_worklist.csv) until a reviewer
                          decides, so nothing is counted twice.
  2025 record not in the 2026 edition, or ambiguous
                          never deleted: built from the 2025 record as before,
                          with edition_status not_in_latest_edition or
                          crosswalk_ambiguous, and listed on
                          data/review/sabin_edition_worklist.csv, since it may
                          have been lifted, merged or renamed.

Every row carries sabin_edition (2026-09 or 2025-06) and edition_status. Where
the 2026 edition changes a matched record's status (a moratorium expired, a
project cancelled), the new status is used; the crosswalk records both
values (status_2025, status_2026) and processed_diff.py lists them.

Nothing is looked up or invented here; every output field is copied from a
source row or derived from it by the rules below.

Outputs
-------
data/seed/contested_projects_seed.csv   one row per contested project (section
                                        ``contested_projects``); fully rewritten.
data/seed/restrictions_seed.csv         one row per local restriction x
                                        technology (section ``local_restrictions``).
                                        Only rows whose ``source`` is SOURCE_LABEL
                                        are replaced; Moratorium Nation and
                                        hand-added rows are kept as they are.
data/review/cases_candidates.csv        projects and restrictions the source flags
                                        as litigated, queued for docket research.
                                        Reviewer-filled case fields survive a
                                        rebuild (see merge_candidates).
data/review/sabin_restrictions_review.csv
                                        restriction rows held back from the seed,
                                        with the reason (state-level rows, rows
                                        without a restricting mechanism, rows that
                                        duplicate a Moratorium Nation or review
                                        queue moratorium, expired rows).
data/review/sabin_edition_worklist.csv  2025 records missing from the 2026
                                        edition or ambiguous in the crosswalk, and
                                        the 2026 entries held with them.

Contested projects
------------------
outcome         outcome ladder shared with pricephillips/data-center-map, mapped
                from source status:
                  cancelled, rejected                   -> blocked_unverified
                  approved, approved_after_opposition,
                  operational                           -> advanced_unverified
                  pending, proposed                     -> pending
                  anything else (in_force, lifted,
                  unknown, blank)                       -> needs_review
                (the 2026 edition uses pending, cancelled, operational and
                unknown)
                A status label alone is never finality evidence, so nothing is
                *_confirmed on the extraction's word. A row is promoted to
                blocked_confirmed / advanced_confirmed only when a case in
                data/seed/cases_seed.csv linked to the same source record was
                decided the same way (ruled_for_opposition / ruled_for_developer).
                ``finality_evidence`` records which: court_ruling,
                outcome_label_only or none. ``restricted_conditional`` is only
                set by hand.
severity_score  1-4 intensity of opposition against the project:
                  4  project blocked (outcome blocked_*)
                  3  litigation filed, project not (yet) blocked
                  2  resident/organized opposition, no litigation, not approved
                  1  project advanced despite opposition, no litigation

Restrictions
------------
Scope           local rows only. The report's state-level rows in the extraction
                are often generic ("State-level prohibitions ... have been
                adopted") with no statute named, so they go to the review file
                until each is checked against the report.
technology      one row per solar / wind / battery_storage token. Other tokens
                (transmission, hydro) are dropped. A blank technology is inferred
                from the description (see infer_technology) and noted.
status          in_force -> active; extended / pending kept; unknown or blank ->
                unknown. lifted / cancelled / expired rows are excluded,
                matching the Moratorium Nation rule that only in-force or
                pending instruments are restrictions.
mechanisms      the 2026 extraction qualifies each mechanism with the
                technology its rule names ("setback (wind)", "moratorium
                (solar+storage)"); a technology's row takes the unqualified
                mechanisms and those naming it. A technology the entry lists
                but no rule names is held for review. The edition's unstated
                "ban or moratorium" is restriction_type ban_or_moratorium.
restriction_type
                the most stringent mechanism present, in the order ban,
                moratorium, height_limit, setback, noise_limit, size_cap,
                zoning_restriction, siting_standard, other. The full list is kept
                in ``mechanisms``.
severity_score  (README scale) highest score any mechanism earns:
                  4  ban/prohibition, or an active/extended/unknown moratorium
                     or unstated ban or moratorium
                  3  wind: setback >= 2,640 ft (half mile) or >= 5x turbine
                     height; noise limit <= 35 dBA; any wind height limit
                     solar / storage: setback >= 1,000 ft
                  2  every other restricting mechanism
                Distances are parsed from the description, reading only the
                sentences that name the row's technology (see text_about), so a
                wind setback never scores a solar row. A pending
                instrument is capped at 2. ``severity_basis`` records which rule
                set the score.
dedup           a row whose only mechanism is a moratorium is dropped when
                Moratorium Nation, or a promoted review-queue row, already has
                a moratorium for the same jurisdiction and technology (both
                are maintained more recently); it is listed in the review file
                instead. A row whose only mechanism is the edition's unstated
                ban or moratorium is held the same way as a possible duplicate.

Usage:
    python scripts/build_sabin_seeds.py [--dry-run]
"""
from __future__ import annotations

import argparse
import re

from common import (
    REVIEW_DIR, ROOT, SEED_DIR, jurisdiction_key, jurisdiction_kind, read_csv,
    state_code, technology_tokens, write_csv,
)

RECORDS_PATH = ROOT / "data" / "renewable_opposition_records_2026-09.csv"
RECORDS_2025_PATH = ROOT / "data" / "renewable_opposition_records.csv"
CROSSWALK_PATH = REVIEW_DIR / "sabin_edition_crosswalk.csv"
CONTESTED_PATH = SEED_DIR / "contested_projects_seed.csv"
RESTRICTIONS_PATH = SEED_DIR / "restrictions_seed.csv"
CASES_PATH = SEED_DIR / "cases_seed.csv"
CANDIDATES_PATH = REVIEW_DIR / "cases_candidates.csv"
RESTRICTIONS_REVIEW_PATH = REVIEW_DIR / "sabin_restrictions_review.csv"
EDITION_WORKLIST_PATH = REVIEW_DIR / "sabin_edition_worklist.csv"

# Every seed row this script writes has a `source` starting with this, whatever
# its edition (config/layers.json row_owner).
SOURCE_PREFIX = "Sabin Center, "
SOURCE_LABEL = (
    "Sabin Center, Opposition to Renewable Energy Facilities in the United States "
    "(Sept. 2026 ed.), via data/renewable_opposition_records_2026-09.csv"
)
SOURCE_URL = "https://scholarship.law.columbia.edu/sabin_climate_change/280/"
SOURCE_LABEL_2025 = (
    "Sabin Center, Opposition to Renewable Energy Facilities in the United States "
    "(June 2025 ed.), via data/renewable_opposition_records.csv"
)
SOURCE_URL_2025 = (
    "https://climate.law.columbia.edu/sites/default/files/content/"
    "Opposition-Report-June-2025.pdf"
)
EDITIONS = {"2026-09": (SOURCE_LABEL, SOURCE_URL), "2025-06": (SOURCE_LABEL_2025, SOURCE_URL_2025)}
MORATORIUM_NATION_LABEL = "Moratorium Nation (mjbommar/moratorium-data-2026), CC-BY-4.0"
QUEUE_PREFIX = "review queue:"

# ── Contested projects ────────────────────────────────────────────────────────

# Rows that are not a single identifiable project.
PROJECT_EXCLUDE = {
    "REC-0501": "reference to a USA Today database, not a project",
}

# Source rows with a blank technology where the project name states it.
PROJECT_TECHNOLOGY_OVERRIDES = {
    "REC-0279": "wind",  # New York Bight Offshore Wind Area
    "REC-0368": "transmission",  # Boardman-to-Hemingway Transmission Line
}

# Projects whose municipality column is blank but whose own text names the
# town. Connecticut replaced its counties with planning regions in 2022, so a
# Connecticut project naming only its old county is placed by its town
# (classify.county_fips_all, method "place"). Each town must appear in the
# record's long_description; build_contested refuses the row otherwise.
PROJECT_MUNICIPALITY_FROM_TEXT = {
    "REC-0039": "Ellington",   # "a 4-MW solar facility in Ellington Airport"
    "REC-0041": "Manchester",  # "a 0.999-MW solar facility in Manchester on Carter Street"
}

OUTCOME = {
    "cancelled": "blocked_unverified",
    "rejected": "blocked_unverified",
    "approved": "advanced_unverified",
    "approved_after_opposition": "advanced_unverified",
    "operational": "advanced_unverified",
    "pending": "pending",
    "proposed": "pending",
}

CONTESTED_FIELDS = [
    "state", "project_name", "technology", "severity_score", "description",
    "outcome", "finality_evidence", "status", "has_litigation", "opposition_type",
    "county", "municipality", "event_date_text", "capacity_mw", "area_acres",
    "long_description", "source_record_id", "source", "source_url", "notes",
    # Reviewer columns, carried forward on a rebuild (carry_groups).
    "opposition_groups", "group_sources",
    # Edition bookkeeping (module docstring).
    "sabin_edition", "edition_status", "pinned_id",
]

CANDIDATE_FIELDS = [
    "state", "project_name", "technology", "source_record_id", "linked_entity",
    "outcome", "opposition_type", "event_date_text", "litigation_context",
    "case_name", "court", "court_level", "docket_number", "case_status",
    "case_source_url", "severity_score", "review_status", "reviewer_notes",
]

# ── Restrictions ─────────────────────────────────────────────────────────────

RESTRICTION_TECH = ("solar", "wind", "battery_storage")

# Local rows whose county/municipality columns are blank but whose description
# names the jurisdiction.
JURISDICTION_OVERRIDES = {
    "REC-0254": ("county", "Nye County"),
    "REC-0358": ("municipal", "Owasso"),
    "REC-0359": ("municipal", "Yukon"),
    "REC-0398": ("county", "Hughes County"),
    "REC-0462": ("county", "Grant County"),
}

# Mechanism spellings in the extraction -> restriction_type.
MECHANISM_TYPE = {
    "ban/prohibition": "ban", "ban": "ban", "primary use prohibition": "ban",
    "moratorium": "moratorium", "pause on new projects": "moratorium",
    # The 2026 edition's "Ban / Moratorium" rule when its text says neither.
    "ban or moratorium": "ban_or_moratorium",
    "extension": "moratorium",
    "height_limit": "height_limit", "height limit": "height_limit",
    "height restriction": "height_limit",
    "height limit with resident permission": "height_limit",
    "setback": "setback", "setback rules": "setback", "buffer zone": "setback",
    "noise_limit": "noise_limit", "noise limit": "noise_limit",
    "cap on acreage": "size_cap", "cap on project size": "size_cap",
    "cap on area": "size_cap", "area limit": "size_cap",
    "cap on capacity": "size_cap", "cap on project area": "size_cap",
    "zoning_restriction": "zoning_restriction", "zoning restriction": "zoning_restriction",
    "overlay_zone": "zoning_restriction", "ag_land_exclusion": "zoning_restriction",
    "zoning regulation update": "zoning_restriction",
    "land preservation program": "zoning_restriction",
    "shadow_flicker_limit": "siting_standard", "visual_impact_rule": "siting_standard",
    "refusal to sign agreements": "other", "extended_producer_responsibility": "other",
}
# Mechanisms that loosen rather than restrict local siting.
NON_RESTRICTING = {"preemption"}
TYPE_ORDER = [
    "ban", "ban_or_moratorium", "moratorium", "height_limit", "setback", "noise_limit", "size_cap",
    "zoning_restriction", "siting_standard", "other",
]

RESTRICTION_STATUS = {
    "in_force": "active", "extended": "extended", "pending": "pending",
    "unknown": "unknown", "": "unknown",
}
EXCLUDED_STATUS = {"lifted", "cancelled", "expired"}

RESTRICTION_FIELDS = [
    "state", "technology", "restriction_type", "severity_score", "description",
    "status", "jurisdiction", "jurisdiction_type", "date_enacted_iso",
    "date_text", "mechanisms", "severity_basis", "long_description",
    "moratorium_id", "source_record_id", "source", "source_url", "notes",
    "sabin_edition", "edition_status", "pinned_id", "source_county_fips",
]
REVIEW_FIELDS = [
    "source_record_id", "state", "jurisdiction", "technology", "mechanisms",
    "status", "reason", "description", "long_description",
]

_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"
_WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "half": 0.5, "one-half": 0.5}


def setback_feet(text: str) -> float:
    """Largest distance stated in feet or miles, in feet (0 if none)."""
    t = text.lower()
    best = 0.0
    for m in re.finditer(_NUM + r"[\s-]*(?:feet|foot|ft\b)", t):
        best = max(best, float(m.group(1).replace(",", "")))
    for m in re.finditer(_NUM + r"[\s-]*miles?\b", t):
        best = max(best, float(m.group(1).replace(",", "")) * 5280)
    for m in re.finditer(r"\b(one-half|half|one|two|three|four|five)[\s-]+(?:a\s+)?miles?\b", t):
        best = max(best, _WORD_NUM[m.group(1)] * 5280)
    return best


def height_multiplier(text: str) -> float:
    """Largest 'N times (turbine/tip/total) height' multiplier stated (0 if none)."""
    t = text.lower()
    best = 0.0
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:x|times)\s+(?:the\s+)?(?:\w+\s+){0,3}height", t):
        best = max(best, float(m.group(1)))
    return best


def min_noise_dba(text: str) -> float:
    vals = [float(v) for v in re.findall(r"(\d{2})\s*db", text.lower())]
    return min(vals) if vals else 0.0


def infer_technology(text: str) -> list[str]:
    """Technologies named in free text; generic renewable wording -> solar + wind."""
    t = text.lower()
    found = [tech for tech, pat in (
        ("solar", r"\bsolar\b"),
        ("wind", r"\bwind\b"),
        ("battery_storage", r"\b(battery|storage)\b"),
    ) if re.search(pat, t)]
    if not found and re.search(r"renewable|energy (facilit|project|generation)|power generation", t):
        found = ["solar", "wind"]
    return found


TECH_WORDS = {
    "wind": r"\b(wind|turbines?|WECS)\b",
    "solar": r"\b(solar|photovoltaic|PV)\b",
    "battery_storage": r"\b(battery|batteries|storage|BESS)\b",
}


def text_about(text: str, tech: str) -> str:
    """Keep only the sentences that name ``tech`` so a wind setback is never
    scored as a solar one. If no sentence names any technology the whole text
    applies; if sentences name only other technologies, nothing does."""
    sentences = re.split(r"(?<=[.;])\s+", text)
    own = [s for s in sentences if re.search(TECH_WORDS[tech], s, re.I)]
    if own:
        return " ".join(own)
    if any(re.search(p, text, re.I) for p in TECH_WORDS.values()):
        return ""
    return text


def restriction_severity(types: set[str], tech: str, status: str, text: str) -> tuple[int, str]:
    score, basis = 2, "restricting mechanism (default)"
    if "ban" in types:
        score, basis = 4, "ban/prohibition"
    elif "ban_or_moratorium" in types and status in ("active", "extended", "unknown"):
        score, basis = 4, "ban or moratorium (the source does not say which)"
    elif "moratorium" in types and status in ("active", "extended", "unknown"):
        score, basis = 4, "in-force moratorium"
    else:
        feet, mult = setback_feet(text), height_multiplier(text)
        if tech == "wind":
            if "setback" in types and (feet >= 2640 or mult >= 5):
                parts = [f"{int(feet)} ft" if feet else "", f"{mult:g}x height" if mult else ""]
                score, basis = 3, "wind setback " + " / ".join(p for p in parts if p)
            elif "height_limit" in types:
                score, basis = 3, "wind height limit"
            elif "noise_limit" in types and 0 < min_noise_dba(text) <= 35:
                score, basis = 3, f"wind noise limit {min_noise_dba(text):g} dBA"
        elif "setback" in types and feet >= 1000:
            score, basis = 3, f"{tech} setback {int(feet)} ft"
    if status == "pending" and score > 2:
        score, basis = 2, basis + "; capped at 2 (pending)"
    return score, basis


# The severity rule that fired names the mechanism that drives the score.
BASIS_TYPE = (("ban/prohibition", "ban"), ("ban or moratorium", "ban_or_moratorium"),
              ("in-force moratorium", "moratorium"),
              ("wind height limit", "height_limit"), ("wind noise limit", "noise_limit"))


def driving_type(types: set[str], basis: str) -> str:
    """restriction_type for a row: the mechanism whose rule set its severity,
    so an ordinance scored 3 for a 5,250 ft setback reads as a setback even
    when it also caps height. Otherwise the most severe mechanism by
    TYPE_ORDER, as before."""
    for prefix, t in BASIS_TYPE:
        if basis.startswith(prefix) and t in types:
            return t
    if " setback " in f" {basis} " and "setback" in types:
        return "setback"
    return next(t for t in TYPE_ORDER if t in types)


def is_litigated(row: dict) -> bool:
    return row["has_litigation"].strip() == "yes" or "litigation" in row["opposition_type"]


# ── Builders ─────────────────────────────────────────────────────────────────

# A linked case decided this way corroborates the unverified outcome.
CONFIRMING_RULING = {
    "blocked_unverified": ("ruled_for_opposition", "blocked_confirmed"),
    "advanced_unverified": ("ruled_for_developer", "advanced_confirmed"),
}


def case_rulings(cases: list[dict]) -> dict[str, list[dict]]:
    """source_record_id -> the seeded cases linked to it."""
    out: dict[str, list[dict]] = {}
    for c in cases:
        if c.get("source_record_id"):
            out.setdefault(c["source_record_id"], []).append(c)
    return out


# A municipality value that names a project or company, not a place.
PROJECT_LIKE = re.compile(r"\b(solar|wind|LLC|plant|array|farm)\b", re.I)


def project_severity(outcome: str, litigated: bool) -> int:
    """The contested-project severity rule (module docstring). Shared with
    resolutions.py, so a reviewed outcome is scored the same way."""
    if outcome.startswith("blocked_"):
        return 4
    if litigated:
        return 3
    if outcome.startswith("advanced_"):
        return 1
    return 2


def finalize_outcome(outcome: str, linked_cases: list[dict]) -> tuple[str, str]:
    """Return (outcome, finality_evidence) given the cases linked to the row."""
    if outcome in CONFIRMING_RULING:
        ruling, confirmed = CONFIRMING_RULING[outcome]
        for c in linked_cases:
            if c.get("case_status") == ruling:
                return confirmed, f"court_ruling: {c.get('case_name', '')}".strip()
        return outcome, "outcome_label_only"
    return outcome, "none"


_QUALIFIER = re.compile(r"\s*\(([^)]*)\)\s*$")
QUALIFIER_TECH = {"storage": "battery_storage", "battery_storage": "battery_storage", "solar": "solar",
                  "wind": "wind", "transmission": "transmission"}


def mechanism_name(m: str) -> str:
    """'setback (wind)' -> 'setback'; an unqualified mechanism is unchanged."""
    return _QUALIFIER.sub("", m).strip()


def mechanisms_for(mechanisms: list[str], tech: str) -> list[str]:
    """The mechanisms that apply to tech: unqualified ones, and those whose
    qualifier names it ("moratorium (solar+storage)")."""
    out = []
    for m in mechanisms:
        q = _QUALIFIER.search(m)
        if not q or tech in {QUALIFIER_TECH.get(t.strip(), t.strip()) for t in q.group(1).split("+")}:
            out.append(m)
    return out


_EXPORT_FIPS = re.compile(r"county FIPS ([\d, ]+)")


def source_county(r: dict) -> str:
    """The one county FIPS the 2026 export gives for an entry (kept in its
    notes), for placing a town or township entry (classify method
    source_fips); '' when it gives none or several."""
    m = _EXPORT_FIPS.search(r.get("notes", ""))
    codes = [c.strip() for c in m.group(1).split(",") if c.strip()] if m else []
    return codes[0].zfill(5) if len(codes) == 1 else ""


def edition_of(r: dict) -> str:
    return r.get("_edition") or ("2025-06" if r.get("record_id", "").startswith("REC-") else "2026-09")


def edition_columns(r: dict) -> dict:
    """source, source_url and the edition bookkeeping for a seed row."""
    ed = edition_of(r)
    label, url = EDITIONS[ed]
    out = {"source": label, "source_url": url, "sabin_edition": ed,
           "edition_status": r.get("_edition_status") or "in_latest_edition"}
    if r.get("record_id", "").startswith("REC-"):
        out["_pin"] = True  # pinned below, per technology (pin_2025_ids)
    return out


def build_contested(records: list[dict], rulings: dict[str, list[dict]] | None = None
                    ) -> tuple[list[dict], list[dict], list[str]]:
    rulings = rulings or {}
    seed, candidates, excluded = [], [], []
    for r in records:
        if r["extraction_source_section"] != "contested_projects":
            continue
        rid = r["record_id"]
        if rid in PROJECT_EXCLUDE:
            excluded.append(f"{rid}: {PROJECT_EXCLUDE[rid]}")
            continue

        notes = [n for n in [r["notes"].strip()] if n]
        project_name, municipality = r["project_or_policy_name"].strip(), r["municipality"].strip()
        if PROJECT_LIKE.search(municipality):
            # The extraction put the project's name in the municipality column
            # and a description in the name column (REC-0190 to REC-0194).
            project_name, municipality = municipality, ""
            notes.append("project name recovered from the municipality column")
        if rid in PROJECT_MUNICIPALITY_FROM_TEXT and not municipality:
            town = PROJECT_MUNICIPALITY_FROM_TEXT[rid]
            if edition_of(r) == "2025-06" and not re.search(rf"\b{re.escape(town)}\b", r["long_description"]):
                raise ValueError(f"{rid}: {town!r} is not named in the record's text")
            if re.search(rf"\b{re.escape(town)}\b", r["long_description"]):
                municipality = town
                notes.append("municipality from the record's text")
        tech_raw = r["technology"]
        if rid in PROJECT_TECHNOLOGY_OVERRIDES and not tech_raw.strip():
            tech_raw = PROJECT_TECHNOLOGY_OVERRIDES[rid]
            notes.append("technology inferred from project name")
        technology = ";".join(technology_tokens(tech_raw))

        outcome, finality = finalize_outcome(
            OUTCOME.get(r["status"].strip(), "needs_review"), rulings.get(rid, []))
        litigated = is_litigated(r)
        severity = project_severity(outcome, litigated)
        row = {
            "state": state_code(r["state"]),
            "project_name": project_name,
            "technology": technology,
            "severity_score": severity,
            "description": r["short_description"].strip(),
            "outcome": outcome,
            "finality_evidence": finality,
            "status": r["status"].strip(),
            "has_litigation": "yes" if litigated else r["has_litigation"].strip(),
            "opposition_type": r["opposition_type"].strip(),
            "county": r["county"].strip(),
            "municipality": municipality,
            "event_date_text": r["adopted_or_event_date_text"].strip(),
            "capacity_mw": r["project_capacity_mw"].strip(),
            "area_acres": r["project_area_acres"].strip(),
            "long_description": r["long_description"].strip(),
            "source_record_id": rid,
            **edition_columns(r),
            "notes": "; ".join(notes),
        }
        seed.append(row)
        if litigated:
            candidates.append({
                "state": row["state"],
                "project_name": row["project_name"],
                "technology": technology,
                "source_record_id": rid,
                "linked_entity": "contested_project",
                "outcome": outcome,
                "opposition_type": row["opposition_type"],
                "event_date_text": row["event_date_text"],
                "litigation_context": row["long_description"],
                "review_status": "needs_docket_research",
            })
    seed.sort(key=lambda x: (x["state"], x["project_name"].lower()))
    return seed, candidates, excluded


def moratorium_nation_index(existing: list[dict]) -> dict[tuple[str, str], str]:
    """(jurisdiction_key, technology) -> moratorium_id for Moratorium Nation
    rows, and -> "queue:<queue_id>" for promoted review-queue rows whose
    restriction_type is moratorium (the same dedup rule for both)."""
    index = {}
    for row in existing:
        source = row.get("source") or ""
        if source == MORATORIUM_NATION_LABEL:
            value = row.get("moratorium_id", "")
        elif source.startswith(QUEUE_PREFIX) and row.get("restriction_type") == "moratorium":
            value = f"queue:{row.get('queue_id') or row.get('pinned_id') or source}"
        else:
            continue
        kind = jurisdiction_kind(row.get("jurisdiction_type", ""))
        key = jurisdiction_key(row["state"], kind, row.get("jurisdiction", ""))
        index.setdefault((key, row["technology"]), value)
    return index


def build_restrictions(records: list[dict], mn_index: dict) -> tuple[list[dict], list[dict], list[dict]]:
    seed, review, candidates = [], [], []
    for r in records:
        section = r["extraction_source_section"]
        if section not in ("local_restrictions", "state_level_restrictions"):
            continue
        rid = r["record_id"]
        st = state_code(r["state"])
        text = " ".join([r["short_description"], r["long_description"]])
        mechanisms = [m.strip() for m in r["policy_mechanism"].split(",") if m.strip()]

        if rid in JURISDICTION_OVERRIDES and not (r["municipality"].strip() or r["county"].strip()):
            kind, jurisdiction = JURISDICTION_OVERRIDES[rid]
        elif r["municipality"].strip():
            kind, jurisdiction = "municipal", r["municipality"].strip()
        elif r["county"].strip():
            kind, jurisdiction = "county", r["county"].strip()
        else:
            kind, jurisdiction = "state", ""

        def hold(reason: str, tech: str = "") -> None:
            review.append({
                "source_record_id": rid, "state": st, "jurisdiction": jurisdiction,
                "technology": tech or r["technology"], "mechanisms": ", ".join(mechanisms),
                "status": r["status"], "reason": reason,
                "description": r["short_description"].strip(),
                "long_description": r["long_description"].strip(),
            })

        if section == "state_level_restrictions" or kind == "state":
            hold("state-level row: verify the statute against the report before seeding")
            continue
        if not mechanisms:
            hold("no restricting mechanism recorded")
            continue
        if set(map(mechanism_name, mechanisms)) & NON_RESTRICTING:
            hold("mechanism loosens local siting (preemption), not a restriction")
            continue
        status_raw = r["status"].strip()
        if status_raw in EXCLUDED_STATUS:
            hold(f"status {status_raw}: no longer in force")
            continue
        status = RESTRICTION_STATUS.get(status_raw)
        if status is None:
            raise SystemExit(f"{rid}: unmapped restriction status {status_raw!r}")

        unknown = [m for m in mechanisms if mechanism_name(m) not in MECHANISM_TYPE]
        if unknown:
            raise SystemExit(f"{rid}: unmapped mechanism(s) {unknown}")
        types = {MECHANISM_TYPE[mechanism_name(m)] for m in mechanisms}
        restriction_type = next(t for t in TYPE_ORDER if t in types)

        notes = [n for n in [r["notes"].strip()] if n]
        techs = [t for t in technology_tokens(r["technology"]) if t in RESTRICTION_TECH]
        if not r["technology"].strip():
            techs = infer_technology(text)
            if techs:
                notes.append("technology inferred from description")
        if not techs:
            hold("no solar/wind/storage technology in scope")
            continue

        jurisdiction_type = "County" if kind == "county" else "Municipality"
        key = jurisdiction_key(st, kind, jurisdiction)
        for tech in techs:
            own = mechanisms_for(mechanisms, tech)
            if not own:
                hold(f"no rule of the entry names {tech}", tech)
                continue
            tech_types = {MECHANISM_TYPE[mechanism_name(m)] for m in own}
            mn_id = mn_index.get((key, tech), "")
            what = "review queue row" if mn_id.startswith("queue:") else "Moratorium Nation"
            if mn_id and tech_types == {"moratorium"}:
                hold(f"duplicate of {what} {mn_id.removeprefix('queue:')}", tech)
                continue
            if mn_id and tech_types == {"ban_or_moratorium"}:
                hold(f"possible duplicate of {what} {mn_id.removeprefix('queue:')}: the edition does not "
                     "say whether this is a ban or a moratorium", tech)
                continue
            severity, basis = restriction_severity(
                tech_types, tech, status, text_about(text, tech)
            )
            row_notes = list(notes)
            if mn_id:
                row_notes.append(f"{what} also lists a moratorium here ({mn_id.removeprefix('queue:')})")
            seed.append({
                "state": st,
                "technology": tech,
                "restriction_type": driving_type(tech_types, basis),
                "severity_score": severity,
                "description": r["short_description"].strip(),
                "status": status,
                "jurisdiction": jurisdiction,
                "jurisdiction_type": jurisdiction_type,
                "date_enacted_iso": "",
                "date_text": r["adopted_or_event_date_text"].strip(),
                "mechanisms": ", ".join(own),
                "severity_basis": basis,
                "long_description": r["long_description"].strip(),
                "moratorium_id": "",
                "source_record_id": rid,
                **edition_columns(r),
                "notes": "; ".join(row_notes),
                "source_county_fips": source_county(r),
            })

        if r["has_litigation"].strip() == "yes":
            candidates.append({
                "state": st,
                "project_name": f"{jurisdiction} {restriction_type}".strip(),
                "technology": ";".join(techs),
                "source_record_id": rid,
                "linked_entity": "restriction",
                "outcome": "",
                "opposition_type": "",
                "event_date_text": r["adopted_or_event_date_text"].strip(),
                "litigation_context": r["long_description"].strip(),
                "review_status": "needs_docket_research",
            })
    seed.sort(key=lambda x: (x["state"], x["jurisdiction"].lower(), x["technology"]))
    review.sort(key=lambda x: (x["reason"], x["state"], x["source_record_id"]))
    return seed, review, candidates


# ── Editions ─────────────────────────────────────────────────────────────────

EDITION_WORKLIST_FIELDS = ["record_id", "kind", "state", "name", "technology", "status", "edition_status",
                           "what_to_check", "candidates_2026", "crosswalk_basis"]
_ENTRY = re.compile(r"\bS26[RP]-\d+\b")
# Fields the 2026 edition leaves blank that the 2025 record filled: kept, and noted.
CARRIED = (("opposition_type", "opposition_type"), ("project_capacity_mw", "capacity"),
           ("project_area_acres", "area"), ("has_litigation", "has_litigation"))


def merge_editions(new: list[dict], old: list[dict], crosswalk: list[dict]) -> tuple[list[dict], list[dict]]:
    """(records to build, worklist rows) from the 2026 records, the 2025
    records and the crosswalk (module docstring)."""
    by_rec = {r["rec_id"]: r for r in crosswalk}
    missing = [o["record_id"] for o in old if o["record_id"] not in by_rec]
    if missing:
        raise SystemExit(f"{len(missing)} 2025 record(s) are not in {CROSSWALK_PATH.name} "
                         f"({', '.join(missing[:5])}); run scripts/sabin_crosswalk.py")
    matched = {r["entry_2026"]: r["rec_id"] for r in crosswalk if r["match"] == "matched"}
    held: dict[str, list[str]] = {}
    for r in crosswalk:
        if r["match"] == "ambiguous":
            for e in _ENTRY.findall(r.get("candidates_2026", "")):
                if e not in matched:
                    held.setdefault(e, []).append(r["rec_id"])
    old_by = {o["record_id"]: o for o in old}
    records, worklist = [], []
    for n in new:
        nid = n["record_id"]
        if nid in held:
            worklist.append({"record_id": nid, "kind": "2026 entry held", "state": n["state"],
                             "name": n["project_or_policy_name"] or n["municipality"] or n["county"],
                             "technology": n["technology"], "status": n["status"], "edition_status": "held",
                             "what_to_check": "a candidate for ambiguous 2025 record(s) " + ", ".join(held[nid])
                                              + ": set review_decision in the crosswalk",
                             "candidates_2026": "", "crosswalk_basis": ""})
            continue
        rec = dict(n, _edition="2026-09", _edition_status="in_latest_edition")
        if nid in matched:
            o = old_by[matched[nid]]
            rec["record_id"] = matched[nid]
            carried = []
            for field, word in CARRIED:
                if not rec.get(field, "").strip() and o.get(field, "").strip():
                    rec[field] = o[field]
                    carried.append(word)
            notes = [rec.get("notes", "")]
            if carried:
                notes.append(f"{', '.join(carried)} carried from the 2025 edition")
            rec["notes"] = "; ".join(x for x in notes if x)
        records.append(rec)
    for o in old:
        cw = by_rec[o["record_id"]]
        if cw["match"] == "matched":
            continue
        status = "not_in_latest_edition" if cw["match"] == "not_in_latest_edition" else "crosswalk_ambiguous"
        records.append(dict(o, _edition="2025-06", _edition_status=status))
        worklist.append({"record_id": o["record_id"], "kind": "2025 record", "state": o["state"],
                         "name": cw["name_2025"], "technology": o["technology"], "status": o["status"],
                         "edition_status": status,
                         "what_to_check": ("not found in the September 2026 edition: check whether it was "
                                           "lifted, merged or renamed, then set review_decision"
                                           if status == "not_in_latest_edition" else
                                           "several 2026 entries could be this record: choose one in "
                                           "review_decision, or none"),
                         "candidates_2026": cw.get("candidates_2026", ""),
                         "crosswalk_basis": cw.get("match_basis", "")})
    worklist.sort(key=lambda w: (w["kind"], w["state"], w["record_id"]))
    return records, worklist


def pin_ids(rows: list[dict], existing: list[dict], entity: str) -> None:
    """A row with a 2025 REC- id keeps the id it was published under: the
    existing Sabin seed row's pinned_id, or the id the build gave it
    (build_seed_outputs.record_id). Restrictions are matched per technology,
    a contested project by its record alone. A technology new to a record
    gets a new id."""
    from build_seed_outputs import normalize_row, record_id
    prior: dict[tuple[str, str], str] = {}
    for r in existing:
        if not (r.get("source") or "").startswith(SOURCE_PREFIX) or not r.get("source_record_id"):
            continue
        key = (r["source_record_id"], r.get("technology", "") if entity == "restrictions" else "")
        prior[key] = r.get("pinned_id") or record_id(entity, normalize_row(r))
    for r in rows:
        if r.pop("_pin", False):
            key = (r["source_record_id"], r.get("technology", "") if entity == "restrictions" else "")
            if key in prior:
                r["pinned_id"] = prior[key]


REVIEW_FIELDS_KEPT = ("case_name", "court", "court_level", "docket_number", "case_status",
                      "case_source_url", "review_status", "severity_score", "reviewer_notes")


def merge_candidates(generated: list[dict], existing: list[dict]) -> list[dict]:
    """Keep reviewer work across rebuilds. For a source record that already has
    rows in cases_candidates.csv (a reviewer may have split one project into
    several cases), keep those rows with their review fields and refresh the
    rest from the source; otherwise add the freshly generated blank row. A
    worked-on row whose record no longer generates a candidate is kept as it
    is."""
    by_rid: dict[str, list[dict]] = {}
    for row in existing:
        by_rid.setdefault(row.get("source_record_id", ""), []).append(row)
    out = []
    for gen in generated:
        prior = by_rid.pop(gen["source_record_id"], None)
        if not prior:
            out.append(gen)
            continue
        for row in prior:
            merged = dict(gen)
            merged.update({k: row[k] for k in REVIEW_FIELDS_KEPT if row.get(k)})
            out.append(merged)
    # A candidate a reviewer has worked on is never dropped, even when its
    # record no longer generates one (an edition that stopped recording it).
    for rows in by_rid.values():
        out += [r for r in rows if any(r.get(k) for k in REVIEW_FIELDS_KEPT if k != "review_status")
                or r.get("review_status") not in ("", None, "needs_docket_research")]
    return out


def carry_groups(generated: list[dict], existing: list[dict]) -> None:
    """Keep the reviewer's opposition_groups and group_sources on each rebuilt
    Sabin row (keyed on source_record_id and technology)."""
    old = {(r.get("source_record_id"), r.get("technology")): r for r in existing}
    for r in generated:
        prev = old.get((r.get("source_record_id"), r.get("technology")), {})
        for f in ("opposition_groups", "group_sources"):
            r[f] = prev.get(f, "") or r.get(f, "")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="report counts without writing files")
    args = ap.parse_args()

    crosswalk = read_csv(CROSSWALK_PATH)
    records, worklist = merge_editions(read_csv(RECORDS_PATH), read_csv(RECORDS_2025_PATH), crosswalk)
    existing = read_csv(RESTRICTIONS_PATH)
    kept = [r for r in existing if not (r.get("source") or "").startswith(SOURCE_PREFIX)]
    # promote_reviewed.py also appends to the contested seed (config/layers.json).
    # Keep its rows, as the restrictions seed keeps Moratorium Nation's.
    existing_contested = read_csv(CONTESTED_PATH)
    kept_contested = [r for r in existing_contested if not (r.get("source") or "").startswith(SOURCE_PREFIX)]

    contested, project_candidates, excluded = build_contested(
        records, case_rulings(read_csv(CASES_PATH)))
    carry_groups(contested, existing_contested)
    pin_ids(contested, existing_contested, "contested_projects")
    restrictions, review, restriction_candidates = build_restrictions(
        records, moratorium_nation_index(existing)
    )
    pin_ids(restrictions, existing, "restrictions")
    candidates = merge_candidates(
        sorted(project_candidates + restriction_candidates,
               key=lambda x: (x["state"], x["project_name"].lower())),
        read_csv(CANDIDATES_PATH),
    )

    editions: dict[str, int] = {}
    for r in records:
        editions[r["_edition_status"]] = editions.get(r["_edition_status"], 0) + 1
    changed = [c for c in crosswalk if c.get("status_changed") == "yes"]
    print("Records: " + ", ".join(f"{k}={v}" for k, v in sorted(editions.items()))
          + f"; {sum(1 for w in worklist if w['kind'] == '2026 entry held')} 2026 entries held for the crosswalk")
    print(f"Status changes in the 2026 edition: {len(changed)} matched record(s)")
    for c in changed[:20]:
        print(f"  {c['rec_id']} -> {c['entry_2026']} {c['name_2025']}: {c['status_2025']} -> {c['status_2026']}")
    if len(changed) > 20:
        print(f"  ... and {len(changed) - 20} more (status_changed in {CROSSWALK_PATH.name})")

    by_outcome: dict[str, int] = {}
    for row in contested:
        by_outcome[row["outcome"]] = by_outcome.get(row["outcome"], 0) + 1
    print(f"Contested projects: {len(contested)} rows, {len(excluded)} excluded")
    for line in excluded:
        print(f"  - excluded {line}")
    print("  outcomes: " + ", ".join(f"{k}={v}" for k, v in sorted(by_outcome.items())))

    by_sev: dict[int, int] = {}
    for row in restrictions:
        by_sev[row["severity_score"]] = by_sev.get(row["severity_score"], 0) + 1
    reasons: dict[str, int] = {}
    for row in review:
        reason = row["reason"].split(" (")[0].split(":")[0]
        reasons[reason] = reasons.get(reason, 0) + 1
    print(f"Restrictions (Sabin, local): {len(restrictions)} rows "
          f"from {len({r['source_record_id'] for r in restrictions})} source records; "
          "severity " + ", ".join(f"{k}={v}" for k, v in sorted(by_sev.items())))
    print(f"  held for review: {len(review)} ("
          + "; ".join(f"{k}={v}" for k, v in sorted(reasons.items())) + ")")
    print(f"  kept {len(kept)} restriction rows from other sources")
    print(f"  kept {len(kept_contested)} contested project rows from other sources")
    print(f"Case candidates: {len(candidates)} "
          f"({len(project_candidates)} projects, {len(restriction_candidates)} restrictions)")
    print(f"Edition worklist: {len(worklist)} rows")

    if args.dry_run:
        print("[dry-run] no files written")
        return
    write_csv(CONTESTED_PATH, kept_contested + contested, CONTESTED_FIELDS)
    write_csv(RESTRICTIONS_PATH, kept + restrictions, RESTRICTION_FIELDS)
    write_csv(CANDIDATES_PATH, candidates, CANDIDATE_FIELDS)
    write_csv(RESTRICTIONS_REVIEW_PATH, review, REVIEW_FIELDS)
    write_csv(EDITION_WORKLIST_PATH, worklist, EDITION_WORKLIST_FIELDS)
    print("Wrote " + ", ".join(str(p.relative_to(ROOT)) for p in (
        CONTESTED_PATH, RESTRICTIONS_PATH, CANDIDATES_PATH, RESTRICTIONS_REVIEW_PATH, EDITION_WORKLIST_PATH)))


if __name__ == "__main__":
    main()
