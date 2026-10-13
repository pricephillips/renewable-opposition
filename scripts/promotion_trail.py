"""An append-only record of promotion decisions that records changes only.

Copied in spirit from pricephillips/data-center-map promotion_trail.py
(docs/pipeline_comparison.md, "Recommended next" item 3), not imported.

promote_reviewed.py runs before every build and decides the same candidates
the same way most days: a queue row missing its court stays "held: missing
court" for weeks. Appending every decision on every run would bury the events
(a row promoted, a hold lifted, a new reason) under restatements; in
data-center-map one trail reached 7,342 rows for 1,947 decisions before this
rule. So a decision is written only when it is new, or differs from the most
recent one recorded for the same candidate.

This module holds the rule and nothing else. promote_reviewed.py owns the
file (data/review/promotion_trail.csv) and does the reading and writing, so
config/layers.json still names one writer.

Usage
  from promotion_trail import new_decisions
  fresh, suppressed = new_decisions(existing, candidates,
                                    key_fields=("file", "key"),
                                    state_fields=("action", "reason"))

  python scripts/promotion_trail.py --selftest
"""
from __future__ import annotations

import argparse
import sys


def decision_key(row: dict, key_fields) -> tuple:
    """What identifies the thing being decided about, not the decision."""
    return tuple((row.get(f) or "").strip() for f in key_fields)


def decision_state(row: dict, state_fields) -> tuple:
    """The decision itself. A change here is the event worth recording."""
    return tuple((row.get(f) or "").strip() for f in state_fields)


def new_decisions(existing: list, candidates: list, key_fields, state_fields) -> tuple[list, int]:
    """(rows to append, count suppressed as unchanged).

    A candidate is appended when it has no prior decision on record, or when
    its decision differs from the most recent one recorded for it. Re-deciding
    a candidate the same way is not an event and is not recorded. Order is
    preserved, and duplicates inside one batch collapse to the first, so one
    run cannot record the same decision twice.
    """
    last: dict = {}
    for row in existing:
        last[decision_key(row, key_fields)] = decision_state(row, state_fields)
    fresh, suppressed = [], 0
    for row in candidates:
        key, state = decision_key(row, key_fields), decision_state(row, state_fields)
        if last.get(key) == state:
            suppressed += 1
            continue
        last[key] = state
        fresh.append(row)
    return fresh, suppressed


def selftest() -> int:
    checks = []
    KEY, STATE = ("file", "key"), ("action", "reason")
    held = {"file": "queue.csv", "key": "q_1", "action": "held", "reason": "missing court"}
    existing = [held]

    def check(name, ok):
        checks.append((name, bool(ok)))

    fresh, suppressed = new_decisions(existing, [dict(held)], KEY, STATE)
    check("re-deciding the same way records nothing", fresh == [] and suppressed == 1)
    fresh, _ = new_decisions(existing, [dict(held, action="promoted", reason="")], KEY, STATE)
    check("a changed decision is recorded", len(fresh) == 1 and fresh[0]["action"] == "promoted")
    fresh, _ = new_decisions(existing, [dict(held, reason="missing court, court_level")], KEY, STATE)
    check("the same action for a new reason is still an event", len(fresh) == 1)
    other = dict(held, key="q_2")
    fresh, suppressed = new_decisions(existing, [dict(held), other], KEY, STATE)
    check("an unseen candidate is recorded even when others repeat",
          len(fresh) == 1 and fresh[0]["key"] == "q_2" and suppressed == 1)
    fresh, suppressed = new_decisions([], [dict(held), dict(held)], KEY, STATE)
    check("a duplicate inside one batch collapses", len(fresh) == 1 and suppressed == 1)
    history = [held, dict(held, action="promoted", reason="")]
    fresh, _ = new_decisions(history, [dict(held)], KEY, STATE)
    check("the latest decision is the one compared against", len(fresh) == 1)
    fresh, _ = new_decisions(history, [dict(held, action="promoted", reason="")], KEY, STATE)
    check("matching the latest decision records nothing", fresh == [])
    check("a missing field is treated as empty, not an error",
          new_decisions([{"file": "q"}], [{"file": "q"}], KEY, STATE) == ([], 1))
    fresh, _ = new_decisions([], [dict(other, key=f"q_{i}") for i in range(3)], KEY, STATE)
    check("order is preserved", [r["key"] for r in fresh] == ["q_0", "q_1", "q_2"])

    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {n}")
    print(f"{len(checks) - len(failed)}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    sys.exit(selftest() if args.selftest else (print(__doc__.strip()) or 0))
