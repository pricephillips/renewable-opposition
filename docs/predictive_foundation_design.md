# Predictive foundation: design

**Status:** 2026-10-15. Price approved the plan and its four decisions on 2026-10-15 (section 6). Steps 1 and 3 are built: `scripts/fetch_county_covariates.py`, `scripts/fetch_queued_up.py` and `scripts/queue_matches.py`, run monthly by `model-inputs.yml`. Step 2 is being built. This plan covers the first three steps toward forward-looking models in this repo: county covariates, a county restriction model, and a universe of proposed projects from LBNL Queued Up. Project-level models stay out of scope (section 7).

`national_database_design.md` (section 2) lists "scores or predictions" as a non-goal, and `pipeline_comparison.md` ("Deliberately not adopted") holds predictive models back "until there is a decided-project universe with dates". This plan does not change the dashboard. It builds internal models and a project universe, and nothing it produces reaches a page until Price decides that separately (section 6, decision 1).

---

## 1. Why now, and why these three steps

The pipeline's ingestion and checks are mature: phases 1 to 5 of the national database are built, the weekly intake is live, and every record carries its evidence level. What it lacks for prediction is what data-center-map needed before its models worked:

| data-center-map model | Needed | This repo today |
|---|---|---|
| County enacted-restriction model (`county_policy_model.py`; the only model shown on its public map) | Every county labelled, plus county covariates | Labels: 3,639 restrictions, 99.9% placed in counties through `county_fips_all`. Covariates: none |
| Project outcome and landmark models | Decided projects with announcement and decision dates | 125 confirmed decided projects (70 blocked, 55 advanced); 568 of 575 projects dated only to a year |
| Emergence model, control groups | Projects with no recorded opposition | None. `data/reference/facilities.csv` is 88% operating plants |

So the cheapest model with the strongest labels is the county one. It needs covariates first (step 1). The project-level models need a project universe (step 3) before anything else, and Queued Up supplies one with its own dates.

One finding shapes step 2. Severe restrictions here have an enactment year far more often than contested projects have a usable date: 654 of the 747 counties with a severity 3 or 4 restriction have a year for it, and more than half of those first restrictions came in 2022 or later:

| First severe restriction | Counties |
|---|---|
| Before 2022 | 304 |
| 2022 to 2025 | 297 |
| 2026 | 53 |
| No year on any severe record | 93 |

A year is enough for a county-year design. That allows a true backtest, fit on what was known at the end of 2021 and scored against the restrictions that followed, which data-center-map's county model, fit on a single snapshot, does not have.

## 2. Goals and non-goals

**Goals**

1. **County covariates** for every county, from public sources, each with its source, vintage and leakage class recorded.
2. **A county restriction model** that passes a calibration gate ported from data-center-map, with a pre-registered label and variable rule, and a report saying what it can and cannot claim.
3. **A project universe** of solar, wind and storage projects that sought interconnection, each placed in a county, with contested projects matched to it.

**Non-goals**

- Changing any page, county report or headline figure. Model output is internal until decision 1.
- Project-level predictions (landmark, emergence, survival) and attributable delay. Step 3 lays their ground; none is fit here.
- Causal claims. data-center-map's `IDENTIFIABILITY.md` found its opposed-versus-control gap fell to about zero after matching, and nothing here is designed to do better.
- County opposition rates. "Share of a county's proposed projects that met opposition" is not computable while most counties are unexamined (section 5).

## 3. Step 1: county covariates

### What

`data/reference/county_covariates.csv`, one row per county in the 50 states and DC (3,144 rows, 2024 FIPS, Connecticut planning regions), plus `county_covariates_catalog.json` giving each column's definition, source, vintage, transform and leakage class.

