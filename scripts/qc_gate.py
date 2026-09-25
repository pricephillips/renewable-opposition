"""Record-level QC gate for the seed files, run by build_seed_outputs.py.

Modelled on pricephillips/data-center-map's qc/qc_pipeline.py: every check
emits an issue with a stable code and a severity, and a record with any
HIGH or CRITICAL issue is quarantined -- kept out of data/processed/ but never
deleted -- while MEDIUM and LOW are reported only. Change BLOCK_AT in one place
to tune strictness.

Structural problems (a missing required field, a severity outside 1-4, an
unknown state, a duplicate record) are not QC findings: build_seed_outputs.py
refuses to build at all when it sees one, because they mean the seed file
itself is broken. This gate is for rows that are well-formed but wrong.

Checks
------
  COORD_OUTSIDE_STATE   HIGH    coordinates not inside the state the row names
                                (state_bounds.py, shared with data-center-map)
  SOURCE_URL_INVALID    HIGH    source_url / case_source_url is not http(s)
  STATUS_VOCAB          HIGH    status / outcome / case_status outside the
                                entity's vocabulary
  DATE_IN_FUTURE        HIGH    an enactment or filing date after the build date
  SEVERITY_STATUS       MEDIUM  a pending instrument scored above 2
  CONFIRMED_NO_EVIDENCE HIGH    a *_confirmed outcome with no finality evidence
  DATE_UNPARSEABLE      LOW     an ISO date column that is not YYYY[-MM[-DD]]

Usage
-----
  python scripts/qc_gate.py            report on the current seeds, no writes
  python scripts/qc_gate.py --selftest
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import state_bounds  # noqa: E402

BLOCK_AT = {"HIGH", "CRITICAL"}

VOCAB = {
    "restrictions": {"status": {"active", "extended", "pending", "unknown"}},
    "contested_projects": {
        "outcome": {"blocked_confirmed", "blocked_unverified", "restricted_conditional",
                    "advanced_confirmed", "advanced_unverified", "pending", "needs_review"},
    },
    "cases": {
        "case_status": {"", "pending", "dismissed", "ruled_for_developer",
                        "ruled_for_opposition", "settled", "withdrawn"},
    },
}
DATE_FIELDS = ("date_enacted_iso", "current_end_date_iso", "filing_date")
# Dates that record something that already happened. An end date is expected
# to be in the future, so it is format-checked only.
PAST_DATE_FIELDS = ("date_enacted_iso", "filing_date")
URL_FIELDS = ("source_url", "case_source_url")
_ISO = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


@dataclass
class Issue:
    code: str
    severity: str
    field: str
    detail: str


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def check_record(entity: str, row: dict, today: date | None = None) -> list[Issue]:
    today = today or date.today()
    issues: list[Issue] = []

    if row.get("latitude") not in (None, "") and row.get("longitude") not in (None, ""):
        if state_bounds.in_state(row["latitude"], row["longitude"], row.get("state")) is False:
            issues.append(Issue("COORD_OUTSIDE_STATE", "HIGH", "latitude/longitude",
                                f"({row['latitude']}, {row['longitude']}) is not in {row.get('state')}"))

    for f in URL_FIELDS:
        v = _s(row.get(f))
        if v and not re.match(r"^https?://[^\s/]+\.[^\s]+$", v):
            issues.append(Issue("SOURCE_URL_INVALID", "HIGH", f, f"not an http(s) URL: {v[:80]}"))

    for f, allowed in VOCAB.get(entity, {}).items():
        v = _s(row.get(f))
        if v not in allowed:
            issues.append(Issue("STATUS_VOCAB", "HIGH", f, f"{v!r} is not in the {entity} vocabulary"))

    for f in DATE_FIELDS:
        v = _s(row.get(f))
        if not v:
            continue
        if not _ISO.match(v):
            issues.append(Issue("DATE_UNPARSEABLE", "LOW", f, f"{v!r} is not YYYY[-MM[-DD]]"))
            continue
        # Compare at the precision given: "2026-10" is in the future only if
        # the month is after this month.
        if f in PAST_DATE_FIELDS and v > today.isoformat()[: len(v)]:
            issues.append(Issue("DATE_IN_FUTURE", "HIGH", f, f"{v} is after {today.isoformat()}"))

    if entity == "restrictions" and _s(row.get("status")) == "pending":
        try:
            sev = int(row.get("severity_score"))
        except (TypeError, ValueError):
            sev = None
        if sev is not None and sev > 2:
            issues.append(Issue("SEVERITY_STATUS", "MEDIUM", "severity_score",
                                f"pending instrument scored {sev}; pending is capped at 2"))

    if entity == "contested_projects" and _s(row.get("outcome")).endswith("_confirmed"):
        if not _s(row.get("finality_evidence")).startswith("court_ruling"):
            issues.append(Issue("CONFIRMED_NO_EVIDENCE", "HIGH", "outcome",
                                "a *_confirmed outcome needs independent finality evidence"))
    return issues


def blocks(issues: list[Issue], block_at: set[str] = BLOCK_AT) -> bool:
    return any(i.severity in block_at for i in issues)


def run(entity: str, rows: list[dict], today: date | None = None) -> tuple[list[dict], list[dict], list[dict]]:
    """Split rows into (passed, quarantined, findings).

    ``findings`` has one entry per row with any issue; ``quarantined`` holds the
    blocked rows themselves with their issues attached.
    """
    passed, quarantined, findings = [], [], []
    for row in rows:
        issues = check_record(entity, row, today)
        if issues:
            findings.append({"entity": entity, "id": row.get("id"), "state": row.get("state"),
                             "blocked": blocks(issues), "issues": [asdict(i) for i in issues]})
        if blocks(issues):
            quarantined.append({**row, "qc_issues": [asdict(i) for i in issues]})
        else:
            passed.append(row)
    return passed, quarantined, findings


def render_report(findings: list[dict], totals: dict[str, int]) -> str:
    from collections import Counter
    by_code = Counter((i["code"], i["severity"]) for f in findings for i in f["issues"])
    blocked = Counter(f["entity"] for f in findings if f["blocked"])
    lines = [
        "# QC report",
        "",
        "Generated by `scripts/build_seed_outputs.py` via `scripts/qc_gate.py`. Rows with a",
        f"{' or '.join(sorted(BLOCK_AT))} issue are quarantined in `data/processed/quarantine.json`",
        "and left out of the published outputs; lower severities are reported only.",
        "",
        "| Entity | Records | Quarantined |",
        "|---|---:|---:|",
    ]
    for entity, n in totals.items():
        lines.append(f"| {entity} | {n} | {blocked[entity]} |")
    lines += ["", "| Code | Severity | Issues |", "|---|---|---:|"]
    for (code, sev), n in sorted(by_code.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| {code} | {sev} | {n} |")
    if not by_code:
        lines.append("| (none) | | 0 |")
    return "\n".join(lines) + "\n"


def selftest() -> int:
    today = date(2026, 9, 25)
    cases = [
        ("restrictions", {"state": "PA", "latitude": 32.5, "longitude": -91.6, "status": "active",
                          "source_url": "https://x.org/a"}, {"COORD_OUTSIDE_STATE"}),
        ("restrictions", {"state": "VA", "latitude": 39.1, "longitude": -77.5, "status": "active",
                          "source_url": "https://x.org/a"}, set()),
        ("restrictions", {"state": "VA", "status": "enacted", "source_url": "x.org"},
         {"STATUS_VOCAB", "SOURCE_URL_INVALID"}),
        ("restrictions", {"state": "VA", "status": "pending", "severity_score": 4,
                          "source_url": "https://x.org"}, {"SEVERITY_STATUS"}),
        ("restrictions", {"state": "VA", "status": "active", "source_url": "https://x.org",
                          "date_enacted_iso": "2026-10"}, {"DATE_IN_FUTURE"}),
        ("restrictions", {"state": "VA", "status": "active", "source_url": "https://x.org",
                          "date_enacted_iso": "2026-09"}, set()),
        ("restrictions", {"state": "VA", "status": "active", "source_url": "https://x.org",
                          "date_enacted_iso": "March 2024"}, {"DATE_UNPARSEABLE"}),
        ("restrictions", {"state": "VA", "status": "active", "source_url": "https://x.org",
                          "current_end_date_iso": "2027-06-01"}, set()),
        ("contested_projects", {"state": "VA", "outcome": "blocked_confirmed",
                                "finality_evidence": "outcome_label_only",
                                "source_url": "https://x.org"}, {"CONFIRMED_NO_EVIDENCE"}),
        ("cases", {"state": "VA", "case_status": "won", "source_url": "https://x.org"}, {"STATUS_VOCAB"}),
    ]
    failed = 0
    for entity, row, expected in cases:
        got = {i.code for i in check_record(entity, row, today)}
        if got != expected:
            failed += 1
            print(f"FAIL {entity} {row}: expected {sorted(expected)}, got {sorted(got)}")
    print(f"{len(cases) - failed}/{len(cases)} checks passed")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    import build_seed_outputs as bso
    for entity, filename in bso.ENTITIES.items():
        rows, errors = bso.build_entity(entity, filename)
        if rows is None:
            continue
        passed, quarantined, findings = run(entity, rows)
        print(f"{entity}: {len(rows)} rows, {len(quarantined)} quarantined, "
              f"{len(findings) - len(quarantined)} with non-blocking findings")
        for f in findings:
            for i in f["issues"]:
                print(f"  {'BLOCK' if f['blocked'] else 'note '} {f['id']} {f['state']} {i['code']}: {i['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
