"""policy_outlook_core.py: the bill outcome model's shared core, format version 1.

One file, kept byte for byte the same in two repositories:
pricephillips/data-centers (policy_outlook_core.py) and
pricephillips/renewable-opposition (scripts/policy_outlook_core.py). Each
repository pins its SHA-256 in a policy outlook format lock
(configs/policy_outlook_format.lock here, config/policy_outlook_format.lock in
renewable-opposition), and each repository's tests fail when the local file
differs from its lock.

What the model answers. A tracked bill would make a kind of state law (for
example, a law that limits what local governments may do). For each kind, the
caller lists past laws of that kind with a sourced effective date (the
precedents) and dated events from its own records (a local restriction
adopted, a project blocked or advanced). The core then describes, for each
precedent, how the events in that state changed in the window after the law
compared with the window before it, against the same change in comparison
states over the same months. Pooling the precedents gives a direction for the
"passes" branch. The "fails" branch is the state's own recent record against
the comparison states, with no law. A leave-one-out check says whether the
pooled direction of the other precedents matches each precedent more often
than the naive answer "no clear change".

Every number is a description of the record and names the rows it counts.
The score is a direction from -2 to +2, never a probability, and the text says
"resembles", never that a law causes anything.

The core holds only the parts that do not depend on the industry: partial
dates, windows, the effect of one precedent, pooling, the fails branch, the
leave-one-out check, the wording guard and the lock check. What a precedent
is, what an event is, the metric list, the thresholds and every text stay in
each repository's adapter and config.

Standard library only. It reads no repository file, names no repository path
and imports nothing from either repository. Changing anything in this file
changes the format: copy the same bytes to both repositories and update both
locks in the same week.

Usage
  python policy_outlook_core.py --selftest
  python policy_outlook_core.py --check-lock LOCK
"""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import math
import os
import re
import statistics
import sys
from datetime import date

FORMAT_VERSION = 1
LOCK_KEYS = ("format_version", "core_sha256")

# Default rules. An adapter passes its own from config; these only fill gaps.
DEFAULT_RULES = {
    "window_months": 12,      # length of the before and the after window
    "min_events": 3,          # fewer events in a state's two windows: precedent too thin
    "min_precedents": 3,      # fewer usable precedents: no pooled direction
    "agreement": 0.67,        # share of usable precedents that must point the same way
    "smoothing": 0.5,         # added to counts before a log ratio
}

SCORE_WORDS = {
    2: "clearly higher than in comparison states",
    1: "higher than in comparison states",
    0: "no clear change against comparison states",
    -1: "lower than in comparison states",
    -2: "clearly lower than in comparison states",
}

# Causal and forecasting wording. An adapter fails its run when its own
# generated text matches; names copied from records are the caller's to skip.
BANNED = re.compile(
    r"\b(cause[sd]?|causing|because of|due to|led to|leads to|will|likely|unlikely|"
    r"probabilit\w*|odds|chance of|forecast\w*|predict\w*)\b",
    re.IGNORECASE,
)


def banned_hits(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in BANNED.finditer(text or "")})


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR = re.compile(r"^(\d{4})$")


def parse_partial(text: str):
    """Return (first_day, last_day) for 'YYYY-MM-DD', 'YYYY-MM' or 'YYYY', else None."""
    s = (text or "").strip()
    try:
        m = _DAY.match(s)
        if m:
            d = date(int(m[1]), int(m[2]), int(m[3]))
            return d, d
        m = _MONTH.match(s)
        if m:
            y, mo = int(m[1]), int(m[2])
            return date(y, mo, 1), date(y, mo, calendar.monthrange(y, mo)[1])
        m = _YEAR.match(s)
        if m:
            y = int(m[1])
            return date(y, 1, 1), date(y, 12, 31)
    except ValueError:
        return None
    return None


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    y += d.year
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def windows(effective: date, months: int):
    """Before window [start, effective) and after window [effective, end)."""
    return (add_months(effective, -months), effective), (effective, add_months(effective, months))


def in_window(span, win) -> bool:
    """True when the whole date span of an event lies inside the half-open window.
    An event dated only by year or month that straddles a boundary is left out
    of both windows rather than guessed into one."""
    lo, hi = span
    start, end = win
    return start <= lo and hi < end


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------
# An event is a dict with keys: state, kind, date (text), ref (row id).
# A metric is a dict: {"type": "count", "kind": k, "threshold": t} or
# {"type": "share", "num": k, "den": [k1, k2, ...], "threshold": t}.


def _index(events):
    out = {}
    for e in events:
        span = parse_partial(e.get("date", ""))
        if span is None:
            continue
        out.setdefault((e["state"], e["kind"]), []).append((span, e.get("ref", "")))
    return out


