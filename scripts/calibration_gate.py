"""Calibration gate: whether a model's scores are calibrated well enough to promote.

Ported from pricephillips/data-center-map calibration_gate.py, keeping its
thresholds (registered for this repo in config/county_model_registration.json):

  ECE_MAX        0.15  expected calibration error over 5 equal-width bins
                       (empty bins skipped), weighted by bin size
  BSS_MIN        0.05  Brier skill score against the base rate: the model has
                       to beat predicting the base rate for everyone
  MIN_SAMPLE     60    fewer cases: HOLD, insufficient data
  MIN_POSITIVES  20    fewer positives: HOLD, insufficient data

PROMOTE when every check passes, HOLD with the reasons otherwise. Promotion
here means only that the scores are fit to be described in the model report;
no score reaches a page without a separate decision
(docs/predictive_foundation_design.md).
"""
from __future__ import annotations

ECE_MAX = 0.15
BSS_MIN = 0.05
MIN_SAMPLE = 60
MIN_POSITIVES = 20
N_BINS = 5


def brier(pred: list[float], y: list[int]) -> float:
    return sum((p - t) ** 2 for p, t in zip(pred, y)) / len(y)


def reliability(pred: list[float], y: list[int], n_bins: int = N_BINS) -> list[dict]:
    """Equal-width bins: lo, hi, count, mean predicted, observed rate; non-empty only."""
    out = []
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        idx = [i for i, p in enumerate(pred) if lo <= p < hi or (b == n_bins - 1 and p == 1.0)]
        if idx:
            out.append({"lo": lo, "hi": hi, "count": len(idx),
                        "mean_pred": sum(pred[i] for i in idx) / len(idx),
                        "observed": sum(y[i] for i in idx) / len(idx)})
    return out


def ece(pred: list[float], y: list[int], n_bins: int = N_BINS) -> float:
    return sum(b["count"] * abs(b["mean_pred"] - b["observed"]) for b in reliability(pred, y, n_bins)) / len(y)


def gate(pred: list[float], y: list[int]) -> dict:
    n, pos = len(y), sum(y)
    base = pos / n if n else 0.0
    b = brier(pred, y) if n else 0.0
    b0 = base * (1 - base)
    bss = 1 - b / b0 if b0 else 0.0
    e = ece(pred, y) if n else 0.0
    reasons = []
    if n < MIN_SAMPLE:
        reasons.append(f"INSUFFICIENT_DATA: n {n} < {MIN_SAMPLE}")
    if pos < MIN_POSITIVES:
        reasons.append(f"INSUFFICIENT_DATA: positives {pos} < {MIN_POSITIVES}")
    if e > ECE_MAX:
        reasons.append(f"MISCALIBRATED: ECE {e:.3f} > {ECE_MAX}")
    if bss < BSS_MIN:
        reasons.append(f"NO_SKILL: Brier skill {bss:.3f} < {BSS_MIN}")
    return {"n": n, "positives": pos, "base_rate": round(base, 4), "brier": round(b, 4),
            "brier_baseline": round(b0, 4), "brier_skill_score": round(bss, 4), "ece": round(e, 4),
            "reliability": [{k: round(v, 4) if isinstance(v, float) else v for k, v in r.items()}
                            for r in reliability(pred, y)],
            "verdict": "HOLD" if reasons else "PROMOTE", "reasons": reasons}
