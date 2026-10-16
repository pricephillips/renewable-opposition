# County restriction model

Written by `scripts/county_restriction_model.py` under `config/county_model_registration.json` (registered 2026-10-16). Do not edit by hand.

**What the scores are.** A resemblance to counties that enacted a severe restriction on renewable energy (severity 3 or 4), from county attributes. Not a probability that a county will restrict, and not a cause. Internal: no page, county report or headline figure reads them.

**The main threat.** Most counties have never been examined, so a county without a recorded restriction may simply be one no source looked at. The NREL-only refit below is the check on that.

## Results

| Label | Run | Counties | Positives | Selected variables | C | Median AUC (p10 to p90) | State-grouped AUC | Brier skill | ECE | Gate |
|---|---|---:|---:|---|---:|---|---:|---:|---:|---|
| `new_severe_2022_2025` | facilities | 2711 | 265 | `log_population`, `log_income`, `pct_bachelors_plus`, `margin`, `log1p_wind_mw`, `neighbor_severe_share` | 0.1 | 0.6767 (0.6343 to 0.7396) | 0.6434 | 0.038 | 0.0067 | HOLD: NO_SKILL: Brier skill 0.038 < 0.05 |
| `new_severe_2022_2025` | queue | 2711 | 265 | `log_income`, `pct_bachelors_plus`, `log1p_solar_mw`, `neighbor_severe_share`, `log1p_queue_mw` | 0.3 | 0.7151 (0.6642 to 0.7673) | 0.6914 | 0.0509 | 0.0096 | PROMOTE |
| `has_severe` | facilities | 3144 | 747 | `log_population`, `log_density`, `log_income`, `pct_bachelors_plus`, `log1p_solar_mw`, `log1p_wind_mw`, `neighbor_severe_share` | 0.1 | 0.7773 (0.7562 to 0.8016) | 0.7707 | 0.1989 | 0.0091 | PROMOTE |
| `has_severe` | queue | 3144 | 747 | `log_population`, `log_income`, `log1p_solar_mw`, `log1p_wind_mw`, `neighbor_severe_share`, `log1p_queue_mw` | 0.01 | 0.7799 (0.7553 to 0.8063) | 0.7726 | 0.2008 | 0.0118 | PROMOTE |
| `has_severity_4` | facilities | 3144 | 453 | `log_population`, `log_density`, `log_income`, `log1p_solar_mw`, `log1p_wind_mw`, `neighbor_severe_share` | 0.01 | 0.772 (0.7438 to 0.805) | 0.7666 | 0.1528 | 0.0032 | PROMOTE |
| `has_severity_4` | queue | 3144 | 453 | `log_population`, `log_income`, `log1p_solar_mw`, `neighbor_severe_share`, `log1p_queue_mw` | 0.03 | 0.7742 (0.7468 to 0.8038) | 0.7696 | 0.1616 | 0.0051 | PROMOTE |

## Coefficients (standardized variables)

Full-sample fit, with the range over the 25 cross-validation folds. Every selected variable keeps its sign in all 25 by construction.

**`new_severe_2022_2025`, facilities run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `log_income` | 0.5358 | 0.4252 | 0.5897 |
| `neighbor_severe_share` | 0.2919 | 0.2395 | 0.3411 |
| `pct_bachelors_plus` | -0.2132 | -0.2855 | -0.1218 |
| `log_population` | 0.193 | 0.1198 | 0.2815 |
| `log1p_wind_mw` | 0.1907 | 0.1414 | 0.2424 |
| `margin` | -0.079 | -0.1577 | -0.0147 |

**`new_severe_2022_2025`, queue run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `log_income` | 0.5714 | 0.4616 | 0.641 |
| `log1p_queue_mw` | 0.5048 | 0.4398 | 0.5704 |
| `neighbor_severe_share` | 0.2876 | 0.2323 | 0.3433 |
| `pct_bachelors_plus` | -0.1669 | -0.231 | -0.0955 |
| `log1p_solar_mw` | -0.1165 | -0.1613 | -0.0424 |

