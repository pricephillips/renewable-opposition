"""Client view audit: read a county's renewables profile the way a skeptical
client analyst does, and list what that reader would ask that the record does
not answer.

The questions come from config/reader_questions.json (Hawthorn's internal
reviews of the renewables pilot). This script answers the ones it can check
mechanically; the client-view-reviewer agent reads the rest from the profile
this script prints (docs/VERIFICATION_ROUTINE.md, section 5).

Checks, one finding per instrument or county:
  PAST_END_DATE            a temporary instrument whose end date (recorded or
                           in its text) has passed and no status reading
                           settled it since                      -> status
  PAUSE_NO_END_DATE        a temporary instrument in force with no end date -> status
  PAUSE_EXTENSIONS_UNKNOWN status extended, but no extension date on record -> status
  PAUSE_DRAFTING_UNKNOWN   a temporary instrument in force; the record does
                           not say whether rules are being drafted  -> status
  PAUSE_NO_START_DATE      a moratorium or ban in force with no enactment date -> restriction
  BAN_OR_PAUSE_UNCLEAR     a severe instrument whose source does not say ban
                           or moratorium                          -> restriction
  UNVERIFIED_IN_HEADLINE   a severe instrument in force that no reviewer has
                           read, so the profile labels it unverified -> restriction
  TIER_WITHOUT_INSTRUMENT  the county is in the closed or severe tier but has
                           no severe instrument in force: its rank rests on
                           other parts of the score                -> issue

The route says who acts: `status` and `restriction` are the daily routine's
own queues (a status-checker or instrument-reader card, then the blind
reviewer and the record-editor), and `issue` is a GitHub issue labelled
client-view for a session to fix.

Usage:
  python scripts/client_view_audit.py --pick 5          counties to review today
  python scripts/client_view_audit.py --county 20021    the profile and its findings
  python scripts/client_view_audit.py                   every finding, to data/review/client_view_findings.csv
  python scripts/client_view_audit.py --selftest
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROCESSED_DIR, REVIEW_DIR, ROOT, read_csv, write_csv  # noqa: E402

SCORES = ROOT / "data" / "model" / "county_record_scores.csv"
QUESTIONS = ROOT / "config" / "reader_questions.json"
LOG = REVIEW_DIR / "client_view_log.csv"
FINDINGS = REVIEW_DIR / "client_view_findings.csv"
FINDING_FIELDS = ["county_fips", "state", "county", "check", "route", "instrument_id", "detail"]
LOG_FIELDS = ["date", "county_fips", "findings", "issues", "note"]
ROUTES = {"PAST_END_DATE": "status", "PAUSE_NO_END_DATE": "status", "PAUSE_EXTENSIONS_UNKNOWN": "status",
          "PAUSE_DRAFTING_UNKNOWN": "status", "PAUSE_NO_START_DATE": "restriction",
          "BAN_OR_PAUSE_UNCLEAR": "restriction", "UNVERIFIED_IN_HEADLINE": "restriction",
          "TIER_WITHOUT_INSTRUMENT": "issue"}
PAUSES = ("moratorium", "ban", "ban_or_moratorium")
LIVE = ("in_force", "unknown")
REVISIT_DAYS = 30


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def _sev(r: dict) -> int:
    try:
        return int(float(_s(r.get("severity_score")) or 0))
    except ValueError:
        return 0


def by_county(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        for f in _s(r.get("county_fips_all") or r.get("county_fips")).split(";"):
            if f:
                out.setdefault(f, []).append(r)
    return out


def instruments(rows: list[dict]) -> list[dict]:
    """One row per instrument (the first row, with every technology named)."""
    seen: dict[str, dict] = {}
    for r in rows:
        iid = _s(r.get("instrument_id")) or _s(r.get("id"))
        if iid in seen:
            seen[iid]["technology"] += ";" + _s(r.get("technology"))
        else:
            seen[iid] = {**r, "technology": _s(r.get("technology"))}
    return list(seen.values())


def findings(fips: str, rows: list[dict], score: dict | None, today: date) -> list[dict]:
    out = []
    t = today.isoformat()

    def add(check: str, inst: dict | None, detail: str) -> None:
        out.append({"county_fips": fips, "state": _s((score or {}).get("state") or (inst or {}).get("state")),
                    "county": _s((score or {}).get("county")), "check": check, "route": ROUTES[check],
                    "instrument_id": _s((inst or {}).get("instrument_id")), "detail": detail})

    severe_live = False
    for i in instruments(rows):
        cur, term, sev = _s(i.get("currency")), _s(i.get("term")), _sev(i)
        where = f"{_s(i.get('jurisdiction'))} ({i['technology']})"
        if sev >= 3 and cur == "in_force":
            severe_live = True
        if term == "temporary":
            end = _s(i.get("ends_on"))
            settled = _s(i.get("status_checked_on"))
            if end and end < t[: len(end)] and not (settled and settled[: len(end)] >= end) \
                    and cur in ("in_force", "lapsed_unconfirmed"):
                add("PAST_END_DATE", i, f"{where}: runs to {end} ({_s(i.get('ends_on_basis'))}); nothing on record "
                                        "says whether it was extended, replaced or lapsed")
            if cur == "in_force" and not end:
                add("PAUSE_NO_END_DATE", i, f"{where}: in force with no end date on record")
            if _s(i.get("status")) == "extended" and not _s(i.get("last_extended_on")):
                add("PAUSE_EXTENSIONS_UNKNOWN", i, f"{where}: marked extended, with no extension date on record")
            if cur == "in_force" and not _s(i.get("drafting")):
                add("PAUSE_DRAFTING_UNKNOWN", i, f"{where}: the record does not say whether rules are being drafted")
        if _s(i.get("restriction_type")) in PAUSES and cur in LIVE and not _s(i.get("date_enacted_iso")):
            add("PAUSE_NO_START_DATE", i, f"{where}: no enactment date, so its time in force is unknown")
        if term == "unclear" and sev >= 3 and cur in LIVE:
            add("BAN_OR_PAUSE_UNCLEAR", i, f"{where}: the source files it as 'ban or moratorium' without saying which")
        if sev >= 3 and cur == "in_force" and _s(i.get("verification")) != "verified":
            add("UNVERIFIED_IN_HEADLINE", i, f"{where}: severity {sev} in force, not yet read against its source")
    if score and _s(score.get("tier")) in ("closed", "severe") and not severe_live:
        add("TIER_WITHOUT_INSTRUMENT", None,
            f"tier {score['tier']} (score {score.get('combined')}, national rank {score.get('us_rank')} of "
            f"{score.get('us_n')}) with no severe instrument in force; a reader will ask what puts it there")
    return out


def profile(fips: str, rows: list[dict], score: dict | None, state_rows: list[dict]) -> str:
    """The county as the pilot shows it, in plain text, for the reviewer."""
    s = score or {}
    lines = [f"County {fips}: {_s(s.get('county'))}, {_s(s.get('state'))}",
             f"Renewables Record Score {s.get('combined', '?')} ({s.get('tier', 'no record')}); "
             f"state rank {s.get('state_rank', '?')} of {s.get('state_n', '?')}, national rank "
             f"{s.get('us_rank', '?')} of {s.get('us_n', '?')}; resemblance score {s.get('profile_score', '?')}",
             f"Parts: instruments {s.get('instrument_points')}, zoning {s.get('zoning_points')}, blocked "
             f"{s.get('blocked_points')}, organizing {s.get('organizing_points')}, approvals -{s.get('approval_credit')}",
             "", "Local rules:"]
    for i in sorted(instruments(rows), key=lambda r: (-_sev(r), _s(r.get("jurisdiction")))):
        lines.append(
            f"- {_s(i.get('jurisdiction'))} | {i['technology']} | {_s(i.get('restriction_type'))} severity {_sev(i)} | "
            f"{_s(i.get('currency'))} | {_s(i.get('verification'))} | adopted {_s(i.get('date_enacted_iso')) or '?'}"
            + (f" | {_s(i.get('term'))}, ends {_s(i.get('ends_on')) or '?'}, extensions {_s(i.get('extensions'))}, "
               f"{_s(i.get('months_in_force')) or '?'} months in force, drafting {_s(i.get('drafting')) or '?'}"
               if _s(i.get("term")) else "")
            + f" | {_s(i.get('description'))[:220]} | {_s(i.get('source_url'))}")
    st = _s(s.get("state"))
    lines += ["", f"State siting law ({st}):"]
    lines += [f"- {_s(r.get('policy_type'))} | {_s(r.get('technology'))} | {_s(r.get('summary'))[:200]}"
              for r in state_rows if _s(r.get("state")) == st] or ["- none on record"]
    return "\n".join(lines)


def pick(scores: list[dict], log: list[dict], n: int, today: date) -> list[str]:
    """Closed and severe counties first, by national rank, skipping any
    reviewed in the last REVISIT_DAYS days; then the rest by rank."""
    recent = {_s(r.get("county_fips")) for r in log
              if _s(r.get("date")) >= (today - timedelta(days=REVISIT_DAYS)).isoformat()}

    def rank(r: dict) -> tuple:
        try:
            us = int(_s(r.get("us_rank")) or 10**6)
        except ValueError:
            us = 10**6
        return (_s(r.get("tier")) not in ("closed", "severe"), us, _s(r.get("county_fips")))
    order = sorted((r for r in scores if _s(r.get("tier")) not in ("", "no_record")), key=rank)
    return [r["county_fips"] for r in order if r["county_fips"] not in recent][:n]


def main(argv: list[str]) -> int:
    today = date.today()
    rows = by_county(read_csv(PROCESSED_DIR / "restrictions.csv"))
    scores = {r["county_fips"]: r for r in read_csv(SCORES)}
    if "--pick" in argv:
        n = int(argv[argv.index("--pick") + 1])
        print("\n".join(pick(list(scores.values()), read_csv(LOG), n, today)))
        return 0
    if "--county" in argv:
        f = argv[argv.index("--county") + 1]
        print(profile(f, rows.get(f, []), scores.get(f), read_csv(PROCESSED_DIR / "state_policies.csv")))
        print("\nFindings:")
        print(json.dumps(findings(f, rows.get(f, []), scores.get(f), today), indent=1))
        print("\nReader questions: " + str(QUESTIONS.relative_to(ROOT)))
        return 0
    out = [x for f in sorted(set(rows) | set(scores)) for x in findings(f, rows.get(f, []), scores.get(f), today)]
    write_csv(FINDINGS, out, FINDING_FIELDS)
    counts: dict[str, int] = {}
    for x in out:
        counts[x["check"]] = counts.get(x["check"], 0) + 1
    print(f"client_view_audit: {len(out)} findings: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return 0


def _selftest() -> int:
    today = date(2026, 11, 19)
    q = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    checks = {x["check"] for x in q["questions"] if x["check"]}
    assert checks <= set(ROUTES) | {"HEADLINE_RECORD_MISMATCH", "STATE_RULES_NOT_SHOWN"}, checks - set(ROUTES)
    base = {"instrument_id": "i1", "county_fips_all": "13247", "jurisdiction": "Rockdale County", "state": "GA",
            "technology": "battery_storage", "restriction_type": "moratorium", "severity_score": "4",
            "term": "temporary", "verification": "verified", "date_enacted_iso": "2026-01-13", "drafting": "active"}
    lapsed = findings("13247", [{**base, "currency": "lapsed_unconfirmed", "ends_on": "2026-10-01",
                                 "ends_on_basis": "record", "status": "extended"}], None, today)
    assert {x["check"] for x in lapsed} == {"PAST_END_DATE", "PAUSE_EXTENSIONS_UNKNOWN"}, lapsed
    settled = findings("13247", [{**base, "currency": "in_force", "ends_on": "2026-10-01",
                                  "status_checked_on": "2026-10-20"}], None, today)
    assert "PAST_END_DATE" not in {x["check"] for x in settled}
    open_ended = findings("1", [{**base, "currency": "in_force", "drafting": "", "verification": "unverified",
                                 "date_enacted_iso": ""}], {"tier": "closed", "county": "X"}, today)
    assert {x["check"] for x in open_ended} == {"PAUSE_NO_END_DATE", "PAUSE_DRAFTING_UNKNOWN",
                                                "PAUSE_NO_START_DATE", "UNVERIFIED_IN_HEADLINE"}, open_ended
    rank_only = findings("2", [], {"tier": "closed", "combined": "43", "us_rank": "50", "us_n": "3144"}, today)
    assert [x["check"] for x in rank_only] == ["TIER_WITHOUT_INSTRUMENT"] and rank_only[0]["route"] == "issue"
    scores = [{"county_fips": "a", "tier": "open", "us_rank": "1"}, {"county_fips": "b", "tier": "closed", "us_rank": "9"},
              {"county_fips": "c", "tier": "severe", "us_rank": "5"}, {"county_fips": "d", "tier": "no_record"}]
    assert pick(scores, [{"date": "2026-11-01", "county_fips": "c"}], 5, today) == ["b", "a"]
    assert pick(scores, [{"date": "2026-09-01", "county_fips": "c"}], 2, today) == ["c", "b"]
    assert "Local rules:" in profile("13247", [{**base, "currency": "in_force"}], None, [])
    print("client_view_audit selftest: ok")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else main(sys.argv[1:]))