def _count(idx, state, kind, win):
    refs = [ref for span, ref in idx.get((state, kind), ()) if in_window(span, win)]
    return len(refs), refs


def _metric_counts(idx, state, metric, win):
    """(numerator, denominator, refs). For a count metric the denominator is None."""
    if metric["type"] == "count":
        n, refs = _count(idx, state, metric["kind"], win)
        return n, None, refs
    num, refs = _count(idx, state, metric["num"], win)
    den = 0
    all_refs = []
    for k in metric["den"]:
        c, r = _count(idx, state, k, win)
        den += c
        all_refs += r
    return num, den, sorted(set(all_refs))


def _direction(delta, threshold):
    if delta is None:
        return None
    if abs(delta) < threshold:
        return 0
    return 1 if delta > 0 else -1


def effect(idx, state, effective: date, metric, comparison_states, rules, as_of: date):
    """Describe one precedent (or the fails branch) for one metric."""
    r = {**DEFAULT_RULES, **(rules or {})}
    before, after = windows(effective, r["window_months"])
    out = {
        "state": state,
        "effective": effective.isoformat(),
        "before": [before[0].isoformat(), before[1].isoformat()],
        "after": [after[0].isoformat(), after[1].isoformat()],
        "comparison_states": len(comparison_states),
        "delta": None,
        "direction": None,
        "status": "ok",
    }
    if after[1] > as_of:
        out["status"] = "too_recent"
        return out
    nb, db, rb = _metric_counts(idx, state, metric, before)
    na, da, ra = _metric_counts(idx, state, metric, after)
    cb = [_metric_counts(idx, s, metric, before) for s in comparison_states]
    ca = [_metric_counts(idx, s, metric, after) for s in comparison_states]
    out.update({"state_before": nb, "state_after": na, "refs_before": rb, "refs_after": ra})
    k = r["smoothing"]
    if metric["type"] == "count":
        if nb + na < r["min_events"] or not comparison_states:
            out["status"] = "thin"
            return out
        mb = sum(c[0] for c in cb) / len(cb)
        ma = sum(c[0] for c in ca) / len(ca)
        out.update({"comparison_before_mean": round(mb, 3), "comparison_after_mean": round(ma, 3)})
        delta = math.log((na + k) / (nb + k)) - math.log((ma + k) / (mb + k))
    else:
        out.update({"state_before_den": db, "state_after_den": da})
        cdb = sum(c[1] for c in cb)
        cda = sum(c[1] for c in ca)
        if min(db, da) < r["min_events"] or min(cdb, cda) < r["min_events"]:
            out["status"] = "thin"
            return out
        cs_b = sum(c[0] for c in cb) / cdb
        cs_a = sum(c[0] for c in ca) / cda
        out.update({"comparison_before_share": round(cs_b, 4), "comparison_after_share": round(cs_a, 4)})
        delta = (na / da - nb / db) - (cs_a - cs_b)
    out["delta"] = round(delta, 4)
    out["direction"] = _direction(delta, metric["threshold"])
    return out


def comparison_states(universe, state, group_dates, effective: date, months: int):
    """States other than `state` with no precedent of the same group taking
    effect within `months` either side of `effective`."""
    lo, hi = add_months(effective, -months), add_months(effective, months)
    busy = {s for s, d in group_dates if lo <= d <= hi}
    return sorted(s for s in universe if s != state and s not in busy)


def pool(effects, threshold, rules=None):
    """Pool the usable precedent effects for one group and metric into a score."""
    r = {**DEFAULT_RULES, **(rules or {})}
    usable = [e for e in effects if e.get("direction") is not None]
    out = {"precedents": len(effects), "usable": len(usable), "score": None,
           "status": "too_few_precedents", "agree": 0}
    if len(usable) < r["min_precedents"]:
        return out
    tally = {s: sum(1 for e in usable if e["direction"] == s) for s in (-1, 0, 1)}
    sign, k = max(tally.items(), key=lambda kv: (kv[1], -abs(kv[0])))
    out["agree"] = k
    if k / len(usable) < r["agreement"]:
        out.update({"status": "mixed", "score": 0})
        return out
    if sign == 0:
        out.update({"status": "ok", "score": 0})
        return out
    med = statistics.median(abs(e["delta"]) for e in usable if e["direction"] == sign)
    strong = k == len(usable) and med >= 2 * threshold
    out.update({"status": "ok", "score": sign * (2 if strong else 1)})
    return out


