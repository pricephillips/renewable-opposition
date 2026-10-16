"""Quantitative fragments (ratings, appendix tables) for each county, from the
provisional model's output and the repository's county summary. Writes
quant_<key>.md fragments the case-study markdown includes by hand."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1] / "model"
REPO = Path(__file__).resolve().parents[4]
R = json.load(open(HERE / "model_results.json"))
snap = R["snapshot"]
scores = pd.read_csv(HERE / "scores_snapshot.csv", dtype={"county_fips": str})
cs = pd.read_csv(REPO / "data/processed/county_summary.csv", dtype={"county_fips": str})
cov = pd.read_csv(REPO / "data/reference/county_covariates.csv", dtype={"county_fips": str})
cs["records"] = cs.restrictions_renewables + cs.restrictions_multi_sector + cs.contested_projects
cs = cs.merge(cov[["county_fips", "population"]], on="county_fips", how="left")
cs["per100k"] = cs.records / cs.population * 1e5


def midrank(values, v):
    a = np.asarray(pd.Series(values).dropna())
    return 100 * ((a < v).sum() + 0.5 * (a == v).sum()) / len(a)


def ordinal(n):
    n = int(round(n))
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}^{suf}^"


def margin(m):
    return f"{'R' if m < 0 else 'D'}+{abs(m) * 100:.1f}"


NAMES = {"log_population": "Population", "log_income": "Median household income",
         "log1p_wind_mw": "Operating wind capacity", "neighbor_severe_share": "Neighbors with a severe restriction",
         "log1p_queue_mw": "Interconnection requests (MW)"}
TIER = {"log_population": 3, "log_income": 3, "log1p_wind_mw": 1, "neighbor_severe_share": 2,
        "log1p_queue_mw": 1}
DIRECTION = {k: ("Higher raises score" if v > 0 else "Higher lowers score") for k, v in snap["median_coef"].items()}

# Evidence status across all counties
n_all = len(cs)
verified = int((cs.restrictions_renewables_verified > 0).sum())
recorded = int((cs.coverage == "record").sum()) - verified
neg = int((cs.coverage == "negative_check").sum())
none = int((cs.coverage == "none").sum())

out = {}
for nm, s in R["sites"].items():
    f = s["fips"]
    row = cs[cs.county_fips == f].iloc[0]
    st = cs[cs.state == row.state]
    v = s["values"]
    b = R["bench"][nm]
    o = {}
    o["score"] = f"{s['score']:.2f}"
    o["range"] = f"{s['lo']:.2f} to {s['hi']:.2f}"
    o["decile"] = s["decile"]
    o["us_pct"] = round(s["us_pct"])
    o["state_pct"] = round(s["state_pct"])
    o["state_rank"] = f"{s['state_rank']} of {s['state_n']}"
    o["state_median"] = f"{s['state_median']:.2f}"
    o["state_top3"] = ", ".join(f"{t['county']} ({t['score']:.2f})" for t in s["state_top3"])
    o["pct_among_restricted"] = round(s["pct_among_restricted"])
    o["records"] = int(row.records)
    o["records_us_pct"] = round(midrank(cs.records, row.records))
    o["records_state_pct"] = round(midrank(st.records, row.records))
    o["per100k"] = f"{row.per100k:.1f}"
    o["per100k_us_pct"] = round(midrank(cs.per100k, row.per100k))
    o["per100k_state_pct"] = round(midrank(st.per100k, row.per100k))
    o["peer_median"] = f"{s['peer_median_score']:.2f}"
    o["peer_restricted"] = s["peer_restricted"]
    o["peers"] = ", ".join(f"{p['county']} ({p['state']})" for p in s["peers"])
    o["peer_top"] = max(s["peers"], key=lambda p: p["score"])
    o["lift_total"] = s["lift_total"]
    o["lifts"] = s["lifts"]
    o["primary_score"] = s["primary_score"]
    peer_f = [p["county_fips"] for p in s["peers"]]
    peer_cs = cs[cs.county_fips.isin(peer_f)]
    peer_scores = scores[scores.county_fips.isin(peer_f)]

    # Ratings table rows are written by hand in each case study; the appendix tables here.
    t1 = ["| **Decile** | **Score range** | **Counties** | **Share with a severe restriction** |", "|---|---|---|---|"]
    for dd in snap["deciles"]:
        lab = f"{dd['decile']}" + (" (lowest)" if dd["decile"] == 1 else " (highest)" if dd["decile"] == 10 else "")
        cells = [lab, f"{dd['lo']:.3f} to {dd['hi']:.3f}", f"{dd['n']}", f"{dd['share'] * 100:.1f}%"]
        if dd["decile"] == s["decile"]:
            cells[0] = f"{cells[0]}: {nm.split()[0]}"
            cells = [f"**{c}**" for c in cells]
        t1.append("| " + " | ".join(cells) + " |")
    o["table1"] = "\n".join(t1)

    def brow(label, val, key, peer_val):
        return f"| {label} | {val} | {round(b[key]['us_pct'])} | {round(b[key]['state_pct'])} | {peer_val} |"
    t2 = ["| **Measure** | **" + nm.split()[0] + "** | **U.S. percentile** | **" + row.state + " percentile** | **Peer median** |",
          "|---|---|---|---|---|",
          f"| Restriction score | {s['score']:.2f} | {o['us_pct']} | {o['state_pct']} | {s['peer_median_score']:.2f} |",
          f"| Opposition records | {o['records']} | {o['records_us_pct']} | {o['records_state_pct']} | {peer_cs.records.median():.0f} |",
          f"| Records per 100,000 residents | {o['per100k']} | {o['per100k_us_pct']} | {o['per100k_state_pct']} | {peer_cs.per100k.median():.1f} |",
          brow("Interconnection requests, MW (all years)", f"{v['queue_mw']:,.0f}", "queue_mw_all", f"{b['queue_mw_all']['peer_median']:,.0f}"),
          brow("Operating solar, MW", f"{v['solar_mw']:,.0f}", "solar_mw_all", f"{b['solar_mw_all']['peer_median']:,.0f}"),
          brow("Operating wind, MW", f"{v['wind_mw']:,.0f}", "wind_mw_all", f"{b['wind_mw_all']['peer_median']:,.0f}"),
          brow("Population (model input)", f"{v['population']:,.0f}", "population", f"{b['population']['peer_median']:,.0f}"),
          brow("Residents per square mile", f"{v['density']:,.0f}", "pop_density_sqmi", f"{b['pop_density_sqmi']['peer_median']:,.0f}"),
          brow("Median household income", f"${v['income']:,.0f}", "median_hh_income", f"${b['median_hh_income']['peer_median']:,.0f}"),
          brow("Bachelor's degree or higher", f"{v['bachelors']:.1f}%", "pct_bachelors_plus", f"{b['pct_bachelors_plus']['peer_median']:.1f}%"),
          brow("2024 presidential margin", margin(v["margin_2024"]), "margin_dr_2024", margin(b["margin_dr_2024"]["peer_median"]))]
    o["table2"] = "\n".join(t2)

    # Table 3: contributions
    tot_abs = sum(abs(x) for x in s["lifts"].values())
    vals = {"log_population": (f"{v['population']:,.0f}", f"{np.exp(snap['frame_means']['log_population']):,.0f}"),
            "log_income": (f"${v['income']:,.0f}", f"${np.exp(snap['frame_means']['log_income']):,.0f}"),
            "log1p_wind_mw": (f"{v['wind_mw']:,.0f}", f"{np.expm1(snap['frame_means']['log1p_wind_mw']):,.1f}"),
            "neighbor_severe_share": (f"{v['neighbor_share'] * 100:.0f}%", f"{snap['frame_means']['neighbor_severe_share'] * 100:.0f}%"),
            "log1p_queue_mw": (f"{v['queue_mw']:,.0f}", f"{np.expm1(snap['frame_means']['log1p_queue_mw']):,.0f}")}
    t3 = ["| **County trait** | **" + nm.split()[0] + " (U.S. average)** | **Model direction** | **Trust tier** | **Lift (log-odds)** | **Share of movement** |",
          "|---|---|---|---|---|---|"]
    for k, lift in sorted(s["lifts"].items(), key=lambda kv: -abs(kv[1])):
        share = abs(lift) / tot_abs * 100 if tot_abs else 0
        t3.append(f"| {NAMES[k]} | {vals[k][0]} ({vals[k][1]}) | {DIRECTION[k]} | {TIER[k]} | {lift:+.2f} | "
                  f"{'under 1' if share < 1 else round(share)}% |")
    o["table3"] = "\n".join(t3)

    # Table 4: neighbors
    t4 = ["| **Neighboring county** | **Restriction score** | **Severe restriction on record** | **Opposition records** | **Interconnection requests, MW** | **Population** |",
          "|---|---|---|---|---|---|"]
    for n in s["neighbors"]:
        rr = cs[cs.county_fips == n["county_fips"]].iloc[0]
        t4.append(f"| {n['county']}, {n['state']} | {n['score']:.2f} | {'yes' if n['has_severe'] else 'no'} | "
                  f"{int(rr.records)} | {n['queue_mw_all']:,.0f} | {n['population']:,} |")
    o["table4"] = "\n".join(t4)

    # Table 5: evidence status
    o["table5"] = "\n".join([
        "| **Status** | **Meaning** | **U.S. counties** |", "|---|---|---|",
        f"| Verified | At least one restriction checked against the instrument itself or the minutes that adopted it | {verified:,} ({verified / n_all * 100:.1f}%) |",
        f"| Recorded | Restrictions or contested projects on record from news, trackers or compiled databases, none yet read against the instrument | {recorded:,} ({recorded / n_all * 100:.1f}%) |",
        f"| Checked, none found | A reviewed search of the county's codes, minutes and news found no restriction (graded A to C by independence of sources) | {neg} ({neg / n_all * 100:.1f}%) |",
        f"| Unexamined | No record and no documented check; absence of a record is not evidence of absence | {none:,} ({none / n_all * 100:.1f}%) |"])
    o["evidence_counts"] = dict(verified=verified, recorded=recorded, neg=neg, none=none, n=n_all)
    out[nm] = o

meta = {"n": snap["n"], "positives": snap["positives"], "base_rate": snap["base_rate"],
        "auc": snap["median_auc"], "auc_state": snap["state_grouped_auc"], "ece": snap["gate"]["ece"],
        "brier": snap["gate"]["brier"], "brier0": snap["gate"]["brier_baseline"], "bss": snap["gate"]["brier_skill"],
        "slope": snap["calibration_slope"], "C": snap["C"], "vars": snap["variables"],
        "median_pos": snap["median_pos"], "median_neg": snap["median_neg"],
        "primary": {k: R["primary"].get(k) for k in ("verdict", "median_auc", "state_grouped_auc", "holdout_2026_auc",
                                                      "holdout_2026_pos", "holdout_2026_n", "n", "positives")},
        "primary_bss": R["primary"]["gate"]["brier_skill"]}
json.dump({"sites": {k: {kk: vv for kk, vv in v.items()} for k, v in out.items()}, "meta": meta},
          open(HERE / "quant.json", "w"), indent=1, default=str)
for nm, o in out.items():
    key = nm.split()[0].lower()
    with open(HERE / f"quant_{key}.md", "w") as fh:
        for k in ("table1", "table2", "table3", "table4", "table5"):
            fh.write(f"<!-- {k} -->\n{o[k]}\n\n")
        fh.write("<!-- facts -->\n" + json.dumps({k: v for k, v in o.items() if not k.startswith('table')}, indent=1, default=str))
print(json.dumps(meta, indent=1, default=str))
