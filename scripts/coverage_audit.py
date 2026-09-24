"""Cross-check local renewables moratoria between the two sources this repo uses.

Neither source is complete, so each is used to measure the other's recall:

  * Sabin (data/renewable_opposition_records.csv, ``local_restrictions``
    section): every row whose mechanisms include a moratorium, any status.
  * Moratorium Nation (the full moratorium_inventory.csv, any status): every
    instrument whose sectors include solar, wind or battery_storage.

Rows are matched on state + jurisdiction kind + normalized jurisdiction name
(``common.jurisdiction_key``) and a shared technology. Moratorium Nation
instruments are split at the report's cut-off (SABIN_CUTOFF): the report
cannot contain moratoria adopted after it went to press, so only the earlier
ones count against its recall.

Writes:
  docs/coverage_audit.md             summary tables
  data/review/coverage_gaps.csv      every unmatched moratorium, for follow-up

Usage:
    python scripts/coverage_audit.py [--source-file moratorium_inventory.csv]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path

from build_sabin_seeds import (
    JURISDICTION_OVERRIDES, RECORDS_PATH, infer_technology,
)
from common import (
    REVIEW_DIR, ROOT, STATE_NAMES, jurisdiction_key, jurisdiction_kind, read_csv,
    state_code, technology_tokens, write_csv,
)
from fetch_moratorium_nation import TARGET_SECTORS, fetch_source_csv

SABIN_CUTOFF = "2025-01-31"  # latest adoption date the June 2025 edition covers
REPORT_PATH = ROOT / "docs" / "coverage_audit.md"
GAPS_PATH = REVIEW_DIR / "coverage_gaps.csv"
GAP_FIELDS = [
    "missing_from", "state", "jurisdiction", "technologies", "status",
    "date", "id", "description",
]


def sabin_moratoria(records: list[dict]) -> list[dict]:
    out = []
    for r in records:
        if r["extraction_source_section"] != "local_restrictions":
            continue
        if "moratorium" not in r["policy_mechanism"]:
            continue
        rid = r["record_id"]
        if rid in JURISDICTION_OVERRIDES:
            kind, name = JURISDICTION_OVERRIDES[rid]
        elif r["municipality"].strip():
            kind, name = "municipal", r["municipality"].strip()
        else:
            kind, name = "county", r["county"].strip()
        techs = [t for t in technology_tokens(r["technology"]) if t in TARGET_SECTORS]
        if not r["technology"].strip():
            techs = infer_technology(r["short_description"] + " " + r["long_description"])
        out.append({
            "id": rid,
            "state": state_code(r["state"]),
            "jurisdiction": name,
            "key": jurisdiction_key(r["state"], kind, name),
            "techs": set(techs),
            "status": r["status"],
            "date": r["adopted_or_event_date_text"],
            "description": r["short_description"],
        })
    return out


def mn_moratoria(csv_text: str) -> list[dict]:
    out = []
    for r in csv.DictReader(io.StringIO(csv_text)):
        try:
            sectors = set(json.loads(r["sectors"])) if r.get("sectors") else set()
        except json.JSONDecodeError:
            sectors = set()
        techs = sectors & TARGET_SECTORS
        if not techs:
            continue
        st = r.get("state_abbrev") or r["state"]
        kind = jurisdiction_kind(r.get("jurisdiction_type", ""))
        out.append({
            "id": r["moratorium_id"],
            "state": state_code(st),
            "jurisdiction": r["jurisdiction"],
            "key": jurisdiction_key(st, kind, r["jurisdiction"]),
            "techs": techs,
            "status": r.get("enacted_status", ""),
            "date": r.get("date_enacted_iso", ""),
            "description": (r.get("trigger") or "")[:300],
        })
    return out


def matches(a: dict, others: dict[str, list[dict]]) -> bool:
    return any(a["techs"] & b["techs"] for b in others.get(a["key"], []))


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "n/a"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-file", type=Path, help="local copy of moratorium_inventory.csv")
    args = ap.parse_args()

    csv_text = (args.source_file.read_text(encoding="utf-8-sig")
                if args.source_file else fetch_source_csv())
    sabin = sabin_moratoria(read_csv(RECORDS_PATH))
    mn = mn_moratoria(csv_text)

    by_key_s: dict[str, list[dict]] = defaultdict(list)
    by_key_m: dict[str, list[dict]] = defaultdict(list)
    for s in sabin:
        by_key_s[s["key"]].append(s)
    for m in mn:
        by_key_m[m["key"]].append(m)

    sabin_hit = [s for s in sabin if matches(s, by_key_m)]
    sabin_miss = [s for s in sabin if not matches(s, by_key_m)]
    mn_window = [m for m in mn if m["date"] and m["date"][:10] <= SABIN_CUTOFF]
    mn_window_hit = [m for m in mn_window if matches(m, by_key_s)]
    mn_window_miss = [m for m in mn_window if not matches(m, by_key_s)]
    mn_later = [m for m in mn if not (m["date"] and m["date"][:10] <= SABIN_CUTOFF)]

    gaps = []
    for s in sabin_miss:
        gaps.append({"missing_from": "moratorium_nation", "state": s["state"],
                     "jurisdiction": s["jurisdiction"], "technologies": ";".join(sorted(s["techs"])),
                     "status": s["status"], "date": s["date"], "id": s["id"],
                     "description": s["description"]})
    for m in mn_window_miss:
        gaps.append({"missing_from": "sabin", "state": m["state"],
                     "jurisdiction": m["jurisdiction"], "technologies": ";".join(sorted(m["techs"])),
                     "status": m["status"], "date": m["date"], "id": m["id"],
                     "description": m["description"]})
    gaps.sort(key=lambda g: (g["missing_from"], g["state"], g["jurisdiction"]))
    write_csv(GAPS_PATH, gaps, GAP_FIELDS)

    states = sorted({x["state"] for x in sabin + mn})
    s_count, s_hit = Counter(x["state"] for x in sabin), Counter(x["state"] for x in sabin_hit)
    m_count = Counter(x["state"] for x in mn)
    mw_count, mw_hit = Counter(x["state"] for x in mn_window), Counter(x["state"] for x in mn_window_hit)

    lines = [
        "# Coverage audit: local renewables moratoria",
        "",
        "Generated by `scripts/coverage_audit.py`. Compares the moratoria in the Sabin",
        "extraction (`data/renewable_opposition_records.csv`) with Moratorium Nation's",
        "full inventory, both restricted to solar, wind and battery storage and",
        "counting every status (a moratorium lifted since is still a detection).",
        "",
        "A match is the same state, jurisdiction and at least one shared technology.",
        "Name matching is loose (\"Town of X\" = \"X\"), but a jurisdiction spelled",
        "differently in the two sources will show up as a gap, so treat the gap list",
        "as a review queue rather than a verdict.",
        "",
        "## Headline",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Sabin moratoria also in Moratorium Nation | {pct(len(sabin_hit), len(sabin))} |",
        f"| Moratorium Nation moratoria adopted on or before {SABIN_CUTOFF} also in Sabin | "
        f"{pct(len(mn_window_hit), len(mn_window))} |",
        f"| Moratorium Nation moratoria adopted after {SABIN_CUTOFF} or undated (outside the report's window) | {len(mn_later)} |",
        f"| Total Moratorium Nation renewables moratoria | {len(mn)} |",
        "",
        "## By state",
        "",
        "| State | Sabin | Sabin found in MN | MN (all) | MN in Sabin window | MN window found in Sabin |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for st in states:
        lines.append(
            f"| {STATE_NAMES.get(st, st)} | {s_count[st]} | {s_hit[st]} | {m_count[st]} | "
            f"{mw_count[st]} | {mw_hit[st]} |"
        )
    lines += [
        "",
        f"The {len(gaps)} unmatched moratoria are listed in `data/review/coverage_gaps.csv`.",
        "",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"Sabin moratoria in Moratorium Nation: {pct(len(sabin_hit), len(sabin))}")
    print(f"Moratorium Nation (<= {SABIN_CUTOFF}) in Sabin: {pct(len(mn_window_hit), len(mn_window))}")
    print(f"Moratorium Nation after cutoff or undated: {len(mn_later)} of {len(mn)}")
    print(f"Wrote {REPORT_PATH.relative_to(ROOT)} and {GAPS_PATH.relative_to(ROOT)} ({len(gaps)} gaps)")


if __name__ == "__main__":
    main()
