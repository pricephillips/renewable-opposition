"""What the decided projects say about the record score's moratorium weights.

The county record score (scripts/county_record_score.py) is a rubric with
weights set by hand. The data center side's county score is fitted instead:
a regularized logistic model, validated by repeated cross-validation and a
calibration gate (data-centers county_policy_model.py). This script takes the
same approach as far as the renewables record allows today, on the question a
reader of the record score asks: did projects fare differently where a
moratorium or ban was on the books when they were decided, and does it matter
whether the pause was new, long-running, extended or waiting on rules being
drafted?

Cases: every contested project whose outcome is blocked_confirmed or
advanced_confirmed, with a county and a resolution_date (the date of the
document that settled the outcome; the record has no separate decision date).
Outcome: 1 for blocked, 0 for advanced.

Features, each read as of the project's resolution date, from the county's
own instruments on the project's technology (an instrument counts when it
was enacted on or before that date and had not ended before it):
  pause_new        a severity 3 or 4 temporary instrument under a year old,
                   never extended
  pause_long       a severity 3 or 4 temporary instrument a year old or more,
                   or extended
  pause_drafting   such a pause while the record says rules are being drafted
  ban              a severity 3 or 4 permanent instrument
  standards        a severity 1 or 2 instrument (setbacks, height or noise limits)
  organized        the project names an opposition group

The fit is L2-regularized logistic regression (scikit-learn), five folds
repeated five times with fixed seeds, scored by out-of-fold AUC and the shared
calibration gate (scripts/calibration_gate.py). Beside it, the hand rubric's
own instrument points for the same project and date give the AUC the hand
weights reach on the same cases.

Limits, stated in the report: the cases are projects that drew opposition,
not every project; an instrument adopted in response to the project it
blocked counts as on the books; and the counts are small, so a coefficient
is a direction, not a weight to copy. The output is internal, read by staff
only: data/model/record_score_fit.json and record_score_fit.md. Associations
only; nothing here says an instrument caused an outcome.

Usage: python scripts/record_score_fit.py [--selftest]
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibration_gate  # noqa: E402
import county_record_score as crs  # noqa: E402
from common import PROCESSED_DIR, ROOT, read_csv  # noqa: E402

OUT_JSON = ROOT / "data" / "model" / "record_score_fit.json"
OUT_MD = ROOT / "data" / "model" / "record_score_fit.md"
CONFIG_PATH = ROOT / "config" / "county_record_score.json"
FEATURES = ("pause_new", "pause_long", "pause_drafting", "ban", "standards", "organized")
FEATURE_WORDS = {
    "pause_new": "a new moratorium (under a year, never extended)",
    "pause_long": "a long-running or extended moratorium",
    "pause_drafting": "a moratorium while rules are being drafted",
    "ban": "a ban (no pause described)",
    "standards": "siting standards only (severity 1 or 2)",
    "organized": "a named opposition group",
}
SEEDS = (11, 23, 37, 41, 53)


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def _date(v: str, end: bool = False) -> date | None:
    v = _s(v)
    try:
        if len(v) == 10:
            return date.fromisoformat(v)
        if len(v) == 7:
            y, m = int(v[:4]), int(v[5:])
            return date(y, m, 28 if end else 1)
        if len(v) == 4:
            return date(int(v), 12 if end else 1, 31 if end else 1)
    except ValueError:
        return None
    return None


def _techs(v: str) -> set[str]:
    return {t for t in _s(v).split(";") if t}


def cases(projects: list[dict], restrictions: list[dict], cfg: dict) -> list[dict]:
    """One row per decided, dated, placed project: outcome, features and the
    hand rubric's instrument points at its resolution date."""
    by_county: dict[str, list[dict]] = {}
    for r in restrictions:
        for f in _s(r.get("county_fips_all") or r.get("county_fips")).split(";"):
            if f:
                by_county.setdefault(f, []).append(r)
    out = []
    for p in projects:
        if p.get("outcome") not in ("blocked_confirmed", "advanced_confirmed"):
            continue
        when, fips = _date(p.get("resolution_date")), _s(p.get("county_fips"))
        if not when or not fips:
            continue
        techs = _techs(p.get("technology"))
        feats = dict.fromkeys(FEATURES, 0)
        feats["organized"] = int(bool(_s(p.get("opposition_groups"))))
        live, any_inst, undated = [], 0, 0
        for r in by_county.get(fips, []):
            if _s(r.get("technology")) not in techs:
                continue
            any_inst = 1
            start = _date(r.get("date_enacted_iso"))
            undated += int(start is None)
            stop = _date(r.get("ends_on") or r.get("current_end_date_iso"), end=True)
            if not start or start > when or (stop and stop < when):
                continue
            sev = crs._int(r.get("severity_score"))
            months = (when.year - start.year) * 12 + when.month - start.month
            ext = crs._int(r.get("extensions"))
            term = _s(r.get("term"))
            if sev >= 3 and term == "temporary":
                if _s(r.get("drafting")) == "active":
                    feats["pause_drafting"] = 1
                elif months >= 12 or ext:
                    feats["pause_long"] = 1
                else:
                    feats["pause_new"] = 1
            elif sev >= 3 and term in ("permanent", "unclear"):
                feats["ban"] = 1
            elif sev in (1, 2):
                feats["standards"] = 1
            live.append({**r, "months_in_force": str(max(months, 0)), "currency": "in_force"})
        insts = list(crs.instruments(live).values())
        pts = crs.stack(sorted((crs.instrument_points(i, cfg) for i in insts), reverse=True), cfg) if insts else 0.0
        out.append({"id": p.get("id"), "state": p.get("state"), "county_fips": fips, "resolution_date": when.isoformat(),
                    "y": int(p["outcome"] == "blocked_confirmed"), "rubric_points": round(pts, 2),
                    "county_has_instrument": any_inst, "instrument_undated": int(undated > 0), **feats})
    return out