| Family | Variables | Source | Leakage class |
|---|---|---|---|
| Demographic | population, land area, density, median household income, share with a bachelor's degree or more | Census ACS 2020-2024 5-year, read from the table-based summary files on `www2.census.gov` (the API has needed a key since May 2026; these files do not), and the 2024 Gazetteer | none |
| Political | presidential margin 2016, 2020, 2024; shift | MEDSL County Presidential Returns 2000-2024 (doi:10.7910/DVN/VOQCHQ, CC0), parsed as data-center-map's `fetch_county_features.py` parses it. Alaska and Connecticut report by units that are not 2024 counties and carry statewide values | none |
| Exposure | operating solar, wind and storage MW and plant count as of the cut year; MW requested in queues before the cut year (after step 3) | `data/reference/facilities.csv` (EIA-860M, USPVDB, USWTDB); Queued Up | none (dated before the cut) |
| State context | state siting authority, state preemption of local rules | `data/processed/state_policies.csv` | none, but grouped by state (see section 4) |
| Spatial | share of neighbouring counties with a severe restriction before the cut year | the database's `county_adjacency` table (built by `build_database.py`) plus this repo's labels | neighbor_outcome |
| Data center pressure | data center opposition events in the county before the cut year | `data/reference/data_center_events.csv` | none |

The leakage classes follow `county_features.py` in data-center-map: `none`, `neighbor_outcome` (built from other counties' labels, never the county's own), and `pre_outcome`. This plan uses no `pre_outcome` variables. Contested-project and restriction records for the county itself are excluded, because Sabin collects project fights and restrictions in the same research pass, so a county's project count measures where Sabin looked as much as where people objected.

### Decision: port the public fetchers, copy only what cannot be fetched

data-center-map holds all of these covariates already. Copying its outputs would be faster, but it would give this repo a second writer it cannot rerun and a dependency on a private repository. So this repo has its own `scripts/fetch_county_covariates.py`, ported from `fetch_census_features.py` and the MEDSL part of `fetch_county_features.py`, with a manifest (`county_covariates_manifest.csv`: URL, release, SHA-256) in the style of `facilities_manifest.csv`. The one copied file is MEDSL's raw CSV: Dataverse serves it only after a guestbook response, so `data/reference/medsl/` holds the copy data-center-map keeps, and each run checks its md5 against the one Dataverse publishes.

Parity, checked once on the first run (2026-10-15) rather than kept as a test: the 2016, 2020 and 2024 margins equal data-center-map's `county_votes.json` in all 3,104 county-basis counties; population differs from its ACS 2019-2023 values by 0.6% at the median, as a newer vintage should.

Exposure variables are computed by the model's feature builder from files already here, not fetched.

### Finished when

- The fetcher has run live in GitHub Actions on this branch (`model-inputs.yml`, `workflow_dispatch`), not only against fixtures.
- Every county has every `none`-class variable or an explicit missing reason, and the catalog lists all of them.
- Parity with data-center-map's census and margin values holds on the sample.

## 4. Step 2: county restriction model

### Labels, pre-registered before any fit

The label is fixed and committed (`config/county_model_registration.json`, registered 2026-10-16) before the first fit, so that no later choice is made by looking at results. That was a lesson from data-center-map: its first frozen variable list shipped nothing and had to be re-registered, and a label polarity bug ("approved" counted as enacted) mislabelled 28 counties for weeks.

| Label | Definition | Positives |
|---|---|---|
| **Primary, prospective** (`new_severe_2022_2025`) | Among counties with no dated severe restriction before 2022 and none undated: the county, or a place within it, enacted a restriction of severity 3 or 4 in 2022 to 2025 | 265 of 2,711 (9.8%; `scripts/county_labels.py`, 2026-10-16) |
| Secondary, snapshot (`has_severe`) | Any in-force restriction of severity 3 or 4 in the county or a place within it | 747 of 3,144 (23.8%) |
| Secondary, bans and moratoria (`has_severity_4`) | As above, severity 4 only | 453 of 3,144 (14.4%) |

Status rules: `pending` rows are already capped at severity 2, so they never count. NREL rows have `status` "unknown" (2,393 rows); they count as in force, because NREL compiled ordinances in effect when it surveyed, and the report states that assumption.

