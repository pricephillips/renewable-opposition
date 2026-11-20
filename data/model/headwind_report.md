# Renewable Headwind Model: project part

Written by `scripts/headwind_model.py` under `config/headwind_model_registration.json` (registered 2026-11-20). Do not edit by hand. Internal, staff only. Read `docs/headwind_model.md` first.

**What it measures.** Among interconnection requests for solar, wind and storage, how far the county's record before the request (its local rules, its neighbours' rules, its own earlier requests and its attributes) sets the requests that withdrew apart from the others, beyond what the request itself says (year, size, technology, grid region). A withdrawal is not opposition: most have market or grid reasons. Associations only, never cause.

**Promotion rule.** The calibration gate says PROMOTE, and the county variables add at least 0.01 AUC over the request-only model, both in cross-validation and out of time. AUC is the chance that a withdrawn request, picked at random, scores above one that did not withdraw; 0.5 is a coin toss.

## Label: withdrawn, among resolved requests made 2010 to 2019 (registered, primary)

**Verdict: HOLD.** Requests: 6742 (5576 withdrew, 1166 reached operation).

| Measure | Request only | Request and county | Gain |
|---|---:|---:|---:|
| Cross-validated AUC (median of 25 folds) | 0.626 | 0.643 (p10 0.632, p90 0.655) | 0.017 |
| State-grouped AUC (5 folds by state) | 0.501 | 0.540 | 0.039 |
| Out of time: fit 2010 to 2016 (3656 requests), score 2017 to 2019 (3086) | 0.531 | 0.537 | 0.007 |

Calibration gate on the recalibrated score: PROMOTE. Brier skill 0.056, ECE 0.011. Regularization C = 1.0.

County variables kept (each keeps its sign on all 25 folds; standardized coefficients, positive means more often withdrew):

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| the county's earlier requests: share withdrawn (smoothed) | 0.217 | 0.182 | 0.251 |
| median household income (log) | -0.156 | -0.206 | -0.070 |
| share with a bachelor's degree | 0.093 | 0.042 | 0.126 |
| 2016 presidential margin (Republican minus Democratic) | 0.077 | 0.032 | 0.113 |
| share of neighbouring counties with a dated severe rule | 0.068 | 0.012 | 0.104 |
| solar and wind MW already operating (log) | -0.053 | -0.088 | -0.019 |

Dropped for changing sign across folds: a severe local rule (severity 3 or 4) on the technology, dated before the request; siting standards (severity 1 or 2) on the technology, dated before the request; a local rule on the technology with no year; the county's earlier requests: how many (log); population density (log).

| Local rule in the county before the request | Requests with it | Share withdrew, with it | Share without it |
|---|---:|---:|---:|
| a severe local rule (severity 3 or 4) on the technology, dated before the request | 134 | 0.851 | 0.827 |
| siting standards (severity 1 or 2) on the technology, dated before the request | 166 | 0.898 | 0.825 |
| a local rule on the technology with no year | 1136 | 0.871 | 0.818 |

Check on contested projects: the county part of this score, applied to 163 contested projects with a confirmed outcome (81 blocked), ranks blocked above advanced projects with AUC 0.523.

## Label: withdrawn within three years, requests made 2010 to 2022 in CAISO, ISO-NE, MISO and PJM (added after the first fit)

**Verdict: HOLD.** Requests: 9694 (4547 withdrew within three years, 5147 did not).

| Measure | Request only | Request and county | Gain |
|---|---:|---:|---:|
| Cross-validated AUC (median of 25 folds) | 0.670 | 0.677 (p10 0.664, p90 0.689) | 0.007 |
| State-grouped AUC (5 folds by state) | 0.647 | 0.655 | 0.008 |
| Out of time: fit 2010 to 2018 (4069 requests), score 2019 to 2022 (5625) | 0.547 | 0.559 | 0.012 |

Calibration gate on the recalibrated score: PROMOTE. Brier skill 0.087, ECE 0.029. Regularization C = 0.01.

County variables kept (each keeps its sign on all 25 folds; standardized coefficients, positive means more often withdrew within three years):

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| the county's earlier requests: how many (log) | 0.132 | 0.097 | 0.160 |
| 2016 presidential margin (Republican minus Democratic) | 0.118 | 0.095 | 0.139 |
| median household income (log) | -0.103 | -0.120 | -0.078 |
| solar and wind MW already operating (log) | -0.102 | -0.120 | -0.074 |
| siting standards (severity 1 or 2) on the technology, dated before the request | -0.070 | -0.089 | -0.051 |

Dropped for changing sign across folds: a severe local rule (severity 3 or 4) on the technology, dated before the request; a local rule on the technology with no year; share of neighbouring counties with a dated severe rule; the county's earlier requests: share withdrawn (smoothed); population density (log); share with a bachelor's degree.

| Local rule in the county before the request | Requests with it | Share withdrew within three years, with it | Share without it |
|---|---:|---:|---:|
| a severe local rule (severity 3 or 4) on the technology, dated before the request | 267 | 0.434 | 0.470 |
| siting standards (severity 1 or 2) on the technology, dated before the request | 484 | 0.335 | 0.476 |
| a local rule on the technology with no year | 1869 | 0.447 | 0.474 |

Check on contested projects: the county part of this score, applied to 163 contested projects with a confirmed outcome (81 blocked), ranks blocked above advanced projects with AUC 0.470.

## Limits

- Withdrawal is the outcome, and most withdrawals have market or grid reasons. The model cannot separate a withdrawal forced by local opposition from one forced by an interconnection cost.
- A county's record is only as complete as its examination: most counties have not been examined, so "no rule before the request" can mean no source looked.
- Many local rules have no year and cannot be placed before or after a request; they are flagged, not counted.
- The census covariates are 2020 to 2024 values for requests made 2010 to 2022.
- The registered label leaves out requests still active, so it leans toward requests that resolved quickly. The three-year label keeps them, but only in the four regions that date their withdrawals.
