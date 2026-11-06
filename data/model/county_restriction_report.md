# County restriction model

Written by `scripts/county_restriction_model.py` under `config/county_model_registration.json` (registered 2026-10-16). Do not edit by hand.

**What the scores are.** A resemblance to counties that enacted a severe restriction on renewable energy (severity 3 or 4), from county attributes. Not a probability that a county will restrict, and not a cause. Internal: no page, county report or headline figure reads them.

**The main threat.** Most counties have never been examined, so a county without a recorded restriction may simply be one no source looked at. The NREL-only refit below is the check on that.

## Results

| Label | Run | Counties | Positives | Selected variables | C | Median AUC (p10 to p90) | State-grouped AUC | Brier skill | ECE | Gate |
|---|---|---:|---:|---|---:|---|---:|---:|---:|---|
| `new_severe_2022_2025` | facilities | 2733 | 251 | `log_population`, `log_income`, `pct_bachelors_plus`, `log1p_solar_mw`, `log1p_wind_mw`, `neighbor_severe_share` | 0.1 | 0.68 (0.6437 to 0.7253) | 0.6484 | 0.0365 | 0.0031 | HOLD: NO_SKILL: Brier skill 0.036 < 0.05 |
| `new_severe_2022_2025` | queue | 2733 | 251 | `log_population`, `log_income`, `margin`, `log1p_solar_mw`, `neighbor_severe_share`, `log1p_queue_mw` | 0.03 | 0.7106 (0.6695 to 0.746) | 0.6832 | 0.0469 | 0.0084 | HOLD: NO_SKILL: Brier skill 0.047 < 0.05 |
| `has_severe` | facilities | 3144 | 715 | `log_population`, `log_density`, `log_income`, `pct_bachelors_plus`, `log1p_wind_mw`, `neighbor_severe_share` | 0.1 | 0.7831 (0.7589 to 0.8011) | 0.7746 | 0.2007 | 0.0058 | PROMOTE |
| `has_severe` | queue | 3144 | 715 | `log_population`, `log_density`, `log_income`, `log1p_wind_mw`, `neighbor_severe_share`, `log1p_queue_mw` | 0.03 | 0.7833 (0.7611 to 0.8048) | 0.7762 | 0.2039 | 0.0084 | PROMOTE |
| `has_severity_4` | facilities | 3144 | 442 | `log_population`, `log_density`, `log_income`, `pct_bachelors_plus`, `log1p_solar_mw`, `neighbor_severe_share` | 1.0 | 0.7742 (0.7349 to 0.8209) | 0.7703 | 0.1577 | 0.0066 | PROMOTE |
| `has_severity_4` | queue | 3144 | 442 | `log_population`, `log_income`, `neighbor_severe_share`, `log1p_queue_mw` | 1.0 | 0.7798 (0.7407 to 0.8147) | 0.7742 | 0.1636 | 0.0017 | PROMOTE |

## Coefficients (standardized variables)

Full-sample fit, with the range over the 25 cross-validation folds. Every selected variable keeps its sign in all 25 by construction.

**`new_severe_2022_2025`, facilities run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `log_income` | 0.5439 | 0.4425 | 0.6096 |
| `neighbor_severe_share` | 0.2801 | 0.199 | 0.3282 |
| `pct_bachelors_plus` | -0.2458 | -0.3179 | -0.1156 |
| `log_population` | 0.2127 | 0.0849 | 0.2894 |
| `log1p_wind_mw` | 0.1624 | 0.1077 | 0.2018 |
| `log1p_solar_mw` | -0.0674 | -0.1531 | -0.0097 |

**`new_severe_2022_2025`, queue run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `log1p_queue_mw` | 0.4068 | 0.3495 | 0.4364 |
| `log_income` | 0.3725 | 0.3029 | 0.4043 |
| `neighbor_severe_share` | 0.2668 | 0.1827 | 0.3122 |
| `log_population` | 0.1253 | 0.0673 | 0.1894 |
| `log1p_solar_mw` | -0.1012 | -0.1626 | -0.0512 |
| `margin` | -0.095 | -0.152 | -0.0224 |

**`has_severe`, facilities run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `neighbor_severe_share` | 0.8493 | 0.7992 | 0.8952 |
| `log_population` | 0.4644 | 0.3753 | 0.5378 |
| `log_income` | 0.3126 | 0.2454 | 0.3685 |
| `log_density` | -0.2148 | -0.2877 | -0.122 |
| `log1p_wind_mw` | 0.1247 | 0.0727 | 0.168 |
| `pct_bachelors_plus` | -0.1107 | -0.1806 | -0.046 |

