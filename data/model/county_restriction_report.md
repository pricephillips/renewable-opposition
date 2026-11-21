# County restriction model

Written by `scripts/county_restriction_model.py` under `config/county_model_registration.json` (registered 2026-10-16). Do not edit by hand.

**What the scores are.** A resemblance to counties that enacted a severe restriction on renewable energy (severity 3 or 4), from county attributes. Not a probability that a county will restrict, and not a cause. Internal: no page, county report or headline figure reads them.

**The main threat.** Most counties have never been examined, so a county without a recorded restriction may simply be one no source looked at. The NREL-only refit below is the check on that.

## Results

| Label | Run | Counties | Positives | Selected variables | C | Median AUC (p10 to p90) | State-grouped AUC | Brier skill | ECE | Gate |
|---|---|---:|---:|---|---:|---|---:|---:|---:|---|
| `new_severe_2022_2025` | facilities | 2733 | 251 | `log_density`, `log1p_wind_mw`, `state_severe_share`, `in_income_pc`, `in_pop_growth_5y`, `in_hpi_growth_5y`, `in_poverty_pct`, `in_employment`, `in_construction_est_share`, `in_utilities_est_share`, `in_ag_support_est_share`, `in_local_govts` | 1.0 | 0.7533 (0.7207 to 0.7807) | 0.73 | 0.0682 | 0.0067 | PROMOTE |
| `new_severe_2022_2025` | queue | 2733 | 251 | `log_income`, `log1p_solar_mw`, `neighbor_severe_share`, `log1p_queue_mw`, `state_severe_share`, `in_income_pc`, `in_pop_growth_5y`, `in_hpi_growth_5y`, `in_poverty_pct`, `in_construction_est_share`, `in_utilities_est_share`, `in_ag_support_est_share`, `in_local_govts` | 0.1 | 0.7604 (0.7355 to 0.7898) | 0.7448 | 0.0818 | 0.0062 | PROMOTE |
| `has_severe` | facilities | 3144 | 715 | `log_population`, `log_density`, `log1p_wind_mw`, `neighbor_severe_share`, `state_severe_share`, `in_income_pc`, `in_poverty_pct`, `in_employment`, `in_construction_est_share`, `in_utilities_est_share`, `in_ag_support_est_share`, `in_local_govts` | 0.1 | 0.8107 (0.7854 to 0.8319) | 0.8057 | 0.2452 | 0.0061 | PROMOTE |
| `has_severe` | queue | 3144 | 715 | `log_population`, `log_density`, `neighbor_severe_share`, `log1p_queue_mw`, `state_severe_share`, `in_income_pc`, `in_hpi_growth_5y`, `in_poverty_pct`, `in_employment`, `in_construction_est_share`, `in_utilities_est_share`, `in_ag_support_est_share`, `in_local_govts` | 0.1 | 0.8136 (0.7862 to 0.8329) | 0.808 | 0.2498 | 0.0041 | PROMOTE |
| `has_severity_4` | facilities | 3144 | 442 | `log_density`, `log1p_solar_mw`, `neighbor_severe_share`, `state_severe_share`, `in_income_pc`, `in_pop_growth_5y`, `in_hpi_growth_5y`, `in_poverty_pct`, `in_median_hh_income_yr`, `in_employment`, `in_construction_est_share`, `in_utilities_est_share`, `in_local_govts` | 0.3 | 0.8091 (0.7726 to 0.8395) | 0.8052 | 0.2043 | 0.0058 | PROMOTE |
| `has_severity_4` | queue | 3144 | 442 | `log_density`, `margin`, `neighbor_severe_share`, `log1p_queue_mw`, `state_severe_share`, `in_income_pc`, `in_pop_growth_5y`, `in_hpi_growth_5y`, `in_poverty_pct`, `in_median_hh_income_yr`, `in_employment`, `in_construction_est_share`, `in_utilities_est_share`, `in_local_govts` | 1.0 | 0.8118 (0.7757 to 0.8377) | 0.8095 | 0.2105 | 0.0062 | PROMOTE |