def _auc(score: list[float], y: list[int]) -> float:
    pos = [s for s, t in zip(score, y) if t]
    neg = [s for s, t in zip(score, y) if not t]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def fit(rows: list[dict]) -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold

    X = [[r[f] for f in FEATURES] for r in rows]
    y = [r["y"] for r in rows]
    n = len(y)
    aucs, coefs = [], {f: [] for f in FEATURES}
    oof_sum, oof_n = [0.0] * n, [0] * n
    for seed in SEEDS:
        folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
        pred = [0.0] * n
        for tr, te in folds.split(X, y):
            m = LogisticRegression(C=1.0, max_iter=1000).fit([X[i] for i in tr], [y[i] for i in tr])
            for f, c in zip(FEATURES, m.coef_[0]):
                coefs[f].append(float(c))
            for i, p in zip(te, m.predict_proba([X[i] for i in te])[:, 1]):
                pred[i] = float(p)
        aucs.append(_auc(pred, y))
        for i, p in enumerate(pred):
            oof_sum[i] += p
            oof_n[i] += 1
    oof = [s / k for s, k in zip(oof_sum, oof_n)]
    full = LogisticRegression(C=1.0, max_iter=1000).fit(X, y)
    aucs.sort()
    stability = {}
    for f in FEATURES:
        vals = sorted(coefs[f])
        stability[f] = {"coef": round(float(full.coef_[0][FEATURES.index(f)]), 3),
                        "min": round(vals[0], 3), "median": round(vals[len(vals) // 2], 3),
                        "max": round(vals[-1], 3), "sign_stable": vals[0] * vals[-1] > 0,
                        "cases_with": sum(r[f] for r in rows),
                        "blocked_share_with": round(sum(r["y"] for r in rows if r[f]) / max(1, sum(r[f] for r in rows)), 3)}
    return {"county_has_instrument": sum(r["county_has_instrument"] for r in rows),
            "instrument_undated": sum(r["instrument_undated"] for r in rows),
            "auc_p10": round(aucs[0], 3), "auc_p50": round(aucs[len(aucs) // 2], 3), "auc_p90": round(aucs[-1], 3),
            "rubric_auc": round(_auc([r["rubric_points"] for r in rows], y), 3),
            "features": stability, "gate": calibration_gate.gate(oof, y)}


def report(rows: list[dict], result: dict, cfg: dict) -> str:
    n, pos = len(rows), sum(r["y"] for r in rows)
    t = cfg["instruments"]["term"]
    lines = [
        "# Record score: what the decided projects say",
        "",
        "Internal, staff only. Built by `scripts/record_score_fit.py`; read `docs/county_record_score.md` first.",
        "",
        f"Cases: {n} contested projects with a confirmed outcome, a county and a resolution date ({pos} blocked, "
        f"{n - pos} advanced). Each feature is read from the county's own instruments on the project's technology "
        "as of the project's resolution date.",
        "",
        f"Learned model (L2 logistic regression, 5 folds x {len(SEEDS)} repeats): out-of-fold AUC "
        f"{result['auc_p50']} (p10 {result['auc_p10']}, p90 {result['auc_p90']}). The hand rubric's instrument "
        f"points on the same cases: AUC {result['rubric_auc']}. AUC is the chance that a blocked project, picked "
        "at random, scores above an advanced one; 0.5 is a coin toss.",
        "",
        f"Coverage: {sum(r['county_has_instrument'] for r in rows)} of the {n} projects are in a county with an "
        f"instrument on their technology in the record, and for {sum(r['instrument_undated'] for r in rows)} of "
        "them at least one such instrument has no enactment date, so it cannot be placed before or after the "
        "decision and is left out. Dated instruments and decision dates are what the fit needs most.",
        "",
        f"Calibration gate: {result['gate']['verdict']}"
        + (f" ({'; '.join(result['gate']['reasons'])})" if result['gate']['reasons'] else "") + ".",
        "",
        "| Feature | Cases with it | Share blocked | Coefficient | Fold range | Same sign in every fold |",
        "|---|---:|---:|---:|---|---|",
    ]
    for f in FEATURES:
        s = result["features"][f]
        lines.append(f"| {FEATURE_WORDS[f]} | {s['cases_with']} | {s['blocked_share_with']} | {s['coef']} | "
                     f"{s['min']} to {s['max']} | {'yes' if s['sign_stable'] else 'no'} |")
    lines += [
        "",
        "## How this bears on the hand weights",
        "",
        f"The rubric counts a new moratorium at {t['base']} of a ban's points, adds {t['per_extension']} for each "
        f"extension and {t['per_year_in_force']} for each year in force (up to {t['max']}), and multiplies by "
        f"{t['drafting_active']} while rules are being drafted. The table says whether the decided projects point "
        "the same way: a long-running or extended pause with a larger coefficient than a new one, and a pause "
        "with rules being drafted with a smaller one. A coefficient whose sign changes across folds, or that "
        "rests on fewer than 10 cases, is not evidence either way.",
        "",
        "## Limits",
        "",
        "- The cases are projects that drew opposition, not every project proposed in a county.",
        "- An instrument adopted in response to the project it blocked counts as on the books. The model "
        "describes association, never cause.",
        "- The resolution date is the date of the document that settled the outcome, not always the decision itself.",
        "- The counts are small. The fit can replace the hand weights only once the calibration gate says PROMOTE "
        "and the project universe with decision dates (Build-Out goal R3) is in place.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    rows = cases(read_csv(PROCESSED_DIR / "contested_projects.csv"), read_csv(PROCESSED_DIR / "restrictions.csv"), cfg)
    result = fit(rows)
    OUT_JSON.write_text(json.dumps({"cases": len(rows), **result}, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(report(rows, result, cfg), encoding="utf-8")
    print(f"record_score_fit: {len(rows)} cases, AUC {result['auc_p50']} (rubric {result['rubric_auc']}), "
          f"gate {result['gate']['verdict']}")
    return 0


def _selftest() -> int:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    mor = {"county_fips_all": "01001", "technology": "solar", "severity_score": "4", "term": "temporary",
           "date_enacted_iso": "2024-01-01", "extensions": "0", "drafting": "", "jurisdiction_type": "County",
           "instrument_id": "m1"}
    projects = [{"id": "p1", "outcome": "blocked_confirmed", "county_fips": "01001", "technology": "solar",
                 "resolution_date": "2024-03-01", "opposition_groups": "X"},
                {"id": "p2", "outcome": "advanced_confirmed", "county_fips": "01001", "technology": "solar",
                 "resolution_date": "2023-06-01"},
                {"id": "p3", "outcome": "blocked_confirmed", "county_fips": "01001", "technology": "solar",
                 "resolution_date": "2025-06-01"},
                {"id": "p4", "outcome": "pending", "county_fips": "01001", "technology": "solar",
                 "resolution_date": "2025-06-01"}]
    rows = {r["id"]: r for r in cases(projects, [mor], cfg)}
    assert set(rows) == {"p1", "p2", "p3"}, rows
    assert rows["p1"]["pause_new"] == 1 and rows["p1"]["organized"] == 1 and rows["p1"]["pause_long"] == 0
    assert rows["p2"]["pause_new"] == 0 and rows["p2"]["rubric_points"] == 0     # before the moratorium
    assert rows["p3"]["pause_long"] == 1                                           # 17 months in
    assert rows["p3"]["rubric_points"] > rows["p1"]["rubric_points"] > 0
    assert _auc([0.9, 0.1], [1, 0]) == 1.0 and _auc([0.5, 0.5], [1, 0]) == 0.5
    print("record_score_fit selftest: ok")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else main())
