"""Renewable Headwind Model: which learner predicts best, tested forward in time.

scripts/headwind_model.py fits the registered logistic model. Price asked on
2026-11-20 for the strongest learner the data supports, a neural net if it
wins. This script races three learners on the same rows
(data/model/headwind_history.csv) and the same time-based holdouts, and names
the one that wins:

  logistic   L2 logistic regression on standardized variables
  boosting   gradient-boosted trees (scikit-learn HistGradientBoosting)
  neural     a small neural net (scikit-learn MLPClassifier, two hidden
             layers, weight decay, early stopping), averaged over 5 seeds

Each learner is fit twice: on the request alone (year, size, technology,
grid region) and on the request plus the county snapshot. The county record
earns its place only by the gain it adds within the same learner.

Holdouts are forward in time, never shuffled: each fold trains on requests
made up to a year and scores the requests made after it. A model never sees
a later request while it is trained.

The winner is the learner with the best mean holdout AUC on request plus
county. It is shipped (scores written for staff use) only when it also passes
the shared calibration gate on the holdout requests and beats the request-only
version of itself by at least 0.01 AUC on every holdout. Otherwise the report
says HOLD. Associations only, never cause. Internal, staff only.

Outputs: data/model/headwind_compare.json and headwind_compare.md.

Usage: python scripts/headwind_compare.py [--selftest]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibration_gate  # noqa: E402
from common import ROOT, read_csv  # noqa: E402
from headwind_history import COUNTY_VARS, OUT_PATH as HISTORY_PATH  # noqa: E402
from headwind_model import LABELS, base_columns, matrix  # noqa: E402

OUT_JSON = ROOT / "data" / "model" / "headwind_compare.json"
OUT_MD = ROOT / "data" / "model" / "headwind_compare.md"
SEEDS = (11, 23, 37, 41, 53)
MIN_GAIN = 0.01
# Forward holdouts: (train through this year, score these years).
HOLDOUTS = {
    "withdrawn": [(2014, (2015, 2016)), (2016, (2017, 2019))],
    "withdrawn_3y": [(2016, (2017, 2018)), (2018, (2019, 2022))],
}
LEARNERS = ("logistic", "boosting", "neural")
WORDS = {"logistic": "logistic regression", "boosting": "gradient-boosted trees", "neural": "neural net"}


def make(learner: str, seed: int):
    if learner == "logistic":
        return make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=5000))
    if learner == "boosting":
        return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
                                              min_samples_leaf=40, l2_regularization=1.0, random_state=seed)
    if learner == "neural":
        return make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(32, 16), alpha=1e-2,
                                                             early_stopping=True, validation_fraction=0.15,
                                                             max_iter=500, random_state=seed))
    raise KeyError(learner)


def predict(learner: str, xtr, ytr, xte) -> np.ndarray:
    seeds = SEEDS if learner == "neural" else SEEDS[:1]
    return np.mean([make(learner, s).fit(xtr, ytr).predict_proba(xte)[:, 1] for s in seeds], axis=0)


def brier_skill(p: np.ndarray, y: np.ndarray, base: float) -> float:
    b0 = float(np.mean((base - y) ** 2))
    return 1 - float(np.mean((p - y) ** 2)) / b0 if b0 else 0.0


def race(rows: list[dict], label: str) -> dict:
    lab = LABELS[label]
    q = [r for r in rows if r["source"] == "queue" and str(r[lab["in_fit"]]) == "1"]
    base = base_columns(q)
    x_full = matrix(q, base, COUNTY_VARS)
    x_base = x_full[:, :len(base)]
    y = np.array([int(r[lab["y"]]) for r in q])
    years = np.array([int(r["year"]) for r in q])
    out = {"label": label, "requests": len(q), "holdouts": [], "learners": {}}
    preds = {lr: {"full": [], "base": []} for lr in LEARNERS}
    ys = []
    for train_to, (lo, hi) in HOLDOUTS[label]:
        tr, te = years <= train_to, (years >= lo) & (years <= hi)
        out["holdouts"].append({"train_through": train_to, "score": [lo, hi], "train": int(tr.sum()),
                                "test": int(te.sum()), "test_positive_share": round(float(y[te].mean()), 4)})
        ys.append(y[te])
        for lr in LEARNERS:
            for kind, x in (("full", x_full), ("base", x_base)):
                preds[lr][kind].append(predict(lr, x[tr], y[tr], x[te]))
    for lr in LEARNERS:
        aucs = {k: [float(roc_auc_score(yt, p)) for yt, p in zip(ys, preds[lr][k])] for k in ("full", "base")}
        gains = [a - b for a, b in zip(aucs["full"], aucs["base"])]
        bss = [brier_skill(p, yt, float(y[years <= h[0]].mean()))
               for (h, yt, p) in zip(HOLDOUTS[label], ys, preds[lr]["full"])]
        pooled_p = np.concatenate(preds[lr]["full"])
        pooled_y = np.concatenate(ys)
        gate = calibration_gate.gate(pooled_p.tolist(), pooled_y.tolist())
        out["learners"][lr] = {
            "auc_full": [round(a, 4) for a in aucs["full"]], "auc_base": [round(a, 4) for a in aucs["base"]],
            "gain": [round(g, 4) for g in gains], "mean_auc_full": round(float(np.mean(aucs["full"])), 4),
            "mean_gain": round(float(np.mean(gains)), 4), "brier_skill": [round(b, 4) for b in bss],
            "gate": gate["verdict"], "gate_reasons": gate["reasons"], "ece": gate["ece"],
        }
    win = max(LEARNERS, key=lambda lr: (out["learners"][lr]["mean_auc_full"], -LEARNERS.index(lr)))
    w = out["learners"][win]
    out["winner"] = win
    out["verdict"] = "SHIP" if w["gate"] == "PROMOTE" and min(w["gain"]) >= MIN_GAIN else "HOLD"
    return out


def _r(v, n=3):
    return "n/a" if v is None else f"{v:.{n}f}"


def report(results: list[dict]) -> str:
    lines = [
        "# Renewable Headwind Model: which learner wins",
        "",
        "Written by `scripts/headwind_compare.py`. Do not edit by hand. Internal, staff only. Read "
        "`docs/headwind_model.md` first.",
        "",
        "Three learners race on the same requests and the same forward-in-time holdouts: each is trained on "
        "requests made up to a year and scored on the requests made after it. AUC is the chance that a request "
        "that withdrew, picked at random, scores above one that did not; 0.5 is a coin toss. The gain is what the "
        "county snapshot adds over the same learner given the request alone (year, size, technology, grid region).",
        "",
        f"A learner ships only when it has the best mean holdout AUC, passes the calibration gate on the holdout "
        f"requests, and gains at least {MIN_GAIN} AUC from the county snapshot on every holdout.",
        "",
    ]
    for res in results:
        lab = LABELS[res["label"]]
        lines += [f"## Label: {lab['title']}", "",
                  f"**Best learner: {WORDS[res['winner']]}. Verdict: {res['verdict']}.** Requests: {res['requests']}.",
                  "", "| Holdout | Trained on | Scored |", "|---|---:|---:|"]
        for h in res["holdouts"]:
            lines.append(f"| train through {h['train_through']}, score {h['score'][0]} to {h['score'][1]} | "
                         f"{h['train']} | {h['test']} |")
        lines += ["", "| Learner | Holdout AUC, request and county | Request only | Gain from the county | "
                  "Brier skill | Gate |", "|---|---|---|---|---|---|"]
        for lr in LEARNERS:
            m = res["learners"][lr]
            lines.append(f"| {WORDS[lr]} | {', '.join(_r(a) for a in m['auc_full'])} | "
                         f"{', '.join(_r(a) for a in m['auc_base'])} | {', '.join(_r(g) for g in m['gain'])} | "
                         f"{', '.join(_r(b) for b in m['brier_skill'])} | {m['gate']} |")
        lines.append("")
    lines += ["Each cell lists the holdouts in the order of the first table.", ""]
    return "\n".join(lines)


def _selftest() -> int:
    rng = np.random.default_rng(5)
    rows = []
    for i in range(1500):
        h = float(rng.uniform(0.5, 1.0))
        # A non-linear county effect: only very high withdrawal histories matter.
        p = 0.3 + 0.6 * (h > 0.85)
        y = int(rng.uniform() < p)
        rows.append({"row_id": str(i), "source": "queue", "in_fit": "1", "in_fit_3y": "1", "state": "S",
                     "county_fips": "00001", "region": ["A", "B"][i % 2], "technology": "solar",
                     "capacity_mw": "50", "year": str(2010 + i % 13), "y": str(y), "y_3y": str(y),
                     **{n: "0" for n in COUNTY_VARS}, "prior_withdrawal_share": str(h)})
    res = race(rows, "withdrawn")
    assert set(res["learners"]) == set(LEARNERS)
    assert res["learners"]["boosting"]["mean_gain"] > 0.1, "trees must find a threshold effect"
    assert res["winner"] in ("boosting", "neural"), res["winner"]
    assert "# Renewable Headwind Model" in report([res])
    print("headwind_compare selftest: ok")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    rows = read_csv(HISTORY_PATH)
    results = [race(rows, label) for label in LABELS]
    OUT_JSON.write_text(json.dumps(results, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    OUT_MD.write_text(report(results), encoding="utf-8")
    for r in results:
        print(f"headwind_compare {r['label']}: winner {r['winner']}, {r['verdict']}; " + "; ".join(
            f"{lr} {r['learners'][lr]['mean_auc_full']} (gain {r['learners'][lr]['mean_gain']})" for lr in LEARNERS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
