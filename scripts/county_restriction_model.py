"""County restriction model (predictive foundation, step 2).

Fits the model config/county_model_registration.json registered on 2026-10-16,
before any fit: which counties resemble those that enacted a severe
restriction on renewable energy (severity 3 or 4). Everything this module
decides is in that file; read it first. In short:

  labels     new_severe_2022_2025 (primary: counties at risk on 2022-01-01,
             variables as of the end of 2021), has_severe and has_severity_4
             (snapshots, latest variables). From data/model/county_labels.csv.
  variables  population, density, income and education (ACS), presidential
             margin (MEDSL), operating solar and wind MW (federal plant
             inventories), the share of neighbouring counties with a severe
             restriction, and, in the "queue" run only, MW requested in
             interconnection queues (LBNL Queued Up).
  selection  L2 logistic regression; at each C, backward elimination of the
             least sign-stable variable; admissible only when every
             coefficient keeps its sign in all 25 folds (5 x 5 stratified);
             best median AUC among admissible. A stability cost over 0.05
             stops the fit.
  calibration
             cross-fitted logistic recalibration, then the calibration gate
             (scripts/calibration_gate.py).
  diagnostics
             cross-validation grouped by state; Moran's I on the residual;
             for the primary label, the NREL-only and
             without-NREL-year-positives refits and the 2026 out-of-time
             check.

Writes, all internal (no page, report or headline figure reads them):
  data/model/county_restriction_scores.csv   calibrated out-of-fold score per
                                             county, label and run
  data/model/county_restriction_metrics.json everything measured
  data/model/county_restriction_report.md    the report

Scores are a resemblance to counties that enacted severe restrictions, never
a probability that a county will restrict.

Usage
  python scripts/county_restriction_model.py
"""
from __future__ import annotations

import json
import math
import random
import statistics as st
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold, RepeatedStratifiedKFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibration_gate  # noqa: E402
import geo  # noqa: E402
from common import ROOT, read_csv, write_csv  # noqa: E402

REGISTRATION_PATH = ROOT / "config" / "county_model_registration.json"
LABELS_PATH = ROOT / "data" / "model" / "county_labels.csv"
COVARIATES_PATH = ROOT / "data" / "reference" / "county_covariates.csv"
FACILITIES_PATH = ROOT / "data" / "reference" / "facilities.csv"
QUEUE_PATH = ROOT / "data" / "reference" / "queue_projects.csv"
RESTRICTIONS_PATH = ROOT / "data" / "processed" / "restrictions.csv"
SCORES_PATH = ROOT / "data" / "model" / "county_restriction_scores.csv"
METRICS_PATH = ROOT / "data" / "model" / "county_restriction_metrics.json"
REPORT_PATH = ROOT / "data" / "model" / "county_restriction_report.md"

REG = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))
SEED = REG["method"]["cv"]["seed"]
FOLDS = REG["method"]["cv"]["folds"]
REPEATS = REG["method"]["cv"]["repeats"]
C_GRID = REG["method"]["c_grid"]
MIN_VARS = 3
STABILITY_COST_ALARM = 0.05
PERMUTATIONS = 999
CUT_YEAR = 2022
POOL = ["log_population", "log_density", "log_income", "pct_bachelors_plus", "margin",
        "log1p_solar_mw", "log1p_wind_mw", "neighbor_severe_share", "log1p_queue_mw"]
RUNS = {"facilities": [v for v in POOL if v != "log1p_queue_mw"], "queue": POOL}
PRIMARY = REG["labels"]["primary"]["name"]
LABELS = {PRIMARY: {"frame": "at_risk_2022", "as_of": 2021},
          "has_severe": {"frame": None, "as_of": None},
          "has_severity_4": {"frame": None, "as_of": None}}


# ── Variables ───────────────────────────────────────────────────────────────

def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _year(v) -> int | None:
    y = _f(v)
    return int(y) if y else None


