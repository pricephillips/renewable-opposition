# Renewable Headwind Model

**Status:** November 20, 2026. Built and internal. Price named it on November 20, 2026. It is the renewables counterpart of the Data Center Headwind Model in data-centers (`county_policy_model.py`, shown to clients there as the Headwind Score). It has a county part and a project part. The county part's score is the Renewable Headwind Score (Headwind score for short). It replaces the older names "predictive score", "predictive model" and "county restriction model" (Price, 2026-11-25); file names such as `scripts/county_restriction_model.py` keep their old names. Build-Out goals R3 and R4.

The Renewables Record Score (`docs/county_record_score.md`) is a different thing and keeps its name. The record score is a rubric with hand-set weights that reads the county's own record. The Headwind Model is fitted to outcomes and gives a resemblance, never a probability or a cause.

## 1. The two parts

Each restriction carries a severity (a score from one to four: one for procedural friction, two for a material burden, three for a likely de facto ban, four for an explicit moratorium or ban). A severe restriction has severity 3 or 4. PROMOTE and HOLD are the two verdicts of the calibration gate (the shared check, `scripts/calibration_gate.py`, that a recalibrated score must pass before it is promoted); section 3 gives the rule.

| Part | Question | Unit | Script and registration | Result on 2026-11-20 |
|---|---|---|---|---|
| County part | How closely does a county resemble counties that enacted a severe restriction (severity 3 or 4)? | County | `scripts/county_restriction_model.py`, `config/county_model_registration.json` (2026-10-16) | Gate PROMOTE on the snapshot labels `has_severe` and `has_severity_4`; PROMOTE on the prospective label `new_severe_2022_2025` since the refits of 2026-11-20 and 2026-11-21 (`data/model/county_restriction_report.md`) |
| Project part | Does the county's record before a request set apart the requests that withdrew, beyond what the request and its market say? | Interconnection request | `scripts/headwind_history.py`, `scripts/headwind_model.py`, `config/headwind_model_registration.json` (2026-11-20) | PROMOTE on the registered label `withdrawn` (the registered logistic fit); HOLD on the three-year label `withdrawn_3y` and in the learner race (`data/model/headwind_report.md`, `data/model/headwind_compare.md`) |

The county part is the same shape as the data center model: a county resemblance score fit on a snapshot of enacted rules, with the same method and calibration gate. The data center model has no project part.

## 2. The dated outcome history

The record score fit (`data/model/record_score_fit.md`) could not learn weights. It had 156 decided projects, and 91 of the 95 in a county with an instrument on their technology had at least one such instrument with no enactment date. The project part works on both gaps:

