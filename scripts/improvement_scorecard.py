"""Grade the two improvement tracks once a month: pipeline depth and algorithm breadth.

The standing improvement structure (docs/model_program.md, section 7). Every
measure in config/improvement_program.json is read from a file another
module wrote, compared with its target and its pace, and graded:

  met      the target is reached
  on_pace  at least where a straight line from the first graded value to the
           target on its date would put it today (a milestone, a yes or no
           measure, is on pace until its date)
  behind   neither

The month's grades are added to data/model/improvement_history.csv (one row
per measure per month; a second run in a month replaces that month's rows).
A measure graded behind in two months in a row is listed under
"needs_action" with the routine that moves it, and the monthly workflow
opens one issue for the list. The script reads no web page and changes no
data.

Writes (internal)
  data/model/improvement_history.csv   month, track, measure, value, target,
                                       by, status
  data/model/improvement_scorecard.json the month's grades and needs_action
  data/model/improvement_scorecard.md   the same as a report

Usage
  python scripts/improvement_scorecard.py [--today YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, read_csv, write_csv  # noqa: E402

PROGRAM_REL = Path("config") / "improvement_program.json"
HISTORY_PATH = ROOT / "data" / "model" / "improvement_history.csv"
JSON_PATH = ROOT / "data" / "model" / "improvement_scorecard.json"
REPORT_PATH = ROOT / "data" / "model" / "improvement_scorecard.md"
HISTORY_FIELDS = ["month", "track", "measure", "value", "target", "by", "status"]
YEAR = re.compile(r"\b(1[89]\d\d|20\d\d)\b")


# ── Reading a measure ───────────────────────────────────────────────────────
def _matches(row: dict, cond: dict) -> bool:
    for col, want in cond.items():
        if col == "_has_year":
            if not any(YEAR.search(row.get(c) or "") for c in want):
                return False
        elif (row.get(col) or "") not in want:
            return False
    return True


def _path(data, path: str):
    for part in path.split("."):
        data = data.get(part) if isinstance(data, dict) else None
    return data


def value_of(m: dict, root: Path) -> float | None:
    """The measure's current value, or None when its file is missing."""
    f = root / m["file"]
    kind = m["kind"]
    if kind == "file_exists":
        return 1.0 if f.exists() else 0.0
    if not f.exists():
        return None
    if kind == "csv_share":
        rows = read_csv(f)
        den = [r for r in rows if _matches(r, m["denominator"])]
        return sum(_matches(r, m["numerator"]) for r in den) / len(den) if den else None
    if kind == "csv_count":
        return float(sum(_matches(r, m.get("where", {})) for r in read_csv(f)))
    if kind == "csv_distinct_share":
        n = len({r[m["column"]] for r in read_csv(f) if r.get(m["column"])})
        d = len(read_csv(root / m["denominator_file"]))
        return n / d if d else None
    data = json.loads(f.read_text(encoding="utf-8"))
    if kind == "json_fills_share":
        wanted = {w["id"] for w in data.get("wanted", [])}
        filled = {i.get("fills") for i in data.get("inputs", [])}
        return len(wanted & filled) / len(wanted) if wanted else None
    if kind == "json_value":
        v = _path(data, m["path"])
        if "equals" in m:
            return 1.0 if v == m["equals"] else 0.0
        if "count_field" in m:
            return float(sum(1 for x in (v or []) if isinstance(x, dict) and x.get(m["count_field"])))
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    raise ValueError(f"unknown measure kind {kind!r}")