def exposure(as_of: int | None) -> dict[str, dict[str, float]]:
    """fips -> {solar, wind, queue} MW: plants operating at the end of as_of
    (begun by then, and not retired by then), queue requests made by as_of;
    every plant and request when as_of is None."""
    out: dict[str, dict[str, float]] = {}
    for p in read_csv(FACILITIES_PATH):
        if p["status"] not in ("operating", "retired") or not p["county_fips"]:
            continue
        y = _year(p["year"])
        # An operating plant's year is when it began operating; a retired
        # plant's is when it retired (registration amendment, 2026-10-16).
        if as_of is not None and p["status"] == "operating" and (y is None or y > as_of):
            continue
        if as_of is not None and p["status"] == "retired" and (y is None or y <= as_of):
            continue
        mw = _f(p["capacity_mw"]) or 0.0
        techs = p["technology"].split(";")
        for t in ("solar", "wind"):
            if t in techs:
                out.setdefault(p["county_fips"], {}).setdefault(t, 0.0)
                out[p["county_fips"]][t] += mw / len([x for x in techs if x in ("solar", "wind")])
    for q in read_csv(QUEUE_PATH):
        if not q["county_fips"] or not q["request_date"]:
            continue
        if as_of is not None and int(q["request_date"][:4]) > as_of:
            continue
        mw = sum(_f(q[k]) or 0.0 for k in ("solar_mw", "wind_mw", "storage_mw"))
        out.setdefault(q["county_fips"], {}).setdefault("queue", 0.0)
        out[q["county_fips"]]["queue"] += mw
    return out


def severe_by_county(before: int | None) -> set[str]:
    """Counties with a severe restriction (dated before `before`, or any)."""
    import county_labels
    out = set()
    for r in read_csv(RESTRICTIONS_PATH):
        if r.get("severity_score") not in county_labels.SEVERE:
            continue
        y = county_labels.year_of(r)
        if before is not None and (y is None or y >= before):
            continue
        out.update(county_labels.counties_of(r))
    return out


def variables(covariates: list[dict], as_of: int | None) -> dict[str, dict[str, float | None]]:
    """fips -> pool variable -> value (None when missing)."""
    exp = exposure(as_of)
    severe = severe_by_county(CUT_YEAR if as_of is not None else None)
    margin_col = "margin_dr_2020" if as_of is not None else "margin_dr_2024"
    out = {}
    for c in covariates:
        f = c["county_fips"]
        e = exp.get(f, {})
        nbrs = geo.neighbors(f)
        def log(v):
            x = _f(v)
            return math.log(x) if x and x > 0 else None
        out[f] = {
            "log_population": log(c["population"]), "log_density": log(c["pop_density_sqmi"]),
            "log_income": log(c["median_hh_income"]), "pct_bachelors_plus": _f(c["pct_bachelors_plus"]),
            "margin": _f(c[margin_col]),
            "log1p_solar_mw": math.log1p(e.get("solar", 0.0)), "log1p_wind_mw": math.log1p(e.get("wind", 0.0)),
            "neighbor_severe_share": (sum(1 for n in nbrs if n in severe) / len(nbrs)) if nbrs else 0.0,
            "log1p_queue_mw": math.log1p(e.get("queue", 0.0)),
        }
    return out


def matrix(fips: list[str], values: dict, names: list[str]) -> tuple[np.ndarray, dict[str, int]]:
    """Rows for fips, columns for names; a missing value takes the column median."""
    x = np.array([[values[f][n] if values[f][n] is not None else np.nan for n in names] for f in fips], float)
    missing = {}
    for j, n in enumerate(names):
        col = x[:, j]
        bad = np.isnan(col)
        missing[n] = int(bad.sum())
        if bad.any():
            col[bad] = np.nanmedian(col)
    return x, missing


# ── Selection (data-center-map's registered rule) ───────────────────────────

def is_sign_stable(coefs) -> bool:
    cs = list(coefs)
    return bool(cs) and (min(cs) > 0 or max(cs) < 0)


def instability(coefs) -> float:
    cs = list(coefs)
    if not cs or is_sign_stable(cs):
        return 0.0
    lo, hi = abs(min(cs)), abs(max(cs))
    return 1.0 if max(lo, hi) == 0 else min(lo, hi) / max(lo, hi)


def least_trustworthy(coef_folds: dict) -> str | None:
    unstable = {f: cs for f, cs in coef_folds.items() if not is_sign_stable(cs)}
    if not unstable:
        return None
    return min(unstable, key=lambda f: (-instability(unstable[f]), abs(st.median(unstable[f])), f))


def model(c: float):
    return make_pipeline(StandardScaler(), LogisticRegression(C=c, max_iter=5000))


