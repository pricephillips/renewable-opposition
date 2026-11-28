"""Rolling-origin yearly backtests of the Headwind 12-month chance (model program, stage two).

docs/model_program.md, stage two. The scorecard's first backtest ranked well
but its 12-month chance was barely more accurate than the base rate (Brier
skill 0.011 against the pilot target of 0.05). That chance came from a model
fit to a four-year window and turned into one year by formula. This module
tries yearly challengers on the same footing a client lives through: each is
fit only on years before the test year and scored on the test year, for every
test year in config/model_program.json (headwind_county.stage_two).

The unit is a county-year. A county is at risk in year t when it has no
severe restriction (severity 3 or 4) dated before t and no undated one; the
event is its first severe restriction dated in t. Each county-year reads the
county as it stood at the start of t: plants and queue requests to the end of
t - 1, the share of neighbouring and same-state counties with a severe
restriction dated before t, the presidential margin of the last election
before t, the plug-in inputs read for t (their own lag applies), and the ACS
attributes (slow-moving, measured once).

Challengers
  window_annualized  the current forward score: the registered four-year
                     window label (first severe in t to t + 3), turned into
                     one year as 1 - (1 - p) ^ (1/4). Fit on windows that end
                     before t.
  yearly             logistic regression on county-years before t (a
                     discrete-time hazard), the registered pool, L2 penalty
  yearly_recal       yearly, then recalibrated: the intercept and slope on
                     the logit are fit on the last training year's out-of-time
                     scores (a model fit on the years before it)
  yearly_level       yearly, with its intercept shifted so the mean chance
                     equals the last training year's event rate
  yearly_recent      the yearly model fit on the last four training years only

Gate (config/model_program.json, stage_two.gate): Brier skill at or above the
pilot target on at least `years_needed` test years, and a median AUC no lower
than window_annualized's. The best challenger that passes is named as the
one the monthly forward score should use; none passing keeps the current one.

Writes (internal)
  data/model/headwind_forward.json   every challenger's measures by test year
  data/model/headwind_forward.md     the report

Usage
  python scripts/headwind_forward.py
"""
from __future__ import annotations

import json
import math
import statistics as st
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibration_gate  # noqa: E402
import county_labels  # noqa: E402
import county_restriction_model as crm  # noqa: E402
import geo  # noqa: E402
import headwind_inputs  # noqa: E402
from common import ROOT, read_csv  # noqa: E402

PROGRAM_PATH = ROOT / "config" / "model_program.json"
JSON_PATH = ROOT / "data" / "model" / "headwind_forward.json"
REPORT_PATH = ROOT / "data" / "model" / "headwind_forward.md"
ELECTIONS = (2000, 2004, 2008, 2012, 2016, 2020, 2024)


# ── The county-year panel ───────────────────────────────────────────────────
def first_severe(restrictions: list[dict]) -> tuple[dict[str, int], set[str]]:
    """fips -> year of its first dated severe restriction; and the counties
    with an undated one (never at risk: their first year is unknown)."""
    years: dict[str, list[int | None]] = {}
    for r in restrictions:
        if r.get("severity_score") in county_labels.SEVERE:
            y = county_labels.year_of(r)
            for f in county_labels.counties_of(r):
                years.setdefault(f, []).append(y)
    undated = {f for f, ys in years.items() if any(y is None for y in ys)}
    first = {f: min(ys) for f, ys in years.items() if f not in undated}
    return first, undated


def year_values(covariates: list[dict], t: int, first: dict[str, int], pool: list[str],
                loaded: dict) -> dict[str, dict[str, float | None]]:
    """fips -> pool variable -> value, as the county stood at the start of t."""
    exp = crm.exposure(t - 1)
    severe = {f for f, y in first.items() if y < t}
    election = max(e for e in ELECTIONS if e < t)
    by_state: dict[str, list[str]] = {}
    for c in covariates:
        by_state.setdefault(c.get("state", ""), []).append(c["county_fips"])
    out = {}
    for c in covariates:
        f = c["county_fips"]
        e = exp.get(f, {})
        nbrs = geo.neighbors(f)

        def log(v):
            x = crm._f(v)
            return math.log(x) if x and x > 0 else None
        others = [g for g in by_state[c.get("state", "")] if g != f]
        row = {
            "log_population": log(c["population"]), "log_density": log(c["pop_density_sqmi"]),
            "log_income": log(c["median_hh_income"]), "pct_bachelors_plus": crm._f(c["pct_bachelors_plus"]),
            "margin": crm._f(c.get(f"margin_dr_{election}")),
            "log1p_solar_mw": math.log1p(max(e.get("solar", 0.0), 0.0)), "log1p_wind_mw": math.log1p(max(e.get("wind", 0.0), 0.0)),
            "neighbor_severe_share": (sum(1 for n in nbrs if n in severe) / len(nbrs)) if nbrs else 0.0,
            "log1p_queue_mw": math.log1p(max(e.get("queue", 0.0), 0.0)),
            "state_severe_share": (sum(1 for g in others if g in severe) / len(others)) if others else 0.0,
        }
        for n, inp in loaded.items():
            row[n] = inp.value(f, c.get("state", ""), t)
        out[f] = {n: row.get(n) for n in pool}
    return out


