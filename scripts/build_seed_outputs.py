"""
build_seed_outputs.py
---------------------
Read data/seed/sabin_seed_examples.csv, split by entity_type, normalize,
and write CSV + JSON into data/processed/.

Produces:
    data/processed/restrictions.csv / .json
    data/processed/contested_projects.csv / .json
    data/processed/cases.csv / .json
"""

import json
import sys
from pathlib import Path

import pandas as pd
from dateutil.parser import parse as parse_date

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_PATH = REPO_ROOT / "data" / "seed" / "sabin_seed_examples.csv"
OUT_DIR = REPO_ROOT / "data" / "processed"

# Column subsets for each entity — canonical order, no extras.
RESTRICTION_COLS = [
    "state", "county", "municipality", "jurisdiction_type",
    "technology", "restriction_type", "severity_score",
    "adopted_date", "effective_date",
    "description", "source_url",
]
CONTESTED_PROJECT_COLS = [
    "state", "county", "municipality", "jurisdiction_type",
    "project_name", "technology",
    "severity_score", "first_event_date",
    "opposition_type", "status",
    "description", "source_url",
]
CASE_COLS = [
    "state", "county", "municipality", "jurisdiction_type",
    "project_name", "technology",
    "severity_score", "filing_date",
    "court_level", "status",
    "description", "source_url",
]

DATE_FIELDS = {"adopted_date", "effective_date", "filing_date", "first_event_date"}


def normalize_date(value: str) -> str:
    """Return ISO YYYY-MM-DD string or empty string."""
    if not value or not str(value).strip():
        return ""
    try:
        return parse_date(str(value).strip()).date().isoformat()
    except ValueError:
        return ""


def load_and_clean(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    # Strip whitespace from all string cells
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
    # Normalize all date columns
    for col in DATE_FIELDS:
        if col in df.columns:
            df[col] = df[col].apply(normalize_date)
    # severity_score: integer or empty
    if "severity_score" in df.columns:
        df["severity_score"] = pd.to_numeric(df["severity_score"], errors="coerce").astype("Int64")
    return df


def select_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Select columns that exist in df; fill missing ones with empty string."""
    for col in cols:
        if col not in df.columns:
            df[col] = ""
    return df[cols].copy()


def write_outputs(df: pd.DataFrame, stem: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / f"{stem}.csv"
    json_path = OUT_DIR / f"{stem}.json"
    df.to_csv(csv_path, index=False)
    records = df.fillna("").to_dict(orient="records")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)
    print(f"  {stem}: {len(df)} records → {csv_path.name}, {json_path.name}")


def main() -> None:
    if not SEED_PATH.exists():
        sys.exit(f"Seed file not found: {SEED_PATH}")

    raw = load_and_clean(SEED_PATH)
    if "entity_type" not in raw.columns:
        sys.exit("Seed CSV must have an 'entity_type' column.")

    entity_counts = raw["entity_type"].value_counts().to_dict()
    print(f"Loaded {len(raw)} seed rows: {entity_counts}")

    restrictions = raw[raw["entity_type"] == "restriction"].copy()
    contested = raw[raw["entity_type"] == "contested_project"].copy()
    cases = raw[raw["entity_type"] == "case"].copy()

    write_outputs(select_cols(restrictions, RESTRICTION_COLS), "restrictions")
    write_outputs(select_cols(contested, CONTESTED_PROJECT_COLS), "contested_projects")
    write_outputs(select_cols(cases, CASE_COLS), "cases")

    print("Done. Outputs in data/processed/")


if __name__ == "__main__":
    main()
