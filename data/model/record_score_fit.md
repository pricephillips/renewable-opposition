# Record score: what the decided projects say

Internal, staff only. Built by `scripts/record_score_fit.py`; read `docs/county_record_score.md` first.

Cases: 161 contested projects with a confirmed outcome, a county and a resolution date (79 blocked, 82 advanced). Each feature is read from the county's own instruments on the project's technology as of the project's resolution date.

Learned model (L2 logistic regression, 5 folds x 5 repeats): out-of-fold AUC 0.5 (p10 0.49, p90 0.509). The hand rubric's instrument points on the same cases: AUC 0.501. AUC is the chance that a blocked project, picked at random, scores above an advanced one; 0.5 is a coin toss.

Coverage: 99 of the 161 projects are in a county with an instrument on their technology in the record, and for 95 of them at least one such instrument has no enactment date, so it cannot be placed before or after the decision and is left out. Dated instruments and decision dates are what the fit needs most.

Calibration gate: HOLD (NO_SKILL: Brier skill 0.002 < 0.05).

| Feature | Cases with it | Share blocked | Coefficient | Fold range | Same sign in every fold |
|---|---:|---:|---:|---|---|
| a new moratorium (under a year, never extended) | 1 | 1.0 | 0.399 | 0.0 to 0.409 | no |
| a long-running or extended moratorium | 1 | 1.0 | 0.399 | 0.0 to 0.409 | no |
| a moratorium while rules are being drafted | 0 | 0.0 | 0.0 | 0.0 to 0.0 | no |
| a ban (no pause described) | 0 | 0.0 | 0.0 | 0.0 to 0.0 | no |
| siting standards only (severity 1 or 2) | 2 | 0.0 | -0.677 | -0.686 to 0.0 | no |
| a named opposition group | 13 | 0.385 | -0.351 | -0.579 to 0.026 | no |

## How this bears on the hand weights

The rubric counts a new moratorium at 0.75 of a ban's points, adds 0.1 for each extension and 0.1 for each year in force (up to 1.0), and multiplies by 0.85 while rules are being drafted. The table says whether the decided projects point the same way: a long-running or extended pause with a larger coefficient than a new one, and a pause with rules being drafted with a smaller one. A coefficient whose sign changes across folds, or that rests on fewer than 10 cases, is not evidence either way.

## Limits

- The cases are projects that drew opposition, not every project proposed in a county.
- An instrument adopted in response to the project it blocked counts as on the books. The model describes association, never cause.
- The resolution date is the date of the document that settled the outcome, not always the decision itself.
- The counts are small. The fit can replace the hand weights only once the calibration gate says PROMOTE and the project universe with decision dates (Build-Out goal R3) is in place.