def evaluate(x: np.ndarray, y: np.ndarray, names: list[str], cols: list[str], c: float, splits) -> dict:
    """Fit every fold: coefficients per variable, fold AUCs, out-of-fold score
    (mean over the repeats)."""
    ix = [names.index(n) for n in cols]
    coefs = {n: [] for n in cols}
    aucs, oof, cnt = [], np.zeros(len(y)), np.zeros(len(y))
    for tr, te in splits:
        m = model(c).fit(x[tr][:, ix], y[tr])
        for n, b in zip(cols, m[-1].coef_[0]):
            coefs[n].append(float(b))
        p = m.predict_proba(x[te][:, ix])[:, 1]
        aucs.append(roc_auc_score(y[te], p))
        oof[te] += p
        cnt[te] += 1
    return {"variables": cols, "C": c, "coefs": coefs, "aucs": aucs, "auc_median": float(np.median(aucs)),
            "oof": oof / cnt, "sign_stable": all(is_sign_stable(v) for v in coefs.values())}


def select(x: np.ndarray, y: np.ndarray, names: list[str], pool: list[str]) -> dict:
    splits = list(RepeatedStratifiedKFold(n_splits=FOLDS, n_repeats=REPEATS, random_state=SEED).split(x, y))
    grid = []
    for c in C_GRID:
        cols = list(pool)
        while True:
            res = evaluate(x, y, names, cols, c, splits)
            grid.append(res)
            drop = least_trustworthy(res["coefs"])
            if drop is None or len(cols) <= MIN_VARS:
                break
            cols = [n for n in cols if n != drop]
    admissible = [g for g in grid if g["sign_stable"]]
    best_any = max(g["auc_median"] for g in grid)
    chosen = sorted(admissible, key=lambda g: (-g["auc_median"], -len(g["variables"]), g["C"]))[0] \
        if admissible else None
    cost = best_any - chosen["auc_median"] if chosen else None
    return {"grid": grid, "chosen": chosen, "best_any_auc": best_any, "stability_cost": cost,
            "stopped": chosen is None or cost > STABILITY_COST_ALARM, "splits": splits}


# ── Calibration and diagnostics ─────────────────────────────────────────────

def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p)).reshape(-1, 1)


def recalibrate(oof: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, dict]:
    """Cross-fitted logistic recalibration, and the pooled slope and intercept."""
    z = logit(oof)
    pooled = LogisticRegression(C=1e6, max_iter=5000).fit(z, y)
    cal = np.zeros(len(y))
    for tr, te in StratifiedKFold(n_splits=FOLDS, shuffle=True, random_state=SEED).split(z, y):
        cal[te] = LogisticRegression(C=1e6, max_iter=5000).fit(z[tr], y[tr]).predict_proba(z[te])[:, 1]
    after = LogisticRegression(C=1e6, max_iter=5000).fit(logit(cal), y)
    return cal, {"slope_before": float(pooled.coef_[0][0]), "intercept_before": float(pooled.intercept_[0]),
                 "slope_after": float(after.coef_[0][0]), "intercept_after": float(after.intercept_[0])}


def state_grouped(x, y, names, cols, c, states) -> dict:
    ix = [names.index(n) for n in cols]
    oof = np.zeros(len(y))
    aucs = []
    for tr, te in GroupKFold(n_splits=FOLDS).split(x, y, groups=states):
        p = model(c).fit(x[tr][:, ix], y[tr]).predict_proba(x[te][:, ix])[:, 1]
        oof[te] = p
        if 0 < y[te].sum() < len(te):
            aucs.append(roc_auc_score(y[te], p))
    return {"pooled_auc": float(roc_auc_score(y, oof)), "fold_auc_median": float(np.median(aucs))}


def morans_i(fips: list[str], resid: np.ndarray) -> dict:
    """Moran's I with row-standardized contiguity weights over the frame, and
    a one-sided permutation p for positive autocorrelation."""
    pos = {f: i for i, f in enumerate(fips)}
    nbrs = [[pos[n] for n in geo.neighbors(f) if n in pos] for f in fips]

    def stat(e: np.ndarray) -> float:
        z = e - e.mean()
        lag = np.array([z[n].mean() if n else 0.0 for n in nbrs])
        s0 = sum(1 for n in nbrs if n)
        return float(len(z) / s0 * (z @ lag) / (z @ z))
    obs = stat(resid)
    rng = random.Random(SEED)
    perm = []
    for _ in range(PERMUTATIONS):
        e = list(resid)
        rng.shuffle(e)
        perm.append(stat(np.array(e)))
    return {"I": obs, "p_one_sided": (sum(1 for v in perm if v >= obs) + 1) / (PERMUTATIONS + 1),
            "expected": -1 / (len(fips) - 1)}


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def refit(x, y, names, chosen, splits=None) -> dict:
    """The chosen variables and C, cross-validated on another frame."""
    splits = splits or list(RepeatedStratifiedKFold(n_splits=FOLDS, n_repeats=REPEATS,
                                                     random_state=SEED).split(x, y))
    return evaluate(x, y, names, chosen["variables"], chosen["C"], splits)