## Coefficients (standardized variables)

Full-sample fit, with the range over the 25 cross-validation folds. Every selected variable keeps its sign in all 25 by construction.

**`new_severe_2022_2025`, facilities run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `in_poverty_pct` | -0.7905 | -0.9477 | -0.6329 |
| `in_local_govts` | 0.4148 | 0.3632 | 0.4717 |
| `in_employment` | 0.3725 | 0.2104 | 0.5542 |
| `in_utilities_est_share` | -0.2725 | -0.4495 | -0.1233 |
| `in_pop_growth_5y` | -0.2646 | -0.3706 | -0.1442 |
| `log_density` | -0.2452 | -0.3356 | -0.0206 |
| `in_income_pc` | -0.2434 | -0.3279 | -0.1149 |
| `state_severe_share` | 0.2185 | 0.1796 | 0.2621 |
| `in_ag_support_est_share` | -0.1493 | -0.2567 | -0.0569 |
| `in_hpi_growth_5y` | 0.1107 | 0.0165 | 0.2044 |
| `log1p_wind_mw` | 0.1065 | 0.0518 | 0.1625 |
| `in_construction_est_share` | 0.0906 | 0.0106 | 0.2117 |

**`new_severe_2022_2025`, queue run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `in_poverty_pct` | -0.5736 | -0.6846 | -0.4425 |
| `log1p_queue_mw` | 0.4197 | 0.3606 | 0.4773 |
| `in_local_govts` | 0.415 | 0.362 | 0.4641 |
| `in_utilities_est_share` | -0.2512 | -0.376 | -0.1239 |
| `in_pop_growth_5y` | -0.193 | -0.2807 | -0.076 |
| `in_income_pc` | -0.1744 | -0.2499 | -0.0989 |
| `state_severe_share` | 0.161 | 0.112 | 0.2044 |
| `log_income` | 0.1362 | 0.0122 | 0.2234 |
| `in_ag_support_est_share` | -0.1286 | -0.2282 | -0.0672 |
| `in_hpi_growth_5y` | 0.1151 | 0.0281 | 0.1927 |
| `neighbor_severe_share` | 0.0756 | 0.0077 | 0.1336 |
| `in_construction_est_share` | 0.0723 | 0.0123 | 0.1708 |
| `log1p_solar_mw` | -0.0612 | -0.1593 | -0.0105 |

**`has_severe`, facilities run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `state_severe_share` | 0.587 | 0.5396 | 0.6271 |
| `neighbor_severe_share` | 0.3848 | 0.3165 | 0.4518 |
| `in_poverty_pct` | -0.3739 | -0.4511 | -0.2853 |
| `log_density` | -0.3389 | -0.4291 | -0.2393 |
| `log_population` | 0.3011 | 0.1855 | 0.389 |
| `in_employment` | 0.2297 | 0.1304 | 0.3629 |
| `in_local_govts` | 0.2037 | 0.1543 | 0.2528 |
| `in_income_pc` | -0.1765 | -0.2214 | -0.1177 |
| `in_ag_support_est_share` | -0.1331 | -0.2034 | -0.0581 |
| `log1p_wind_mw` | 0.1022 | 0.04 | 0.1534 |
| `in_construction_est_share` | 0.0912 | 0.0554 | 0.141 |
| `in_utilities_est_share` | -0.09 | -0.1745 | -0.0208 |

**`has_severe`, queue run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `state_severe_share` | 0.5972 | 0.5495 | 0.6407 |
| `in_poverty_pct` | -0.3801 | -0.4506 | -0.2925 |
| `neighbor_severe_share` | 0.3674 | 0.3011 | 0.4385 |
| `log_density` | -0.2873 | -0.3783 | -0.1743 |
| `log1p_queue_mw` | 0.2587 | 0.202 | 0.2998 |
| `in_employment` | 0.2231 | 0.1262 | 0.3616 |
| `in_local_govts` | 0.1928 | 0.1479 | 0.239 |
| `log_population` | 0.1927 | 0.0804 | 0.281 |
| `in_income_pc` | -0.1425 | -0.1896 | -0.0859 |
| `in_ag_support_est_share` | -0.1326 | -0.2059 | -0.0556 |
| `in_utilities_est_share` | -0.1031 | -0.1769 | -0.0321 |
| `in_construction_est_share` | 0.0858 | 0.0506 | 0.1331 |
| `in_hpi_growth_5y` | 0.0626 | 0.0059 | 0.1166 |

