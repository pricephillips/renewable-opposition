"""Is the agent review pipeline still producing work? (.github/workflows/pipeline-freshness.yml)

Every reading run, scheduled or by hand, ends in a pull request that adds lines to
data/review/verification_log.csv. The daily verification routine
(docs/VERIFICATION_ROUTINE.md) can fail without anyone seeing it: from 2026-10-13
to 2026-10-19 it fired every morning, reported success, and read nothing because
its session could not push. Any log line counts as activity, so this check
makes a stop like that visible once hand runs are not filling the log either.

The pipeline is stale when, for more than --max-days days, main has gained no
verification log line and no open pull request titled "Verification: ..." has
been opened. An open run waiting for review counts as activity, so an unmerged
pull request does not raise the alarm; merging it is a separate step.

  python scripts/pipeline_freshness.py [--prs PRS_JSON] [--today YYYY-MM-DD]
                                       [--max-days N] [--github-output PATH]

PRS_JSON is the body of GET /repos/{owner}/{repo}/pulls?state=open. Prints one
line and, with --github-output, writes stale=true|false and message=... for the
workflow. Exit 0 either way; the workflow opens or closes the issue.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "review" / "verification_log.csv"
MAX_DAYS = 3
RUN_TITLE = "verification:"


def last_log_date(path: Path = LOG, today: date | None = None) -> date | None:
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8-sig") as f:
        dates = [r.get("date", "")[:10] for r in csv.DictReader(f)]
    parsed = []
    for d in dates:
        try:
            parsed.append(date.fromisoformat(d))
        except ValueError:
            continue
    # A date after today is a typo (review_lint refuses one); it must not hold the alarm off.
    return max((d for d in parsed if d <= (today or date.today())), default=None)


def last_run_pr(prs: list[dict]) -> date | None:
    """The opening date of the newest open pull request a reading run made."""
    opened = [date.fromisoformat(p["created_at"][:10]) for p in prs
              if str(p.get("title", "")).strip().lower().startswith(RUN_TITLE) and p.get("created_at")]
    return max(opened, default=None)


def check(log_date: date | None, pr_date: date | None, today: date, max_days: int = MAX_DAYS) -> tuple[bool, str]:
    latest = max([d for d in (log_date, pr_date) if d], default=None)
    seen = (f"last verification log line {log_date or 'none'}; "
            f"newest open verification pull request {pr_date or 'none'}")
    if latest is None:
        return True, f"No verification activity on record ({seen})."
    age = (today - latest).days
    if age > max_days:
        return True, (f"No verification activity for {age} days, more than {max_days} ({seen}). "
                      "Check the last runs of the daily verification routine (docs/VERIFICATION_ROUTINE.md).")
    return False, f"Verification activity {age} day(s) ago ({seen})."


def _selftest() -> None:
    today = date(2026, 10, 19)
    pr = [{"title": "Verification: 2026-10-18", "created_at": "2026-10-18T08:01:00Z"},
          {"title": "Bump the all group", "created_at": "2026-10-19T01:00:00Z"}]
    assert last_run_pr(pr) == date(2026, 10, 18)
    assert last_run_pr([pr[1]]) is None
    assert not check(date(2026, 10, 16), None, today)[0]
    assert check(date(2026, 10, 15), None, today)[0]
    assert not check(date(2026, 10, 1), date(2026, 10, 18), today)[0]
    assert check(None, None, today)[0]
    assert "4 days" in check(date(2026, 10, 15), None, today)[1]
    print("pipeline_freshness selftest: ok")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prs", help="JSON body of the open pull request list")
    ap.add_argument("--today", default=None)
    ap.add_argument("--max-days", type=int, default=MAX_DAYS)
    ap.add_argument("--github-output", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    today = date.fromisoformat(a.today) if a.today else date.today()
    prs = json.loads(Path(a.prs).read_text()) if a.prs else []
    stale, message = check(last_log_date(today=today), last_run_pr(prs), today, a.max_days)
    print(("STALE: " if stale else "ok: ") + message)
    if a.github_output:
        with open(a.github_output, "a", encoding="utf-8") as f:
            f.write(f"stale={'true' if stale else 'false'}\nmessage={message}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
