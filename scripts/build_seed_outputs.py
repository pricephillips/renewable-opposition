"""Validate the seed CSVs and write the canonical outputs in data/processed/.

For each entity (restrictions, contested_projects, cases) with a seed file:
  - checks required fields, the 1-4 severity scale, the state code and that
    every row has a source_url (the README's provenance-first rule);
  - normalizes state to its two-letter code;
  - assigns a stable ``id`` (see record_id; a seed row's ``pinned_id``, set
    by promote_reviewed.py, wins) and a ``source_id``;
  - writes data/processed/<entity>.csv and <entity>.json.

Rows that pass validation then go through the QC gate (scripts/qc_gate.py).
A row with a HIGH or CRITICAL finding is quarantined: left out of the entity
outputs and written, with its issues, to data/processed/quarantine.json.
data/processed/qc_report.md summarizes every finding.

Restrictions and contested projects get a derived ``county_fips``
(classify.county_fips, from the lookup copied into data/county_fips_lookup.json).
Every published row that should have one and does not is listed, with its
reason, in data/review/fips_misses.csv; nothing is guessed.

It also writes data/processed/sources.csv / sources.json: one row per distinct
source document, keyed by ``source_id`` (a hash of the normalized URL, so the
same document cited by many records, or with a trailing slash or #fragment, is
stored once).

Exits non-zero, writing nothing, if any seed row fails validation.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import classify  # noqa: E402
import geo  # noqa: E402
import headline_metrics  # noqa: E402
import qc_gate  # noqa: E402
import resolutions  # noqa: E402
from common import (  # noqa: E402
    PROCESSED_DIR, REVIEW_DIR, ROOT, STATE_NAMES, SEED_DIR, normalize_url, read_csv, source_id_for,
    state_code, write_csv,
)

ENTITIES = {
    "restrictions": "restrictions_seed.csv",
    "contested_projects": "contested_projects_seed.csv",
    "cases": "cases_seed.csv",
}

REQUIRED = {
    "restrictions": ["state", "technology", "restriction_type", "severity_score", "description", "source_url"],
    "contested_projects": ["state", "project_name", "technology", "severity_score", "description", "source_url"],
    "cases": ["state", "project_name", "technology", "court_level", "severity_score", "description", "source_url"],
}

# Fields that identify a row within its source, in order of preference.
ROW_KEY_FIELDS = ["case_id", "moratorium_id", "source_record_id"]

INT_FIELDS = {"severity_score"}
FLOAT_FIELDS = {"latitude", "longitude"}

SOURCE_FIELDS = ["source_id", "url", "normalized_url", "title", "record_count", "entities",
                 "archived_url"]
# Written by scripts/source_archive.py (weekly, in Actions). Read here so each
# source carries its Internet Archive snapshot; absent until the first run.
ARCHIVE_PATH = SEED_DIR.parent / "source_archive.csv"
# County FIPS lookup, copied from pricephillips/data-center-map (passoff B4).
FIPS_LOOKUP = ROOT / "data" / "county_fips_lookup.json"
# Town/township name -> county, from the Census Gazetteer (scripts/build_place_index.py).
# Optional: without it, town-level records with no coordinates stay unplaced.
PLACE_INDEX = ROOT / "data" / "place_county_index.json"
# Published rows that need a county FIPS and have none; one row per record.
FIPS_MISSES = REVIEW_DIR / "fips_misses.csv"
FIPS_MISS_FIELDS = ["entity", "id", "instrument_id", "state", "county_name", "reason", "county_fips_all"]
# Cases carry no county of their own; a page places a case at its project.
FIPS_ENTITIES = ("restrictions", "contested_projects")


def load_fips_lookup(path: Path | None = None) -> dict[str, str]:
    """'<county>|<state name>' -> FIPS. Keys starting with '_' are comments."""
    path = path or FIPS_LOOKUP
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k.strip().lower(): str(v) for k, v in data.items() if not k.startswith("_")}


def load_place_index(path: Path | None = None) -> dict[str, list[str]]:
    path = path or PLACE_INDEX
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def stamp_fips(entity: str, rows: list[dict], lookup: dict[str, str],
               places: dict[str, list[str]] | None = None) -> None:
    """county_fips: the one county a county-level record covers (the map paints
    it). county_fips_all: every county the record touches, ';'-joined, for
    finding records by place (scripts/site_profile.py); county_fips_method says
    how they were found (classify's module docstring lists the methods).
    Reviewer overrides (data/review/place_overrides.csv) are laid over these
    in main, once every entity is built."""
    if places is None:
        places = load_place_index()
    for row in rows:
        fips, _ = classify.county_fips(entity, row, lookup, STATE_NAMES)
        row["county_fips"] = fips or None
        found, method = classify.county_fips_all(entity, row, lookup, STATE_NAMES, geo.county_at, places)
        row["county_fips_all"] = ";".join(found) or None
        row["county_fips_method"] = method or None


def fips_misses(datasets: dict[str, list[dict]], lookup: dict[str, str]) -> list[dict]:
    out = []
    for entity, rows in datasets.items():
        if entity not in FIPS_ENTITIES:
            continue
        for row in rows:
            fips, reason = classify.county_fips(entity, row, lookup, STATE_NAMES)
            if reason:
                out.append({"entity": entity, "id": row.get("id"),
                            "instrument_id": row.get("instrument_id"), "state": row.get("state"),
                            "county_name": classify.county_name(entity, row), "reason": reason,
                            "county_fips_all": row.get("county_fips_all")})
    return sorted(out, key=lambda r: (r["entity"], r["state"] or "", r["county_name"] or "", r["id"]))


def archived_urls(path: Path | None = None) -> dict[str, str]:
    """url -> Wayback URL for every source with a confirmed 200 capture."""
    path = path or ARCHIVE_PATH
    if not path.exists():
        return {}
    return {r["url"]: r["archived_url"] for r in read_csv(path)
            if r.get("status") == "archived" and r.get("archived_url")}


def clean(v):
    v = (v or "").strip()
    return v if v else None


def record_id(entity: str, row: dict) -> str:
    """Stable id: entity prefix + hash of the row's key within its source and
    its technology. Re-running the build never renumbers records. A case row's
    key includes both its case_id and the project record it is linked to, since
    one case can concern two source records."""
    key = "|".join(row[f] for f in ROW_KEY_FIELDS if row.get(f)) or None
    if key is None:
        key = "|".join(str(row.get(f) or "") for f in ("state", "project_name", "jurisdiction", "description"))
    raw = f"{entity}|{row.get('source_url')}|{key}|{row.get('technology')}"
    return f"{entity[:3]}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:10]}"


def normalize_row(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        key = (k or "").strip()
        if not key:
            continue
        val = clean(v)
        if val is not None and key in INT_FIELDS:
            try:
                val = int(val)
            except ValueError:
                pass
        if val is not None and key in FLOAT_FIELDS:
            try:
                val = float(val)
            except ValueError:
                pass
        out[key] = val
    return out


def validate(entity: str, filename: str, rows: list[dict]) -> list[str]:
    errors = []
    for i, row in enumerate(rows, start=2):
        where = f"{filename}: row {i}"
        missing = [f for f in REQUIRED[entity] if row.get(f) in (None, "")]
        if missing:
            errors.append(f"{where} missing required fields: {', '.join(missing)}")
        sev = row.get("severity_score")
        if sev is not None and (not isinstance(sev, int) or not 1 <= sev <= 4):
            errors.append(f"{where} severity_score {sev!r} is not an integer 1-4")
        if row.get("state"):
            try:
                row["state"] = state_code(row["state"])
            except ValueError as exc:
                errors.append(f"{where} {exc}")
    return errors


def build_entity(entity: str, filename: str,
                 fips_lookup: dict[str, str] | None = None) -> tuple[list[dict] | None, list[str]]:
    src = SEED_DIR / filename
    if not src.exists():
        print(f"Skipping missing {src.relative_to(SEED_DIR.parent.parent)}")
        return None, []
    rows = [normalize_row(r) for r in read_csv(src)]
    errors = validate(entity, filename, rows)
    seen: dict[str, int] = {}
    for i, row in enumerate(rows, start=2):
        # A promoted review-queue row keeps the id it was first published
        # under (promote_reviewed.py pins it), so a corrected description or
        # source URL never renumbers it.
        rid = row.get("pinned_id") or record_id(entity, row)
        if rid in seen:
            errors.append(f"{filename}: row {i} duplicates row {seen[rid]} (same source, key and technology)")
        seen[rid] = i
        row["id"] = rid
        if row.get("source_url"):
            row["source_id"] = source_id_for(row["source_url"])
        classify.stamp(entity, row)
    # Reviewer evidence, then re-derive: a resolution changes the outcome or
    # adds a primary source, which changes evidence_level.
    if entity == "contested_projects":
        errors += resolutions.apply_outcomes(rows, qc_gate.VOCAB[entity]["outcome"])
    elif entity == "restrictions":
        errors += resolutions.apply_restriction_sources(rows)
    for row in rows:
        classify.stamp(entity, row)
    if fips_lookup is not None and entity in FIPS_ENTITIES:
        stamp_fips(entity, rows, fips_lookup)
    return rows, errors


def collect_sources(datasets: dict[str, list[dict]], archive: dict[str, str] | None = None) -> list[dict]:
    archive = archive or {}
    sources: dict[str, dict] = {}
    for entity, rows in datasets.items():
        for row in rows:
            for url_field, title_field in (("source_url", "source"), ("case_source_url", None)):
                url = row.get(url_field)
                if not url:
                    continue
                sid = source_id_for(url)
                s = sources.setdefault(sid, {
                    "source_id": sid,
                    "url": url,
                    "normalized_url": normalize_url(url),
                    "title": (row.get(title_field) if title_field else None) or "",
                    "record_count": 0,
                    "entities": set(),
                    "archived_url": archive.get(url, ""),
                })
                s["record_count"] += 1
                s["entities"].add(entity)
    out = []
    for s in sorted(sources.values(), key=lambda s: (-s["record_count"], s["url"])):
        out.append({**s, "entities": ";".join(sorted(s["entities"]))})
    return out


def json_records(rows: list[dict], archive: dict[str, str] | None = None) -> list[dict]:
    """JSON rows carry a ``sources`` array the dashboard renders as links, each
    with its Internet Archive snapshot when one is confirmed."""
    archive = archive or {}

    def link(title: str, url: str) -> dict:
        out = {"title": title, "url": url}
        if archive.get(url):
            out["archived_url"] = archive[url]
        return out

    out = []
    for row in rows:
        rec = dict(row)
        links = []
        if row.get("source_url"):
            links.append(link(row.get("source") or "Source", row["source_url"]))
        if row.get("case_source_url") and row.get("case_source_url") != row.get("source_url"):
            links.append(link(row.get("case_name") or "Case record", row["case_source_url"]))
        rec["sources"] = links
        out.append(rec)
    return out


def write_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> int:
    datasets: dict[str, list[dict]] = {}
    errors: list[str] = []
    fips_lookup = load_fips_lookup()
    for entity, filename in ENTITIES.items():
        rows, errs = build_entity(entity, filename, fips_lookup)
        errors.extend(errs)
        if rows is not None:
            datasets[entity] = rows
    # Reviewer counties go last, over whatever classify.county_fips_all found.
    errors += resolutions.apply_place_overrides(datasets, geo.known)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        print(f"{len(errors)} validation error(s); nothing written.", file=sys.stderr)
        return 1

    quarantine, findings, totals = [], [], {}
    for entity in list(datasets):
        totals[entity] = len(datasets[entity])
        passed, held, found = qc_gate.run(entity, datasets[entity])
        datasets[entity] = passed
        quarantine.extend({"entity": entity, **r} for r in held)
        findings.extend(found)

    archive = archived_urls()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    write_json(PROCESSED_DIR / "quarantine.json", quarantine)
    (PROCESSED_DIR / "qc_report.md").write_text(qc_gate.render_report(findings, totals), encoding="utf-8")
    print(f"QC: {len(quarantine)} quarantined, "
          f"{sum(1 for f in findings if not f['blocked'])} with non-blocking findings")
    for entity, rows in datasets.items():
        preferred = ["id"] + [k for k in rows[0] if k != "id"] if rows else ["id"]
        write_csv(PROCESSED_DIR / f"{entity}.csv", rows, preferred)
        write_json(PROCESSED_DIR / f"{entity}.json", json_records(rows, archive))
        print(f"Wrote data/processed/{entity}.csv/.json ({len(rows)} records)")

    metrics = headline_metrics.compute(datasets)
    write_json(PROCESSED_DIR / "headline_metrics.json", metrics)
    (PROCESSED_DIR / "headline_metrics.md").write_text(headline_metrics.render(metrics), encoding="utf-8")
    ren = metrics["restrictions"]["by_scope"]["renewables_only"]
    print(f"Headline: {ren['instruments']} renewables-only restrictions "
          f"({ren['severe_instruments']} severe), "
          f"{metrics['restrictions']['by_scope']['multi_sector_data_centers']['instruments']} "
          f"also covering data centers; {metrics['contested_projects']['projects']} projects, "
          f"{metrics['contested_projects']['confirmed_outcomes']} confirmed")

    misses = fips_misses(datasets, fips_lookup)
    write_csv(FIPS_MISSES, misses, FIPS_MISS_FIELDS)
    for entity in FIPS_ENTITIES:
        need = [r for r in datasets.get(entity, []) if classify.county_name(entity, r) is not None]
        hit = sum(1 for r in need if r.get("county_fips"))
        print(f"county_fips: {entity} {hit}/{len(need)} rows with a county have a FIPS")
    print(f"Wrote data/review/fips_misses.csv ({len(misses)} misses)")

    sources = collect_sources(datasets, archive)
    write_csv(PROCESSED_DIR / "sources.csv", sources, SOURCE_FIELDS)
    write_json(PROCESSED_DIR / "sources.json", sources)
    print(f"Wrote data/processed/sources.csv/.json ({len(sources)} sources)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