- **Outcomes.** LBNL Queued Up records every interconnection request, opposed or not, with its own request, withdrawal and operation dates. `scripts/headwind_history.py` keeps solar, wind and storage requests made 2010 to 2022 that are placed in a county: 19,131 requests. Of the 10,835 made 2010 to 2019, 6,742 have resolved (5,576 withdrew, 1,166 reached operation). The 163 contested projects with a confirmed outcome, a county and a year (81 blocked) are kept beside them as a check.
- **Rule dates.** A rule's year is the year of its enactment date, or else the first year in its date text, as the county labels use (`scripts/county_labels.py`). This places more rules than full dates alone do. A rule with no year is flagged, never counted as before a request.
- **County snapshots.** Each row holds the county as it stood on January 1 of the request year: local rules on the request's technology dated in earlier years, the share of neighbouring counties with a dated severe rule, the county's earlier requests and how many had withdrawn by the request date, the solar and wind MW in operation, and the census covariates.
- **Time-matched inputs (added November 20, 2026).** The presidential margin (Democratic minus Republican) is now the one in the last election before the request year: `scripts/fetch_county_covariates.py` writes the 2000 to 2024 margins from the MEDSL file (the MIT Election Data and Science Lab's county returns) already in the repository. Four inputs are added, each dated before the request: the contested renewables projects in the county with an earlier year, the data center opposition events in the county with an earlier year (`data/reference/data_center_events.csv`), the smoothed share of earlier requests that withdrew in the state, and the same share in the neighbouring counties. The margin was first registered as "Republican minus Democratic" while the column read was Democratic minus Republican, so the first reports read its sign backwards. The registration records the correction.

## 3. Method

The method is the county part's method, which was ported from the data center model: L2 logistic regression (logistic regression with a penalty that shrinks the coefficients), 5 folds repeated 5 times (25 cross-validation fits, each scored on the fifth of the data it did not see), the sign-stability rule for variables (a county variable is kept only if its coefficient has the same sign in all 25 folds), a state-grouped check (folds split by state), cross-fitted recalibration and the shared gate (`scripts/calibration_gate.py`). The project part adds three checks:

1. **A request-only baseline** on the same folds: year, size, technology and grid region. The county variables count only for the AUC (the chance that a withdrawn request, picked at random, scores above one that did not withdraw; 0.5 is a coin toss) they add over it.
2. **An out-of-time test.** The model is fit on earlier requests and scored on later ones.
3. **Contested projects.** The county part of the score is applied to blocked and advanced contested projects.

The model is promoted only when the gate says PROMOTE and the county variables add at least 0.01 AUC, both in cross-validation and out of time.

## 4. Results

| Label | Requests | AUC, request only | AUC, with county | Out of time, gain | Contested check AUC | Verdict |
|---|---:|---:|---:|---:|---:|---|
| `withdrawn` (registered): resolved requests made 2010 to 2019 | 6,742 | 0.627 | 0.656 | 0.023 | 0.528 | PROMOTE |
| `withdrawn_3y` (added after the first fit): withdrew within three years, requests made 2010 to 2022 in CAISO, ISO-NE, MISO and PJM | 9,694 | 0.670 | 0.678 | 0.010 (just under 0.01 before rounding) | 0.471 | HOLD |

With the time-matched inputs, the registered logistic fit now passes its promotion rule: the gate says PROMOTE, and the county inputs add 0.030 AUC in cross-validation and 0.023 out of time. Without them, the county inputs added 0.017 and 0.007. The three-year label is still HOLD.

On the registered label, the two largest county coefficients come from queue history, not from local rules: the share of earlier requests that withdrew in the state (0.235) and in the neighbouring counties (0.175). The county's own share is 0.099, smaller than median household income (-0.116). Queued Up does not record why a request withdrew, so these inputs do not separate local opposition from grid or market conditions. A severe local rule dated before the request keeps a small negative sign (-0.017). Siting standards change sign across folds and are dropped. The contested project and data center inputs also change sign and are dropped, on both labels. On the two labels, the county part still ranks blocked contested projects about as often below advanced ones as above them (AUC 0.528 and 0.471). Few requests had a severe rule before them: 134 of the 6,742 on the registered label. Of the 2,492 rows of `data/processed/restrictions.csv` with a year (one instrument can have several rows), 1,850 are dated 2020 or later, after every request in the registered label was made.

The pass comes after three amendments made once the first fit was seen (the three-year label, the learner race and these inputs). Each one is dated in the registration, but a pass reached after looking is weaker evidence than a pass on the first registered fit.

The `withdrawn_3y` label was added after the first fit, to reach requests made through 2022 without dropping the ones still active. The registration records it as a dated amendment, and the report marks it.

### Which learner wins

On November 20, 2026 Price asked for the strongest predictor the data supports, ideally a neural net. `scripts/headwind_compare.py` races three learners on the same rows: logistic regression, gradient-boosted trees and a small neural net (two hidden layers, averaged over five seeds). Each one is trained only on earlier requests and scored on later ones, and each is fit with and without the county snapshot. A learner ships only when it has the best mean holdout AUC, passes the calibration gate on the holdout requests, and gains at least 0.01 AUC from the county snapshot on every holdout (`data/model/headwind_compare.md`).

| Label | Learner | Holdout AUC, request and county | Gain from the county | Gate |
|---|---|---|---|---|
| `withdrawn` | logistic regression | 0.599, 0.543 | 0.008, 0.014 | HOLD |
| `withdrawn` | gradient-boosted trees | 0.618, 0.628 | -0.014, -0.081 | HOLD |
| `withdrawn` | neural net | 0.620, 0.580 | 0.009, 0.001 | HOLD |
| `withdrawn_3y` | logistic regression | 0.511, 0.540 | -0.003, 0.008 | HOLD |
| `withdrawn_3y` | gradient-boosted trees | 0.532, 0.582 | -0.026, 0.029 | HOLD |
| `withdrawn_3y` | neural net | 0.515, 0.578 | -0.007, 0.041 | HOLD |

Each cell lists the two holdouts, the earlier one first. Gradient-boosted trees have the best mean holdout AUC on both labels, so they are the best learner, but none of the three ships. The trees and the neural net rank requests better than the logistic model does. However, the county snapshot's gain changes sign from one holdout to the next, and on the registered label's later holdout the trees do better on the request alone (0.709) than with the county added (0.628). The race fits every county input with a fixed penalty and without the sign-stability rule, so it does not confirm the registered fit's pass. No learner passes the calibration gate. On the pooled holdout requests, each learner's probabilities are less accurate than the holdout's own withdrawal share used as a constant (its Brier skill, the gain in accuracy over that constant, is below zero). One reason is that the share of requests that withdraw changes from one period to the next, so a model trained on earlier years is off for later ones. A neural net needs far more rows with a stable outcome than these labels hold, and it does not beat the trees here.

### Wide search over variables and combinations

On November 20, 2026 Price asked whether the model should test hundreds of variables against each other to find the combination that works best. `scripts/headwind_search.py` does this (`data/model/headwind_search.md`). It pools every county variable: the registered core and every configured input, registered or not, 24 in all. Two searches run over the pool. A sparse logistic regression (lasso) is given 396 candidates: the 24 variables, their squares, every pair multiplied together, and each variable times each technology. Its penalty keeps only the candidates that help. Gradient-boosted trees are given the 24 variables and find combinations and thresholds on their own.

Four guards stop a lucky combination from passing:

1. **Forward in time.** Each search trains on requests made up to a year and is scored on requests made later.
2. **Nested choice.** Each search picks its penalty and its variables on the last two training years only. The later years it is scored on never touch a choice.
3. **The same learner without the county.** The county pool counts only for the AUC it adds over the same learner given the request alone.
4. **Shuffled data.** Each search is run again 99 times with the county rows shuffled, so the variables keep their joint pattern but lose any link to the outcome. The real search must beat nearly all of these runs: p must be 0.0125 or less (0.05 divided by the four searches run).

A search holds up only if it adds at least 0.01 AUC on average, adds something in every later period and passes the shuffle test.

| Label | Search | Gain, earlier then later period | p | Holds up |
|---|---|---|---:|---|
| `withdrawn` | sparse logistic | 0.041, 0.080 | 0.01 | yes |
| `withdrawn` | boosted trees | -0.020, -0.103 | 0.36 | no |
| `withdrawn_3y` | sparse logistic | -0.009, 0.030 | 0.16 | no |
| `withdrawn_3y` | boosted trees | -0.025, 0.036 | 0.01 | no (loses in the earlier period) |

One combination holds up, and it is small. Of the 396 candidates, the sparse logistic search on the registered label keeps the same two in both later periods: the share of the state's earlier requests that withdrew, and that share multiplied by the county's own share. The two together mean a request withdrew more often where both its state and its county had a record of withdrawals. None of the new economic inputs, no local rule variable and no other pair is kept in both periods. The trees do worse with the county pool than without it on the registered label. The gain also partly reflects how weak the request-only lasso is in later years (AUC 0.513 for requests made 2017 to 2019), so it is larger than the gain the registered model shows.

The search does not change the registered model. It confirms what the registered fit found: the county signal that survives a wide, guarded search is queue withdrawal history, which mixes grid cost with local opposition. A source that measures grid cost directly would be needed to separate them.

### County part refit with yearly inputs, a state share and local governments

On November 20 and 21, 2026 the county part's variable pool grew by eleven variables (registration amendments of those dates). One is `state_severe_share`, the share of the other counties in the same state with a severe rule dated before 2022. The county itself is left out. The other ten are the plug-in inputs of `config/headwind_inputs.json` (section 6), read for 2021 on the prospective label and for their latest year on the snapshot labels. All ten configured inputs entered the pool, so none was picked by hand. The selection rule, the folds and the gate did not change. The state share was added because the residual's Moran's I was 0.10, which means the errors clustered by region. The yearly inputs are the first county measures that can be read as of 2021 instead of from the 2020 to 2024 census release.

The tenth input, `in_local_govts`, came from a screen of the data center model's county variables. About 150 of them (data-centers `data/county_features_expanded.csv`) were each added on their own to the refit model. Four kept their sign on every fold, added at least 0.01 AUC in both runs and added some AUC on 2026: cropland share, local governments, incorporated places and the non-Hispanic white share. In ten screens of the same variables with their values shuffled across counties, the best variable gained at most 0.005, so gains this size are unlikely to come from the width of the screen alone. Local governments (incorporated places and town or township governments, counted by `scripts/build_headwind_local_govts.py` from `data/census_governments_2024.csv`) is built here. Incorporated places is part of the same count. Cropland share waits for a USDA NASS key (the data center model reads it through one). The white share is left out, because a score sold to clients should not rank counties by race.

| Measure, prospective label `new_severe_2022_2025` | Facilities run, before | after | Queue run, before | after |
|---|---:|---:|---:|---:|
| Cross-validated AUC (median of 25 folds) | 0.680 | 0.753 | 0.711 | 0.760 |
| State-grouped AUC | 0.648 | 0.730 | 0.683 | 0.745 |
| Brier skill | 0.036 | 0.068 | 0.047 | 0.082 |
| Gate | HOLD | PROMOTE | HOLD | PROMOTE |
| Held-back 2026 AUC (53 enactments) | 0.657 | 0.724 | 0.623 | 0.702 |
| NREL-only AUC | 0.690 | 0.769 | 0.720 | 0.750 |
| Moran's I on the residual | 0.103 | 0.071 | 0.098 | 0.066 |

The selected models keep the state share and nine of the ten inputs (facilities run) or eight (queue run). The largest coefficient is the county poverty rate, negative: counties with less poverty more often enacted a severe rule. Local governments is next, positive: counties with more governments that can enact a rule more often had one. The state share and county employment are positive. Five-year population growth and the utilities share of establishments are negative. These are associations, not causes. The 2026 check is not wholly unseen: exploratory runs printed it beside the cross-validated result before the pool was settled. 2026 is also a partial year. On the NREL-only labels three to five of the selected variables change sign, so the all-source result still partly reflects where sources looked.

Two project part changes were tested and left out. The combination the wide search kept (the county's earlier withdrawal share times the state's) lowered the registered model's out-of-time gain from 0.023 to 0.009 and turned its verdict to HOLD. Queue congestion built from Queued Up (MW requested in the county, state or grid region in the three years before a request), a stand-in for grid cost, added at most 0.003 AUC out of time on the registered label and lost AUC on the three-year label. No openly licensed source of interconnection cost exists yet (section 6). Local governments adds nothing to the project part (its lift table).

## 5. What would change the result

- **Census values as of the request.** The census inputs are 2020 to 2024 values. Earlier American Community Survey five-year releases (for example 2015 to 2019) would match requests made in the 2010s. `scripts/fetch_county_covariates.py` reads only the 2020 to 2024 release, so using an earlier release needs a change to that script.
- **Rule adoption dates.** Every local rule with a year enters the snapshot. The 1,064 rows with no year (1,019 of them NREL rows) are the largest gap. The instrument-reader agent in the daily routine drafts `date_enacted_iso` when it reads a rule, so each verified rule can add a date.
- **State law dates.** `data/processed/state_policies.csv` has no enactment date column, so state siting law is not in the snapshot. The LegiScan intake (`scripts/fetch_legiscan.py`, with the `LEGISCAN_API_KEY` secret) and the state-law-reader agent give bill dates. A dated state policy field would let the snapshot include state preemption as of the request date.
- **A withdrawal reason.** Queued Up does not say why a request withdrew. Contested projects matched to their requests (`data/reference/queue_matches.csv`, 118 projects) are the only rows where opposition is known.
- **Time.** Requests made 2020 to 2022 resolve over the next few years. Of the dated rows, 589 are dated 2020 to 2022 and 642 before 2020, so more rules can fall before these requests than before the registered label's. The monthly refit (`model-inputs.yml`) picks them up from each new Queued Up edition.

## 6. Adding an input

New inputs plug in without a change to the model code. `config/headwind_inputs.json` holds two lists:

- `wanted`: the inputs the model lacks, in priority order (grid cost, land use, the local economy by year, dated state policy, local attention, wildlife constraints). The shared Gov Data Scout and Repo Scout in data-centers read this list in their renewables lane and look for a source that fills the first open item.
- `inputs`: data files the model reads. Each one is a county or state file with an optional year column. `scripts/headwind_inputs.py` adds it to every request's snapshot as `in_<id>`. A dated file is time-matched: a request made in a year reads the latest value from an earlier year.

An input reaches the fit only when the registration lists it and records an amendment that names it, so a new data file never changes the model by itself. Every configured input is still loaded into the history, and the report measures each one's lift on its own: the model selected from the core county variables, then the same model with that one input added, on the same folds and the same out-of-time split. An input is registered only when it keeps its sign on all 25 folds and adds at least 0.01 AUC, both in cross-validation and out of time. Once Price ticks a scout's pick, the `renewables-integrator` agent builds it by its "Headwind Model input" path: a fetcher, the config entry and a layer declaration. The monthly refit (`model-inputs.yml`) then refetches it and reports its lift.

### Inputs built so far

| Input | Source | Years | Lift on `withdrawn` (cross-validated, out of time) | Registered |
|---|---|---|---|---|
| `in_income_pc`: per capita personal income (log) | BEA CAINC1 (`scripts/fetch_headwind_bea_income.py`) | yearly, 2000 to 2024 | -0.001, -0.000 | no |
| `in_pop_growth_5y`: population change over five years | BEA CAINC1 | yearly, 2000 to 2024 | -0.001, -0.000 | no |
| `in_hpi_growth_5y`: house price change over five years | FHFA county house price index (`scripts/fetch_headwind_fhfa_hpi.py`) | yearly, 2000 to 2024 | -0.001, 0.003 | no |
| `in_poverty_pct`: poverty rate | Census SAIPE (`scripts/fetch_headwind_saipe.py`) | yearly, 2005 to 2023 | 0.000, -0.000 | no |
| `in_median_hh_income_yr`: median household income (log) | Census SAIPE | yearly, 2005 to 2023 | 0.001, 0.000 | no |
| `in_employment`: employment (log) | County Business Patterns (`scripts/fetch_headwind_cbp.py`) | yearly, 2007 to 2022 | -0.002, -0.001 | no |
| `in_construction_est_share`: share of establishments in construction | County Business Patterns | yearly, 2007 to 2022 | -0.000, 0.000 | no |
| `in_utilities_est_share`: share of establishments in utilities | County Business Patterns | yearly, 2007 to 2022 | -0.000, -0.000 | no |
| `in_ag_support_est_share`: share of establishments in agriculture support | County Business Patterns | yearly, 2007 to 2022 | 0.001, 0.001 | no |
| `in_local_govts`: local governments in the county (log) | Census Gazetteer 2024, via `data/census_governments_2024.csv` (`scripts/build_headwind_local_govts.py`) | static, 2024 | 0.001, -0.000 | no |

The nine inputs were built on November 20, 2026, and none adds lift on its own or in the wide search (section 4). The model already has the 2020 to 2024 census income and the county's queue history. Yearly income, poverty, population growth, house prices and the mix of local businesses add nothing beyond them. The sources most likely to add lift are still grid cost and rule adoption dates, at the top of the wanted list. The project part has no registered inputs. The county part reads all ten (section 4, county part refit), and there they add lift.

### How each source joins

- **Join key.** County files join on the five-digit county FIPS code, and state files on the state's postal code. BEA folds 23 Virginia independent cities into a neighbouring county; the fetcher writes each combined row under every county it names. Connecticut stays on its eight old counties.
- **Time lag.** A request made in year Y reads the latest row from year Y minus `lag_years` or earlier. The default is 1, so nothing from the request's own year enters. A source that is published late, such as the Census of Agriculture (released about two years after its reference year), should set `lag_years` to 2.
- **Form.** An index with a different base in each county (the FHFA index) enters as a change over time, never as a level. Dollar amounts enter as logs.

### Build order for the other sources

The first pass (November 20, 2026) found ten leads, now on the wanted list. A second pass the same day found ten more. They are built in this order:

1. **Keyless, yearly, county (next).** Census Small Area Income and Poverty Estimates and County Business Patterns are built. Next: IRS county-to-county migration (yearly inflow and outflow, from 2011); USDA NASS Census of Agriculture (land value per acre and cropland share, 2007 to 2022; the Gov Data Scout found a bulk file with no key); Census of Governments (how many townships and municipalities share land use authority in the county, 2007 to 2022); USDA ERS rural-urban continuum codes (2003, 2013 and 2023).
2. **Blocked from a cloud session, to be fetched by the workflow.** BLS county unemployment (the site refuses requests without a contact address in the User-Agent); LBNL state renewable portfolio standard targets (the site refuses requests from the session).
3. **Waiting on a license.** LBNL interconnection cost studies. The Gov Data Scout found no license and deferred it until LBNL answers.
4. **Must be built from other records.** State siting law effective dates (LegiScan); county rule adoption dates (Lerner's wind ordinance data and the NREL ordinance editions); wind opposition coded from news (Stokes and others, 2023); protected land share (a PAD-US overlay); EIA-861 retail electricity prices by state; FEMA disaster declarations and the FEMA National Risk Index.

## 7. Where it is used

The county part reaches one place: the staff-only renewables pilot in the client portal. Price asked for it on November 26, 2026. There the score appears as a band, never a number: lower (deciles 1 to 3 of U.S. counties), typical (4 to 7) or higher (8 to 10), set in `config/headwind_band.json`. `scripts/county_record_score.py` writes the band as `headwind_band` in `data/model/county_record_scores.csv`, the staff file the pilot already reads. No public page, county report, headline figure or client bundle reads the score itself or `data/model/headwind_*`. Showing either part to a client outside Hawthorn is Price's decision, made with the report in hand. `docs/headwind_strategy.md` sets the targets and stages for that decision (`docs/predictive_foundation_design.md`, section 6, decision 1). The client portal's refusal list in data-centers (`scripts/refused_columns.py`) already refuses the county part's scores.
