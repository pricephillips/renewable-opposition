"""Score every frozen vintage forward, and open or close each model's stages by rule.

The model improvement program (docs/model_program.md, stage one). For each
vintage in data/model/vintages/manifest.csv, the scorecard reads the outcomes
recorded since (config/model_program.json "outcome"), measures the vintage on
them, and checks the measures against the targets of each stage. It is the
only source for an accuracy figure a client may ever see; backtests and
vintages whose horizon has not ended are reported, but labelled, and they
never open a stage.

Measures, per vintage
  auc           ranking of the rank score (the score the pilot band is cut
                from): the chance that a county with the event, picked at
                random, scores above one without it
  auc_chance    the same for the chance score
  brier_skill   accuracy gain of the chance score over the base rate
  ece           calibration error of the chance score (5 equal-width bins)
Brier skill and ECE come from scripts/calibration_gate.py, the shared gate.

Stage rule (each model, each stage)
  Periods are matured live vintages at least one horizon apart, chained back
  from the latest. A vintage passes a stage when it has the minimum sample and
  positives and meets every target. A closed stage opens when its last
  `periods` periods all pass; an open stage closes after `close_after_misses`
  misses in a row. The rule is applied from the oldest period forward, so the
  result is the same on every run with the same inputs.

Writes (internal)
  data/model/model_scorecard.json   every measure, every stage's state, and
                                    what changed since the committed file
  data/model/model_scorecard.md     the same as a report

Usage
  python scripts/model_scorecard.py [--today YYYY-MM-DD] [--github-output PATH]

--github-output appends stage_changed=true|false and a one-line message, for
the monthly workflow to open an issue when a stage opens or closes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from calibration_gate import brier, ece  # noqa: E402
from common import ROOT, read_csv  # noqa: E402
from county_labels import SEVERE, counties_of  # noqa: E402
from model_vintage import VINTAGE_REL  # noqa: E402

PROGRAM_PATH = ROOT / "config" / "model_program.json"
JSON_PATH = ROOT / "data" / "model" / "model_scorecard.json"
REPORT_PATH = ROOT / "data" / "model" / "model_scorecard.md"


# ── Dates ───────────────────────────────────────────────────────────────────
def add_months(d: dt.date, months: int) -> dt.date:
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    last = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)).day
    return dt.date(y, m, min(d.day, last))


def enacted_interval(row: dict) -> tuple[dt.date, dt.date] | None:
    """The earliest and latest day the rule can have been enacted, or None when
    undated. date_enacted_iso first (day, month or year), else the first year
    in date_text."""
    iso = (row.get("date_enacted_iso") or "").strip()
    m = re.fullmatch(r"(\d{4})(?:-(\d\d)(?:-(\d\d))?)?", iso)
    if m:
        y, mo, d = int(m.group(1)), m.group(2), m.group(3)
        if d:
            day = dt.date(y, int(mo), int(d))
            return day, day
        if mo:
            lo = dt.date(y, int(mo), 1)
            return lo, add_months(lo, 1) - dt.timedelta(days=1)
        return dt.date(y, 1, 1), dt.date(y, 12, 31)
    m = re.search(r"\b(1[89]\d\d|20\d\d)\b", row.get("date_text") or "")
    if m:
        y = int(m.group(1))
        return dt.date(y, 1, 1), dt.date(y, 12, 31)
    return None


def severe_intervals(restrictions: list[dict]) -> dict[str, list]:
    out = defaultdict(list)
    for r in restrictions:
        if r.get("severity_score") in SEVERE:
            iv = enacted_interval(r)
            for f in counties_of(r):
                out[f].append(iv)
    return out


def outcome(intervals: list, start: dt.date, end: dt.date) -> tuple[int | None, str]:
    """(1, '') when the first severe rule falls in (start, end]; (0, '') when
    none does; (None, reason) when the county cannot be placed."""
    if not intervals:
        return 0, ""
    if any(iv is None for iv in intervals):
        return None, "undated"
    if any(hi <= start for _, hi in intervals):
        return None, "on_or_before_vintage"
    if any(lo <= start for lo, _ in intervals):
        return None, "straddles_vintage"
    if any(hi <= end for _, hi in intervals):
        return 1, ""
    if all(lo > end for lo, _ in intervals):
        return 0, ""
    return None, "straddles_horizon_end"


# ── Measures ────────────────────────────────────────────────────────────────
def auc(scores: list[float], y: list[int]) -> float | None:
    """Mann-Whitney AUC with ties counted half."""
    pos = [s for s, t in zip(scores, y) if t]
    neg = [s for s, t in zip(scores, y) if not t]
    if not pos or not neg:
        return None
    ordered = sorted(scores)
    rank, i = {}, 0
    while i < len(ordered):
        j = i
        while j < len(ordered) and ordered[j] == ordered[i]:
            j += 1
        rank[ordered[i]] = (i + 1 + j) / 2  # mean of ranks i+1 .. j
        i = j
    r_pos = sum(rank[s] for s in pos)
    return (r_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def measure(rows: list[dict], intervals: dict, start: dt.date, end: dt.date) -> dict:
    placed, excluded = [], defaultdict(int)
    for r in rows:
        y, why = outcome(intervals.get(r["county_fips"], []), start, end)
        if y is None:
            excluded[why] += 1
        else:
            placed.append((r, y))
    y = [t for _, t in placed]
    rank = [(float(r["rank_score"]), t) for r, t in placed if r.get("rank_score") not in ("", None)]
    ch = [(float(r["chance_horizon"]), t) for r, t in placed if r.get("chance_horizon") not in ("", None)]
    out = {"n": len(y), "positives": sum(y), "excluded": dict(sorted(excluded.items())),
           "auc": None, "auc_chance": None, "brier_skill": None, "ece": None, "base_rate": None}
    if y:
        out["base_rate"] = round(sum(y) / len(y), 4)
    if rank:
        a = auc([s for s, _ in rank], [t for _, t in rank])
        out["auc"] = None if a is None else round(a, 4)
    if ch:
        p, t = [s for s, _ in ch], [v for _, v in ch]
        a = auc(p, t)
        out["auc_chance"] = None if a is None else round(a, 4)
        base = sum(t) / len(t)
        b0 = base * (1 - base)
        out["brier_skill"] = round(1 - brier(p, t) / b0, 4) if b0 else None
        out["ece"] = round(ece(p, t), 4)
    return out


def passes(m: dict, stage: dict, spec: dict) -> tuple[bool, list[str]]:
    why = []
    if m["n"] < spec["min_sample"]:
        why.append(f"n {m['n']} < {spec['min_sample']}")
    if m["positives"] < spec["min_positives"]:
        why.append(f"positives {m['positives']} < {spec['min_positives']}")
    for key, op, target in (("auc", ">=", stage.get("auc_min")), ("brier_skill", ">=", stage.get("brier_skill_min")),
                            ("ece", "<=", stage.get("ece_max"))):
        if target is None:  # a stage that sets no target for this measure
            continue
        v = m.get(key)
        if v is None:
            why.append(f"{key} not measured")
        elif (op == ">=" and v < target) or (op == "<=" and v > target):
            why.append(f"{key} {v} {'<' if op == '>=' else '>'} {target}")
    return not why, why


def periods(vintages: list[dict], horizon: int) -> list[dict]:
    """Matured live vintages one horizon apart, chained back from the latest;
    returned oldest first."""
    chain, last = [], None
    for v in sorted(vintages, key=lambda v: v["as_of"], reverse=True):
        d = dt.date.fromisoformat(v["as_of"])
        if last is None or add_months(d, horizon) <= last:
            chain.append(v)
            last = d
    return list(reversed(chain))


def stage_states(chain: list[dict], spec: dict) -> dict:
    out = {}
    for stage in spec["stages"]:
        state, run, misses, history = "closed", 0, 0, []
        for v in chain:
            ok, _ = passes(v["measures"], stage, spec)
            run, misses = (run + 1, 0) if ok else (0, misses + 1)
            if state == "closed" and run >= stage["periods"]:
                state = "open"
            elif state == "open" and misses >= spec["close_after_misses"]:
                state = "closed"
            history.append({"vintage_id": v["vintage_id"], "pass": ok})
        out[stage["stage"]] = {"state": state, "periods_needed": stage["periods"],
                               "passes_in_a_row": run, "history": history}
    return out


# ── Scorecard ───────────────────────────────────────────────────────────────
def build(program: dict, root: Path, today: dt.date) -> dict:
    manifest_path = root / VINTAGE_REL / "manifest.csv"
    manifest = read_csv(manifest_path) if manifest_path.exists() else []
    models = {}
    for model, spec in program["models"].items():
        intervals = severe_intervals(read_csv(root / spec["outcome"]["file"]))
        vs = []
        for m in (m for m in manifest if m["model"] == model):
            start = dt.date.fromisoformat(m["as_of"])
            end = add_months(start, spec["horizon_months"])
            rows = read_csv(root / VINTAGE_REL / model / f"{m['vintage_id']}.csv")
            vs.append({"vintage_id": m["vintage_id"], "kind": m["kind"], "as_of": m["as_of"],
                       "horizon_end": end.isoformat(), "matured": today >= end,
                       "measures": measure(rows, intervals, start, min(end, today))})
        matured_live = [v for v in vs if v["kind"] == "live" and v["matured"]]
        chain = periods(matured_live, spec["horizon_months"])
        states = stage_states(chain, spec)
        stop = spec.get("stop_rule")
        stop_hit = bool(stop and today > dt.date.fromisoformat(stop["by"])
                        and states.get(stop["stage"], {}).get("state") != "open")
        models[model] = {"name": spec["name"], "horizon_months": spec["horizon_months"],
                         "vintages": sorted(vs, key=lambda v: v["as_of"]),
                         "periods": [v["vintage_id"] for v in chain], "stages": states,
                         "stop_rule_reached": stop_hit}
    return {"as_of": today.isoformat(), "program_version": program.get("version", ""), "models": models}


def changes(old: dict, new: dict) -> list[str]:
    out = []
    for model, m in new["models"].items():
        prev = old.get("models", {}).get(model, {})
        for stage, s in m["stages"].items():
            before = prev.get("stages", {}).get(stage, {}).get("state", "closed")
            if s["state"] != before:
                out.append(f"{m['name']}: stage {stage} {before} -> {s['state']}")
        if m["stop_rule_reached"] and not prev.get("stop_rule_reached"):
            out.append(f"{m['name']}: stop rule reached")
    return out


def _f(v) -> str:
    return "" if v is None else f"{v:.3f}" if isinstance(v, float) else str(v)


def report(card: dict, program: dict) -> str:
    lines = ["# Model scorecard", "",
             f"Built {card['as_of']} by `scripts/model_scorecard.py` from the frozen vintages in "
             "`data/model/vintages/` and the targets in `config/model_program.json`. Internal.", "",
             "Each vintage is scored on the outcomes recorded since it was frozen. A **provisional** row's "
             "horizon has not ended, so its counts are still growing. A **backtest** row was made after its date. "
             "Neither kind opens a stage; only matured live vintages do.", ""]
    for model, m in card["models"].items():
        spec = program["models"][model]
        lines += [f"## {m['name']}", "",
                  f"Horizon {m['horizon_months']} months. Rank score `{spec['scores']['rank_column']}`, "
                  f"chance score `{spec['scores'].get('chance_column', '')}`.", "",
                  "| Vintage | Kind | Horizon ends | Status | Counties | Events | Left out | AUC | AUC (chance) "
                  "| Brier skill | ECE |",
                  "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
        for v in m["vintages"]:
            x = v["measures"]
            status = "matured" if v["matured"] else "provisional"
            lines.append(f"| {v['vintage_id']} | {v['kind']} | {v['horizon_end']} | {status} | {x['n']} "
                         f"| {x['positives']} | {sum(x['excluded'].values())} | {_f(x['auc'])} "
                         f"| {_f(x['auc_chance'])} | {_f(x['brier_skill'])} | {_f(x['ece'])} |")
        if not m["vintages"]:
            lines.append("| none yet | | | | | | | | | | |")
        lines += ["", "| Stage | Targets (AUC, Brier skill, ECE) | Periods needed | State | Passes in a row |",
                  "|---|---|---:|---|---:|"]
        for st in spec["stages"]:
            s = m["stages"][st["stage"]]
            lines.append(f"| {st['stage']} | {st.get('auc_min')}, {st.get('brier_skill_min') if st.get('brier_skill_min') is not None else 'not set'}, {st.get('ece_max')} "
                         f"| {st['periods']} | {s['state']} | {s['passes_in_a_row']} |")
        lines += ["", f"Periods scored: {len(m['periods'])}. "
                  + ("The stop rule has been reached." if m["stop_rule_reached"] else
                     f"Stop rule: {spec['stop_rule']['stage']} must open by {spec['stop_rule']['by']}."
                     if spec.get("stop_rule") else ""), ""]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--github-output", type=Path)
    args = ap.parse_args()
    program = json.loads(PROGRAM_PATH.read_text(encoding="utf-8"))
    old = json.loads(JSON_PATH.read_text(encoding="utf-8")) if JSON_PATH.exists() else {}
    card = build(program, ROOT, args.today)
    changed = changes(old, card)
    card["changed"] = changed
    JSON_PATH.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(report(card, program), encoding="utf-8")
    for model, m in card["models"].items():
        print(f"{m['name']}: {len(m['vintages'])} vintages, {len(m['periods'])} periods scored; "
              + ", ".join(f"{k} {v['state']}" for k, v in m["stages"].items()))
    for c in changed:
        print(f"Changed: {c}")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as f:
            f.write(f"stage_changed={'true' if changed else 'false'}\n")
            f.write(f"message={'; '.join(changed)}\n")
    print(f"Wrote {JSON_PATH.relative_to(ROOT)}, {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