# ── One label and run ───────────────────────────────────────────────────────

def fit(label: str, run: str, labels: list[dict], values: dict) -> dict:
    spec = LABELS[label]
    rows = [r for r in labels if not spec["frame"] or r[spec["frame"]] == "1"]
    fips = [r["county_fips"] for r in rows]
    y = np.array([int(r[label]) for r in rows])
    x, missing = matrix(fips, values, POOL)
    sel = select(x, y, POOL, RUNS[run])
    out = {"label": label, "run": run, "n": len(y), "positives": int(y.sum()),
           "missing_filled": {k: v for k, v in missing.items() if v},
           "candidates": [{"variables": g["variables"], "C": g["C"], "auc_median": round(g["auc_median"], 4),
                           "sign_stable": g["sign_stable"]} for g in sel["grid"]],
           "best_any_auc": round(sel["best_any_auc"], 4),
           "stability_cost": None if sel["stability_cost"] is None else round(sel["stability_cost"], 4),
           "stopped": sel["stopped"], "fips": fips}
    if sel["stopped"]:
        out["stop_reason"] = ("no admissible candidate" if sel["chosen"] is None
                              else f"stability cost {sel['stability_cost']:.3f} > {STABILITY_COST_ALARM}")
        return out
    ch = sel["chosen"]
    cal, slopes = recalibrate(ch["oof"], y)
    aucs = sorted(ch["aucs"])
    full = model(ch["C"]).fit(x[:, [POOL.index(n) for n in ch["variables"]]], y)
    out.update({
        "selected": {"variables": ch["variables"], "C": ch["C"]},
        "auc": {"p10": round(aucs[int(0.1 * len(aucs))], 4), "median": round(ch["auc_median"], 4),
                "p90": round(aucs[min(len(aucs) - 1, int(0.9 * len(aucs)))], 4),
                "pooled_oof": round(float(roc_auc_score(y, ch["oof"])), 4)},
        "coefficients": {n: {"full_fit": round(float(b), 4), "fold_min": round(min(ch["coefs"][n]), 4),
                             "fold_median": round(st.median(ch["coefs"][n]), 4),
                             "fold_max": round(max(ch["coefs"][n]), 4)}
                         for n, b in zip(ch["variables"], full[-1].coef_[0])},
        "recalibration": {k: round(v, 4) for k, v in slopes.items()},
        "gate": calibration_gate.gate([float(v) for v in cal], [int(v) for v in y]),
        "state_grouped": {k: round(v, 4) for k, v in state_grouped(x, y, POOL, ch["variables"], ch["C"],
                                                                     [r["state"] for r in rows]).items()},
        "morans_i": {k: round(v, 4) for k, v in morans_i(fips, y - cal).items()},
        "_cal": cal, "_oof": ch["oof"], "_x": x, "_y": y, "_rows": rows, "_chosen": ch,
    })
    return out


