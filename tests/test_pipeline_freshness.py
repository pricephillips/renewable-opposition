"""The review pipeline freshness check (scripts/pipeline_freshness.py)."""
from datetime import date

import pipeline_freshness as pf

TODAY = date(2026, 10, 19)


def test_the_newest_log_line_is_found_and_bad_dates_are_skipped(tmp_path):
    log = tmp_path / "verification_log.csv"
    log.write_text("date,queue,key,outcome,note\n2026-10-16,outcome,a,written,x\nbad,outcome,b,written,x\n"
                   "2026-10-18,status,c,disputed,x\n")
    assert pf.last_log_date(log, TODAY) == date(2026, 10, 18)
    with log.open("a") as f:
        f.write("2062-10-01,outcome,d,written,a typo in the future\n")
    assert pf.last_log_date(log, TODAY) == date(2026, 10, 18)
    assert pf.last_log_date(tmp_path / "missing.csv") is None


def test_only_verification_pull_requests_count_as_activity():
    prs = [{"title": "Verification: 2026-10-18", "created_at": "2026-10-18T08:01:00Z"},
           {"title": "Bump the all group", "created_at": "2026-10-19T01:00:00Z"}]
    assert pf.last_run_pr(prs) == date(2026, 10, 18)
    assert pf.last_run_pr(prs[1:]) is None


def test_stale_after_more_than_the_allowed_days_without_any_activity():
    assert not pf.check(date(2026, 10, 16), None, TODAY)[0]
    stale, message = pf.check(date(2026, 10, 15), None, TODAY)
    assert stale and "4 days" in message
    assert not pf.check(date(2026, 10, 1), date(2026, 10, 18), TODAY)[0]
    assert pf.check(None, None, TODAY)[0]


def test_the_workflow_output_carries_the_verdict(tmp_path, capsys):
    out = tmp_path / "out"
    pf.main(["--today", "2099-01-01", "--github-output", str(out)])
    assert "stale=true" in out.read_text() and capsys.readouterr().out.startswith("STALE")
