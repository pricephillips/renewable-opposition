# Headwind forward backtests (model program, stage two)

Built by `scripts/headwind_forward.py`. Internal. Each challenger is fit only on years before the test year and scored on that year's first severe restrictions (severity 3 or 4). These are backtests: they choose the method, and only the frozen vintages (`data/model/model_scorecard.md`) open a stage.

Gate: Brier skill 0.05 or more on at least 3 of 4 test years, and a median AUC no more than 0.0 below window_annualized (0.7546).

The ceiling column is the Brier skill a perfectly calibrated version of the same ranking would reach on that year (isotonic regression fit on the test year itself). It is a diagnostic of what the ranking allows, not a result.

| Challenger | Test year | Counties | Events | AUC | Brier skill | Ceiling | ECE | Mean chance |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| window_annualized | 2022 | 2759 | 65 | 0.7629 | 0.0069 | 0.0337 | 0.0142 | 0.0098 |
| window_annualized | 2023 | 2694 | 60 | 0.7233 | -0.0136 | 0.0217 | 0.0064 | 0.0189 |
| window_annualized | 2024 | 2634 | 54 | 0.7638 | -0.0142 | 0.033 | 0.0077 | 0.0282 |
| window_annualized | 2025 | 2580 | 47 | 0.7462 | -0.081 | 0.0226 | 0.0189 | 0.0371 |
| yearly | 2022 | 2759 | 65 | 0.768 | 0.0082 | 0.0372 | 0.0143 | 0.0098 |
| yearly | 2023 | 2694 | 60 | 0.7225 | -0.021 | 0.023 | 0.0041 | 0.0222 |
| yearly | 2024 | 2634 | 54 | 0.7512 | -0.0097 | 0.0327 | 0.0062 | 0.0267 |
| yearly | 2025 | 2580 | 47 | 0.7464 | -0.021 | 0.0255 | 0.0083 | 0.0265 |
| yearly_recal | 2022 | 2759 | 65 | 0.768 | 0.016 | 0.0372 | 0.0093 | 0.0147 |
| yearly_recal | 2023 | 2694 | 60 | 0.7225 | -0.0804 | 0.023 | 0.0234 | 0.0456 |
| yearly_recal | 2024 | 2634 | 54 | 0.7512 | 0.0171 | 0.0327 | 0.0049 | 0.0254 |
| yearly_recal | 2025 | 2580 | 47 | 0.7464 | 0.0098 | 0.0255 | 0.0022 | 0.0204 |
| yearly_level | 2022 | 2759 | 65 | 0.768 | 0.0113 | 0.0372 | 0.0122 | 0.0118 |
| yearly_level | 2023 | 2694 | 60 | 0.7225 | -0.0246 | 0.023 | 0.0026 | 0.0236 |
| yearly_level | 2024 | 2634 | 54 | 0.7512 | 0.0006 | 0.0327 | 0.0018 | 0.0223 |
| yearly_level | 2025 | 2580 | 47 | 0.7464 | -0.0037 | 0.0255 | 0.0023 | 0.0205 |
| yearly_recent | 2022 | 2759 | 65 | 0.7666 | 0.0086 | 0.0381 | 0.0143 | 0.0098 |
| yearly_recent | 2023 | 2694 | 60 | 0.7208 | -0.0158 | 0.0233 | 0.0041 | 0.0264 |
| yearly_recent | 2024 | 2634 | 54 | 0.7572 | 0.0157 | 0.035 | 0.0067 | 0.0272 |
| yearly_recent | 2025 | 2580 | 47 | 0.7406 | -0.0002 | 0.0217 | 0.0059 | 0.0241 |

| Challenger | Years at target | Median AUC | Median Brier skill | Passes |
|---|---:|---:|---:|---|
| window_annualized | 0 | 0.7546 | -0.0139 | no |
| yearly | 0 | 0.7488 | -0.0154 | no |
| yearly_recal | 0 | 0.7488 | 0.0129 | no |
| yearly_level | 0 | 0.7488 | -0.0016 | no |
| yearly_recent | 0 | 0.7489 | 0.0042 | no |

Chosen: none; the current forward score stays.
