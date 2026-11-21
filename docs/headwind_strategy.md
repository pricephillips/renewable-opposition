# Headwind Score: long-term strategy and goals

**Status:** November 20, 2026. A plan, not a result. Price asked for a long-term goal set for the Headwind Score built around an AUC and a calibration that can be sold. The working copy for discussion is a Claude Doc; this page is the record the routines read.

The Headwind Score becomes sellable when it ranks counties at a forward AUC of at least 0.70 and its stated chances are calibrated within 5 points, on two later periods in a row. Today it does not meet that bar. The county part (`scripts/county_restriction_model.py`) reached the pilot levels on its prospective label `new_severe_2022_2025` in the refits of 2026-11-20 and 2026-11-21 (AUC 0.75 to 0.76 in cross-validation, 0.70 to 0.72 on 2026 enactments, Brier skill 0.068 to 0.082), but only on one partial year and with its Brier skill measured in cross-validation, not forward. The project part (`scripts/headwind_model.py`) ranks later requests at 0.546, close to a coin toss.

## 1. Targets

Every target is measured forward in time: the model is fit on earlier years and scored on later years it never saw. That is what a client lives through, and cross-validation flatters a model whose world changes year to year.

| Measure | Today (county part, prospective label) | Today (project part) | Pilot | Sellable | Premium | Why this level |
|---|---|---|---|---|---|---|
| Forward AUC | 0.70 to 0.72 on 2026 enactments | 0.546 | 0.65 | 0.70 | 0.75 | 0.70 is the usual line for acceptable discrimination in risk scoring; below 0.65 a ranked list barely beats a careful analyst's guess |
| Brier skill (accuracy gain over the base rate) | 0.068 to 0.082 (cross-validated) | 0.074 (cross-validated) | 0.05 | 0.10 | 0.15 | Below 0.05 the score adds little to the base rate alone |
| Calibration error (ECE) | 0.006 to 0.007 | 0.009 | 0.10 | 0.05 | 0.03 | A client reads "30 percent" as 3 in 10; 5 points is the widest gap that survives that reading |
| Gain over the attributes-only or request-only model | not measured yet | 0.014 forward | 0.01 | 0.02 | 0.03 | The county record must earn its place over what a client already knows |
| Periods passed in a row | 0 | 0 | 1 | 2 | 3 yearly | One good year can be luck |

The shared calibration gate (`scripts/calibration_gate.py`: ECE 0.15 or less, Brier skill 0.05 or more) stays the floor for promotion inside the repository. The targets above are stricter because a client pays for them.

## 2. Stages

| Stage | Target date | Shown to clients as | Data it needs | Opens when |
|---|---|---|---|---|
| Internal | now | nothing | monthly refit and reports, the wide search (in place) | running today |
| Pilot | mid 2027 | tiers (higher, typical, lower), no percentages | rule adoption dates for undated rows; the first frozen monthly vintages | pilot targets met on one later period |
| Sellable | 2028 | a calibrated track record | 12 months of prospective outcomes; state siting law dates; grid cost for the project part | sellable targets met on two periods in a row |
| Premium | 2030 | calibrated by region, with the county facts that moved the score | withdrawal reasons for contested projects; local attention counts by year | premium targets met on three yearly vintages |

The county part leads, because it does not wait on grid cost. The earliest sellable date is set by time, not work: a vintage frozen in early 2027 can be scored only after 12 months of outcomes.

## 3. Data

The wide search of November 20, 2026 (`data/model/headwind_search.md`) tested 396 variables and pairs. Only queue withdrawal history held up, and nine new economic inputs added nothing. More of the same kind of data will not move the score. Dated data will: rule adoption dates (1,064 rule rows have no year), prospective outcomes, grid cost (the LBNL cost studies, deferred until their license is known), state siting law effective dates (LegiScan), withdrawal reasons and local attention counts. `config/headwind_inputs.json` keeps the wanted list in this order of need.

## 4. Measurement and reporting

No step waits on a person.

1. **Frozen vintages.** Each monthly refit (`model-inputs.yml`) saves that month's county scores with the commit and data date that made them. They are never edited.
2. **A scorecard.** A script scores every frozen vintage against the outcomes recorded since, once 12 months have passed, and writes each measure in section 1 with its value, its target and pass or miss for each stage.
3. **Promotion by rule.** A stage opens when the scorecard shows its targets met for the required run of periods, and closes again after two scorecards in a row miss. The scorecard opens an issue when a stage opens or closes.

The scorecard is the only source for any accuracy figure a client sees. Backtests stay in the internal reports and are labelled as backtests. The vintages and the scorecard are the first things to build.

## 5. How it is framed

The score says how closely a county resembles counties that later restricted renewables. It never says the county will restrict, and it never names a cause. At the pilot stage it is a tier with the county's own record beside it. At the sellable stage it is a calibrated frequency worded as a track record ("of counties scored like this one, about 3 in 10 enacted a severe rule within three years"), with the scorecard's figures and the dates they cover. At the premium stage it adds the two or three county facts that moved the score most, as reasons the score is high, not reasons the county will act.

## 6. Risks and the stop rule

- The record follows where sources looked. On NREL-only labels the county part's AUC falls to 0.69 to 0.72 and its ranking shifts. Rule dates and county examinations reduce this.
- Few restrictions arrive per year (53 severe enactments recorded in 2026 so far), so a yearly forward test swings by several points. The scorecard reports a range.
- The share of requests that withdraw changes between periods, which broke the learners' calibration in the race. Each vintage is recalibrated on its latest year before it is frozen.
- Without grid cost the project part may never pass sellable. The county part does not depend on it.
- **Stop rule.** If the county part has not reached pilot by the end of 2027, the score stays internal, and the product sells the record itself (rules, dates, outcomes) without a score.