def sensitivity(res: dict, labels: list[dict], values: dict) -> dict:
    """The registered refits of the primary label's selected model."""
    ch = res["_chosen"]
    out = {}
    nrel_rows = [r for r in labels if r["nrel_at_risk_2022"] == "1"]
    nf = [r["county_fips"] for r in nrel_rows]
    ny = np.array([int(r["nrel_new_severe_2022_2025"]) for r in nrel_rows])
    nx, _ = matrix(nf, values, POOL)
    n = refit(nx, ny, POOL, ch)
    main = dict(zip(res["fips"], res["_oof"]))
    common = [i for i, f in enumerate(nf) if f in main]
    flips = [v for v in ch["variables"]
             if np.sign(st.median(n["coefs"][v])) != np.sign(st.median(ch["coefs"][v]))]
    out["nrel_only"] = {"n": len(ny), "positives": int(ny.sum()), "auc_median": round(n["auc_median"], 4),
                        "sign_stable": n["sign_stable"], "sign_changes": flips,
                        "spearman_with_main": round(spearman(n["oof"][common],
                                                             np.array([main[nf[i]] for i in common])), 4)}
    keep = [i for i, r in enumerate(res["_rows"]) if r["positive_rests_on_nrel_year"] != "1"]
    k = refit(res["_x"][keep], res["_y"][keep], POOL, ch)
    out["without_nrel_year_positives"] = {
        "n": len(keep), "positives": int(res["_y"][keep].sum()), "auc_median": round(k["auc_median"], 4),
        "sign_stable": k["sign_stable"],
        "sign_changes": [v for v in ch["variables"]
                         if np.sign(st.median(k["coefs"][v])) != np.sign(st.median(ch["coefs"][v]))]}
    # Held-back 2026: fit on the whole 2022 frame, score the counties still
    # without a severe restriction at the end of 2025.
    ix = [POOL.index(v) for v in ch["variables"]]
    m = model(ch["C"]).fit(res["_x"][:, ix], res["_y"])
    still = [i for i, r in enumerate(res["_rows"]) if r[PRIMARY] == "0"]
    h = np.array([int(res["_rows"][i]["new_severe_2026"]) for i in still])
    s = m.predict_proba(res["_x"][still][:, ix])[:, 1]
    out["holdout_2026"] = {"n": len(still), "positives": int(h.sum()),
                           "auc": round(float(roc_auc_score(h, s)), 4) if 0 < h.sum() < len(h) else None,
                           "note": "2026 is a partial year; restrictions enacted in it are still being recorded."}
    return out


# ── Report ──────────────────────────────────────────────────────────────────

def fmt_vars(vs: list[str]) -> str:
    return ", ".join(f"`{v}`" for v in vs)


def report(results: list[dict], sens: dict) -> str:
    L = ["# County restriction model", "",
         "Written by `scripts/county_restriction_model.py` under `config/county_model_registration.json` "
         f"(registered {REG['registered']}). Do not edit by hand.", "",
         "**What the scores are.** A resemblance to counties that enacted a severe restriction on renewable "
         "energy (severity 3 or 4), from county attributes. Not a probability that a county will restrict, and "
         "not a cause. Internal: no page, county report or headline figure reads them.", "",
         "**The main threat.** Most counties have never been examined, so a county without a recorded "
         "restriction may simply be one no source looked at. The NREL-only refit below is the check on that.", "",
         "## Results", "",
         "| Label | Run | Counties | Positives | Selected variables | C | Median AUC (p10 to p90) | "
         "State-grouped AUC | Brier skill | ECE | Gate |",
         "|---|---|---:|---:|---|---:|---|---:|---:|---:|---|"]
    for r in results:
        if r["stopped"]:
            L.append(f"| `{r['label']}` | {r['run']} | {r['n']} | {r['positives']} | stopped: {r['stop_reason']} "
                     "| | | | | | |")
            continue
        g = r["gate"]
        L.append(f"| `{r['label']}` | {r['run']} | {r['n']} | {r['positives']} | {fmt_vars(r['selected']['variables'])} "
                 f"| {r['selected']['C']} | {r['auc']['median']} ({r['auc']['p10']} to {r['auc']['p90']}) "
                 f"| {r['state_grouped']['pooled_auc']} | {g['brier_skill_score']} | {g['ece']} "
                 f"| {g['verdict']}{': ' + '; '.join(g['reasons']) if g['reasons'] else ''} |")
    L += ["", "## Coefficients (standardized variables)", "",
          "Full-sample fit, with the range over the 25 cross-validation folds. Every selected variable keeps "
          "its sign in all 25 by construction.", ""]
    for r in results:
        if r["stopped"]:
            continue
        L += [f"**`{r['label']}`, {r['run']} run**", "", "| Variable | Coefficient | Fold min | Fold max |",
              "|---|---:|---:|---:|"]
        for v, c in sorted(r["coefficients"].items(), key=lambda kv: -abs(kv[1]["full_fit"])):
            L.append(f"| `{v}` | {c['full_fit']} | {c['fold_min']} | {c['fold_max']} |")
        L.append("")
    L += ["## Diagnostics", "", "| Label | Run | Stability cost | Recalibration slope before, after | "
          "Moran's I on residual (p) |", "|---|---|---:|---|---|"]
    for r in results:
        if r["stopped"]:
            continue
        rc, mi = r["recalibration"], r["morans_i"]
        L.append(f"| `{r['label']}` | {r['run']} | {r['stability_cost']} | {rc['slope_before']}, {rc['slope_after']} "
                 f"| {mi['I']} ({mi['p_one_sided']}) |")
    L += ["", "A Moran's I well above zero means the errors cluster in space: neighbouring counties are "
          "mis-scored together, so the model misses something regional, such as state law or a regional "
          "campaign. The snapshot labels' negative values come from `neighbor_severe_share`, which there is "
          "built from the same labels the model predicts, so the neighbours' outcomes are already in the "
          "score; the primary label's variable uses only restrictions before 2022 and does not have this.", ""]
    for run, s in sens.items():
        n, w, h = s["nrel_only"], s["without_nrel_year_positives"], s["holdout_2026"]
        L += [f"## Primary label checks, {run} run", "",
              f"- **NREL-only labels** ({n['n']} counties, {n['positives']} positive): median AUC {n['auc_median']}; "
              f"sign changes: {fmt_vars(n['sign_changes']) or 'none'}; Spearman with the all-source score "
              f"{n['spearman_with_main']}. "
              + ("The registered reading applies: the all-source result partly reflects where sources looked."
                 if n["sign_changes"] or n["spearman_with_main"] < 0.7 else
                 "Below the registered thresholds: no sign change and Spearman of 0.7 or more."),
              f"- **Without positives that rest only on an NREL year** ({w['n']} counties, {w['positives']} "
              f"positive): median AUC {w['auc_median']}; sign changes: {fmt_vars(w['sign_changes']) or 'none'}.",
              f"- **Held-back 2026** ({h['n']} counties still without a severe restriction at the end of 2025, "
              f"{h['positives']} enacted one in 2026): AUC {h['auc']}. {h['note']}", ""]
    if REG.get("amendments"):
        L += ["## Registration amendments", ""]
        L += [f"- {m['date']}{' (after the first fit)' if m.get('after_first_fit') else ''}: {m['change']} "
              f"{m['reason']}" for m in REG["amendments"]]
        L.append("")
    L += ["## Not built", "",
          "- Score intervals (data-center-map's Venn-Abers intervals). The scores are internal for now.",
          "- State siting law as a variable: it cannot be measured as of 2021 (see the registration).", ""]
    return "\n".join(L) + "\n"