**`has_severity_4`, facilities run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `in_employment` | 0.5861 | 0.4767 | 0.6824 |
| `state_severe_share` | 0.5048 | 0.4535 | 0.58 |
| `in_poverty_pct` | -0.4201 | -0.523 | -0.2998 |
| `in_utilities_est_share` | -0.3105 | -0.4489 | -0.2037 |
| `neighbor_severe_share` | 0.2895 | 0.2287 | 0.3453 |
| `in_local_govts` | 0.2848 | 0.2119 | 0.3354 |
| `in_income_pc` | -0.2148 | -0.2958 | -0.0959 |
| `log_density` | -0.209 | -0.2801 | -0.1028 |
| `in_median_hh_income_yr` | -0.1761 | -0.306 | -0.0186 |
| `in_construction_est_share` | 0.1658 | 0.073 | 0.2322 |
| `log1p_solar_mw` | 0.1197 | 0.0528 | 0.1606 |
| `in_pop_growth_5y` | -0.1102 | -0.1669 | -0.0367 |
| `in_hpi_growth_5y` | 0.0947 | 0.0142 | 0.1569 |

**`has_severity_4`, queue run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `in_poverty_pct` | -0.5253 | -0.666 | -0.387 |
| `state_severe_share` | 0.5172 | 0.4681 | 0.6013 |
| `in_employment` | 0.5143 | 0.3943 | 0.6328 |
| `in_utilities_est_share` | -0.3744 | -0.5377 | -0.2634 |
| `log1p_queue_mw` | 0.3326 | 0.2668 | 0.4055 |
| `in_median_hh_income_yr` | -0.2614 | -0.4562 | -0.0781 |
| `neighbor_severe_share` | 0.2608 | 0.1933 | 0.3202 |
| `in_local_govts` | 0.2453 | 0.1567 | 0.2993 |
| `in_income_pc` | -0.2007 | -0.3068 | -0.0724 |
| `in_construction_est_share` | 0.1668 | 0.072 | 0.239 |
| `log_density` | -0.1573 | -0.238 | -0.0483 |
| `in_hpi_growth_5y` | 0.1493 | 0.0818 | 0.2113 |
| `in_pop_growth_5y` | -0.1072 | -0.1668 | -0.0384 |
| `margin` | 0.0716 | 0.0121 | 0.1444 |

## Diagnostics

| Label | Run | Stability cost | Recalibration slope before, after | Moran's I on residual (p) |
|---|---|---:|---|---|
| `new_severe_2022_2025` | facilities | 0.0 | 0.9398, 0.9972 | 0.0705 (0.001) |
| `new_severe_2022_2025` | queue | 0.0 | 1.0023, 0.9982 | 0.0655 (0.001) |
| `has_severe` | facilities | 0.0 | 1.002, 0.9946 | -0.047 (1.0) |
| `has_severe` | queue | 0.0003 | 0.9996, 0.9921 | -0.0462 (1.0) |
| `has_severity_4` | facilities | 0.0003 | 0.9806, 0.9972 | -0.0068 (0.721) |
| `has_severity_4` | queue | 0.0 | 0.9694, 0.9969 | -0.0062 (0.703) |

A Moran's I well above zero means the errors cluster in space: neighbouring counties are mis-scored together, so the model misses something regional, such as state law or a regional campaign. The snapshot labels' negative values come from `neighbor_severe_share`, which there is built from the same labels the model predicts, so the neighbours' outcomes are already in the score; the primary label's variable uses only restrictions before 2022 and does not have this.

