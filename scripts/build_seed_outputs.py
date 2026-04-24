"""
build_seed_outputs.py
---------------------
Read data/seed/sabin_seed_examples.csv, split by entity_type, normalize,
and write CSV + JSON into data/processed/.

Produces:
    data/processed/restrictions.csv / .json
    data/processed/contested_projects.csv / .json
    data/processed/cases.csv / .json
    data/processed/sources.csv / .json
    data/processed/entity_source_links.csv / .json
"""

import json
import sys
from pathlib import Path

import pandas as pd
from dateutil.parser import parse as parse_date

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_PATH = REPO_ROOT / "data" / "seed" / "sabin_seed_examples.csv"
OUT_DIR = REPO_ROOT / "data" / "processed"

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
SOURCE_COLS = [
    "source_id", "url", "publisher", "document_type",
    "crawl_date", "content_hash", "title",
]
ENTITY_LINK_COLS = [
    "entity_type", "entity_local_id", "source_id",
]

DATE_FIELDS = {"adopted_date", "effective_date", "filing_date", "first_event_date"}


def normalize_date(value: str) -> str:
    if not value or not str(value).strip():
        return ""
    try:
        return parse_date(str(value).strip()).date().isoformat()
    except ValueError:
        return ""


def load_and_clean(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
    for col in DATE_FIELDS:
        if col in df.columns:
            df[col] = df[col].apply(normalize_date)
    if "severity_score" in df.columns:
        df["severity_score"] = pd.to_numeric(df["severity_score"], errors="coerce").astype("Int64")
    return df


def select_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
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
    print(f"  {stem}: {len(df)} records -> {csv_path.name}, {json_path.name}")


def build_sources(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Derive a sources table from all distinct non-empty source_url values in
    the seed CSV. Assigns stable IDs SRC001, SRC002, ... sorted by URL.
    Publisher, document_type, crawl_date, content_hash, title are left empty
    for the crawler/parser layer to backfill.
    """
    urls = (
        raw["source_url"]
        .dropna()
        .loc[lambda s: s.str.strip() != ""]
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )
    sources = pd.DataFrame({
        "source_id": [f"SRC{i+1:03d}" for i in range(len(urls))],
        "url": urls,
        "publisher": "",
        "document_type": "",
        "crawl_date": "",
        "content_hash": "",
        "title": "",
    })
    return sources


def build_entity_source_links(
    entity_type: str,
    entity_df: pd.DataFrame,
    sources: pd.DataFrame,
) -> pd.DataFrame:
    """
    For each row in entity_df, look up its source_url in the sources table
    and emit (entity_type, entity_local_id, source_id).
    entity_local_id is the 0-based row index within that entity's table.
    """
    url_to_sid = dict(zip(sources["url"], sources["source_id"]))
    rows = []
    for local_id, row in entity_df.reset_index(drop=True).iterrows():
        url = str(row.get("source_url", "")).strip()
        sid = url_to_sid.get(url, "")
        if sid:
            rows.append({
                "entity_type": entity_type,
                "entity_local_id": local_id,
                "source_id": sid,
            })
    return pd.DataFrame(rows, columns=ENTITY_LINK_COLS)


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

    # Sources table
    sources = build_sources(raw)
    write_outputs(select_cols(sources, SOURCE_COLS), "sources")

    # Entity-source links
    links = pd.concat([
        build_entity_source_links("restriction", select_cols(restrictions, RESTRICTION_COLS), sources),
        build_entity_source_links("contested_project", select_cols(contested, CONTESTED_PROJECT_COLS), sources),
        build_entity_source_links("case", select_cols(cases, CASE_COLS), sources),
    ], ignore_index=True)
    write_outputs(links, "entity_source_links")

    print("Done. Outputs in data/processed/")


if __name__ == "__main__":
    main()
