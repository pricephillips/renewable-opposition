"""build_seed_outputs.py

Reads data/seed/sabin_seed_examples.csv, splits by entity_type,
normalizes each subset, and writes CSV + JSON to data/processed/.

Usage:
    python scripts/build_seed_outputs.py

Outputs:
    data/processed/restrictions.csv / restrictions.json
    data/processed/contested_projects.csv / contested_projects.json
    data/processed/cases.csv / cases.json
"""

import json
import sys
from pathlib import Path

import pandas as pd
from dateutil.parser import parse as parse_date

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "data" / "seed" / "sabin_seed_examples.csv"
OUT  = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Column subsets per entity type (stable order, no extras)
# ---------------------------------------------------------------------------
COLS = {
    "restriction": [
        "state", "county", "municipality", "jurisdiction_type",
        "technology", "restriction_type",
        "severity_score", "adopted_date", "effective_date",
        "description", "source_url",
    ],
    "contested_project": [
        "state", "county", "municipality", "jurisdiction_type",
        "project_name", "developer", "technology", "capacity_mw",
        "severity_score", "first_event_date", "opposition_type",
        "description", "source_url",
    ],
    "case": [
        "state", "county", "municipality", "jurisdiction_type",
        "project_name", "technology", "court_level",
        "severity_score", "filing_date",
        "description", "source_url",
    ],
}

DATE_COLS = {
    "restriction":        ["adopted_date", "effective_date"],
    "contested_project":  ["first_event_date"],
    "case":               ["filing_date"],
}

OUT_NAME = {
    "restriction":       "restrictions",
    "contested_project": "contested_projects",
    "case":              "cases",
}


def normalize_date(val: str) -> str:
    """Return ISO YYYY-MM-DD string or empty string."""
    if not val or str(val).strip() == "":
        return ""
    try:
        return parse_date(str(val).strip()).strftime("%Y-%m-%d")
    except Exception:
        return ""


def normalize(df: pd.DataFrame, entity: str) -> pd.DataFrame:
    # Strip whitespace from all string columns
    str_cols = df.select_dtypes(include="object").columns
    df[str_cols] = df[str_cols].apply(lambda c: c.str.strip())

    # Parse dates
    for col in DATE_COLS[entity]:
        if col in df.columns:
            df[col] = df[col].apply(normalize_date)

    # Select and reorder columns; add missing ones as empty string
    cols = COLS[entity]
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols].copy()


def write(df: pd.DataFrame, stem: str) -> None:
    csv_path  = OUT / f"{stem}.csv"
    json_path = OUT / f"{stem}.json"

    df.to_csv(csv_path, index=False)

    # Replace NaN with empty string so JSON is clean
    records = df.fillna("").to_dict(orient="records")
    json_path.write_text(json.dumps(records, indent=2))

    print(f"  {stem}: {len(df)} rows → {csv_path.name}, {json_path.name}")


def main() -> None:
    if not SEED.exists():
        print(f"ERROR: seed file not found: {SEED}", file=sys.stderr)
        sys.exit(1)

    raw = pd.read_csv(SEED, dtype=str).fillna("")
    raw.columns = raw.columns.str.strip()

    print(f"Loaded {len(raw)} seed rows from {SEED.name}")

    for entity, stem in OUT_NAME.items():
        subset = raw[raw["entity_type"].str.strip() == entity].copy()
        if subset.empty:
            print(f"  {stem}: 0 rows (skipped)")
            continue
        normalized = normalize(subset.reset_index(drop=True), entity)
        write(normalized, stem)

    print("Done.")


if __name__ == "__main__":
    main()