**`has_severe`, facilities run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `neighbor_severe_share` | 0.8393 | 0.7951 | 0.8763 |
| `log_population` | 0.4248 | 0.3234 | 0.5014 |
| `log_income` | 0.3282 | 0.2453 | 0.3714 |
| `log_density` | -0.1966 | -0.2759 | -0.088 |
| `log1p_wind_mw` | 0.1416 | 0.0946 | 0.1763 |
| `pct_bachelors_plus` | -0.1341 | -0.2142 | -0.093 |
| `log1p_solar_mw` | 0.051 | 0.0088 | 0.0946 |

**`has_severe`, queue run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `neighbor_severe_share` | 0.7021 | 0.6463 | 0.707 |
| `log_income` | 0.2369 | 0.1936 | 0.2606 |
| `log1p_queue_mw` | 0.1993 | 0.1597 | 0.2353 |
| `log_population` | 0.172 | 0.1065 | 0.2103 |
| `log1p_wind_mw` | 0.0978 | 0.0683 | 0.1227 |
| `log1p_solar_mw` | 0.0352 | 0.0103 | 0.0688 |

**`has_severity_4`, facilities run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `neighbor_severe_share` | 0.6375 | 0.5739 | 0.6451 |
| `log_population` | 0.248 | 0.2082 | 0.2599 |
| `log1p_solar_mw` | 0.126 | 0.0989 | 0.1791 |
| `log_income` | 0.1065 | 0.0726 | 0.1534 |
| `log1p_wind_mw` | 0.0694 | 0.0132 | 0.1057 |
| `log_density` | 0.0496 | 0.0278 | 0.0838 |

**`has_severity_4`, queue run**

| Variable | Coefficient | Fold min | Fold max |
|---|---:|---:|---:|
| `neighbor_severe_share` | 0.7244 | 0.666 | 0.7589 |
| `log_population` | 0.2915 | 0.2465 | 0.3345 |
| `log1p_queue_mw` | 0.2207 | 0.1619 | 0.2652 |
| `log_income` | 0.0991 | 0.0557 | 0.1635 |
| `log1p_solar_mw` | 0.0696 | 0.0345 | 0.1268 |

## Diagnostics

| Label | Run | Stability cost | Recalibration slope before, after | Moran's I on residual (p) |
|---|---|---:|---|---|
| `new_severe_2022_2025` | facilities | 0.0006 | 1.0001, 0.9773 | 0.1145 (0.001) |
| `new_severe_2022_2025` | queue | 0.0003 | 0.9858, 0.9807 | 0.1062 (0.001) |
| `has_severe` | facilities | 0.0005 | 1.0131, 0.9947 | -0.125 (1.0) |
| `has_severe` | queue | 0.0 | 1.1855, 0.995 | -0.1124 (1.0) |
| `has_severity_4` | facilities | 0.0004 | 1.2109, 0.9949 | -0.0353 (1.0) |
| `has_severity_4` | queue | 0.0 | 1.0712, 0.9961 | -0.0424 (1.0) |

A Moran's I well above zero means the errors cluster in space: neighbouring counties are mis-scored together, so the model misses something regional, such as state law or a regional campaign.

## Primary label checks, facilities run

- **NREL-only labels** (2846 counties, 101 positive): median AUC 0.6849; sign changes: `log_population`; Spearman with the all-source score 0.7851. The registered reading applies: the all-source result partly reflects where sources looked.
- **Without positives that rest only on an NREL year** (2636 counties, 190 positive): median AUC 0.6976; sign changes: none.
- **Held-back 2026** (2446 counties still without a severe restriction at the end of 2025, 49 enacted one in 2026): AUC 0.6467. 2026 is a partial year; restrictions enacted in it are still being recorded.

## Primary label checks, queue run

- **NREL-only labels** (2846 counties, 101 positive): median AUC 0.7072; sign changes: none; Spearman with the all-source score 0.9373. Below the registered thresholds: no sign change and Spearman of 0.7 or more.
- **Without positives that rest only on an NREL year** (2636 counties, 190 positive): median AUC 0.7173; sign changes: none.
- **Held-back 2026** (2446 counties still without a severe restriction at the end of 2025, 49 enacted one in 2026): AUC 0.6094. 2026 is a partial year; restrictions enacted in it are still being recorded.

## Not built

- Score intervals (data-center-map's Venn-Abers intervals). The scores are internal for now.
- State siting law as a variable: it cannot be measured as of 2021 (see the registration).
