"""Validate the seed CSVs and write the canonical outputs in data/processed/.

For each entity (restrictions, contested_projects, cases) with a seed file:
  - checks required fields, the 1-4 severity scale, the state code and that
    every row has a source_url (the README's provenance-first rule);
  - normalizes state to its two-letter code;
  - assigns a stable ``id`` (see record_id) and a ``source_id``;
  - writes data/processed/<entity>.csv and <entity>.json.

Rows that pass validation then go through the QC gate (scripts/qc_gate.py).
A row with a HIGH or CRITICAL finding is quarantined: left out of the entity
outputs and written, with its issues, to data/processed/quarantine.json.
data/processed/qc_report.md summarizes every finding.

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
import qc_gate  # noqa: E402
from common import (  # noqa: E402
    PROCESSED_DIR, SEED_DIR, normalize_url, read_csv, source_id_for, state_code, write_csv,
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

SOURCE_FIELDS = ["source_id", "url", "normalized_url", "title", "record_count", "entities"]


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


def build_entity(entity: str, filename: str) -> tuple[list[dict] | None, list[str]]:
    src = SEED_DIR / filename
    if not src.exists():
        print(f"Skipping missing {src.relative_to(SEED_DIR.parent.parent)}")
        return None, []
    rows = [normalize_row(r) for r in read_csv(src)]
    errors = validate(entity, filename, rows)
    seen: dict[str, int] = {}
    for i, row in enumerate(rows, start=2):
        rid = record_id(entity, row)
        if rid in seen:
            errors.append(f"{filename}: row {i} duplicates row {seen[rid]} (same source, key and technology)")
        seen[rid] = i
        row["id"] = rid
        if row.get("source_url"):
            row["source_id"] = source_id_for(row["source_url"])
    return rows, errors


def collect_sources(datasets: dict[str, list[dict]]) -> list[dict]:
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
                })
                s["record_count"] += 1
                s["entities"].add(entity)
    out = []
    for s in sorted(sources.values(), key=lambda s: (-s["record_count"], s["url"])):
        out.append({**s, "entities": ";".join(sorted(s["entities"]))})
    return out


def json_records(rows: list[dict]) -> list[dict]:
    """JSON rows carry a ``sources`` array the dashboard renders as links."""
    out = []
    for row in rows:
        rec = dict(row)
        links = []
        if row.get("source_url"):
            links.append({"title": row.get("source") or "Source", "url": row["source_url"]})
        if row.get("case_source_url") and row.get("case_source_url") != row.get("source_url"):
            links.append({"title": row.get("case_name") or "Case record", "url": row["case_source_url"]})
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
    for entity, filename in ENTITIES.items():
        rows, errs = build_entity(entity, filename)
        errors.extend(errs)
        if rows is not None:
            datasets[entity] = rows
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

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    write_json(PROCESSED_DIR / "quarantine.json", quarantine)
    (PROCESSED_DIR / "qc_report.md").write_text(qc_gate.render_report(findings, totals), encoding="utf-8")
    print(f"QC: {len(quarantine)} quarantined, "
          f"{sum(1 for f in findings if not f['blocked'])} with non-blocking findings")
    for entity, rows in datasets.items():
        preferred = ["id"] + list(rows[0].keys()) if rows else ["id"]
        write_csv(PROCESSED_DIR / f"{entity}.csv", rows, preferred)
        write_json(PROCESSED_DIR / f"{entity}.json", json_records(rows))
        print(f"Wrote data/processed/{entity}.csv/.json ({len(rows)} records)")

    sources = collect_sources(datasets)
    write_csv(PROCESSED_DIR / "sources.csv", sources, SOURCE_FIELDS)
    write_json(PROCESSED_DIR / "sources.json", sources)
    print(f"Wrote data/processed/sources.csv/.json ({len(sources)} sources)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