def leave_one_out(effects, threshold, rules=None):
    """For each usable precedent, pool the others and compare directions.
    Returns how often the others' direction matched, and how often the naive
    answer 'no clear change' (0) matched."""
    usable = [e for e in effects if e.get("direction") is not None]
    tested = hits = naive = 0
    for i, e in enumerate(usable):
        p = pool(usable[:i] + usable[i + 1:], threshold, rules)
        if p["score"] is None:
            continue
        tested += 1
        hits += int((p["score"] > 0) - (p["score"] < 0) == e["direction"])
        naive += int(e["direction"] == 0)
    if tested == 0:
        verdict = "not_testable"
    elif hits > naive:
        verdict = "beats_naive"
    else:
        verdict = "no_reliable_pattern"
    return {"tested": tested, "matched": hits, "naive_matched": naive, "verdict": verdict}


def outlook(events, precedents, metrics, universe, rules, as_of: date, bills=()):
    """Run the whole model.

    precedents: list of dicts {id, state, group, effective (YYYY-MM-DD), ...}
    metrics: {name: metric}
    universe: list of state codes used for comparison
    bills: list of dicts {id, state, group, ...}; each gets both branches.

    Returns {"groups": {group: {metric: {...}}}, "bills": [...]}.
    """
    r = {**DEFAULT_RULES, **(rules or {})}
    idx = _index(events)
    by_group = {}
    for p in precedents:
        by_group.setdefault(p["group"], []).append(p)
    groups = {}
    for g, plist in sorted(by_group.items()):
        gdates = [(p["state"], date.fromisoformat(p["effective"])) for p in plist]
        groups[g] = {}
        for mname, m in metrics.items():
            effs = []
            for p in plist:
                eff = date.fromisoformat(p["effective"])
                comp = comparison_states(universe, p["state"], gdates, eff, r["window_months"])
                e = effect(idx, p["state"], eff, m, comp, r, as_of)
                e["precedent"] = p["id"]
                effs.append(e)
            pooled = pool(effs, m["threshold"], r)
            groups[g][mname] = {"pooled": pooled,
                                "validation": leave_one_out(effs, m["threshold"], r),
                                "effects": effs}
    out_bills = []
    for b in bills:
        res = {"bill": b["id"], "state": b["state"], "group": b["group"], "passes": {}, "fails": {}}
        plist = by_group.get(b["group"], [])
        gdates = [(p["state"], date.fromisoformat(p["effective"])) for p in plist]
        pseudo = add_months(as_of, -r["window_months"])
        for mname, m in metrics.items():
            g = groups.get(b["group"], {}).get(mname)
            res["passes"][mname] = dict(g["pooled"]) if g else {
                "precedents": 0, "usable": 0, "score": None, "status": "too_few_precedents", "agree": 0}
            res["passes"][mname]["validation"] = g["validation"]["verdict"] if g else "not_testable"
            comp = comparison_states(universe, b["state"], gdates, pseudo, r["window_months"])
            res["fails"][mname] = effect(idx, b["state"], pseudo, m, comp, r, as_of)
        out_bills.append(res)
    return {"groups": groups, "bills": out_bills}


def score_words(score, status):
    if status == "too_few_precedents":
        return "too few dated precedents"
    if status == "mixed":
        return "precedents point different ways"
    if score is None:
        return "not scored"
    return SCORE_WORDS[score]


# ---------------------------------------------------------------------------
# Lock
# ---------------------------------------------------------------------------

