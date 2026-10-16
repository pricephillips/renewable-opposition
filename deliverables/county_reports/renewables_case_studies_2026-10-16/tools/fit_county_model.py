"""Provisional fit of the county restriction model, following
config/county_model_registration.json (registered 2026-10-16) as closely as a
scratch script can. Not the repository's step 2 model: written for the
county case studies in this folder; the repository's own step 2 model is
built separately. county_labels.csv is a copy of data/model/county_labels.csv
from commit 4ae9eca (the label builder registered on 2026-10-16).

Usage: python fit_county_model.py REPO_DIR OUT_DIR  (OUT_DIR: ../model)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedKFold, GroupKFold

REPO = Path(sys.argv[1])
OUT = Path(sys.argv[2])
HERE = Path(__file__).resolve().parents[1] / "model"  # county_labels.csv lives here
SEED = 20261016
C_GRID = [1.0, 0.3, 0.1, 0.03, 0.01]
SITES = {"21181": "Nicholas KY", "19113": "Linn IA", "20021": "Cherokee KS", "48201": "Harris TX"}


def load():
    cov = pd.read_csv(REPO / "data/reference/county_covariates.csv", dtype={"county_fips": str})
    lab = pd.read_csv(HERE / "county_labels.csv", dtype={"county_fips": str})
    fac = pd.read_csv(REPO / "data/reference/facilities.csv", dtype={"county_fips": str})
    que = pd.read_csv(REPO / "data/reference/queue_projects.csv", dtype={"county_fips": str})
    adj = pd.read_parquet(REPO / "data/db/parquet/county_adjacency.parquet")
    df = cov.merge(lab.drop(columns=["state", "county"]), on="county_fips", how="left")

    # Facilities: EIA-860M only (one source, so no double counting), operating or retired.
    e = fac[(fac.source == "eia860m") & fac.status.isin(["operating", "retired"])].copy()
    e["year"] = pd.to_numeric(e.year, errors="coerce")
    e["capacity_mw"] = pd.to_numeric(e.capacity_mw, errors="coerce").fillna(0)
    for tech in ("solar", "wind"):
        t = e[e.technology.str.contains(tech, na=False)]
        df[f"{tech}_mw_all"] = df.county_fips.map(t.groupby("county_fips").capacity_mw.sum()).fillna(0)
        t21 = t[t.year <= 2021]
        df[f"{tech}_mw_2021"] = df.county_fips.map(t21.groupby("county_fips").capacity_mw.sum()).fillna(0)

    # Queue: solar, wind and storage MW requested, by request date.
    q = que.copy()
    for c in ("solar_mw", "wind_mw", "storage_mw"):
        q[c] = pd.to_numeric(q[c], errors="coerce").fillna(0)
    q["mw"] = q.solar_mw + q.wind_mw + q.storage_mw
    q["req_year"] = pd.to_datetime(q.request_date, errors="coerce").dt.year
    df["queue_mw_all"] = df.county_fips.map(q.groupby("county_fips").mw.sum()).fillna(0)
    df["queue_n_all"] = df.county_fips.map(q[q.mw > 0].groupby("county_fips").size()).fillna(0)
    df["queue_mw_2021"] = df.county_fips.map(q[q.req_year < 2022].groupby("county_fips").mw.sum()).fillna(0)

    # Neighbour share with a severe restriction (before 2022, or ever).
    sev = lab.set_index("county_fips")
    first = pd.to_numeric(sev.first_severe_year, errors="coerce")
    sev_before = ((sev.has_severe == 1) & ((first < 2022) | (sev.has_undated_severe == 1)))
    a = adj.copy()
    a["n_any"] = a.neighbor_fips.map(sev.has_severe).fillna(0)
    a["n_pre"] = a.neighbor_fips.map(sev_before.astype(int)).fillna(0)
    g = a.groupby("county_fips")
    df["neighbor_severe_share_all"] = df.county_fips.map(g.n_any.mean()).fillna(0)
    df["neighbor_severe_share_2021"] = df.county_fips.map(g.n_pre.mean()).fillna(0)
    return df, adj


def design(df, asof):
    X = pd.DataFrame(index=df.index)
    X["log_population"] = np.log(df.population)
    X["log_density"] = np.log(df.pop_density_sqmi)
    X["log_income"] = np.log(df.median_hh_income)
    X["pct_bachelors_plus"] = df.pct_bachelors_plus
    X["margin"] = df.margin_dr_2020 if asof == "2021" else df.margin_dr_2024
    X["log1p_solar_mw"] = np.log1p(df[f"solar_mw_{asof}"])
    X["log1p_wind_mw"] = np.log1p(df[f"wind_mw_{asof}"])
    X["neighbor_severe_share"] = df[f"neighbor_severe_share_{asof}"]
    X["log1p_queue_mw"] = np.log1p(df[f"queue_mw_{asof}"])
    return X.apply(lambda c: c.fillna(c.median()))


def fit_folds(X, y, cols, C):
    rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=5, random_state=SEED)
    coefs, aucs, models = [], [], []
    oof = np.zeros((5, len(y)))
    for i, (tr, te) in enumerate(rskf.split(X, y)):
        mu, sd = X.iloc[tr][cols].mean(), X.iloc[tr][cols].std(ddof=0)
        Ztr = (X.iloc[tr][cols] - mu) / sd
        Zte = (X.iloc[te][cols] - mu) / sd
        m = LogisticRegression(C=C, max_iter=2000).fit(Ztr, y[tr])
        lo = m.decision_function(Zte)
        oof[i // 5, te] = lo
        aucs.append(roc_auc_score(y[te], lo))
        coefs.append(m.coef_[0])
        models.append((m, mu, sd))
    return np.array(coefs), np.array(aucs), oof, models


def select(X, y, pool):
    candidates = []
    for C in C_GRID:
        cols = list(pool)
        while True:
            coefs, aucs, _, _ = fit_folds(X, y, cols, C)
            pos = (coefs > 0).sum(0)
            neg = (coefs < 0).sum(0)
            unstable = [j for j in range(len(cols)) if pos[j] and neg[j]]
            candidates.append({"C": C, "cols": list(cols), "auc": float(np.median(aucs)),
                               "admissible": not unstable})
            if not unstable or len(cols) <= 3:
                break
            # drop the variable that most evenly straddles zero
            def key(j):
                return (-min(pos[j], neg[j]), float(np.median(np.abs(coefs[:, j]))), cols[j])
            drop = sorted(unstable, key=key)[0]
            cols.pop(drop)
    adm = [c for c in candidates if c["admissible"]]
    best_any = max(c["auc"] for c in candidates)
    if not adm:
        return None, candidates, None
    win = sorted(adm, key=lambda c: (-c["auc"], -len(c["cols"]), c["C"]))[0]
    return win, candidates, best_any - win["auc"]


def recalibrate(logit, y):
    """Cross-fitted logistic recalibration of the pooled out-of-fold logit."""
    cal = np.zeros(len(y))
    maps = []
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=SEED).split(logit.reshape(-1, 1), y):
        r = LogisticRegression(C=1e6, max_iter=1000).fit(logit[tr].reshape(-1, 1), y[tr])
        cal[te] = r.predict_proba(logit[te].reshape(-1, 1))[:, 1]
        maps.append(r)
    full = LogisticRegression(C=1e6, max_iter=1000).fit(logit.reshape(-1, 1), y)
    return cal, full, maps


def ece(p, y, bins=5):
    qs = np.quantile(p, np.linspace(0, 1, bins + 1))
    idx = np.clip(np.searchsorted(qs, p, side="right") - 1, 0, bins - 1)
    e = 0.0
    for b in range(bins):
        m = idx == b
        if m.any():
            e += m.mean() * abs(p[m].mean() - y[m].mean())
    return e


def morans_i(resid, fips, adj, perms=999):
    pos = {f: i for i, f in enumerate(fips)}
    a = adj[adj.county_fips.isin(pos) & adj.neighbor_fips.isin(pos)]
    i_idx = a.county_fips.map(pos).values
    j_idx = a.neighbor_fips.map(pos).values
    deg = np.bincount(i_idx, minlength=len(fips)).astype(float)
    w = 1.0 / deg[i_idx]
    def stat(z):
        z = z - z.mean()
        return (len(z) / w.sum()) * (w * z[i_idx] * z[j_idx]).sum() / (z ** 2).sum()
    obs = stat(resid)
    rng = np.random.default_rng(SEED)
    sims = np.array([stat(rng.permutation(resid)) for _ in range(perms)])
    p = (1 + (np.abs(sims) >= abs(obs)).sum()) / (perms + 1)
    return float(obs), float(p)


def midrank_pct(values, v):
    values = np.asarray(values)
    return 100 * ((values < v).sum() + 0.5 * (values == v).sum()) / len(values)


def run(df, adj, label, frame_col, asof, name):
    sub = df if frame_col is None else df[df[frame_col] == 1]
    sub = sub.reset_index(drop=True)
    y = sub[label].fillna(0).astype(int).values
    X = design(sub, asof)
    pool = list(X.columns)
    win, cands, cost = select(X, y, pool)
    res = {"name": name, "label": label, "n": int(len(y)), "positives": int(y.sum()),
           "base_rate": float(y.mean()), "candidates": cands}
    if win is None or cost > 0.05:
        res["verdict"] = "STOP: no admissible candidate or stability cost above 0.05"
        return res, None
    cols, C = win["cols"], win["C"]
    coefs, aucs, oof, models = fit_folds(X, y, cols, C)
    logit = oof.mean(0)
    cal, full_map, _ = recalibrate(logit, y)
    # Interval: 200 bootstrap refits of the selected model and its recalibration;
    # the 10th to 90th percentile of each county's bootstrap scores.
    rng = np.random.default_rng(SEED)
    boot = []
    Xc = X[cols].values
    for _ in range(200):
        b = rng.integers(0, len(y), len(y))
        mu_b, sd_b = Xc[b].mean(0), Xc[b].std(0)
        m = LogisticRegression(C=C, max_iter=2000).fit((Xc[b] - mu_b) / sd_b, y[b])
        z_all = m.decision_function((Xc - mu_b) / sd_b)
        r = LogisticRegression(C=1e6, max_iter=1000).fit(z_all[b].reshape(-1, 1), y[b])
        boot.append(r.predict_proba(z_all.reshape(-1, 1))[:, 1])
    boot = np.array(boot)
    lo, hi = np.percentile(boot, 10, axis=0), np.percentile(boot, 90, axis=0)

    brier = brier_score_loss(y, cal)
    brier0 = brier_score_loss(y, np.full(len(y), y.mean()))
    bss = 1 - brier / brier0
    e = ece(cal, y)
    slope = LogisticRegression(C=1e6).fit(np.log(cal / (1 - cal)).reshape(-1, 1), y).coef_[0][0]
    gate = {"ece": e, "ece_ok": e <= 0.15, "brier": brier, "brier_baseline": brier0,
            "brier_skill": bss, "bss_ok": bss >= 0.05, "n_ok": len(y) >= 60, "pos_ok": y.sum() >= 20}
    verdict = "PROMOTE" if all(v for k, v in gate.items() if k.endswith("_ok")) else "HOLD"

    # State-grouped CV
    g_aucs = []
    for tr, te in GroupKFold(5).split(X, y, groups=sub.state):
        mu, sd = X.iloc[tr][cols].mean(), X.iloc[tr][cols].std(ddof=0)
        m = LogisticRegression(C=C, max_iter=2000).fit((X.iloc[tr][cols] - mu) / sd, y[tr])
        if len(set(y[te])) > 1:
            g_aucs.append(roc_auc_score(y[te], m.decision_function((X.iloc[te][cols] - mu) / sd)))
    mi, mi_p = morans_i(y - cal, sub.county_fips.tolist(), adj)

    # Full-frame fit for contributions (median of fold coefficients on full-frame standardization)
    mu, sd = X[cols].mean(), X[cols].std(ddof=0)
    med_coef = np.median(coefs, axis=0)
    Z = (X[cols] - mu) / sd

    scores = sub[["county_fips", "state", "county"]].copy()
    scores["label"] = y
    scores["score"] = cal
    scores["lo"] = lo
    scores["hi"] = hi
    scores["logit_oof"] = logit
    for j, c in enumerate(cols):
        scores[f"lift_{c}"] = Z[c].values * med_coef[j]
    scores["decile"] = pd.qcut(scores.score.rank(method="first"), 10, labels=range(1, 11)).astype(int)

    res.update({"verdict": verdict, "C": C, "variables": cols, "median_auc": float(np.median(aucs)),
                "auc_iqr": [float(np.percentile(aucs, 25)), float(np.percentile(aucs, 75))],
                "pooled_oof_auc": float(roc_auc_score(y, cal)),
                "state_grouped_auc": float(np.median(g_aucs)) if g_aucs else None,
                "stability_cost": cost, "gate": gate, "calibration_slope": float(slope),
                "morans_i": mi, "morans_p": mi_p,
                "median_coef": dict(zip(cols, med_coef.tolist())),
                "coef_sign_folds": {c: int((coefs[:, j] > 0).sum()) for j, c in enumerate(cols)},
                "frame_means": mu.to_dict(), "frame_sds": sd.to_dict()})
    dec = scores.groupby("decile").agg(lo=("score", "min"), hi=("score", "max"), n=("score", "size"),
                                       share=("label", "mean"))
    res["deciles"] = dec.reset_index().to_dict(orient="records")
    pos_scores = scores[scores.label == 1].score.median()
    neg_scores = scores[scores.label == 0].score.median()
    res["median_pos"], res["median_neg"] = float(pos_scores), float(neg_scores)
    return res, scores


def peers(df, scores, fips, k=10):
    """Nearest counties on log population, log density, bachelor's share and 2024 margin."""
    feats = pd.DataFrame({"lp": np.log(df.population), "ld": np.log(df.pop_density_sqmi),
                          "ba": df.pct_bachelors_plus, "m": df.margin_dr_2024})
    feats = feats.fillna(feats.median())
    Z = (feats - feats.mean()) / feats.std(ddof=0)
    i = df.index[df.county_fips == fips][0]
    d = np.sqrt(((Z - Z.loc[i]) ** 2).sum(1))
    d[i] = np.inf
    near = d.nsmallest(k).index
    out = df.loc[near, ["county_fips", "state", "county", "population", "has_severe"]].copy()
    out = out.merge(scores[["county_fips", "score"]], on="county_fips", how="left")
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df, adj = load()
    snap, s_scores = run(df, adj, "has_severe", None, "all", "snapshot_has_severe_queue")
    prim, p_scores = run(df, adj, "new_severe_2022_2025", "at_risk_2022", "2021", "primary_prospective_queue")
    s_scores.to_csv(OUT / "scores_snapshot.csv", index=False)
    if p_scores is not None:
        p_scores.to_csv(OUT / "scores_primary.csv", index=False)
        # Held-back 2026 check: at-risk counties with no severe restriction through 2025
        hb = df[(df.at_risk_2022 == 1) & (df.new_severe_2022_2025 == 0)][["county_fips", "new_severe_2026"]]
        hb = hb.merge(p_scores[["county_fips", "score"]], on="county_fips")
        if hb.new_severe_2026.sum() > 0:
            prim["holdout_2026_auc"] = float(roc_auc_score(hb.new_severe_2026, hb.score))
            prim["holdout_2026_n"] = int(len(hb))
            prim["holdout_2026_pos"] = int(hb.new_severe_2026.sum())
    for r in (snap, prim):
        r.pop("candidates", None)
    site = {}
    st = s_scores.set_index("county_fips")
    for f, nm in SITES.items():
        row = st.loc[f]
        state_rows = s_scores[s_scores.state == row.state]
        pos_rows = s_scores[s_scores.label == 1]
        lifts = {c[5:]: float(row[c]) for c in st.columns if c.startswith("lift_")}
        drow = df.set_index("county_fips").loc[f]
        pr = peers(df, s_scores, f)
        nb = adj[adj.county_fips == f].neighbor_fips.tolist()
        nbt = df[df.county_fips.isin(nb)][["county_fips", "state", "county", "population", "has_severe",
                                           "queue_mw_all", "solar_mw_all", "wind_mw_all"]]
        nbt = nbt.merge(s_scores[["county_fips", "score"]], on="county_fips").sort_values("score", ascending=False)
        site[nm] = {
            "fips": f, "score": float(row.score), "lo": float(row.lo), "hi": float(row.hi),
            "label_has_severe": int(row.label), "decile": int(row.decile),
            "us_pct": midrank_pct(s_scores.score, row.score),
            "state_pct": midrank_pct(state_rows.score, row.score),
            "state_rank": int((state_rows.score > row.score).sum() + 1), "state_n": int(len(state_rows)),
            "state_median": float(state_rows.score.median()),
            "state_top3": state_rows.nlargest(3, "score")[["county", "score"]].to_dict(orient="records"),
            "pct_among_restricted": midrank_pct(pos_rows.score, row.score),
            "n_restricted": int(len(pos_rows)),
            "lifts": lifts, "lift_total": float(sum(lifts.values())),
            "values": {k: (None if pd.isna(v) else float(v)) for k, v in {
                "population": drow.population, "land_sqmi": drow.land_sqmi,
                "density": drow.pop_density_sqmi, "income": drow.median_hh_income,
                "bachelors": drow.pct_bachelors_plus, "margin_2024": drow.margin_dr_2024,
                "margin_2020": drow.margin_dr_2020, "margin_2016": drow.margin_dr_2016,
                "solar_mw": drow.solar_mw_all, "wind_mw": drow.wind_mw_all,
                "queue_mw": drow.queue_mw_all, "queue_n": drow.queue_n_all,
                "neighbor_share": drow.neighbor_severe_share_all}.items()},
            "primary_score": (float(p_scores.set_index("county_fips").score.get(f))
                              if p_scores is not None and f in set(p_scores.county_fips) else None),
            "peers": pr.to_dict(orient="records"),
            "peer_median_score": float(pr.score.median()),
            "peer_restricted": int(pr.has_severe.sum()),
            "neighbors": nbt.to_dict(orient="records"),
        }
    # National medians and percentiles of each trait for benchmark tables
    bench = {}
    for f, nm in SITES.items():
        drow = df.set_index("county_fips").loc[f]
        st_df = df[df.state == drow.state]
        b = {}
        for col in ["population", "pop_density_sqmi", "median_hh_income", "pct_bachelors_plus",
                    "margin_dr_2024", "solar_mw_all", "wind_mw_all", "queue_mw_all", "queue_n_all"]:
            pr = pd.DataFrame(site[nm]["peers"]).county_fips
            b[col] = {"value": float(drow[col]), "us_pct": midrank_pct(df[col].dropna(), drow[col]),
                      "state_pct": midrank_pct(st_df[col].dropna(), drow[col]),
                      "us_median": float(df[col].median()),
                      "peer_median": float(df[df.county_fips.isin(pr)][col].median())}
        bench[nm] = b
    json.dump({"snapshot": snap, "primary": prim, "sites": site, "bench": bench,
               "frame_n": int(len(df))}, open(OUT / "model_results.json", "w"), indent=1, default=float)
    print(json.dumps({k: snap[k] for k in snap if k not in ("deciles",)}, indent=1, default=float)[:3000])
    print("PRIMARY", json.dumps({k: prim.get(k) for k in ("verdict", "variables", "median_auc", "state_grouped_auc", "gate", "holdout_2026_auc", "holdout_2026_pos", "n", "positives")}, default=float))
    for nm, s in site.items():
        print(nm, round(s["score"], 3), round(s["lo"], 3), round(s["hi"], 3), "dec", s["decile"],
              "us", round(s["us_pct"]), "state", s["state_rank"], "/", s["state_n"], {k: round(v, 2) for k, v in s["lifts"].items()})


if __name__ == "__main__":
    main()