The prospective label is the primary because it is the only one that predicts. Covariates for it are measured as of the end of 2021: exposure counts only plants online and queue requests made before 2022, and neighbour labels count only restrictions before 2022. 2026 restrictions are held back as a second, later out-of-time check.

### Method

Ported from data-center-map's `county_policy_model.py`, keeping what worked there and dropping what did not:

- L2 logistic regression, 5 × 5 repeated stratified cross-validation, cross-fitted recalibration.
- The variable rule data-center-map registered on 2026-08-26: a variable is admitted only if its coefficient keeps its sign on all 25 folds, with a minimum of 3 variables.
- State-grouped cross-validation reported beside the stratified result, because state siting law makes counties in one state alike.
- Moran's I on residuals, computed by hand from `county_adjacency` (no `esda`).
- `scripts/calibration_gate.py`, ported with data-center-map's thresholds: ECE at most 0.15, Brier skill at least 0.05, at least 60 cases and 20 positives. A model that fails it is reported, not promoted.

Dependencies: `numpy` and `scikit-learn`, pinned in `requirements/ci.in` for Python 3.11. The rest of data-center-map's modelling stack (firthmodels, netcal, esda, InterpretML, skops) stays out, as `PASSOFF_2026-09-29_tooling_from_data_center_map.md` decided.

### Detection bias

This is the main threat to every result here. 1,808 of 3,222 counties have no record of any kind, and only 2 have a negative check, so "no recorded restriction" is not "checked and found none". The plan handles it three ways, none of which removes it:

1. **Source sensitivity.** Refit on NREL-only labels. NREL surveyed ordinances nationally, so its coverage depends less on news. If the model changes sign or rank order on NREL labels, the all-source result is reported as reflecting where sources looked.
2. **NREL's error rate.** NREL's databases were compiled with language models; `nrel_sample_report.md` measures their error by feature. The report carries that rate beside every figure that uses NREL labels.
3. **Wording.** Like data-center-map's map, the output is a "resemblance to counties that have enacted severe restrictions", never a probability that a county will restrict.

A second, smaller bias: NREL's ordinance year may be the latest amendment rather than first enactment, which would push some old restrictions into 2022 to 2025. The report counts how many prospective positives rest only on an NREL year and refits without them.

### Outputs

- `data/model/county_restriction_scores.csv`: calibrated out-of-fold score and interval for each county, per label.
- `data/model/county_restriction_report.md`: label counts, variables admitted and why, the stratified and state-grouped results, the gate verdict, the source sensitivity, Moran's I, and what the model may not be used to say.
- `--selftest` on the model and gate scripts, and tests under `tests/` for the label builder (the polarity bug above gets a named test).

None of these is read by a page or by `build_database.py`.

### Finished when

The registration is committed before the first fit. The model runs end to end in CI. The gate verdict, promote or hold, is in the report. A model that holds is still a finished step: the report is the deliverable.

## 5. Step 3: project universe from Queued Up

### Source

LBNL Queued Up, 2026 edition: an Excel workbook (last updated May 2026, data through the end of 2025) with the full project-level interconnection queue dataset and a codebook, from all seven ISOs and RTOs plus 50 non-ISO utilities, covering about 98% of installed US capacity. Licence CC BY 4.0, credited to Lawrence Berkeley National Laboratory and GridTracker. Already listed in `config/source_registry.csv` as "to integrate" for exactly this.

Why it matters here: it records projects whether or not anyone objected, and it carries its own dates (request, withdrawal, commercial operation). data-center-map had no such source and built its baseline by hand.

### What

| File | Writer | Contents |
|---|---|---|
| `data/reference/queue_projects.csv` | `scripts/fetch_queued_up.py` | Solar, wind, storage and hybrid projects: queue id, region and utility, status, request date, withdrawal date, operation date, state, county name as given, `county_fips` and how it was found, capacity by technology |
| `data/reference/queued_up_manifest.csv` | same | Workbook URL, edition, SHA-256, row counts kept and dropped by reason |
| `data/reference/queue_matches.csv` | `scripts/queue_matches.py` | Contested project to queue project, strong matches only, with the evidence for each |