def panel(covariates: list[dict], restrictions: list[dict], years: range, pool: list[str]) -> dict[int, dict]:
    """year -> {fips, x, y, y4}: the counties at risk at the start of the year,
    their values, the yearly event and the four-year window event."""
    first, undated = first_severe(restrictions)
    loaded = {n: i for n, i in headwind_inputs.load(every=True).items() if n in pool}
    out = {}
    for t in years:
        vals = year_values(covariates, t, first, pool, loaded)
        fips = [c["county_fips"] for c in covariates
                if c["county_fips"] not in undated and first.get(c["county_fips"], 10**4) >= t]
        x, _ = crm.matrix(fips, vals, pool)
        y = np.array([int(first.get(f) == t) for f in fips])
        y4 = np.array([int(t <= first.get(f, 10**4) <= t + 3) for f in fips])
        out[t] = {"fips": fips, "x": x, "y": y, "y4": y4}
    return out


# ── Challengers ─────────────────────────────────────────────────────────────
def _fit(x: np.ndarray, y: np.ndarray, c: float):
    return crm.model(c).fit(x, y)


def _stack(p: dict, years) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (np.vstack([p[t]["x"] for t in years]), np.concatenate([p[t]["y"] for t in years]),
            np.concatenate([p[t]["y4"] for t in years]))


def logit(q: np.ndarray) -> np.ndarray:
    q = np.clip(q, 1e-6, 1 - 1e-6)
    return np.log(q / (1 - q))


def predict(p: dict, t: int, train: list[int], c: float) -> dict[str, np.ndarray]:
    """Each challenger's 12-month chance for the counties at risk in year t."""
    out = {}
    w_years = [s for s in train if s + 3 < t]
    if w_years:
        x, _, y4 = _stack(p, w_years)
        if 0 < y4.sum() < len(y4):
            p4 = _fit(x, y4, c).predict_proba(p[t]["x"])[:, 1]
            out["window_annualized"] = 1 - (1 - p4) ** 0.25
    x, y, _ = _stack(p, train)
    m = _fit(x, y, c)
    out["yearly"] = m.predict_proba(p[t]["x"])[:, 1]
    last, before = train[-1], train[:-1]
    if before:
        xb, yb, _ = _stack(p, before)
        if 0 < yb.sum() < len(yb):
            q = _fit(xb, yb, c).predict_proba(p[last]["x"])[:, 1]
            yl = p[last]["y"]
            if 0 < yl.sum() < len(yl):
                cal = LogisticRegression(C=1e6, max_iter=2000).fit(logit(q).reshape(-1, 1), yl)
                out["yearly_recal"] = cal.predict_proba(logit(out["yearly"]).reshape(-1, 1))[:, 1]
    # The last training year's event rate, carried into the test year by
    # shifting the yearly score's intercept (slope kept at 1).
    rate = float(p[last]["y"].mean())
    if 0 < rate < 1:
        z = logit(out["yearly"])
        lo, hi = -10.0, 10.0
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if (1 / (1 + np.exp(-(z + mid)))).mean() < rate else (lo, mid)
        out["yearly_level"] = 1 / (1 + np.exp(-(z + (lo + hi) / 2)))
    recent = train[-4:]
    xr, yr, _ = _stack(p, recent)
    if 0 < yr.sum() < len(yr):
        out["yearly_recent"] = _fit(xr, yr, c).predict_proba(p[t]["x"])[:, 1]
    return out


def ceiling(score: np.ndarray, y: np.ndarray) -> float | None:
    """The Brier skill a perfectly calibrated version of this ranking would
    reach on the test year: isotonic regression fit on the test year itself.
    A diagnostic of what the ranking allows, never a challenger."""
    from sklearn.isotonic import IsotonicRegression
    if not 0 < y.sum() < len(y):
        return None
    q = IsotonicRegression(out_of_bounds="clip").fit(score, y).predict(score)
    base = y.mean()
    return round(1 - float(((q - y) ** 2).mean()) / (base * (1 - base)), 4)


def measures(pred: np.ndarray, y: np.ndarray) -> dict:
    g = calibration_gate.gate([float(v) for v in pred], [int(v) for v in y])
    auc = float(roc_auc_score(y, pred)) if 0 < y.sum() < len(y) else None
    return {"n": int(len(y)), "events": int(y.sum()), "auc": None if auc is None else round(auc, 4),
            "brier_skill": g["brier_skill_score"], "ece": g["ece"], "mean_chance": round(float(pred.mean()), 4)}