def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def lock_problems(lock_path, core_path=None) -> list[str]:
    core_path = core_path or os.path.abspath(__file__)
    try:
        with open(lock_path, encoding="utf-8") as f:
            lock = json.load(f)
    except (OSError, ValueError) as exc:
        return [f"cannot read lock {lock_path}: {exc}"]
    probs = [f"lock lacks {k}" for k in LOCK_KEYS if k not in lock]
    if lock.get("format_version") != FORMAT_VERSION:
        probs.append(f"lock format_version {lock.get('format_version')} != core {FORMAT_VERSION}")
    if lock.get("core_sha256") != sha256_file(core_path):
        probs.append("core SHA-256 differs from the lock")
    return probs


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> None:
    assert parse_partial("2024-03-05") == (date(2024, 3, 5), date(2024, 3, 5))
    assert parse_partial("2024-02") == (date(2024, 2, 1), date(2024, 2, 29))
    assert parse_partial("2024") == (date(2024, 1, 1), date(2024, 12, 31))
    assert parse_partial("spring 2024") is None and parse_partial("2024-13-01") is None
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2024, 3, 15), -12) == date(2023, 3, 15)
    win = (date(2024, 1, 1), date(2025, 1, 1))
    assert in_window(parse_partial("2024"), win)
    assert not in_window(parse_partial("2024"), (date(2024, 6, 1), date(2025, 6, 1)))

    # Five states. Precedent states A, B, C each see restrictions rise after
    # their law while comparison states D and E stay flat.
    eff = {"A": "2022-01-01", "B": "2022-06-01", "C": "2023-01-01"}
    events = []
    for s, d in eff.items():
        e0 = date.fromisoformat(d)
        for i in range(2):
            events.append({"state": s, "kind": "restr", "date": add_months(e0, -3 - i).isoformat(), "ref": f"{s}b{i}"})
        for i in range(8):
            events.append({"state": s, "kind": "restr", "date": add_months(e0, 1 + i).isoformat(), "ref": f"{s}a{i}"})
    for s in ("D", "E"):
        for m in range(0, 48, 6):
            events.append({"state": s, "kind": "restr", "date": add_months(date(2020, 6, 1), m).isoformat(), "ref": f"{s}{m}"})
    precedents = [{"id": f"p{s}", "state": s, "group": "limits", "effective": d} for s, d in eff.items()]
    metrics = {"restr": {"type": "count", "kind": "restr", "threshold": math.log(1.5)}}
    res = outlook(events, precedents, metrics, list("ABCDE"), {}, date(2026, 1, 1),
                  bills=[{"id": "billD", "state": "D", "group": "limits"},
                         {"id": "billX", "state": "D", "group": "nogroup"}])
    g = res["groups"]["limits"]["restr"]
    assert g["pooled"]["status"] == "ok" and g["pooled"]["score"] == 2, g["pooled"]
    assert all(e["direction"] == 1 for e in g["effects"])
    assert g["effects"][0]["refs_after"] and g["effects"][0]["comparison_states"] == 2
    assert g["validation"] == {"tested": 0, "matched": 0, "naive_matched": 0, "verdict": "not_testable"}
    b = res["bills"][0]
    assert b["passes"]["restr"]["score"] == 2 and b["fails"]["restr"]["status"] in ("ok", "thin")
    assert res["bills"][1]["passes"]["restr"]["status"] == "too_few_precedents"

    # Too recent and thin.
    e = effect(_index(events), "A", date(2025, 6, 1), metrics["restr"], ["D"], {}, date(2026, 1, 1))
    assert e["status"] == "too_recent"
    e = effect(_index(events), "A", date(2019, 1, 1), metrics["restr"], ["D"], {}, date(2026, 1, 1))
    assert e["status"] == "thin" and e["direction"] is None

    # Share metric and pooling rules.
    sm = {"type": "share", "num": "blk", "den": ["blk", "adv"], "threshold": 0.1}
    ev2 = ([{"state": "A", "kind": "adv", "date": "2021-0%d-01" % m, "ref": "x"} for m in range(1, 7)]
           + [{"state": "A", "kind": "blk", "date": "2022-0%d-01" % m, "ref": "y"} for m in range(1, 7)]
           + [{"state": "D", "kind": k, "date": f"{y}-03-01", "ref": "z"} for y in (2021, 2022) for k in ("adv", "blk", "adv", "blk")])
    e = effect(_index(ev2), "A", date(2022, 1, 1), sm, ["D"], {}, date(2026, 1, 1))
    assert e["direction"] == 1 and abs(e["delta"] - 1.0) < 1e-9, e
    mk = lambda d: {"direction": d, "delta": 0.5 * d}
    assert pool([mk(1), mk(-1), mk(0)], 0.1)["status"] == "mixed"
    assert pool([mk(1), mk(1)], 0.1)["status"] == "too_few_precedents"
    assert pool([mk(1), mk(1), mk(1), mk(0)], 0.1)["score"] == 1
    assert pool([mk(0), mk(0), mk(0)], 0.1)["score"] == 0
    loo = leave_one_out([mk(1)] * 4, 0.1)
    assert loo["tested"] == 4 and loo["matched"] == 4 and loo["verdict"] == "beats_naive"
    loo = leave_one_out([mk(0)] * 4, 0.1)
    assert loo["verdict"] == "no_reliable_pattern"

    assert banned_hits("This law will cause bans") == ["cause", "will"]
    assert banned_hits("Resembles what followed in 3 states") == []
    for w in SCORE_WORDS.values():
        assert not banned_hits(w)
    assert score_words(None, "too_few_precedents") == "too few dated precedents"
    print("policy_outlook_core selftest: ok")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--check-lock", metavar="LOCK")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
    if a.check_lock:
        probs = lock_problems(a.check_lock)
        for p in probs:
            print(p)
        if probs:
            return 1
        print("policy_outlook_core lock: ok")
    if not (a.selftest or a.check_lock):
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
