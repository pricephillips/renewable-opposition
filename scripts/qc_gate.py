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
  PRIMARY_SOURCE_CONTRADICTS HIGH  a reviewer found the primary source disagrees
                                with the record (data/review/restriction_sources.csv)
                                MEDIUM when that source was seen only as
                                search-index text (access snippet): a lead to
                                read, not grounds to hold the record back
  SCOPE_DATA_CENTER_ONLY HIGH   a restriction whose text names data centers and
                                no renewable technology (classify.scope): the
                                source's sector tag is not supported by the record
  DATE_UNPARSEABLE      LOW     an ISO date column that is not YYYY[-MM[-DD]]
  END_DATE_PASSED       MEDIUM  an active or extended restriction whose own end
                                date is before the build date and that no
                                reviewer re-confirmed since (classify.currency
                                lapsed_unconfirmed): the source's status may be
                                out of date. Reported, never quarantined; the
                                headline counts it apart and the worklist ranks
                                it first

The table above is also CHECKS, which scripts/codebook.py publishes; a code
emitted here that CHECKS does not list fails tests/test_brain.py. Each entry
also says what releases a row from quarantine, so qc_report.md's quarantine
table reads as triage, not investigation (after pricephillips/data-center-map
review_worklists.py's suggested_resolution).

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
    "restrictions": {
        "status": {"active", "extended", "pending", "unknown"},
        # Derived by classify.py; a value outside these means the rules and the
        # vocabulary drifted apart.
        "scope": {"renewables_only", "multi_sector_data_centers", "data_center_only"},
        "evidence_level": {"primary_source", "compiled_record", "compiled_flagged",
                           "report_citation"},
        "verification": {"verified", "located", "unverified"},
        "currency": {"in_force", "lapsed_unconfirmed", "pending", "unknown"},
        "state_limits_local": {"yes", "no", "unknown", ""},
    },
    "contested_projects": {
        "outcome": {"blocked_confirmed", "blocked_unverified", "restricted_conditional",
                    "advanced_confirmed", "advanced_unverified", "pending", "needs_review"},
        "verification": {"verified", "unverified"},
    },
    "cases": {
        "case_status": {"", "pending", "dismissed", "ruled_for_developer",
                        "ruled_for_opposition", "settled", "withdrawn"},
        "verification": {"verified", "unverified"},
    },
}
DERIVED_FIELDS = {"scope", "evidence_level", "verification", "currency", "state_limits_local"}
# (code, severity, what it means, what releases the row), the table in the
# module docstring. A severity given as "MEDIUM or HIGH" varies with the row.
CHECKS = (
    ("COORD_OUTSIDE_STATE", "HIGH", "coordinates not inside the state the row names",
     "correct the coordinates or the state in the seed (or the source's row) so they agree"),
    ("SOURCE_URL_INVALID", "HIGH", "source_url, case_source_url or primary_source_url is not http(s)",
     "replace the value with the document's http(s) address"),
    ("STATUS_VOCAB", "HIGH", "status, outcome, case_status or a derived field outside the entity's vocabulary",
     "map the source's value onto the vocabulary in the importer (build_sabin_seeds, fetch_moratorium_nation) "
     "or the queue row"),
    ("DATE_IN_FUTURE", "HIGH", "an enactment or filing date after the build date",
     "check the date against the instrument or docket; a proposal date belongs in date_text, not date_enacted_iso"),
    ("SEVERITY_STATUS", "MEDIUM", "a pending instrument scored above 2",
     "nothing to do: reported only; the score is capped at 2 while pending"),
    ("CONFIRMED_NO_EVIDENCE", "HIGH", "a *_confirmed outcome with no independent finality evidence",
     "add a data/review/outcome_resolutions.csv row with the document that shows the outcome (access opened or "
     "archived), or set the outcome back to *_unverified"),
    ("PRIMARY_SOURCE_CONTRADICTS", "MEDIUM or HIGH",
     "a reviewer found the primary source disagrees with the record; MEDIUM when that source was seen only "
     "as search-index text (a lead to read), HIGH when it was opened or archived",
     "correct the record to what the primary source says (a queue row, or a note to the upstream source), then "
     "set the restriction_sources.csv verdict to confirmed"),
    ("SCOPE_DATA_CENTER_ONLY", "HIGH", "a restriction whose text names data centers and no renewable technology",
     "if the instrument does cover a renewable technology, say so in the record's text or sectors; if not, it "
     "belongs to data-center-map and stays out"),
    ("DATE_UNPARSEABLE", "LOW", "an ISO date column that is not YYYY[-MM[-DD]]",
     "nothing to do: reported only; rewrite the date as YYYY, YYYY-MM or YYYY-MM-DD when touching the row"),
    ("END_DATE_PASSED", "MEDIUM", "an active or extended restriction whose own end date has passed with no "
     "reviewer confirmation since; the source's status may be out of date",
     "nothing to do here: reported only; the restriction worklist lists it first, and a restriction_sources.csv "
     "row checked on or after the end date restores it to in_force"),
)
RELEASE = {code: release for code, _, _, release in CHECKS}
DATE_FIELDS = ("date_enacted_iso", "current_end_date_iso", "filing_date")
# Dates that record something that already happened. An end date is expected
# to be in the future, so it is format-checked only.
PAST_DATE_FIELDS = ("date_enacted_iso", "filing_date")
URL_FIELDS = ("source_url", "case_source_url", "primary_source_url")
# Independent evidence that makes an outcome *_confirmed: a linked court ruling,
# or a reviewer's resolution citing a document (data/review/outcome_resolutions.csv).
FINALITY_PREFIXES = ("court_ruling", "resolution")
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
        if f in DERIVED_FIELDS and f not in row:
            continue  # stamped by classify.py during a build; absent in isolation
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

    if _s(row.get("primary_source_verdict")) == "contradicts":
        unread = _s(row.get("primary_source_access")) == "snippet"
        issues.append(Issue("PRIMARY_SOURCE_CONTRADICTS", "MEDIUM" if unread else "HIGH", "primary_source_url",
                            ("primary source located, not yet read, may disagree: " if unread
                             else "primary source disagrees: ") + _s(row.get('primary_source_url'))[:80]))

    if entity == "restrictions" and _s(row.get("status")) in ("active", "extended"):
        end = _s(row.get("current_end_date_iso"))
        if _ISO.match(end) and end < today.isoformat()[: len(end)]:
            checked = _s(row.get("primary_source_checked_on"))
            reconfirmed = _s(row.get("primary_source_verdict")) == "confirmed" and _ISO.match(checked) \
                and checked[: len(end)] >= end
            if not reconfirmed:
                issues.append(Issue("END_DATE_PASSED", "MEDIUM", "current_end_date_iso",
                                    f"end date {end} is before {today.isoformat()} and nothing confirms an "
                                    "extension; the source's status may be out of date"))

    if entity == "restrictions" and _s(row.get("scope")) == "data_center_only":
        issues.append(Issue("SCOPE_DATA_CENTER_ONLY", "HIGH", "scope",
                            "text names data centers and no renewable technology"))

    if entity == "contested_projects" and _s(row.get("outcome")).endswith("_confirmed"):
        if not _s(row.get("finality_evidence")).startswith(FINALITY_PREFIXES):
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


