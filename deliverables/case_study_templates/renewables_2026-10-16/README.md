# Example case studies (templates): renewables, October 16, 2026

**These are example case studies, kept as templates.** They show the Hawthorn Intelligence case-study format applied to renewable energy, and serve as models for future county reports. They are not part of the platform's published data, and nothing in the build or the dashboard reads them. Their facts and scores are as of October 16, 2026 and are not kept up to date.

Four county case studies on wind, solar and battery-storage siting risk, written in the form of the Hawthorn Intelligence Coweta County data-center case study: Nicholas County, Kentucky; Linn County, Iowa; Cherokee County, Kansas; and Harris County, Texas. Data as of October 16, 2026. Each score is placed in a national decile (one tenth of U.S. counties, ranked by score).

| County | File | Restriction score | Severe restriction on record |
|---|---|---|---|
| Nicholas, KY | `Example_Case_Study_Nicholas_County_KY_Renewables.docx` | 0.05 (decile 1) | Yes, found in this review |
| Linn, IA | `Example_Case_Study_Linn_County_IA_Renewables.docx` | 0.39 (decile 8) | No |
| Cherokee, KS | `Example_Case_Study_Cherokee_County_KS_Renewables.docx` | 0.14 (decile 5) | Yes |
| Harris, TX | `Example_Case_Study_Harris_County_TX_Renewables.docx` | 0.36 (decile 8) | Yes, a lapsed city moratorium |

## What is in this folder

- The four `.docx` reports, built on the Coweta example's template so that styles, footers and page layout match it.
- `sources/`: the text of each report in the small markdown dialect that `tools/render_docx.py` reads. Edit these, not the `.docx` files.
- `img/`: the page-one locator maps. Three are David Benbennick's public-domain Wikimedia Commons maps; the Harris County map is drawn by `tools/draw_locator.py` from `data/geo/counties_2024.topojson`.
- `model/`: the provisional county restriction model's inputs and outputs. `county_labels.csv` is a copy of the labels registered on October 16, 2026 (commit 4ae9eca); `scores_snapshot.csv` holds every county's recalibrated out-of-fold score, interval and trait contributions; `model_results.json` holds validation and the four counties' benchmarks.
- `tools/`: the scripts that fit the model, build the benchmark tables, draw the Harris map and render the reports.

## The restriction score is provisional

The repository's own county model (docs/predictive_foundation_design.md, step 2) is still being built, and its registration says no score reaches a report without a separate decision. These case studies needed a score to match the Coweta form, so `tools/fit_county_model.py` fits the registered method (`config/county_model_registration.json` on the step 2 branch) to the `has_severe` snapshot label: L2 logistic regression, 5 x 5 repeated cross-validation, the sign-stability selection rule and cross-fitted recalibration. It passes the registered calibration gate (cross-validated AUC (area under the ROC curve) 0.78, 0.81 with whole states held out; Brier (mean squared error) skill 0.20; expected calibration error 0.016). The prospective label, the registered primary, fits weaker and holds at the gate (Brier skill 0.047), so the reports use the snapshot label, as the Coweta model did. Replace these scores with the step 2 model's once it is promoted.

## Corrections to the platform's data found in this review

These are in the reports but not yet in the database; each needs a review row.

- **Nicholas, KY:** Ordinance 06/2024-Solar (June 14, 2024; 2,000-foot setback from non-participating property lines and public roads) and Ordinance September-2026-18-01 (a one-year solar moratorium, September 18, 2026), both read in Kentucky Siting Board Case 2026-00256, which also opens a contested project, South Fork Solar. The October 9 negative check is superseded.
- **Cherokee, KS:** the 2021 wind moratorium and the commercial solar moratorium chain (Resolution 16-2024, June 10, 2024; Resolution 23-2024; Resolution 20-2025; extended in 2026 to March 31, 2027).
- **Harris, TX:** Pasadena's battery-storage moratorium is not in force. Ordinance 2025-082 (April 1, 2025) replaced it with Article XII, Energy Storage Systems. Contested projects: Tomball (denied 2023) and Baytown's Massey and Claire projects (approved 2025).
- **Linn, IA:** Duane Arnold Solar IV (pending) and Jones County's October 15, 2024 battery-storage moratorium, a neighbor.

## Using these as templates

To write a case study for another county, copy a file in `sources/`, replace its text and figures, and render it with `tools/render_docx.py` on the Coweta template. `tools/fit_county_model.py` and `tools/gen_quant.py` produce the score and the appendix tables for any county (add its FIPS code to `SITES` in the fit script).

## Rebuilding

From this folder, with the Coweta example saved as `coweta.docx`:

    python tools/fit_county_model.py ../../.. model
    python tools/gen_quant.py
    python tools/render_docx.py sources/nicholas_ky.md Example_Case_Study_Nicholas_County_KY_Renewables.docx coweta.docx "Case Study: Nicholas County, Kentucky"

The research notes behind each report, with every source marked as read or seen only in a search result, were kept in the working session and are summarized in each report's Sources list.
