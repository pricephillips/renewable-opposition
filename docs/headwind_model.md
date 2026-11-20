# Renewable Headwind Model

**Status:** November 20, 2026. Built and internal. Price named it on November 20, 2026. It is the renewables counterpart of the Data Center Headwind Model in data-centers (`county_policy_model.py`, shown to clients there as the Headwind Score). It has a county part and a project part. Build-Out goals R3 and R4.

The Renewables Record Score (`docs/county_record_score.md`) is a different thing and keeps its name. The record score is a rubric with hand-set weights that reads the county's own record. The Headwind Model is fitted to outcomes and gives a resemblance, never a probability or a cause.

## 1. The two parts

Each restriction carries a severity (a score from one to four: one for procedural friction, two for a material burden, three for a likely de facto ban, four for an explicit moratorium or ban). A severe restriction has severity 3 or 4. PROMOTE and HOLD are the two verdicts of the calibration gate (the shared check, `scripts/calibration_gate.py`, that a recalibrated score must pass before it is promoted); section 3 gives the rule.

| Part | Question | Unit | Script and registration | Result on 2026-11-20 |
|---|---|---|---|---|
| County part | How closely does a county resemble counties that enacted a severe restriction (severity 3 or 4)? | County | `scripts/county_restriction_model.py`, `config/county_model_registration.json` (2026-10-16) | Gate PROMOTE on the snapshot labels `has_severe` and `has_severity_4`; HOLD on the prospective label `new_severe_2022_2025` (`data/model/county_restriction_report.md`) |
| Project part | Does the county's record before a request set apart the requests that withdrew, beyond what the request and its market say? | Interconnection request | `scripts/headwind_history.py`, `scripts/headwind_model.py`, `config/headwind_model_registration.json` (2026-11-20) | HOLD on both labels (`data/model/headwind_report.md`) |

The county part is the same shape as the data center model: a county resemblance score fit on a snapshot of enacted rules, with the same method and calibration gate. The data center model has no project part.

## 2. The dated outcome history

The record score fit (`data/model/record_score_fit.md`) could not learn weights. It had 156 decided projects, and 91 of the 95 in a county with an instrument on their technology had at least one such instrument with no enactment date. The project part works on both gaps:

- **Outcomes.** LBNL Queued Up records every interconnection request, opposed or not, with its own request, withdrawal and operation dates. `scripts/headwind_history.py` keeps solar, wind and storage requests made 2010 to 2022 that are placed in a county: 19,131 requests. Of the 10,835 made 2010 to 2019, 6,742 have resolved (5,576 withdrew, 1,166 reached operation). The 163 contested projects with a confirmed outcome, a county and a year (81 blocked) are kept beside them as a check.
- **Rule dates.** A rule's year is the year of its enactment date, or else the first year in its date text, as the county labels use (`scripts/county_labels.py`). This places more rules than full dates alone do. A rule with no year is flagged, never counted as before a request.
- **County snapshots.** Each row holds the county as it stood on January 1 of the request year: local rules on the request's technology dated in earlier years, the share of neighbouring counties with a dated severe rule, the county's earlier requests and how many had withdrawn by the request date, the solar and wind MW in operation, and the census and 2016 election covariates.

## 3. Method

The method is the county part's method, which was ported from the data center model: L2 logistic regression (logistic regression with a penalty that shrinks the coefficients), 5 folds repeated 5 times (25 cross-validation fits, each scored on the fifth of the data it did not see), the sign-stability rule for variables (a county variable is kept only if its coefficient has the same sign in all 25 folds), a state-grouped check (folds split by state), cross-fitted recalibration and the shared gate (`scripts/calibration_gate.py`). The project part adds three checks:

1. **A request-only baseline** on the same folds: year, size, technology and grid region. The county variables count only for the AUC (the chance that a withdrawn request, picked at random, scores above one that did not withdraw; 0.5 is a coin toss) they add over it.
2. **An out-of-time test.** The model is fit on earlier requests and scored on later ones.
3. **Contested projects.** The county part of the score is applied to blocked and advanced contested projects.

The model is promoted only when the gate says PROMOTE and the county variables add at least 0.01 AUC, both in cross-validation and out of time.

## 4. Results

| Label | Requests | AUC, request only | AUC, with county | Out of time, gain | Contested check AUC | Verdict |
|---|---:|---:|---:|---:|---:|---|
| `withdrawn` (registered): resolved requests made 2010 to 2019 | 6,742 | 0.626 | 0.643 | 0.007 | 0.523 | HOLD |
| `withdrawn_3y` (added after the first fit): withdrew within three years, requests made 2010 to 2022 in CAISO, ISO-NE, MISO and PJM | 9,694 | 0.670 | 0.677 | 0.012 | 0.470 | HOLD |

On these results, the county's record adds little to what the request and its market already say about which requests withdraw. In cross-validation the county variables add 0.017 AUC on the registered label and 0.007 on the three-year label. Out of time they add 0.007 and 0.012. Each label falls below 0.01 on one of the two tests. On both labels the county part ranks blocked contested projects about as often below advanced ones as above them (AUC 0.523 and 0.470).

The largest county coefficient on each label comes from the county's own earlier requests: the share that withdrew on the registered label, and how many there were on the three-year label. Queued Up does not record why a request withdrew, so this variable does not separate local opposition from grid or market conditions. A severe local rule dated before the request does not keep a stable sign on either label. Siting standards (severity 1 or 2) dated before the request do not keep a stable sign on the registered label; on the three-year label they keep a negative sign (requests with them withdrew less often). Few requests had a severe rule before them: 134 of the 6,742 on the registered label. Of the 2,492 rows of `data/processed/restrictions.csv` with a year (one instrument can have several rows), 1,850 are dated 2020 or later, after every request in the registered label was made.

The `withdrawn_3y` label was added after the first fit, to reach requests made through 2022 without dropping the ones still active. The registration records it as a dated amendment, and the report marks it.

## 5. What would change the result

- **Rule adoption dates.** Every local rule with a year enters the snapshot. The 1,064 rows with no year (1,019 of them NREL rows) are the largest gap. The instrument-reader agent in the daily routine drafts `date_enacted_iso` when it reads a rule, so each verified rule can add a date.
- **State law dates.** `data/processed/state_policies.csv` has no enactment date column, so state siting law is not in the snapshot. The LegiScan intake (`scripts/fetch_legiscan.py`, with the `LEGISCAN_API_KEY` secret) and the state-law-reader agent give bill dates. A dated state policy field would let the snapshot include state preemption as of the request date.
- **A withdrawal reason.** Queued Up does not say why a request withdrew. Contested projects matched to their requests (`data/reference/queue_matches.csv`, 118 projects) are the only rows where opposition is known.
- **Time.** Requests made 2020 to 2022 resolve over the next few years. Of the dated rows, 589 are dated 2020 to 2022 and 642 before 2020, so more rules can fall before these requests than before the registered label's. The monthly refit (`model-inputs.yml`) picks them up from each new Queued Up edition.

## 6. Where it is used

Nowhere outside staff files yet. No page, county report, headline figure or client bundle reads `data/model/headwind_*`. Showing either part to a client is Price's decision, made with the report in hand (`docs/predictive_foundation_design.md`, section 6, decision 1). The client portal's refusal list in data-centers (`scripts/refused_columns.py`) already refuses the county restriction model.