def run(p: dict, spec: dict) -> dict:
    s2 = spec["stage_two"]
    results: dict[str, dict] = {}
    for t in s2["test_years"]:
        train = [y for y in range(s2["first_train_year"], t)]
        preds = predict(p, t, train, s2["C"])
        for name, pr in preds.items():
            m = measures(pr, p[t]["y"])
            m["brier_skill_ceiling"] = ceiling(pr, p[t]["y"])
            results.setdefault(name, {})[str(t)] = m
    gate = s2["gate"]
    ref = results.get(gate["auc_reference"], {})
    ref_auc = st.median([m["auc"] for m in ref.values() if m["auc"] is not None]) if ref else None
    verdicts = {}
    for name, by_year in results.items():
        bss = [m["brier_skill"] for m in by_year.values()]
        aucs = [m["auc"] for m in by_year.values() if m["auc"] is not None]
        passed_years = sum(1 for b in bss if b >= gate["brier_skill_min"])
        med_auc = st.median(aucs) if aucs else None
        ok = (len(by_year) == len(s2["test_years"]) and passed_years >= gate["years_needed"]
              and (ref_auc is None or (med_auc is not None and med_auc >= ref_auc - gate["auc_tolerance"])))
        verdicts[name] = {"years_at_target": passed_years, "median_auc": None if med_auc is None else round(med_auc, 4),
                          "median_brier_skill": round(st.median(bss), 4), "passes": ok}
    passing = [n for n, v in verdicts.items() if v["passes"]]
    best = max(passing, key=lambda n: (verdicts[n]["median_brier_skill"], verdicts[n]["median_auc"] or 0)) \
        if passing else None
    return {"test_years": s2["test_years"], "gate": gate, "reference_median_auc": None if ref_auc is None else
            round(ref_auc, 4), "results": results, "verdicts": verdicts, "chosen": best}


def report(out: dict) -> str:
    g = out["gate"]
    lines = ["# Headwind forward backtests (model program, stage two)", "",
             "Built by `scripts/headwind_forward.py`. Internal. Each challenger is fit only on years before the "
             "test year and scored on that year's first severe restrictions (severity 3 or 4). These are "
             "backtests: they choose the method, and only the frozen vintages (`data/model/model_scorecard.md`) "
             "open a stage.", "",
             f"Gate: Brier skill {g['brier_skill_min']} or more on at least {g['years_needed']} of "
             f"{len(out['test_years'])} test years, and a median AUC no more than {g['auc_tolerance']} below "
             f"{g['auc_reference']} ({out['reference_median_auc']}).", "",
             "The ceiling column is the Brier skill a perfectly calibrated version of the same ranking would reach "
             "on that year (isotonic regression fit on the test year itself). It is a diagnostic of what the "
             "ranking allows, not a result.", "",
             "| Challenger | Test year | Counties | Events | AUC | Brier skill | Ceiling | ECE | Mean chance |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, by_year in out["results"].items():
        for t, m in by_year.items():
            lines.append(f"| {name} | {t} | {m['n']} | {m['events']} | {m['auc']} | {m['brier_skill']} "
                         f"| {m['brier_skill_ceiling']} | {m['ece']} | {m['mean_chance']} |")
    lines += ["", "| Challenger | Years at target | Median AUC | Median Brier skill | Passes |",
              "|---|---:|---:|---:|---|"]
    for name, v in out["verdicts"].items():
        lines.append(f"| {name} | {v['years_at_target']} | {v['median_auc']} | {v['median_brier_skill']} "
                     f"| {'yes' if v['passes'] else 'no'} |")
    lines += ["", f"Chosen: {out['chosen'] or 'none; the current forward score stays'}.", ""]
    return "\n".join(lines)


def main() -> int:
    spec = json.loads(PROGRAM_PATH.read_text(encoding="utf-8"))["models"]["headwind_county"]
    s2 = spec["stage_two"]
    covariates = read_csv(crm.COVARIATES_PATH)
    years = range(s2["first_train_year"], max(s2["test_years"]) + 1)
    p = panel(covariates, read_csv(crm.RESTRICTIONS_PATH), years, crm.POOL)
    out = run(p, spec)
    JSON_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(report(out), encoding="utf-8")
    for name, v in out["verdicts"].items():
        print(f"{name}: {v['years_at_target']} years at target, median AUC {v['median_auc']}, "
              f"median Brier skill {v['median_brier_skill']}, passes {v['passes']}")
    print(f"Chosen: {out['chosen']}")
    print(f"Wrote {JSON_PATH.relative_to(ROOT)}, {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
