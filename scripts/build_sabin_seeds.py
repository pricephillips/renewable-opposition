"""Build seed rows from the Sabin-derived records in data/renewable_opposition_records.csv.

That file is an extraction of the Sabin Center's "Opposition to Renewable
Energy Facilities in the United States" report (June 2025 edition), one row per
entry, tagged by the report section it came from (``extraction_source_section``).
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
                                        duplicate a Moratorium Nation moratorium).

Contested projects
------------------
outcome         four-tier vocabulary from the plan doc, mapped from source status:
                  cancelled, rejected                   -> blocked_confirmed
                  approved, approved_after_opposition,
                  operational                           -> advanced_confirmed
                  pending, proposed                     -> pending
                  anything else (in_force, lifted,
                  unknown, blank)                       -> needs_review
                ``restricted_conditional`` is only set by hand.
severity_score  1-4 intensity of opposition against the project:
                  4  project blocked (outcome blocked_confirmed)
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
                unknown. lifted / cancelled rows are excluded, matching the
                Moratorium Nation rule that only in-force or pending instruments
                are restrictions.
restriction_type
                the most stringent mechanism present, in the order ban,
                moratorium, height_limit, setback, noise_limit, size_cap,
                zoning_restriction, siting_standard, other. The full list is kept
                in ``mechanisms``.
severity_score  (README scale) highest score any mechanism earns:
                  4  ban/prohibition, or an active/extended/unknown moratorium
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
                Moratorium Nation already has a moratorium for the same
                jurisdiction and technology (Moratorium Nation is maintained
                more recently); it is listed in the review file instead.

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

RECORDS_PATH = ROOT / "data" / "renewable_opposition_records.csv"
CONTESTED_PATH = SEED_DIR / "contested_projects_seed.csv"
RESTRICTIONS_PATH = SEED_DIR / "restrictions_seed.csv"
CANDIDATES_PATH = REVIEW_DIR / "cases_candidates.csv"
RESTRICTIONS_REVIEW_PATH = REVIEW_DIR / "sabin_restrictions_review.csv"

SOURCE_LABEL = (
    "Sabin Center, Opposition to Renewable Energy Facilities in the United States "
    "(June 2025 ed.), via data/renewable_opposition_records.csv"
)
SOURCE_URL = (
    "https://climate.law.columbia.edu/sites/default/files/content/"
    "Opposition-Report-June-2025.pdf"
)
MORATORIUM_NATION_LABEL = "Moratorium Nation (mjbommar/moratorium-data-2026), CC-BY-4.0"

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

OUTCOME = {
    "cancelled": "blocked_confirmed",
    "rejected": "blocked_confirmed",
    "approved": "advanced_confirmed",
    "approved_after_opposition": "advanced_confirmed",
    "operational": "advanced_confirmed",
    "pending": "pending",
    "proposed": "pending",
}

CONTESTED_FIELDS = [
    "state", "project_name", "technology", "severity_score", "description",
    "outcome", "status", "has_litigation", "opposition_type",
    "county", "municipality", "event_date_text", "capacity_mw", "area_acres",
    "long_description", "source_record_id", "source", "source_url", "notes",
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
    "ban", "moratorium", "height_limit", "setback", "noise_limit", "size_cap",
    "zoning_restriction", "siting_standard", "other",
]

RESTRICTION_STATUS = {
    "in_force": "active", "extended": "extended", "pending": "pending",
    "unknown": "unknown", "": "unknown",
}
EXCLUDED_STATUS = {"lifted", "cancelled"}

RESTRICTION_FIELDS = [
    "state", "technology", "restriction_type", "severity_score", "description",
    "status", "jurisdiction", "jurisdiction_type", "date_enacted_iso",
    "date_text", "mechanisms", "severity_basis", "long_description",
    "moratorium_id", "source_record_id", "source", "source_url", "notes",
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
    elif "moratorium" in types and status in ("active", "extended", "unknown"):
        score, basis = 4, "in-force moratorium"
    else:
        feet, mult = setback_feet(text), height_multiplier(text)
        if tech == "wind":
            if "setback" in types and (feet >= 2640 or mult >= 5):
                score, basis = 3, f"wind setback {int(feet)} ft / {mult:g}x height"
            elif "height_limit" in types:
                score, basis = 3, "wind height limit"
            elif "noise_limit" in types and 0 < min_noise_dba(text) <= 35:
                score, basis = 3, f"wind noise limit {min_noise_dba(text):g} dBA"
        elif "setback" in types and feet >= 1000:
            score, basis = 3, f"{tech} setback {int(feet)} ft"
    if status == "pending" and score > 2:
        score, basis = 2, basis + "; capped at 2 (pending)"
    return score, basis


def is_litigated(row: dict) -> bool:
    return row["has_litigation"].strip() == "yes" or "litigation" in row["opposition_type"]


# ── Builders ─────────────────────────────────────────────────────────────────

def build_contested(records: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    seed, candidates, excluded = [], [], []
    for r in records:
        if r["extraction_source_section"] != "contested_projects":
            continue
        rid = r["record_id"]
        if rid in PROJECT_EXCLUDE:
            excluded.append(f"{rid}: {PROJECT_EXCLUDE[rid]}")
            continue

        notes = [n for n in [r["notes"].strip()] if n]
        tech_raw = r["technology"]
        if rid in PROJECT_TECHNOLOGY_OVERRIDES:
            tech_raw = PROJECT_TECHNOLOGY_OVERRIDES[rid]
            notes.append("technology inferred from project name")
        technology = ";".join(technology_tokens(tech_raw))

        outcome = OUTCOME.get(r["status"].strip(), "needs_review")
        litigated = is_litigated(r)
        if outcome == "blocked_confirmed":
            severity = 4
        elif litigated:
            severity = 3
        elif outcome == "advanced_confirmed":
            severity = 1
        else:
            severity = 2
        row = {
            "state": state_code(r["state"]),
            "project_name": r["project_or_policy_name"].strip(),
            "technology": technology,
            "severity_score": severity,
            "description": r["short_description"].strip(),
            "outcome": outcome,
            "status": r["status"].strip(),
            "has_litigation": "yes" if litigated else r["has_litigation"].strip(),
            "opposition_type": r["opposition_type"].strip(),
            "county": r["county"].strip(),
            "municipality": r["municipality"].strip(),
            "event_date_text": r["adopted_or_event_date_text"].strip(),
            "capacity_mw": r["project_capacity_mw"].strip(),
            "area_acres": r["project_area_acres"].strip(),
            "long_description": r["long_description"].strip(),
            "source_record_id": rid,
            "source": SOURCE_LABEL,
            "source_url": SOURCE_URL,
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
    """(jurisdiction_key, technology) -> moratorium_id for Moratorium Nation rows."""
    index = {}
    for row in existing:
        if row.get("source") != MORATORIUM_NATION_LABEL:
            continue
        kind = jurisdiction_kind(row.get("jurisdiction_type", ""))
        key = jurisdiction_key(row["state"], kind, row.get("jurisdiction", ""))
        index[(key, row["technology"])] = row.get("moratorium_id", "")
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

        if rid in JURISDICTION_OVERRIDES:
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
        if set(mechanisms) & NON_RESTRICTING:
            hold("mechanism loosens local siting (preemption), not a restriction")
            continue
        status_raw = r["status"].strip()
        if status_raw in EXCLUDED_STATUS:
            hold(f"status {status_raw}: no longer in force")
            continue
        status = RESTRICTION_STATUS.get(status_raw)
        if status is None:
            raise SystemExit(f"{rid}: unmapped restriction status {status_raw!r}")

        unknown = [m for m in mechanisms if m not in MECHANISM_TYPE]
        if unknown:
            raise SystemExit(f"{rid}: unmapped mechanism(s) {unknown}")
        types = {MECHANISM_TYPE[m] for m in mechanisms}
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
            mn_id = mn_index.get((key, tech), "")
            if mn_id and types == {"moratorium"}:
                hold(f"duplicate of Moratorium Nation {mn_id}", tech)
                continue
            severity, basis = restriction_severity(
                types, tech, status, text_about(text, tech)
            )
            row_notes = list(notes)
            if mn_id:
                row_notes.append(f"Moratorium Nation also lists a moratorium here ({mn_id})")
            seed.append({
                "state": st,
                "technology": tech,
                "restriction_type": restriction_type,
                "severity_score": severity,
                "description": r["short_description"].strip(),
                "status": status,
                "jurisdiction": jurisdiction,
                "jurisdiction_type": jurisdiction_type,
                "date_enacted_iso": "",
                "date_text": r["adopted_or_event_date_text"].strip(),
                "mechanisms": ", ".join(mechanisms),
                "severity_basis": basis,
                "long_description": r["long_description"].strip(),
                "moratorium_id": "",
                "source_record_id": rid,
                "source": SOURCE_LABEL,
                "source_url": SOURCE_URL,
                "notes": "; ".join(row_notes),
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


REVIEW_FIELDS_KEPT = ("case_name", "court", "court_level", "docket_number", "case_status",
                      "case_source_url", "review_status", "severity_score", "reviewer_notes")


def merge_candidates(generated: list[dict], existing: list[dict]) -> list[dict]:
    """Keep reviewer work across rebuilds. For a source record that already has
    rows in cases_candidates.csv (a reviewer may have split one project into
    several cases), keep those rows with their review fields and refresh the
    rest from the source; otherwise add the freshly generated blank row."""
    by_rid: dict[str, list[dict]] = {}
    for row in existing:
        by_rid.setdefault(row.get("source_record_id", ""), []).append(row)
    out = []
    for gen in generated:
        prior = by_rid.get(gen["source_record_id"])
        if not prior:
            out.append(gen)
            continue
        for row in prior:
            merged = dict(gen)
            merged.update({k: row[k] for k in REVIEW_FIELDS_KEPT if row.get(k)})
            out.append(merged)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="report counts without writing files")
    args = ap.parse_args()

    records = read_csv(RECORDS_PATH)
    existing = read_csv(RESTRICTIONS_PATH)
    kept = [r for r in existing if r.get("source") != SOURCE_LABEL]

    contested, project_candidates, excluded = build_contested(records)
    restrictions, review, restriction_candidates = build_restrictions(
        records, moratorium_nation_index(existing)
    )
    candidates = merge_candidates(
        sorted(project_candidates + restriction_candidates,
               key=lambda x: (x["state"], x["project_name"].lower())),
        read_csv(CANDIDATES_PATH),
    )

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
    print(f"Case candidates: {len(candidates)} "
          f"({len(project_candidates)} projects, {len(restriction_candidates)} restrictions)")

    if args.dry_run:
        print("[dry-run] no files written")
        return
    write_csv(CONTESTED_PATH, contested, CONTESTED_FIELDS)
    write_csv(RESTRICTIONS_PATH, kept + restrictions, RESTRICTION_FIELDS)
    write_csv(CANDIDATES_PATH, candidates, CANDIDATE_FIELDS)
    write_csv(RESTRICTIONS_REVIEW_PATH, review, REVIEW_FIELDS)
    print("Wrote " + ", ".join(str(p.relative_to(ROOT)) for p in (
        CONTESTED_PATH, RESTRICTIONS_PATH, CANDIDATES_PATH, RESTRICTIONS_REVIEW_PATH)))


if __name__ == "__main__":
    main()