## Primary label checks, facilities run

- **NREL-only labels** (2871 counties, 84 positive): median AUC 0.7691; sign changes: `in_hpi_growth_5y`, `in_construction_est_share`, `in_ag_support_est_share`; Spearman with the all-source score 0.8208. The registered reading applies: the all-source result partly reflects where sources looked.
- **Without positives that rest only on an NREL year** (2675 counties, 193 positive): median AUC 0.7462; sign changes: none.
- **Held-back 2026** (2482 counties still without a severe restriction at the end of 2025, 53 enacted one in 2026): AUC 0.7244. 2026 is a partial year; restrictions enacted in it are still being recorded.

## Primary label checks, queue run

- **NREL-only labels** (2871 counties, 84 positive): median AUC 0.7498; sign changes: `log_income`, `in_income_pc`, `in_hpi_growth_5y`, `in_utilities_est_share`, `in_ag_support_est_share`; Spearman with the all-source score 0.8826. The registered reading applies: the all-source result partly reflects where sources looked.
- **Without positives that rest only on an NREL year** (2675 counties, 193 positive): median AUC 0.7575; sign changes: none.
- **Held-back 2026** (2482 counties still without a severe restriction at the end of 2025, 53 enacted one in 2026): AUC 0.7016. 2026 is a partial year; restrictions enacted in it are still being recorded.

## Registration amendments

- 2026-10-16 (after the first fit): log1p_solar_mw and log1p_wind_mw as of 2021: a retired plant counts when it retired after 2021, not when its year is 2021 or earlier. For a retired plant, facilities.csv's year is EIA's retirement year, not its operating year, so the registered wording counted plants already closed by the cut (104) and missed plants still running then (80). Found while checking the first fit; 184 plants, 2.5 GW in all. The snapshot definition (operating or retired, any year) is unchanged.
- 2026-11-20 (after the first fit): Adds ten variables to the pool, in both runs: state_severe_share (the share of the other counties in the same state with a severe restriction dated before 2022) and the nine plug-in inputs configured in config/headwind_inputs.json (BEA per capita income and five-year population change, the FHFA five-year house price change, the SAIPE poverty rate and median household income, and the County Business Patterns employment and construction, utilities and agriculture support establishment shares), each read for 2021 for the primary label and for its latest year for the snapshot labels. Every configured input enters, not a chosen few; the selection rule, the folds and the gate are unchanged. Plug-in variables are named in_<id> and read through scripts/headwind_inputs.py. Price, 2026-11-20: keep improving the model's algorithm and inputs. The residual Moran's I of 0.10 (p 0.001) showed errors clustered by region, which a state-level share addresses, and the inputs are the first county measures that can be read as of 2021 rather than from the 2020 to 2024 ACS. Before the pool was settled, an exploratory run added candidates one at a time and printed the held-back 2026 AUC beside the cross-validated result, so the 2026 check is no longer wholly unseen; the report says so.
- 2026-11-21 (after the first fit): Adds in_local_govts to the pool, in both runs: the log of the general purpose local governments in the county (incorporated places and town or township governments), counted from data/census_governments_2024.csv by scripts/build_headwind_local_govts.py and read as a static plug-in input. Price, 2026-11-20: try the data center model's variables. About 150 county variables from data-centers (data/county_features_expanded.csv) were each added on their own to the selected primary model of the amendment of 2026-11-20. Four kept their sign on every fold and added at least 0.01 AUC in both runs and some AUC on 2026: cropland share, local governments, incorporated places and the non-Hispanic white share. The best of ten shuffled screens of the same variables gained at most 0.005. Local governments is the one built here: the source is already in this repository and any of these governments can enact a rule the labels count. Incorporated places is part of the same count. Cropland share needs a USDA NASS key this repository does not have yet. The white share is left out: a score sold to clients does not rank counties by race.

## Not built

- Score intervals (data-center-map's Venn-Abers intervals). The scores are internal for now.
- State siting law as a variable: it cannot be measured as of 2021 (see the registration).

