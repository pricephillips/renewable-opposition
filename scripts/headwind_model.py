"""The Renewable Headwind Model: project part.

Fits the model registered in config/headwind_model_registration.json on the
dated outcomes in data/model/headwind_history.csv (scripts/headwind_history.py)
and writes an internal report. Read docs/headwind_model.md first.

The question: among interconnection requests made 2010 to 2019 that have
since resolved, does the county's record as it stood before the request
(local rules, neighbours' rules, the county's own queue history, its
attributes) say anything about which ones withdrew, beyond what the request
itself and its market (year, size, technology, grid region) already say?

Method, as the county restriction model (scripts/county_restriction_model.py)
and the data center model it was ported from: L2 logistic regression, 5 x 5
repeated stratified cross-validation, the sign-stability variable rule, a
state-grouped check, cross-fitted recalibration and the shared calibration
gate. In addition: the base model alone on the same folds, an out-of-time
test (fit 2010 to 2016, score 2017 to 2019), and a check on contested
projects (does the county part of the score rank blocked projects above
advanced ones?).

Outputs (internal, staff only; no page or client bundle reads them):
  data/model/headwind_scores.csv     calibrated out-of-fold score per request
  data/model/headwind_metrics.json   every number in the report
  data/model/headwind_report.md      the report

Associations only: nothing here says a rule or a county caused a withdrawal.

Usage: python scripts/headwind_model.py [--selftest]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold, RepeatedStratifiedKFold, StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibration_gate  # noqa: E402
from common import ROOT, read_csv, write_csv  # noqa: E402
from county_restriction_model import is_sign_stable, least_trustworthy, logit, model  # noqa: E402
from headwind_history import COUNTY_VARS, OUT_PATH as HISTORY_PATH  # noqa: E402

REGISTRATION_PATH = ROOT / "config" / "headwind_model_registration.json"
SCORES_PATH = ROOT / "data" / "model" / "headwind_scores.csv"
METRICS_PATH = ROOT / "data" / "model" / "headwind_metrics.json"
REPORT_PATH = ROOT / "data" / "model" / "headwind_report.md"

REG = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))
SEED = REG["method"]["cv"]["seed"]
FOLDS = REG["method"]["cv"]["folds"]
REPEATS = REG["method"]["cv"]["repeats"]
C_GRID = REG["method"]["c_grid"]
MIN_GAIN = 0.01
# The registered label, and the one added by the amendment of 2026-11-20
# (config/headwind_model_registration.json, amendments).
LABELS = {
    "withdrawn": {"y": "y", "in_fit": "in_fit", "train": (2010, 2016), "test": (2017, 2019),
                  "title": "withdrawn, among resolved requests made 2010 to 2019 (registered, primary)",
                  "positive": "withdrew", "negative": "reached operation"},
    "withdrawn_3y": {"y": "y_3y", "in_fit": "in_fit_3y", "train": (2010, 2018), "test": (2019, 2022),
                     "title": "withdrawn within three years, requests made 2010 to 2022 in CAISO, ISO-NE, MISO and "
                              "PJM (added after the first fit)",
                     "positive": "withdrew within three years", "negative": "did not"},
}
assert list(REG["variables"]) == COUNTY_VARS, "registration variables and headwind_history.COUNTY_VARS differ"

WORDS = {
    "severe_before": "a severe local rule (severity 3 or 4) on the technology, dated before the request",
    "standards_before": "siting standards (severity 1 or 2) on the technology, dated before the request",
    "undated_rule": "a local rule on the technology with no year",
    "neighbor_severe_share": "share of neighbouring counties with a dated severe rule",
    "prior_withdrawal_share": "the county's earlier requests: share withdrawn (smoothed)",
    "log1p_prior_requests": "the county's earlier requests: how many (log)",
    "log1p_operating_mw": "solar and wind MW already operating (log)",
    "log_density": "population density (log)",
    "log_income": "median household income (log)",
    "pct_bachelors_plus": "share with a bachelor's degree",
    "margin": "2016 presidential margin (Republican minus Democratic)",
}


# ── Design matrix ───────────────────────────────────────────────────────────

def base_columns(rows: list[dict]) -> list[str]:
    regions = sorted({r["region"] for r in rows if r["region"]})
    # One region is the reference level.
    return ["request_year", "log_capacity_mw", "tech_solar", "tech_wind", "tech_storage"] + \
        [f"region_{g}" for g in regions[1:]]


def base_value(r: dict, col: str) -> float:
    techs = set(r["technology"].split(";"))
    if col == "request_year":
        return float(r["year"])
    if col == "log_capacity_mw":
        try:
            return math.log1p(max(float(r["capacity_mw"]), 0.0))
        except (TypeError, ValueError):
            return float("nan")
    if col == "tech_solar":
        return float("solar" in techs)
    if col == "tech_wind":
        return float("wind" in techs)
    if col == "tech_storage":
        return float("battery_storage" in techs)
    if col.startswith("region_"):
        return float(r["region"] == col[len("region_"):])
    raise KeyError(col)


def matrix(rows: list[dict], base: list[str], county: list[str]) -> np.ndarray:
    x = np.array([[base_value(r, c) for c in base] +
                  [float(r[c]) if r[c] != "" else np.nan for c in county] for r in rows], float)
    for j in range(x.shape[1]):
        bad = np.isnan(x[:, j])
        if bad.any():
            x[bad, j] = np.nanmedian(x[:, j]) if (~bad).any() else 0.0
    return x


# ── Fitting ─────────────────────────────────────────────────────────────────

def evaluate(x, y, names, cols, c, splits) -> dict:
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
            "auc_p10": float(np.percentile(aucs, 10)), "auc_p90": float(np.percentile(aucs, 90)),
            "oof": oof / cnt}


def select(x, y, names, base, pool, splits) -> dict:
    """Drop the least sign-stable county variable until every county variable
    keeps its sign on every fold; base variables always stay."""
    grid = []
    for c in C_GRID:
        cols = list(pool)
        while True:
            res = evaluate(x, y, names, base + cols, c, splits)
            grid.append(res)
            drop = least_trustworthy({n: res["coefs"][n] for n in cols})
            if drop is None or not cols:
                break
            cols = [n for n in cols if n != drop]
    ok = [g for g in grid if all(is_sign_stable(g["coefs"][n]) for n in g["variables"] if n not in base)]
    return sorted(ok, key=lambda g: (-g["auc_median"], -len(g["variables"]), g["C"]))[0]


def recalibrate(oof, y) -> np.ndarray:
    z = logit(oof)
    cal = np.zeros(len(y))
    for tr, te in StratifiedKFold(n_splits=FOLDS, shuffle=True, random_state=SEED).split(z, y):
        cal[te] = LogisticRegression(C=1e6, max_iter=5000).fit(z[tr], y[tr]).predict_proba(z[te])[:, 1]
    return cal


def grouped_auc(x, y, names, cols, c, groups) -> float:
    ix = [names.index(n) for n in cols]
    oof = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=FOLDS).split(x, y, groups):
        oof[te] = model(c).fit(x[tr][:, ix], y[tr]).predict_proba(x[te][:, ix])[:, 1]
    return float(roc_auc_score(y, oof))


def out_of_time(x, y, years, names, cols, c, train, test) -> dict:
    ix = [names.index(n) for n in cols]
    tr = (years >= train[0]) & (years <= train[1])
    te = (years >= test[0]) & (years <= test[1])
    m = model(c).fit(x[tr][:, ix], y[tr])
    return {"train": int(tr.sum()), "test": int(te.sum()), "test_withdrawn_share": float(y[te].mean()),
            "auc": float(roc_auc_score(y[te], m.predict_proba(x[te][:, ix])[:, 1]))}


def county_part(x, y, names, base, chosen, c, rows_c, base_c) -> dict:
    """Fit the chosen model on every queue row, then score contested projects
    by the county variables' part of the linear predictor alone (they have no
    queue region or capacity)."""
    ix = [names.index(n) for n in chosen]
    m = model(c).fit(x[:, ix], y)
    scaler, lr = m[0], m[-1]
    county = [n for n in chosen if n not in base]
    if not county or not rows_c:
        return {"cases": len(rows_c), "auc": None, "variables": county}
    xc = matrix(rows_c, [], county)
    j = [chosen.index(n) for n in county]
    z = ((xc - scaler.mean_[j]) / scaler.scale_[j]) @ lr.coef_[0][j]
    yc = np.array([int(r["y"]) for r in rows_c])
    auc = float(roc_auc_score(yc, z)) if 0 < yc.sum() < len(yc) else None
    return {"cases": len(rows_c), "blocked": int(yc.sum()), "auc": auc, "variables": county}


def fit(rows: list[dict], label: str = "withdrawn") -> dict:
    lab = LABELS[label]
    q = [r for r in rows if r["source"] == "queue" and str(r[lab["in_fit"]]) == "1"]
    rows_c = [r for r in rows if r["source"] == "contested"]
    base = base_columns(q)
    names = base + COUNTY_VARS
    x = matrix(q, base, COUNTY_VARS)
    y = np.array([int(r[lab["y"]]) for r in q])
    years = np.array([int(r["year"]) for r in q])
    splits = list(RepeatedStratifiedKFold(n_splits=FOLDS, n_repeats=REPEATS, random_state=SEED).split(x, y))

    chosen = select(x, y, names, base, COUNTY_VARS, splits)
    c = chosen["C"]
    base_only = evaluate(x, y, names, base, c, splits)
    cal = recalibrate(chosen["oof"], y)
    gate = calibration_gate.gate(cal.tolist(), y.tolist())
    states = np.array([r["state"] for r in q])
    oot_full = out_of_time(x, y, years, names, chosen["variables"], c, lab["train"], lab["test"])
    oot_base = out_of_time(x, y, years, names, base, c, lab["train"], lab["test"])
    gain = chosen["auc_median"] - base_only["auc_median"]
    gain_oot = oot_full["auc"] - oot_base["auc"]
    promote = gate["verdict"] == "PROMOTE" and gain >= MIN_GAIN and gain_oot >= MIN_GAIN

    county_vars = [n for n in chosen["variables"] if n not in base]
    full_m = model(c).fit(x[:, [names.index(n) for n in chosen["variables"]]], y)
    coef = dict(zip(chosen["variables"], full_m[-1].coef_[0]))
    shares = {}
    for n in COUNTY_VARS:
        if n in ("severe_before", "standards_before", "undated_rule"):
            on = x[:, names.index(n)] == 1
            shares[n] = {"with": int(on.sum()), "withdrawn_with": float(y[on].mean()) if on.any() else None,
                         "withdrawn_without": float(y[~on].mean())}

    return {
        "label": label, "registration": REG["registered"],
        "frame": {"requests": len(q), "positive": int(y.sum()), "negative": int(len(y) - y.sum())},
        "C": c, "base": base, "county_variables_kept": county_vars,
        "county_variables_dropped": [n for n in COUNTY_VARS if n not in county_vars],
        "auc": {"full": chosen["auc_median"], "full_p10": chosen["auc_p10"], "full_p90": chosen["auc_p90"],
                "base": base_only["auc_median"], "gain": gain,
                "state_grouped_full": grouped_auc(x, y, names, chosen["variables"], c, states),
                "state_grouped_base": grouped_auc(x, y, names, base, c, states)},
        "out_of_time": {"full": oot_full, "base": oot_base, "gain": gain_oot},
        "gate": {k: v for k, v in gate.items() if k != "reliability"},
        "verdict": "PROMOTE" if promote else "HOLD",
        "coefficients": {n: {"coef": float(coef[n]), "fold_min": min(chosen["coefs"][n]),
                             "fold_max": max(chosen["coefs"][n])} for n in county_vars},
        "flags": shares,
        "contested_check": county_part(x, y, names, base, chosen["variables"], c, rows_c, base),
        "_scores": [(label, r["row_id"], r["county_fips"], r["year"], round(float(p), 4)) for r, p in zip(q, cal)],
    }


# ── Report ──────────────────────────────────────────────────────────────────

def _r(v, n=3):
    return "n/a" if v is None else f"{v:.{n}f}"


def section(m: dict) -> list[str]:
    lab = LABELS[m["label"]]
    f, a, o, g = m["frame"], m["auc"], m["out_of_time"], m["gate"]
    cc = m["contested_check"]
    lines = [
        f"## Label: {lab['title']}",
        "",
        f"**Verdict: {m['verdict']}.** Requests: {f['requests']} ({f['positive']} {lab['positive']}, "
        f"{f['negative']} {lab['negative']}).",
        "",
        "| Measure | Request only | Request and county | Gain |",
        "|---|---:|---:|---:|",
        f"| Cross-validated AUC (median of 25 folds) | {_r(a['base'])} | {_r(a['full'])} "
        f"(p10 {_r(a['full_p10'])}, p90 {_r(a['full_p90'])}) | {_r(a['gain'])} |",
        f"| State-grouped AUC (5 folds by state) | {_r(a['state_grouped_base'])} | {_r(a['state_grouped_full'])} | "
        f"{_r(a['state_grouped_full'] - a['state_grouped_base'])} |",
        f"| Out of time: fit {lab['train'][0]} to {lab['train'][1]} ({o['full']['train']} requests), "
        f"score {lab['test'][0]} to {lab['test'][1]} ({o['full']['test']}) | {_r(o['base']['auc'])} | "
        f"{_r(o['full']['auc'])} | {_r(o['gain'])} |",
        "",
        f"Calibration gate on the recalibrated score: {g['verdict']}"
        + (f" ({'; '.join(g.get('reasons', []))})" if g.get("reasons") else "")
        + f". Brier skill {_r(g.get('brier_skill_score'))}, ECE {_r(g.get('ece'))}. Regularization C = {m['C']}.",
        "",
        "County variables kept (each keeps its sign on all 25 folds; standardized coefficients, positive means "
        f"more often {lab['positive']}):",
        "",
        "| Variable | Coefficient | Fold min | Fold max |",
        "|---|---:|---:|---:|",
    ]
    for n, v in sorted(m["coefficients"].items(), key=lambda kv: -abs(kv[1]["coef"])):
        lines.append(f"| {WORDS[n]} | {_r(v['coef'])} | {_r(v['fold_min'])} | {_r(v['fold_max'])} |")
    if not m["coefficients"]:
        lines.append("| (none) | | | |")
    lines += ["", "Dropped for changing sign across folds: "
              + ("; ".join(WORDS[n] for n in m["county_variables_dropped"]) or "none") + ".", "",
              f"| Local rule in the county before the request | Requests with it | Share {lab['positive']}, with it "
              "| Share without it |",
              "|---|---:|---:|---:|"]
    for n, s in m["flags"].items():
        lines.append(f"| {WORDS[n]} | {s['with']} | {_r(s['withdrawn_with'])} | {_r(s['withdrawn_without'])} |")
    lines += ["", f"Check on contested projects: the county part of this score, applied to {cc['cases']} contested "
              f"projects with a confirmed outcome ({cc.get('blocked', 0)} blocked), ranks blocked above advanced "
              f"projects with AUC {_r(cc['auc'])}.", ""]
    return lines


def report(results: list[dict]) -> str:
    lines = [
        "# Renewable Headwind Model: project part",
        "",
        "Written by `scripts/headwind_model.py` under `config/headwind_model_registration.json` "
        f"(registered {REG['registered']}). Do not edit by hand. Internal, staff only. Read "
        "`docs/headwind_model.md` first.",
        "",
        "**What it measures.** Among interconnection requests for solar, wind and storage, how far the county's "
        "record before the request (its local rules, its neighbours' rules, its own earlier requests and its "
        "attributes) sets the requests that withdrew apart from the others, beyond what the request itself says "
        "(year, size, technology, grid region). A withdrawal is not opposition: most have market or grid reasons. "
        "Associations only, never cause.",
        "",
        f"**Promotion rule.** The calibration gate says PROMOTE, and the county variables add at least {MIN_GAIN} "
        "AUC over the request-only model, both in cross-validation and out of time. AUC is the chance that a "
        "withdrawn request, picked at random, scores above one that did not withdraw; 0.5 is a coin toss.",
        "",
    ]
    for m in results:
        lines += section(m)
    lines += [
        "## Limits",
        "",
        "- Withdrawal is the outcome, and most withdrawals have market or grid reasons. The model cannot separate a "
        "withdrawal forced by local opposition from one forced by an interconnection cost.",
        "- A county's record is only as complete as its examination: most counties have not been examined, so "
        "\"no rule before the request\" can mean no source looked.",
        "- Many local rules have no year and cannot be placed before or after a request; they are flagged, not counted.",
        "- The census covariates are 2020 to 2024 values for requests made 2010 to 2022.",
        "- The registered label leaves out requests still active, so it leans toward requests that resolved quickly. "
        "The three-year label keeps them, but only in the four regions that date their withdrawals.",
        "",
    ]
    return "\n".join(lines)


def write(results: list[dict]) -> None:
    scores = [{"label": lab, "queue_project_id": i, "county_fips": f, "request_year": y, "headwind_score": p}
              for m in results for lab, i, f, y, p in m["_scores"]]
    write_csv(SCORES_PATH, scores, ["label", "queue_project_id", "county_fips", "request_year", "headwind_score"])
    out = {m["label"]: {k: v for k, v in m.items() if not k.startswith("_")} for m in results}
    METRICS_PATH.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(report(results), encoding="utf-8")


# ── Self-test ───────────────────────────────────────────────────────────────

def _selftest() -> int:
    rng = np.random.default_rng(3)
    rows = []
    for i in range(600):
        hist = float(rng.uniform(0.5, 1.0))
        noise = float(rng.normal())
        p = 1 / (1 + math.exp(-(4 * (hist - 0.75))))
        rows.append({"row_id": str(i), "source": "queue", "in_fit": "1", "state": "S" + str(i % 7),
                     "county_fips": f"{i % 50:05d}", "region": ["A", "B"][i % 2], "technology": "solar",
                     "capacity_mw": "50", "year": str(2010 + i % 10), "y": str(int(rng.uniform() < p)),
                     **{n: "0" for n in COUNTY_VARS}, "prior_withdrawal_share": str(hist), "margin": str(noise)})
        rows[-1].update({"y_3y": rows[-1]["y"], "in_fit_3y": "1"})
    rows += [{"row_id": f"c{i}", "source": "contested", "in_fit": "0", "state": "S1", "county_fips": "00001",
              "region": "", "technology": "wind", "capacity_mw": "", "year": "2015", "y": str(i % 2),
              **{n: "0" for n in COUNTY_VARS}, "prior_withdrawal_share": str(0.6 + 0.3 * (i % 2)),
              "y_3y": "", "in_fit_3y": "0"} for i in range(20)]
    m = fit(rows)
    assert "prior_withdrawal_share" in m["county_variables_kept"], m["county_variables_kept"]
    assert m["coefficients"]["prior_withdrawal_share"]["coef"] > 0
    assert m["auc"]["gain"] > 0, "a variable that drives the label must add AUC over the base"
    assert m["contested_check"]["auc"] == 1.0, "the county part ranks the synthetic blocked projects first"
    assert "verdict" in m and "# Renewable Headwind Model" in report([m, fit(rows, "withdrawn_3y")])
    print("headwind_model selftest: ok")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    rows = read_csv(HISTORY_PATH)
    results = [fit(rows, label) for label in LABELS]
    write(results)
    for m in results:
        print(f"headwind_model {m['label']}: {m['verdict']}; AUC request only {m['auc']['base']:.3f}, with county "
              f"{m['auc']['full']:.3f}; out of time {m['out_of_time']['base']['auc']:.3f} -> "
              f"{m['out_of_time']['full']['auc']:.3f}; gate {m['gate']['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
