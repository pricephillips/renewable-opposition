"""Renewable Headwind Model: a wide search over variables and their combinations.

Price asked on 2026-11-20 whether the model should test hundreds of variables
against each other to find the combination that works best. This script does
that, with guards so that a combination found by luck is not reported as one
that works. It reads data/model/headwind_history.csv (scripts/headwind_history.py)
and changes nothing the registered model reads.

The pool. Every county variable in the history: the registered core
(headwind_history.COUNTY_VARS) and every plug-in input configured in
config/headwind_inputs.json, registered or not. Two searches run over it:

  sparse logistic   L1 (lasso) logistic regression over the variables, their
                    squares, every pair of them multiplied together, and each
                    one times each technology: several hundred candidates. The
                    penalty keeps only the ones that help.
  boosted trees     gradient-boosted trees over the variables, which find
                    combinations and thresholds on their own; variables are
                    kept only when shuffling them hurts the inner validation.

The guards:

1. Forward in time. Each outer fold trains on requests made up to a year and
   scores requests made later. A model never sees a later request.
2. Nested selection. Inside each outer fold the search picks its penalty and
   its variables on an inner split of the training years only (the last two
   training years held out). The outer test years never touch a choice.
3. A request-only baseline of the same learner, chosen the same way. The
   county pool counts only for the AUC it adds over that baseline.
4. A shuffled-data null. The whole nested search is rerun NULL_RUNS times
   with the county variables' rows shuffled together (the variables keep
   their joint pattern but lose any link to the outcome). Any gain the real
   search shows must beat these: p is the share of shuffled runs whose mean
   gain is at least the real one.
5. The bar. A search holds up only if its mean gain over the outer folds is
   at least 0.01 AUC, the gain is positive on every outer fold, and p is
   0.0125 or less: 0.05 divided by the four searches run (two learners, two
   labels), so that running four searches does not make a chance pass four
   times as likely.

Associations only, never cause. Internal, staff only. Outputs:
data/model/headwind_search.json and data/model/headwind_search.md.

Usage: python scripts/headwind_search.py [--selftest] [--null-runs N]
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, read_csv  # noqa: E402
import headwind_inputs  # noqa: E402
from headwind_history import COUNTY_VARS, OUT_PATH as HISTORY_PATH  # noqa: E402
from headwind_model import LABELS, WORDS, base_columns, base_value  # noqa: E402

OUT_JSON = ROOT / "data" / "model" / "headwind_search.json"
OUT_MD = ROOT / "data" / "model" / "headwind_search.md"
SEED = 20261120
NULL_RUNS = 99
SEARCHES = 4
MIN_GAIN, MAX_P = 0.01, 0.05 / SEARCHES  # Bonferroni across the four searches
C_GRID = (0.003, 0.01, 0.03, 0.1, 0.3)
INNER_YEARS = 2
# Forward outer folds: (train through this year, score these years), as headwind_compare.py.
OUTER = {
    "withdrawn": [(2014, (2015, 2016)), (2016, (2017, 2019))],
    "withdrawn_3y": [(2016, (2017, 2018)), (2018, (2019, 2022))],
}
TECHS = ("tech_solar", "tech_wind", "tech_storage")


# ── Data ────────────────────────────────────────────────────────────────────

def pool(rows: list[dict]) -> list[str]:
    """The county variables in the history: the core, then every configured input."""
    have = set(rows[0]) if rows else set()
    return [n for n in dict.fromkeys(COUNTY_VARS + headwind_inputs.configured()) if n in have]


def frame(rows: list[dict], label: str):
    lab = LABELS[label]
    q = [r for r in rows if r["source"] == "queue" and str(r[lab["in_fit"]]) == "1"]
    base = base_columns(q)
    county = pool(q)
    xb = np.array([[base_value(r, c) for c in base] for r in q], float)
    xc = np.array([[float(r[c]) if r[c] != "" else np.nan for c in county] for r in q], float)
    y = np.array([int(r[lab["y"]]) for r in q])
    years = np.array([int(r["year"]) for r in q])
    return base, county, xb, xc, y, years


def impute(train: np.ndarray, *others: np.ndarray):
    """Fill missing values with the training medians only."""
    med = np.nanmedian(np.where(np.isnan(train).all(0), 0.0, train), axis=0) if train.size else 0
    med = np.where(np.isnan(med), 0.0, med)
    return [np.where(np.isnan(a), med, a) for a in (train, *others)]


def standardize(train: np.ndarray, *others: np.ndarray):
    mu, sd = train.mean(0), train.std(0)
    sd = np.where(sd > 0, sd, 1.0)
    return [(a - mu) / sd for a in (train, *others)]


def expand(xb: np.ndarray, xc: np.ndarray, base: list[str], county: list[str]):
    """County variables, their squares, every pair multiplied, and each times each technology."""
    cols, names = [xc], list(county)
    cols.append(xc ** 2)
    names += [f"{n}^2" for n in county]
    pairs = list(itertools.combinations(range(len(county)), 2))
    if pairs:
        cols.append(np.column_stack([xc[:, i] * xc[:, j] for i, j in pairs]))
        names += [f"{county[i]} x {county[j]}" for i, j in pairs]
    for t in TECHS:
        if t in base:
            cols.append(xc * xb[:, [base.index(t)]])
            names += [f"{n} x {t}" for n in county]
    return np.hstack(cols), names


# ── Learners, each with its own nested choice ───────────────────────────────

def _auc(y, p) -> float:
    return float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else float("nan")


def lasso(xtr, ytr, xte, inner_tr, inner_va, l1: bool):
    """Pick C on the inner split, refit on all training rows, score the test rows."""
    xtr_s, xte_s = standardize(xtr, xte)
    ratio = 1.0 if l1 else 0.0
    best = (-1.0, C_GRID[0])
    for c in C_GRID:
        m = LogisticRegression(l1_ratio=ratio, C=c, solver="liblinear", max_iter=2000)
        m.fit(xtr_s[inner_tr], ytr[inner_tr])
        best = max(best, (_auc(ytr[inner_va], m.predict_proba(xtr_s[inner_va])[:, 1]), c))
    m = LogisticRegression(l1_ratio=ratio, C=best[1], solver="liblinear", max_iter=2000).fit(xtr_s, ytr)
    return m.predict_proba(xte_s)[:, 1], {"C": best[1], "coef": m.coef_[0]}


def trees(xtr, ytr, xte, inner_tr, inner_va, keep_from: int, seed: int):
    """Boosted trees. Columns from keep_from on (the county pool) are kept only
    when shuffling them lowers the inner validation AUC."""
    def model():
        return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
                                              min_samples_leaf=40, l2_regularization=1.0, random_state=seed)
    cols = list(range(xtr.shape[1]))
    if keep_from < xtr.shape[1]:
        m = model().fit(xtr[inner_tr], ytr[inner_tr])
        imp = permutation_importance(m, xtr[inner_va], ytr[inner_va], scoring="roc_auc", n_repeats=3,
                                     random_state=seed).importances_mean
        cols = list(range(keep_from)) + [j for j in range(keep_from, xtr.shape[1]) if imp[j] > 0]
    m = model().fit(xtr[:, cols], ytr)
    return m.predict_proba(xte[:, cols])[:, 1], {"kept": [j - keep_from for j in cols if j >= keep_from]}


# ── One search ──────────────────────────────────────────────────────────────

def search(learner: str, label: str, base, county, xb, xc, y, years, seed: int = SEED) -> dict:
    folds = []
    for train_to, (t0, t1) in OUTER[label]:
        tr, te = years <= train_to, (years >= t0) & (years <= t1)
        inner_va_mask = years[tr] > train_to - INNER_YEARS
        inner_tr, inner_va = np.where(~inner_va_mask)[0], np.where(inner_va_mask)[0]
        xb_tr, xb_te = impute(xb[tr], xb[te])
        xc_tr, xc_te = impute(xc[tr], xc[te])
        if learner == "lasso":
            pb, _ = lasso(xb_tr, y[tr], xb_te, inner_tr, inner_va, l1=True)
            ex_tr, names = expand(xb_tr, xc_tr, base, county)
            ex_te, _ = expand(xb_te, xc_te, base, county)
            pf, info = lasso(np.hstack([xb_tr, ex_tr]), y[tr], np.hstack([xb_te, ex_te]), inner_tr, inner_va, l1=True)
            coef = info["coef"][len(base):]
            chosen = {names[j]: float(coef[j]) for j in np.nonzero(coef)[0]}
            extra = {"C": info["C"], "candidates": len(names)}
        else:
            pb, _ = trees(xb_tr, y[tr], xb_te, inner_tr, inner_va, xb_tr.shape[1], seed)
            pf, info = trees(np.hstack([xb_tr, xc_tr]), y[tr], np.hstack([xb_te, xc_te]), inner_tr, inner_va,
                             len(base), seed)
            chosen = {county[j]: 1.0 for j in info["kept"]}
            extra = {"candidates": len(county)}
        auc_b, auc_f = _auc(y[te], pb), _auc(y[te], pf)
        folds.append({"train_to": train_to, "test": [t0, t1], "train_n": int(tr.sum()), "test_n": int(te.sum()),
                      "auc_request": auc_b, "auc_county": auc_f, "gain": auc_f - auc_b, "chosen": chosen, **extra})
    gains = [f["gain"] for f in folds]
    return {"learner": learner, "label": label, "folds": folds, "mean_gain": float(np.mean(gains)),
            "min_gain": float(np.min(gains))}


def with_null(learner: str, label: str, data, null_runs: int) -> dict:
    base, county, xb, xc, y, years = data
    real = search(learner, label, base, county, xb, xc, y, years)
    rng = np.random.default_rng(SEED)
    null = []
    for k in range(null_runs):
        perm = rng.permutation(len(y))
        null.append(search(learner, label, base, county, xb, xc[perm], y, years, seed=SEED + k + 1)["mean_gain"])
    p = (1 + sum(g >= real["mean_gain"] for g in null)) / (1 + len(null))
    holds = real["mean_gain"] >= MIN_GAIN and real["min_gain"] > 0 and p <= MAX_P
    stable = stable_choices(real["folds"])
    return {**real, "null_gains": null, "null_p95": float(np.percentile(null, 95)) if null else None, "p": p,
            "holds_up": bool(holds), "stable": stable, "rows": int(len(y)), "pool": county}


def stable_choices(folds: list[dict]) -> dict:
    """Variables chosen in every outer fold with the same sign."""
    common = set.intersection(*(set(f["chosen"]) for f in folds)) if folds else set()
    out = {}
    for n in common:
        signs = {np.sign(f["chosen"][n]) for f in folds}
        if len(signs) == 1:
            out[n] = float(np.mean([f["chosen"][n] for f in folds]))
    return dict(sorted(out.items(), key=lambda kv: -abs(kv[1])))


# ── Report ──────────────────────────────────────────────────────────────────

def _r(v, n=3):
    return "n/a" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:.{n}f}"


def _word(term: str) -> str:
    parts = term.replace("^2", " (squared)").split(" x ")
    words = {**WORDS, "tech_solar": "solar", "tech_wind": "wind", "tech_storage": "storage"}
    return " times ".join(words.get(p.replace(" (squared)", ""), p) + (" (squared)" if "(squared)" in p else "")
                          for p in parts)


def report(results: list[dict], null_runs: int) -> str:
    lines = [
        "# Renewable Headwind Model: wide search over variables and combinations",
        "",
        "Written by `scripts/headwind_search.py`. Do not edit by hand. Internal, staff only. Read "
        "`docs/headwind_model.md` first.",
        "",
        "**What it tests.** Whether some combination of the county variables, searched widely, predicts which "
        "interconnection requests withdrew better than the request alone (year, size, technology, grid region), on "
        "later years the search never saw. Two searches: a sparse (lasso) logistic regression over the variables, "
        "their squares, every pair multiplied and each times each technology, and gradient-boosted trees over the "
        "variables. Each picks its settings and variables on earlier years only.",
        "",
        f"**The bar.** A search holds up only if it adds at least {MIN_GAIN} AUC over the request-only model on "
        f"average, adds something on every later period, and beats the same search run on shuffled county data in "
        f"nearly all of {null_runs} shuffles (p of {MAX_P} or less: 0.05 divided by the {SEARCHES} searches run). AUC is the "
        "chance that a withdrawn request, picked at random, scores above one that did not; 0.5 is a coin toss.",
        "",
        "| Label | Search | Candidates | Gain by later period | Mean gain | Best shuffled gain (95th percentile) | p | "
        "Holds up |",
        "|---|---|---:|---|---:|---:|---:|---|",
    ]
    for m in results:
        cand = m["folds"][0].get("candidates", "")
        per = "; ".join(f"{f['test'][0]} to {f['test'][1]}: {_r(f['gain'])}" for f in m["folds"])
        lines.append(f"| `{m['label']}` | {'sparse logistic' if m['learner'] == 'lasso' else 'boosted trees'} | "
                     f"{cand} | {per} | {_r(m['mean_gain'])} | {_r(m['null_p95'])} | {_r(m['p'], 2)} | "
                     f"{'yes' if m['holds_up'] else 'no'} |")
    lines += ["", "## Variables and combinations chosen in every later period, with the same sign", ""]
    for m in results:
        name = "sparse logistic" if m["learner"] == "lasso" else "boosted trees"
        lines.append(f"**`{m['label']}`, {name}** ({'holds up' if m['holds_up'] else 'does not hold up'}):")
        lines.append("")
        if not m["stable"]:
            lines.append("- none")
        for n, v in list(m["stable"].items())[:15]:
            sign = "" if m["learner"] != "lasso" else (" (more often withdrew)" if v > 0 else " (less often withdrew)")
            lines.append(f"- {_word(n)}{sign}")
        if len(m["stable"]) > 15:
            lines.append(f"- and {len(m['stable']) - 15} more")
        lines.append("")
    lines += [
        "## Limits",
        "",
        "- Withdrawal is the outcome, and most withdrawals have market or grid reasons. A variable that holds up "
        "describes requests that withdrew, not opposition.",
        "- Only two later periods per label are scored, so a gain that holds up rests on few periods.",
        "- With 99 shuffles the smallest p possible is 0.01, so a pass means the real search beat every shuffle or "
        "all but one.",
        "",
    ]
    return "\n".join(lines)


# ── Self-test and main ──────────────────────────────────────────────────────

def _selftest() -> int:
    rng = np.random.default_rng(5)
    n = 2400
    years = rng.integers(2010, 2020, n)
    base = ["request_year", "tech_solar", "tech_wind", "tech_storage"]
    xb = np.column_stack([years, rng.integers(0, 2, n), rng.integers(0, 2, n), np.zeros(n)]).astype(float)
    a, b, noise = rng.normal(size=n), rng.normal(size=n), rng.normal(size=n)
    xc = np.column_stack([a, b, noise])
    xc[rng.random(n) < 0.05, 2] = np.nan
    z = 1.5 * a * b  # signal only in the pair
    y = (rng.random(n) < 1 / (1 + np.exp(-z))).astype(int)
    data = (base, ["a", "b", "noise"], xb, xc, y, years)
    m = with_null("lasso", "withdrawn", data, 3)
    assert m["mean_gain"] > 0.05 and "a x b" in m["stable"], (m["mean_gain"], m["stable"])
    assert m["p"] == 0.25, "the real gain beats every shuffle"
    t = with_null("trees", "withdrawn", data, 2)
    assert t["mean_gain"] > 0.05, t["mean_gain"]
    y0 = rng.integers(0, 2, n)
    null = with_null("lasso", "withdrawn", (base, ["a", "b", "noise"], xb, xc, y0, years), 3)
    assert not null["holds_up"], "pure noise must not hold up"
    assert "# Renewable Headwind Model" in report([m, t, null], 3)
    print("headwind_search selftest: ok")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    null_runs = int(sys.argv[sys.argv.index("--null-runs") + 1]) if "--null-runs" in sys.argv else NULL_RUNS
    rows = read_csv(HISTORY_PATH)
    results = []
    for label in OUTER:
        data = frame(rows, label)
        for learner in ("lasso", "trees"):
            m = with_null(learner, label, data, null_runs)
            results.append(m)
            print(f"headwind_search {label} {learner}: mean gain {m['mean_gain']:.3f} (min {m['min_gain']:.3f}), "
                  f"p {m['p']:.2f}, {'holds up' if m['holds_up'] else 'does not hold up'}", flush=True)
    OUT_JSON.write_text(json.dumps(results, indent=1, sort_keys=True, default=float) + "\n", encoding="utf-8")
    OUT_MD.write_text(report(results, null_runs), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
