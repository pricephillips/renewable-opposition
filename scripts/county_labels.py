"""County labels for the county restriction model (predictive foundation, step 2).

One row per 2024 county in the 50 states and DC (the frame of
data/reference/county_covariates.csv), in data/model/county_labels.csv. The
labels are defined in config/county_model_registration.json, committed before
any model was fit; this module computes them and nothing else.

A restriction is severe when its severity_score is 3 or 4. A pending
instrument is already capped at 2 (README, "Restrictions: how severity is
assigned"), so only enacted ones count; NREL rows, whose status is "unknown",
count as in force, because NREL surveyed ordinances in effect. A restriction
touches every county in its county_fips_all: the county itself, or a place
within it. Its year is the year of date_enacted_iso, else the first four-digit
year in date_text; a severe restriction with neither is undated.

  new_severe_2022_2025  primary. Defined on the at-risk frame: counties with
                        no dated severe restriction before 2022 and no
                        undated one (at_risk_2022 = 1). 1 when the county's
                        first severe restriction is dated 2022 to 2025.
  new_severe_2026       the held-back out-of-time check: at-risk counties
                        whose first severe restriction is dated 2026.
  has_severe            secondary snapshot: any severe restriction.
  has_severity_4        secondary snapshot: any severity 4 restriction (bans
                        and moratoria).

For the registered sensitivity checks:

  nrel_at_risk_2022, nrel_new_severe_2022_2025
                        the primary label computed from NREL rows alone.
  positive_rests_on_nrel_year
                        1 when every severe restriction dated 2022 to 2025
                        that makes the county positive is an NREL row, whose
                        year may be the last amendment rather than enactment.

The other columns say where each label comes from: the first severe year, the
severe and severity 4 counts, and the sources behind them. Never edited by
hand; rebuilt from data/processed/restrictions.csv.

Usage
  python scripts/county_labels.py
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROCESSED_DIR, ROOT, read_csv, write_csv  # noqa: E402

RESTRICTIONS_PATH = PROCESSED_DIR / "restrictions.csv"
COVARIATES_PATH = ROOT / "data" / "reference" / "county_covariates.csv"
LABELS_PATH = ROOT / "data" / "model" / "county_labels.csv"

CUT_YEAR = 2022
WINDOW = (2022, 2025)
HOLDOUT_YEAR = 2026
SEVERE = {"3", "4"}

FIELDS = ["county_fips", "state", "county", "has_severe", "has_severity_4", "first_severe_year",
          "has_undated_severe", "at_risk_2022", "new_severe_2022_2025", "new_severe_2026",
          "nrel_at_risk_2022", "nrel_new_severe_2022_2025", "positive_rests_on_nrel_year",
          "n_severe", "n_severity_4", "severe_sources"]


def year_of(row: dict) -> int | None:
    for v in (row.get("date_enacted_iso"), row.get("date_text")):
        m = re.search(r"\b(1[89]\d\d|20\d\d)\b", v or "")
        if m:
            return int(m.group(1))
    return None


def is_nrel(row: dict) -> bool:
    return (row.get("source") or "").startswith("NREL")


def counties_of(row: dict) -> list[str]:
    return [f.strip() for f in re.split(r"[;,]", row.get("county_fips_all") or "") if f.strip()]


def window_label(rows: list[dict]) -> tuple[int, int, int]:
    """(at_risk_2022, new_severe_2022_2025, new_severe_2026) for one county's
    severe rows. Not at risk: any undated row, or a dated row before 2022."""
    years = [year_of(r) for r in rows]
    if any(y is None for y in years) or any(y < CUT_YEAR for y in years):
        return 0, 0, 0
    first = min(years) if years else None
    return (1, int(first is not None and WINDOW[0] <= first <= WINDOW[1]),
            int(first == HOLDOUT_YEAR))


def label_rows(restrictions: list[dict], frame: list[dict]) -> list[dict]:
    severe = defaultdict(list)
    for r in restrictions:
        if r.get("severity_score") in SEVERE:
            for f in counties_of(r):
                severe[f].append(r)
    out = []
    for c in frame:
        f = c["county_fips"]
        rows = severe.get(f, [])
        years = [y for y in (year_of(r) for r in rows) if y is not None]
        at_risk, new, holdout = window_label(rows)
        n_at_risk, n_new, _ = window_label([r for r in rows if is_nrel(r)])
        in_window = [r for r in rows if (year_of(r) or 0) in range(WINDOW[0], WINDOW[1] + 1)]
        sources = sorted({(r.get("source") or "").split(",")[0].split(" (")[0] for r in rows})
        out.append({
            "county_fips": f, "state": c["state"], "county": c["county"],
            "has_severe": int(bool(rows)),
            "has_severity_4": int(any(r["severity_score"] == "4" for r in rows)),
            "first_severe_year": min(years) if years else "",
            "has_undated_severe": int(any(year_of(r) is None for r in rows)),
            "at_risk_2022": at_risk, "new_severe_2022_2025": new, "new_severe_2026": holdout,
            "nrel_at_risk_2022": n_at_risk, "nrel_new_severe_2022_2025": n_new,
            "positive_rests_on_nrel_year": int(bool(new) and all(is_nrel(r) for r in in_window)),
            "n_severe": len(rows), "n_severity_4": sum(1 for r in rows if r["severity_score"] == "4"),
            "severe_sources": "; ".join(s for s in sources if s),
        })
    return out


def main() -> int:
    frame = read_csv(COVARIATES_PATH)
    rows = label_rows(read_csv(RESTRICTIONS_PATH), frame)
    write_csv(LABELS_PATH, rows, FIELDS)
    at_risk = [r for r in rows if r["at_risk_2022"]]
    print(f"Counties: {len(rows)}; has_severe {sum(r['has_severe'] for r in rows)}, "
          f"has_severity_4 {sum(r['has_severity_4'] for r in rows)}")
    print(f"At risk on 2022-01-01: {len(at_risk)}; new_severe_2022_2025 "
          f"{sum(r['new_severe_2022_2025'] for r in at_risk)}, new_severe_2026 "
          f"{sum(r['new_severe_2026'] for r in at_risk)}, positives resting on an NREL year only "
          f"{sum(r['positive_rests_on_nrel_year'] for r in at_risk)}")
    nrel = [r for r in rows if r["nrel_at_risk_2022"]]
    print(f"NREL-only frame: {len(nrel)} at risk, {sum(r['nrel_new_severe_2022_2025'] for r in nrel)} positive")
    print(f"Wrote {LABELS_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
