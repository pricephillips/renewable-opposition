"""The published siting_standards entity, built from NREL's stored workbooks.

One row per jurisdiction, technology and feature from NREL's 2025 wind and
solar ordinance databases, read from data/raw/ by nrel_ordinances.all_standards
(the schema guard runs first). build_seed_outputs.py calls build() and writes
data/processed/siting_standards.csv and .json. The JSON keeps JSON_FIELDS
only: NREL's summary text (13 MB in all), its name fields and the dataset
label are in the CSV.

Placement uses the existing county logic: classify.county_fips for a county
jurisdiction, classify.county_fips_all for every row (county name, town via
the Census place index, and NREL's own county code as the last resort,
method source_fips).

evidence_level is compiled_flagged on every row. verification is verified
only for a feature a reviewer confirmed against the ordinance itself (opened
or archived) in data/review/nrel_sample_review.csv (docs/AGENT_REVIEW.md);
every other row is unverified, whatever NREL says.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import classify  # noqa: E402
from common import REVIEW_DIR, STATE_NAMES, read_csv  # noqa: E402

SAMPLE_REVIEW_PATH = REVIEW_DIR / "nrel_sample_review.csv"
READ = ("opened", "archived")
OUT_FIELDS = [
    "id", "state", "jurisdiction", "jurisdiction_type", "nrel_jurisdiction_type", "county_fips",
    "county_fips_all", "county_fips_method", "technology", "feature", "value", "units", "setback_adder",
    "min_setback_ft", "max_setback_ft", "summary", "section", "ordinance_year", "ordinance_url",
    "nrel_fips_code", "county_name", "subdivision", "restricting", "restriction_instrument_id", "source",
    "source_url", "evidence_level", "verification", "verified_by",
]


def confirmed_features(path: Path | None = None) -> dict[str, str]:
    """standard_id -> reviewer, for features a reviewer confirmed against the
    ordinance, read (opened or archived), and who is not the drafter."""
    out = {}
    for r in read_csv(path or SAMPLE_REVIEW_PATH):
        if (r.get("verdict") == "confirmed" and r.get("access") in READ and r.get("standard_id")
                and r.get("reviewer")):
            out[r["standard_id"]] = r["reviewer"]
    return out


def build(lookup: dict[str, str], places: dict[str, list[str]] | None = None,
          seed: list[dict] | None = None, confirmed: dict[str, str] | None = None) -> list[dict]:
    if seed is None:
        import nrel_ordinances
        seed = nrel_ordinances.all_standards()
    rows = seed
    confirmed = confirmed_features() if confirmed is None else confirmed
    out = []
    for s in rows:
        r = dict(s)
        r["id"] = r.pop("standard_id")
        fips, _ = classify.county_fips("restrictions", r, lookup, STATE_NAMES)
        r["county_fips"] = fips
        found, method = classify.county_fips_all("restrictions", r, lookup, STATE_NAMES, None, places)
        r["county_fips_all"] = ";".join(found)
        r["county_fips_method"] = method
        r["restriction_instrument_id"] = f"nrel:{r['nrel_id']}" if r.get("nrel_restriction") == "yes" else ""
        r["evidence_level"] = "compiled_flagged"
        r["verification"] = "verified" if r["id"] in confirmed else "unverified"
        r["verified_by"] = confirmed.get(r["id"], "")
        out.append({k: r.get(k, "") for k in OUT_FIELDS})
    return out


# The JSON keeps what a downstream app needs to place and read a row; NREL's
# summary, its own name fields and the dataset label are in the CSV.
JSON_FIELDS = ["id", "state", "jurisdiction", "jurisdiction_type", "county_fips", "county_fips_all",
               "county_fips_method", "technology", "feature", "value", "units", "setback_adder", "min_setback_ft",
               "max_setback_ft", "section", "ordinance_year", "ordinance_url", "restriction_instrument_id",
               "source_url", "evidence_level", "verification", "verified_by"]


def json_records(rows: list[dict]) -> list[dict]:
    """JSON rows: JSON_FIELDS, empty values left out (24,000 rows)."""
    return [{k: r[k] for k in JSON_FIELDS if r.get(k) not in ("", None)} for r in rows]