Rules, following `fetch_facilities.py` and `facility_matches.py`:

- The fetcher finds the workbook link on `emp.lbl.gov/queues` rather than hard-coding it (those pages refuse some automated clients; it then fetches the last workbook URL in its manifest, and the workbook itself downloads from `eta-publications.lbl.gov`), and its schema guard checks the codebook's field names; a renamed field fails the run with the name, it never yields blank columns.
- Queued Up gives one county per request (the first, for a request spanning several) and its FIPS code. A code that is a 2024 county in the request's state is used as given; otherwise the county name goes through this repo's lookup (`classify.county_fips_all`). `county_fips_method` records which; a request neither places is left blank with the reason in `county_miss`, never guessed.
- A match never changes a contested project's outcome. Where a matched queue record contradicts it (say, a project recorded as blocked that reached commercial operation), the conflict is flagged for review, as `facility_conflict` does.
- Refreshed monthly by `model-inputs.yml`. The workbook is annual, so an unchanged SHA-256 rewrites nothing.

### What it unlocks, and what it does not

- **Now:** the queue exposure variables for step 2, and dates for matched contested projects. A withdrawal or operation date is not a decision date, but it bounds one, which is what the landmark model's 50-odd missing decision dates in data-center-map were short of.
- **Later, not in this plan:** a frame for the emergence model and matched controls. A queue project with no recorded opposition is not an unopposed project. data-center-map's emergence model is still locked because all of its audit codings came from a purposive sample. If this repo builds one, it draws the random audit sample first.
- **Never, at current coverage:** published rates of opposition per proposed project, by county or state.

### Finished when

The fetcher has run live in GitHub Actions on this branch and its manifest is committed. Every kept row has a county or a listed reason. The match report gives counts of strong matches, conflicts, and contested projects with no queue match.

## 6. Order, size, and decisions for Price

**Order.** Steps 1 and 3 are independent and can run in parallel. Step 2 runs first on step 1's covariates with facility exposure only, then once more with queue exposure when step 3 lands; the registration names both runs in advance.

| Step | Pull requests | Main risk |
|---|---|---|
| 1. Covariates | 1 | Census API rate limits on the first live run |
| 2. County model | 2 (label builder and registration; model, gate and report) | Detection bias decides the result more than the covariates do |
| 3. Queued Up | 2 (fetcher; matches) | The workbook link sits behind a form or changes shape between editions |

**Decisions for Price** (all four approved by Price on 2026-10-15, as written)

1. **Non-goal.** Approve internal models in this repo while the dashboard stays descriptive. Surfacing any score later is a separate decision, made with the report in hand.
2. **Primary label.** The prospective label (`new_severe_2022_2025`) as primary, with the two snapshot labels as secondary. The alternative is to lead with the snapshot label, which matches data-center-map's model but cannot be backtested.
3. **Dependencies.** Add `numpy` and `scikit-learn` to `requirements/ci.in`.
4. **Planning format.** Keep design documents in `docs/`, as this repo has done, or set up spec-kit (`.specify/` and a constitution) here first, as data-center-map uses. This plan assumes `docs/`; spec-kit would add a constitution step before any code.

## 7. Out of scope, with the trigger to revisit

| Model | Revisit when |
|---|---|
| Project outcome model (decided projects only) | Anyone needs it; 125 confirmed decided projects already clear the gate's minimums, but it can only describe past cases |
| Landmark model (early warning for pending projects) | Step 3 matches give announcement and decision bounds for at least 40 decided projects, 12 in each arm (data-center-map's floors) |
| Emergence model | A random-stratum audit of queue projects exists |
| Survival and attributable delay | Not planned; both are at chance or withheld in data-center-map |
