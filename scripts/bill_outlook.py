"""Bill outcome model for renewables: what followed past state laws like a tracked bill.

The renewables adapter for the shared core in scripts/policy_outlook_core.py
(pinned by config/policy_outlook_format.lock, the same bytes as
policy_outlook_core.py in data-centers). Settings, precedents and tracked
bills live in config/bill_outlook.json; nothing about a state or a bill is in
this file.

Inputs (all published or internal model files already in the repository):
  config/bill_outlook.json              rules, metrics, precedents, bills
  data/processed/state_policies.csv     the state laws each precedent rests on
  data/processed/restrictions.csv       local restrictions with a year or date
  data/processed/contested_projects.csv contested projects blocked or advanced
  data/model/headwind_history.csv       interconnection requests withdrawn or operating

Outputs (internal; no page reads them):
  data/model/bill_outlook.json          every effect, pooled score and check, with row ids
  data/model/bill_outlook_report.md     the same in words

The model describes resemblance to past records. A score is a direction from
-2 to +2 against comparison states. It is not a probability, and nothing here
says a law causes what followed.

Usage
  python scripts/bill_outlook.py            build both outputs
  python scripts/bill_outlook.py --check    validate the config only
  python scripts/bill_outlook.py --as-of 2026-11-24
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import policy_outlook_core as core  # noqa: E402
from common import ROOT, read_csv  # noqa: E402
from county_labels import year_of  # noqa: E402

CONFIG = ROOT / "config" / "bill_outlook.json"
LOCK = ROOT / "config" / "policy_outlook_format.lock"
POLICIES = ROOT / "data" / "processed" / "state_policies.csv"
RESTRICTIONS = ROOT / "data" / "processed" / "restrictions.csv"
PROJECTS = ROOT / "data" / "processed" / "contested_projects.csv"
QUEUE = ROOT / "data" / "model" / "headwind_history.csv"
OUT_JSON = ROOT / "data" / "model" / "bill_outlook.json"
OUT_MD = ROOT / "data" / "model" / "bill_outlook_report.md"


def load_config(path: Path = CONFIG) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def config_problems(cfg: dict, policies: list[dict]) -> list[str]:
    """Every precedent rests on published state_policies rows, sits in a known
    group, has an ISO date, and quotes its date word for word from one of its rows."""
    by_id = {p["id"]: p for p in policies}
    probs = []
    groups = set(cfg.get("groups", {}))
    seen = set()
    for p in cfg.get("precedents", []):
        pid = p.get("id", "?")
        if pid in seen:
            probs.append(f"{pid}: duplicate id")
        seen.add(pid)
        if p.get("group") not in groups:
            probs.append(f"{pid}: unknown group {p.get('group')!r}")
        try:
            eff = date.fromisoformat(p.get("effective", ""))
        except ValueError:
            probs.append(f"{pid}: effective is not YYYY-MM-DD")
            continue
        rows = [by_id.get(i) for i in p.get("state_policy_ids", [])]
        if not rows or None in rows:
            probs.append(f"{pid}: state_policy_ids missing from state_policies.csv")
            continue
        if any(r["state"] != p.get("state") for r in rows):
            probs.append(f"{pid}: a state_policies row is for another state")
        quote = p.get("date_quote", "")
        if not quote or not any(quote in (r["summary"] + " " + r["amendments_note"]) for r in rows):
            probs.append(f"{pid}: date_quote not found in its state_policies rows")
        if str(eff.year) not in quote:
            probs.append(f"{pid}: date_quote does not contain the effective year")
    for b in cfg.get("bills", []):
        for k in ("id", "state", "group", "source_url"):
            if not b.get(k):
                probs.append(f"bill {b.get('id', '?')}: missing {k}")
        if b.get("group") and b["group"] not in groups:
            probs.append(f"bill {b.get('id', '?')}: unknown group {b['group']!r}")
    for name, m in cfg.get("metrics", {}).items():
        if m.get("type") not in ("count", "share") or "threshold" not in m:
            probs.append(f"metric {name}: needs type count or share and a threshold")
    return probs


def build_events(restrictions, projects, queue) -> list[dict]:
    events = []
    for r in restrictions:
        iso = (r.get("date_enacted_iso") or "").strip()
        when = iso[:10] if iso else (str(year_of(r)) if year_of(r) else "")
        if when and r.get("state"):
            events.append({"state": r["state"], "kind": "local_restriction", "date": when, "ref": r["id"]})
    for p in projects:
        out = p.get("outcome", "")
        kind = "project_blocked" if out.startswith("blocked_") else "project_advanced" if out.startswith("advanced_") else ""
        when = (p.get("resolution_date") or p.get("event_date_text") or "").strip()
        if kind and when and p.get("state"):
            events.append({"state": p["state"], "kind": kind, "date": when, "ref": p["id"]})
    for q in queue:
        if q.get("source") != "queue" or not q.get("outcome_date"):
            continue
        kind = {"withdrawn": "queue_withdrawn", "operational": "queue_operating"}.get(q.get("outcome", ""))
        if kind and q.get("state"):
            events.append({"state": q["state"], "kind": kind, "date": q["outcome_date"], "ref": q["row_id"]})
    return events


def commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run(cfg: dict, policies, restrictions, projects, queue, as_of: date) -> dict:
    universe = sorted({p["state"] for p in policies if p.get("state")})
    events = build_events(restrictions, projects, queue)
    bills = list(cfg.get("bills", []))
    recent = []
    if cfg.get("recent_record_all_states"):
        recent = [{"id": f"recent:{s}", "state": s, "group": ""} for s in universe]
    res = core.outlook(events, cfg["precedents"], cfg["metrics"], universe, cfg.get("rules", {}),
                       as_of, bills=bills + recent)
    res["recent_record"] = [b for b in res["bills"] if b["bill"].startswith("recent:")]
    res["bills"] = [b for b in res["bills"] if not b["bill"].startswith("recent:")]
    for b in res["recent_record"]:
        del b["passes"]
    res["stamp"] = {"as_of": as_of.isoformat(), "commit": commit(), "core_format": core.FORMAT_VERSION,
                    "config": "config/bill_outlook.json", "events": len(events),
                    "events_by_kind": {k: sum(1 for e in events if e["kind"] == k)
                                       for k in sorted({e["kind"] for e in events})}}
    return res


def _fmt_delta(m, d):
    if d is None:
        return ""
    return f"{d:+.2f} (log ratio)" if m["type"] == "count" else f"{round(d * 100):+d} points"


def report(cfg: dict, res: dict) -> str:
    m = cfg["metrics"]
    st = res["stamp"]
    lines = [
        "# Bill outcome model: what followed past state laws",
        "",
        f"Built {st['as_of']} from commit {st['commit']} with {st['config']} (core format {st['core_format']}).",
        "",
        "For each kind of state law, this report lists the past laws of that kind with a sourced effective date "
        "(the precedents). For each one it compares the state's record in the "
        f"{cfg['rules']['window_months']} months after the law with the "
        f"{cfg['rules']['window_months']} months before it, against the same change in comparison states over the "
        "same months. Comparison states are those with no law of the same kind taking effect in that span. "
        "A score is a direction from -2 to +2 and describes resemblance to past records only. "
        "The record does not show that a law produced what followed.",
        "",
        "Events counted: " + ", ".join(f"{k} {v}" for k, v in st["events_by_kind"].items()) + ". "
        "An event dated only by year is counted only when the whole year falls inside one window. "
        "Recent months are less complete than older ones in every state, which the comparison states partly offset.",
        "",
    ]
    for g, desc in cfg["groups"].items():
        lines += [f"## {g}", "", desc, ""]
        gres = res["groups"].get(g)
        if not gres:
            lines += ["No precedent is listed for this kind of law.", ""]
            continue
        lines += ["| Measure | Score | Reading | Usable precedents | Leave-one-out check |", "|---|---|---|---|---|"]
        for name, r in gres.items():
            p, v = r["pooled"], r["validation"]
            score = "" if p["score"] is None else f"{p['score']:+d}"
            check = v["verdict"] if v["tested"] == 0 else f"{v['verdict']} ({v['matched']} of {v['tested']} matched; naive {v['naive_matched']})"
            lines.append(f"| {m[name]['label']} | {score} | {core.score_words(p['score'], p['status'])} | "
                         f"{p['usable']} of {p['precedents']} | {check} |")
        lines += ["", "| Precedent | Measure | Status | State before, after | Change against comparison | Direction |",
                  "|---|---|---|---|---|---|"]
        for name, r in gres.items():
            for e in r["effects"]:
                ba = "" if "state_before" not in e else f"{e['state_before']}, {e['state_after']}"
                if m[name]["type"] == "share" and "state_before_den" in e:
                    ba = f"{e['state_before']}/{e['state_before_den']}, {e['state_after']}/{e['state_after_den']}"
                d = "" if e["direction"] is None else f"{e['direction']:+d}"
                lines.append(f"| {e['precedent']} ({e['state']}, {e['effective']}) | {m[name]['label']} | "
                             f"{e['status']} | {ba} | {_fmt_delta(m[name], e['delta'])} | {d} |")
        lines.append("")
    lines += ["## Tracked bills", ""]
    if not res["bills"]:
        lines += ["No bill is listed in config/bill_outlook.json yet. Add one entry per bill (id, state, group, "
                  "source_url) and rebuild. Its passes branch is the pooled score of its group above, and its "
                  "fails branch is the state's recent record below.", ""]
    for b in res["bills"]:
        lines += [f"### {b['bill']} ({b['state']}, {b['group']})", "",
                  "| Measure | If it passes: resembles | If it fails: recent record |", "|---|---|---|"]
        for name in m:
            p, f = b["passes"][name], b["fails"][name]
            fd = "" if f["direction"] is None else f"{f['direction']:+d}"
            lines.append(f"| {m[name]['label']} | {core.score_words(p['score'], p['status'])} | "
                         f"{f['status']} {fd} {_fmt_delta(m[name], f['delta'])} |")
        lines.append("")
    if res.get("recent_record"):
        lines += ["## Recent record by state (the fails branch)", "",
                  "The last window against the window before it, compared with the same change in all other states.",
                  "", "| State | " + " | ".join(m[n]["label"] for n in m) + " |",
                  "|---|" + "---|" * len(m)]
        for b in res["recent_record"]:
            cells = []
            for n in m:
                f = b["fails"][n]
                cells.append(f["status"] if f["direction"] is None else f"{f['direction']:+d} {_fmt_delta(m[n], f['delta'])}")
            lines.append(f"| {b['state']} | " + " | ".join(cells) + " |")
        lines.append("")
    text = "\n".join(lines)
    hits = core.banned_hits(text)
    if hits:
        raise SystemExit(f"bill_outlook: report uses banned wording {hits}")
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="validate the config and the core lock only")
    ap.add_argument("--as-of", default=date.today().isoformat())
    a = ap.parse_args(argv)
    cfg = load_config()
    policies = read_csv(POLICIES)
    probs = core.lock_problems(LOCK, core.__file__) + config_problems(cfg, policies)
    for p in probs:
        print(f"bill_outlook: {p}")
    if probs:
        return 1
    if a.check:
        print(f"bill_outlook: config ok ({len(cfg['precedents'])} precedents, {len(cfg.get('bills', []))} bills)")
        return 0
    res = run(cfg, policies, read_csv(RESTRICTIONS), read_csv(PROJECTS), read_csv(QUEUE),
              date.fromisoformat(a.as_of))
    OUT_JSON.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(report(cfg, res), encoding="utf-8")
    print(f"bill_outlook: wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