def _place(row: dict) -> str:
    return _s(row.get("jurisdiction")) or _s(row.get("project_name")) or _s(row.get("county"))


def render_report(findings: list[dict], totals: dict[str, int], quarantined: list[dict] | None = None) -> str:
    """The QC findings by code, and (when given the quarantined rows) one line
    per held row saying what would release it, so the list reads as triage."""
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
    if quarantined:
        lines += ["", "## Quarantined rows", "",
                  "Held out of the published data until the release action is done. The action comes from the "
                  "check's entry in `qc_gate.CHECKS` (also in `docs/codebook.md`).", "",
                  "| Entity | Id | State | Place | Blocking code(s) | What releases it |", "|---|---|---|---|---|---|"]
        for row in sorted(quarantined, key=lambda r: (_s(r.get("entity")), _s(r.get("state")), _place(r), _s(r.get("id")))):
            codes = sorted({i["code"] for i in row.get("qc_issues", []) if i["severity"] in BLOCK_AT})
            release = " / ".join(RELEASE.get(c, "") for c in codes)
            lines.append(f"| {_s(row.get('entity'))} | {_s(row.get('id'))} | {_s(row.get('state'))} | {_place(row)} | "
                         f"{', '.join(codes)} | {release} |")
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
        ("restrictions", {"state": "VA", "status": "extended", "source_url": "https://x.org",
                          "current_end_date_iso": "2026-09-01"}, {"END_DATE_PASSED"}),
        ("restrictions", {"state": "VA", "status": "active", "source_url": "https://x.org",
                          "current_end_date_iso": "2026-09", "primary_source_url": "https://x.gov/o.pdf",
                          "primary_source_verdict": "confirmed", "primary_source_checked_on": "2026-09-20"},
         set()),
        ("restrictions", {"state": "VA", "status": "pending", "source_url": "https://x.org",
                          "current_end_date_iso": "2026-09-01"}, set()),
        ("restrictions", {"state": "VA", "status": "active", "source_url": "https://x.org",
                          "currency": "stale"}, {"STATUS_VOCAB"}),
        ("contested_projects", {"state": "VA", "outcome": "blocked_confirmed",
                                "finality_evidence": "outcome_label_only",
                                "source_url": "https://x.org"}, {"CONFIRMED_NO_EVIDENCE"}),
        ("cases", {"state": "VA", "case_status": "won", "source_url": "https://x.org"}, {"STATUS_VOCAB"}),
        ("restrictions", {"state": "KS", "status": "active", "source_url": "https://x.org",
                          "scope": "data_center_only"}, {"SCOPE_DATA_CENTER_ONLY"}),
        ("restrictions", {"state": "KS", "status": "active", "source_url": "https://x.org",
                          "evidence_level": "rumour"}, {"STATUS_VOCAB"}),
        ("restrictions", {"state": "KS", "status": "active", "source_url": "https://x.org",
                          "primary_source_url": "https://town.gov/o.pdf",
                          "primary_source_verdict": "contradicts"}, {"PRIMARY_SOURCE_CONTRADICTS"}),
        ("restrictions", {"state": "KS", "status": "active", "source_url": "https://x.org",
                          "primary_source_url": "https://town.gov/o.pdf", "primary_source_access": "snippet",
                          "primary_source_verdict": "contradicts"}, {"PRIMARY_SOURCE_CONTRADICTS"}),
        ("contested_projects", {"state": "VA", "outcome": "blocked_confirmed",
                                "finality_evidence": "lead: https://county.gov/minutes.pdf",
                                "source_url": "https://x.org"}, {"CONFIRMED_NO_EVIDENCE"}),
        ("contested_projects", {"state": "VA", "outcome": "blocked_confirmed",
                                "finality_evidence": "resolution: https://county.gov/minutes.pdf",
                                "source_url": "https://x.org"}, set()),
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
