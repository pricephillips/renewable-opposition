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
| logistic regression | 0.592, 0.534 | 0.592, 0.529 | 0.000, 0.005 | -0.005, -0.199 | HOLD |
| gradient-boosted trees | 0.642, 0.650 | 0.632, 0.709 | 0.010, -0.059 | 0.013, -0.055 | HOLD |
| neural net | 0.666, 0.591 | 0.611, 0.579 | 0.055, 0.012 | 0.068, -0.044 | HOLD |

## Label: withdrawn within three years, requests made 2010 to 2022 in CAISO, ISO-NE, MISO and PJM (added after the first fit)

**Best learner: gradient-boosted trees. Verdict: HOLD.** Requests: 9694.

| Holdout | Trained on | Scored |
|---|---:|---:|
| train through 2016, score 2017 to 2018 | 2716 | 1353 |
| train through 2018, score 2019 to 2022 | 4069 | 5625 |

| Learner | Holdout AUC, request and county | Request only | Gain from the county | Brier skill | Gate |
|---|---|---|---|---|---|
| logistic regression | 0.511, 0.546 | 0.514, 0.533 | -0.004, 0.013 | -0.036, 0.132 | HOLD |
| gradient-boosted trees | 0.542, 0.587 | 0.558, 0.553 | -0.016, 0.034 | -0.050, 0.069 | HOLD |
| neural net | 0.519, 0.579 | 0.522, 0.537 | -0.003, 0.041 | -0.018, 0.094 | HOLD |

Each cell lists the holdouts in the order of the first table.