def main() -> int:
    labels = read_csv(LABELS_PATH)
    covariates = read_csv(COVARIATES_PATH)
    if [r["county_fips"] for r in labels] != [c["county_fips"] for c in covariates]:
        print("county_labels.csv and county_covariates.csv list different counties; run county_labels.py",
              file=sys.stderr)
        return 1
    values = {2021: variables(covariates, 2021), None: variables(covariates, None)}
    results, sens = [], {}
    for label, spec in LABELS.items():
        for run in RUNS:
            res = fit(label, run, labels, values[spec["as_of"]])
            if label == PRIMARY and not res["stopped"]:
                sens[run] = sensitivity(res, labels, values[2021])
            results.append(res)
    scores = {c["county_fips"]: {"county_fips": c["county_fips"], "state": c["state"], "county": c["county"]}
              for c in covariates}
    for res in results:
        col = f"{res['label']}__{res['run']}"
        for c in scores.values():
            c.setdefault(col, "")
        if not res["stopped"]:
            for f, v in zip(res["fips"], res["_cal"]):
                scores[f][col] = round(float(v), 4)
    lab = {r["county_fips"]: r for r in labels}
    for f, c in scores.items():
        for k in (PRIMARY, "at_risk_2022", "has_severe", "has_severity_4"):
            c[k] = lab[f][k]
    write_csv(SCORES_PATH, list(scores.values()))
    public = [{k: v for k, v in r.items() if not k.startswith("_") and k != "fips"} for r in results]
    METRICS_PATH.write_text(json.dumps({"registered": REG["registered"], "results": public,
                                        "primary_checks": sens}, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(report(results, sens), encoding="utf-8")
    for r in results:
        if r["stopped"]:
            print(f"{r['label']} / {r['run']}: stopped ({r['stop_reason']})")
        else:
            print(f"{r['label']} / {r['run']}: n {r['n']}, positives {r['positives']}, "
                  f"{r['selected']['variables']} C {r['selected']['C']}, median AUC {r['auc']['median']}, "
                  f"state-grouped {r['state_grouped']['pooled_auc']}, gate {r['gate']['verdict']}")
    print(f"Wrote {SCORES_PATH.relative_to(ROOT)}, {METRICS_PATH.relative_to(ROOT)}, {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
