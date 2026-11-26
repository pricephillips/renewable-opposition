"""Freeze each model's scores once a month, so they can be scored later on what happened.

The model improvement program (docs/model_program.md, stage one). A vintage is
the model's scores for the counties still at risk, saved on the day they were
made, with the commit and the input hashes that made them. A frozen file is
never edited: the scorecard (scripts/model_scorecard.py) can trust that a
vintage says what the model said on its date, not what a later refit says.

Reads (config/model_program.json names each file)
  the model's scores, the band file, the at-risk frame

Writes
  data/model/vintages/<model>/<vintage_id>.csv   one row per county at risk:
        county_fips, state, county, rank_score, chance_window, chance_horizon,
        and the band columns
  data/model/vintages/manifest.csv               one row per vintage: model,
        vintage_id, kind (live or backtest), as_of, frozen_on, commit,
        scores_sha256, registration_sha256, program_sha256, rows

Rules
  - One live vintage per model per month. A second run in the same month
    freezes nothing.
  - A backtest vintage (config "backtest") is frozen once, as of its stated
    date, from the first scores file that carries the chance column. It is
    labelled a backtest in the manifest and never opens a stage.
  - An existing vintage file is never rewritten.

Usage
  python scripts/model_vintage.py [--today YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, read_csv, write_csv  # noqa: E402

PROGRAM_REL = Path("config") / "model_program.json"
VINTAGE_REL = Path("data") / "model" / "vintages"
PROGRAM_PATH = ROOT / PROGRAM_REL
MANIFEST_FIELDS = ["model", "vintage_id", "kind", "as_of", "frozen_on", "commit", "scores_sha256",
                   "registration_sha256", "program_sha256", "rows"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def commit(root: Path) -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _float(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def horizon_chance(p: float | None, window_years: float, horizon_months: int) -> float | None:
    """The window's chance turned into the horizon's: 1 - (1 - p) ^ (h / w)."""
    if p is None:
        return None
    p = min(max(p, 0.0), 1.0)
    return 1 - (1 - p) ** ((horizon_months / 12) / window_years)


def vintage_rows(spec: dict, root: Path, kind: str) -> list[dict]:
    """The counties a vintage holds, with their scores.

    live: every county at risk today (has_severe == 0 in the frame file).
    backtest: every county with a chance score (the held-back model scored
    exactly the counties at risk at its as-of date).
    """
    s = spec["scores"]
    scores = {r["county_fips"]: r for r in read_csv(root / s["file"])}
    frame = {r["county_fips"]: r for r in read_csv(root / spec["frame"]["file"])}
    band_cols = spec.get("band", {}).get("columns", [])
    bands = ({r["county_fips"]: r for r in read_csv(root / spec["band"]["file"])}
             if band_cols and (root / spec["band"]["file"]).exists() else {})
    cc = s.get("chance_column", "")
    out = []
    for f, r in sorted(scores.items()):
        chance = _float(r.get(cc)) if cc else None
        if kind == "live":
            if frame.get(f, {}).get("has_severe") != "0":
                continue
        elif chance is None:
            continue
        rank = _float(r.get(s["rank_column"]))
        ch = horizon_chance(chance, s.get("chance_window_years", 1), spec["horizon_months"])
        row = {"county_fips": f, "state": r.get("state", ""), "county": r.get("county", ""),
               "rank_score": "" if rank is None else round(rank, 4),
               "chance_window": "" if chance is None else round(chance, 4),
               "chance_horizon": "" if ch is None else round(ch, 4)}
        for c in band_cols:
            row[c] = bands.get(f, {}).get(c, "")
        out.append(row)
    return out


def freeze(program: dict, root: Path, today: dt.date) -> list[dict]:
    """Freeze what is due; return the new manifest rows."""
    vdir = root / VINTAGE_REL
    manifest_path = vdir / "manifest.csv"
    manifest = read_csv(manifest_path) if manifest_path.exists() else []
    head = commit(root)
    new = []
    for model, spec in program["models"].items():
        have = [m for m in manifest if m["model"] == model]
        due = []
        if not any(m["kind"] == "live" and m["as_of"][:7] == today.isoformat()[:7] for m in have):
            due.append(("live", today.isoformat()))
        bt = spec.get("backtest")
        cc = spec["scores"].get("chance_column")
        if bt and cc and not any(m["kind"] == "backtest" for m in have):
            header = (root / spec["scores"]["file"]).read_text(encoding="utf-8").split("\n", 1)[0].split(",")
            if cc in header:
                due.append(("backtest", bt["as_of"]))
        for kind, as_of in due:
            vid = as_of if kind == "live" else f"backtest_{as_of}"
            path = vdir / model / f"{vid}.csv"
            if path.exists():
                print(f"{model}: {path.relative_to(root)} exists; a frozen vintage is never rewritten")
                continue
            rows = vintage_rows(spec, root, kind)
            if not rows:
                print(f"{model}: no rows for a {kind} vintage; nothing frozen")
                continue
            write_csv(path, rows, ["county_fips", "state", "county", "rank_score", "chance_window",
                                   "chance_horizon", *spec.get("band", {}).get("columns", [])])
            m = {"model": model, "vintage_id": vid, "kind": kind, "as_of": as_of,
                 "frozen_on": today.isoformat(), "commit": head,
                 "scores_sha256": sha256(root / spec["scores"]["file"]),
                 "registration_sha256": sha256(root / spec["registration"]),
                 "program_sha256": sha256(root / PROGRAM_REL), "rows": len(rows)}
            new.append(m)
            print(f"{model}: froze {kind} vintage {vid}, {len(rows)} counties")
    if new:
        write_csv(manifest_path, manifest + new, MANIFEST_FIELDS)
    else:
        print("No vintage due.")
    return new


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    args = ap.parse_args()
    program = json.loads(PROGRAM_PATH.read_text(encoding="utf-8"))
    freeze(program, ROOT, args.today)
    return 0


if __name__ == "__main__":
    sys.exit(main())
