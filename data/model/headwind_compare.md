# Renewable Headwind Model: which learner wins

Written by `scripts/headwind_compare.py`. Do not edit by hand. Internal, staff only. Read `docs/headwind_model.md` first.

Three learners race on the same requests and the same forward-in-time holdouts: each is trained on requests made up to a year and scored on the requests made after it. AUC is the chance that a request that withdrew, picked at random, scores above one that did not; 0.5 is a coin toss. The gain is what the county snapshot adds over the same learner given the request alone (year, size, technology, grid region).

A learner ships only when it has the best mean holdout AUC, passes the calibration gate on the holdout requests, and gains at least 0.01 AUC from the county snapshot on every holdout.

## Label: withdrawn, among resolved requests made 2010 to 2019 (registered, primary)

**Best learner: gradient-boosted trees. Verdict: HOLD.** Requests: 6742.

| Holdout | Trained on | Scored |
|---|---:|---:|
| train through 2014, score 2015 to 2016 | 2134 | 1522 |
| train through 2016, score 2017 to 2019 | 3656 | 3086 |

| Learner | Holdout AUC, request and county | Request only | Gain from the county | Brier skill | Gate |
|---|---|---|---|---|---|
| logistic regression | 0.599, 0.543 | 0.592, 0.529 | 0.008, 0.014 | -0.001, -0.235 | HOLD |
| gradient-boosted trees | 0.618, 0.628 | 0.632, 0.709 | -0.014, -0.081 | -0.012, -0.057 | HOLD |
| neural net | 0.620, 0.580 | 0.611, 0.579 | 0.009, 0.001 | 0.047, -0.058 | HOLD |

## Label: withdrawn within three years, requests made 2010 to 2022 in CAISO, ISO-NE, MISO and PJM (added after the first fit)

**Best learner: gradient-boosted trees. Verdict: HOLD.** Requests: 9694.

| Holdout | Trained on | Scored |
|---|---:|---:|
| train through 2016, score 2017 to 2018 | 2716 | 1353 |
| train through 2018, score 2019 to 2022 | 4069 | 5625 |

| Learner | Holdout AUC, request and county | Request only | Gain from the county | Brier skill | Gate |
|---|---|---|---|---|---|
| logistic regression | 0.511, 0.540 | 0.514, 0.533 | -0.003, 0.008 | -0.036, 0.131 | HOLD |
| gradient-boosted trees | 0.532, 0.582 | 0.558, 0.553 | -0.026, 0.029 | -0.066, 0.057 | HOLD |
| neural net | 0.515, 0.578 | 0.522, 0.537 | -0.007, 0.041 | -0.015, 0.123 | HOLD |

Each cell lists the holdouts in the order of the first table.