# ── Grading ─────────────────────────────────────────────────────────────────
def grade(m: dict, value: float | None, first: tuple[dt.date, float] | None, today: dt.date) -> str:
    if value is None:
        return "missing"
    low = m.get("lower_is_better", False)
    target = float(m["target"])
    if (value <= target) if low else (value >= target):
        return "met"
    by = dt.date.fromisoformat(m["by"])
    if m.get("milestone"):
        return "on_pace" if today <= by else "behind"
    if today >= by:
        return "behind"
    if first is None:
        return "on_pace"
    d0, v0 = first
    span = (by - d0).days
    if span <= 0:
        return "behind"
    pace = v0 + (target - v0) * min(max((today - d0).days / span, 0), 1)
    return "on_pace" if ((value <= pace) if low else (value >= pace)) else "behind"


def build(program: dict, root: Path, today: dt.date, history: list[dict]) -> tuple[dict, list[dict]]:
    month = today.isoformat()[:7]
    keep = [h for h in history if h["month"] != month]
    rows, tracks, needs = [], {}, []
    for track, spec in program["tracks"].items():
        out = []
        for m in spec["measures"]:
            past = sorted((h for h in keep if h["measure"] == m["id"] and h["value"] != ""),
                          key=lambda h: h["month"])
            first = (dt.date.fromisoformat(past[0]["month"] + "-01"), float(past[0]["value"])) if past else None
            v = value_of(m, root)
            status = grade(m, v, first, today)
            prev = past[-1]["status"] if past else ""
            g = {"id": m["id"], "goal": m.get("goal", ""), "label": m["label"],
                 "value": None if v is None else round(v, 4), "target": m["target"], "by": m["by"],
                 "status": status, "previous": prev, "moved_by": m.get("moved_by", "")}
            if status == "behind" and prev == "behind":
                needs.append(g)
            out.append(g)
            rows.append({"month": month, "track": track, "measure": m["id"],
                         "value": "" if v is None else round(v, 4), "target": m["target"],
                         "by": m["by"], "status": status})
        tracks[track] = {"label": spec["label"], "measures": out}
    card = {"as_of": today.isoformat(), "program_version": program.get("version", ""),
            "tracks": tracks, "needs_action": [f"{g['label']} ({g['goal']}): {g['value']} against "
                                               f"{g['target']} by {g['by']}; moved by {g['moved_by']}"
                                               for g in needs]}
    return card, keep + rows


def _v(v) -> str:
    if v is None:
        return ""
    return f"{v:g}" if float(v).is_integer() else f"{v:.3f}"


def report(card: dict) -> str:
    lines = ["# Improvement scorecard", "",
             f"Graded {card['as_of']} by `scripts/improvement_scorecard.py` against the targets in "
             "`config/improvement_program.json`. Internal. A measure is met, on pace (on or above a straight "
             "line from its first grade to its target date) or behind.", ""]
    for t in card["tracks"].values():
        lines += [f"## {t['label']}", "", "| Goal | Measure | Value | Target | By | Status | Moved by |",
                  "|---|---|---:|---:|---|---|---|"]
        for g in t["measures"]:
            lines.append(f"| {g['goal']} | {g['label']} | {_v(g['value'])} | {g['target']} | {g['by']} "
                         f"| {g['status'].replace('_', ' ')} | {g['moved_by']} |")
        lines.append("")
    lines += ["## Behind two months in a row", ""]
    lines += [f"- {n}" for n in card["needs_action"]] or ["None."]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    args = ap.parse_args()
    program = json.loads((ROOT / PROGRAM_REL).read_text(encoding="utf-8"))
    history = read_csv(HISTORY_PATH) if HISTORY_PATH.exists() else []
    card, history = build(program, ROOT, args.today, history)
    write_csv(HISTORY_PATH, history, HISTORY_FIELDS)
    JSON_PATH.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(report(card), encoding="utf-8")
    for t in card["tracks"].values():
        print(f"{t['label']}: " + ", ".join(f"{g['id']} {g['status']}" for g in t["measures"]))
    for n in card["needs_action"]:
        print(f"Behind twice: {n}")
    print(f"Wrote {HISTORY_PATH.relative_to(ROOT)}, {JSON_PATH.relative_to(ROOT)}, {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