**`has_severe`, queue run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `neighbor_severe_share` | 0.7955 | 0.7422 | 0.8281 |
| `log_population` | 0.2726 | 0.1985 | 0.3152 |
| `log_income` | 0.2543 | 0.2142 | 0.2962 |
| `log1p_queue_mw` | 0.2148 | 0.1667 | 0.2463 |
| `log_density` | -0.0951 | -0.1327 | -0.0206 |
| `log1p_wind_mw` | 0.0751 | 0.0272 | 0.1188 |

**`has_severity_4`, facilities run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `neighbor_severe_share` | 0.8035 | 0.7285 | 0.8541 |
| `log_population` | 0.5247 | 0.4072 | 0.6621 |
| `log_density` | -0.1813 | -0.2655 | -0.0734 |
| `log_income` | 0.1336 | 0.0354 | 0.2349 |
| `log1p_solar_mw` | 0.1128 | 0.0455 | 0.161 |
| `pct_bachelors_plus` | -0.0828 | -0.1678 | -0.0272 |

**`has_severity_4`, queue run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `neighbor_severe_share` | 0.7834 | 0.7064 | 0.8349 |
| `log_population` | 0.3351 | 0.2687 | 0.3927 |
| `log1p_queue_mw` | 0.2875 | 0.2319 | 0.3731 |
| `log_income` | 0.091 | 0.002 | 0.1738 |

## Diagnostics

| Label | Run | Stability cost | Recalibration slope before, after | Moran's I on residual (p) |
|---|---|---:|---|---|
| `new_severe_2022_2025` | facilities | 0.0 | 1.002, 0.9972 | 0.1025 (0.001) |
| `new_severe_2022_2025` | queue | 0.0005 | 1.1189, 0.9941 | 0.0975 (0.001) |
| `has_severe` | facilities | 0.0 | 1.0161, 0.9973 | -0.125 (1.0) |
| `has_severe` | queue | 0.0 | 1.0637, 0.9957 | -0.1194 (1.0) |
| `has_severity_4` | facilities | 0.0006 | 0.9846, 0.9977 | -0.0475 (1.0) |
| `has_severity_4` | queue | 0.0 | 0.9885, 0.9966 | -0.0474 (1.0) |

A Moran's I well above zero means the errors cluster in space: neighbouring counties are mis-scored together, so the model misses something regional, such as state law or a regional campaign. The snapshot labels' negative values come from `neighbor_severe_share`, which there is built from the same labels the model predicts, so the neighbours' outcomes are already in the score; the primary label's variable uses only restrictions before 2022 and does not have this.

## Primary label checks, facilities run

- **NREL-only labels** (2871 counties, 84 positive): median AUC 0.6895; sign changes: `log_population`; Spearman with the all-source score 0.7262. The registered reading applies: the all-source result partly reflects where sources looked.
- **Without positives that rest only on an NREL year** (2675 counties, 193 positive): median AUC 0.6831; sign changes: none.
- **Held-back 2026** (2482 counties still without a severe restriction at the end of 2025, 53 enacted one in 2026): AUC 0.6574. 2026 is a partial year; restrictions enacted in it are still being recorded.

## Primary label checks, queue run

- **NREL-only labels** (2871 counties, 84 positive): median AUC 0.72; sign changes: `log_population`; Spearman with the all-source score 0.8284. The registered reading applies: the all-source result partly reflects where sources looked.
- **Without positives that rest only on an NREL year** (2675 counties, 193 positive): median AUC 0.7087; sign changes: none.
- **Held-back 2026** (2482 counties still without a severe restriction at the end of 2025, 53 enacted one in 2026): AUC 0.6227. 2026 is a partial year; restrictions enacted in it are still being recorded.

## Registration amendments

- 2026-10-16 (after the first fit): log1p_solar_mw and log1p_wind_mw as of 2021: a retired plant counts when it retired after 2021, not when its year is 2021 or earlier. For a retired plant, facilities.csv's year is EIA's retirement year, not its operating year, so the registered wording counted plants already closed by the cut (104) and missed plants still running then (80). Found while checking the first fit; 184 plants, 2.5 GW in all. The snapshot definition (operating or retired, any year) is unchanged.

## Not built

- Score intervals (data-center-map's Venn-Abers intervals). The scores are internal for now.
- State siting law as a variable: it cannot be measured as of 2021 (see the registration).

