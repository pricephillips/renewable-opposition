# Model improvement program: Renewable Headwind Model, then the cost model

**Status:** November 26, 2026. Stage one of the Headwind program is built (frozen monthly vintages, each a month's county scores saved and never edited, and a forward scorecard, a script that scores each vintage against the outcomes recorded after it). Everything else here is a plan. Build-Out goals R4 and D16.

Price asked for a program that takes the renewables models to a final state, where they need little oversight, give high output and carry low risk and cost. The Renewable Headwind Model comes first and the cost model second. This page says what "final" means for each model in measurable terms, the stages that get there, the automatic steps that replace a person's review, and what each run costs. It mirrors the data center model work in data-centers (research scouts, challengers that report and never ship, a boosted challenger behind the calibration gate) and shares formats with it rather than copying code.

## 1. What "final" means

### Renewable Headwind Model, county part

The model is final when the scorecard (`scripts/model_scorecard.py`) shows the sellable stage open and nothing in its upkeep waits on a person. In numbers:

| Gate | Measure | Target | Where it is checked |
|---|---|---|---|
| Ranking | forward AUC (area under the ROC curve: the chance that a county which later enacted a severe rule scores above one that did not) of the score the band is cut from | 0.70 or more | scorecard, each matured vintage |
| Accuracy | Brier skill of the 12-month chance (accuracy gain over the base rate) | 0.10 or more | scorecard |
| Calibration | ECE of the 12-month chance (expected calibration error: the average gap between stated chances and observed shares) | 0.05 or less | scorecard |
| Track record | matured yearly periods in a row that pass | 2 | scorecard stage rule |
| Upkeep | runs, freezes, scores and opens or closes stages with no person | every month | `model-inputs.yml` |
| Change control | a new input or method replaces the current one only by the promotion rule (section 3) | every change | the challenger trial and its pull request |

The targets live in `config/model_program.json`, the one place the scorecard reads them. `docs/headwind_strategy.md` explains why each level was chosen. A matured period is a vintage whose 12-month horizon has ended. The earliest dates are set by time, not work: the first live vintage is frozen on December 6, 2026, so the pilot stage can open in December 2027 at the earliest and the sellable stage in December 2028.

### Renewable Headwind Model, project part

The project part ranks later interconnection requests at an AUC of 0.546, close to a coin toss. It stays internal. It is final when it either reaches the pilot targets on a forward test or is retired at the end of 2027. The county part does not depend on it.

### Cost model

The cost model predicts nothing, so its final state is measured by parity with the data center cost model and by upkeep. It is final when every gate below holds:

| Gate | Measure | Target |
|---|---|---|
| Shared core | `scripts/cost_ledger.py` runs on the pinned `cost_core.py`; a `config/cost_format.lock` matches the one in data-centers | no copied cost code left |
| Spec 039 parity | market-scoped anchors, the carrying cost on deployed capital, per-site cost cards, a staff-only page | all four built |
| Sources | every anchor has a source URL and a re-verify-by date | 100 percent |
| Freshness | anchors past their re-verify-by date | none older than 30 days |
| Coverage | decided contested projects with dates, each priced or withheld with a stated reason | 100 percent accounted for |
| Framing | no probability multiplied into any cost; the cost layer stays internal | a test fails otherwise |

## 2. How it runs without oversight

Every step is a script on a schedule or an agent pair (a drafting agent and an independent reviewing agent). Merging a pull request is the only step a person takes. No new schedule is added: each step rides a job that already runs.

| Step | What does it | When |
|---|---|---|
| Measure | `scripts/model_vintage.py` freezes the month's scores; `scripts/model_scorecard.py` scores every vintage and applies the stage rule | monthly, in `model-inputs.yml` (built) |
| Alert | the same job opens an issue when a stage opens or closes | monthly (built) |
| Propose | the shared research scouts, Gov Data Scout and Repo Scout in data-centers; the wanted inputs in `config/headwind_inputs.json` | their own schedules (existing) |
| Trial | the renewables integrator tries a picked paper or input as a challenger in `headwind_compare.py` or `headwind_search.py` (`docs/SCOUT_BUILDS.md`, path 3b) | the weekly build session (existing) |
| Promote | the promotion rule (section 3) decides; the qc-auditor agent checks the branch | in the trial's pull request |
| Feed | the Renewable Daily Check dates undated severe rules (severity 3 or 4) with the instrument-reader and blind-reviewer agents | daily (stage four) |
| Guard | drift between vintages, input freshness, the refusal list in data-centers, the stop rule | monthly and on every build |

## 3. Stages: Renewable Headwind Model

**Stage one: measure (built November 26, 2026).** The month's scores are frozen with the commit and input hashes that made them, and never edited. The scorecard scores each vintage on the rules enacted after its date, applies the stage rule to decide whether each stage opens, and labels backtests and unfinished horizons so they never open a stage. The county model now also writes `forward__<run>`, the held-back model's score for each county with no severe rule through 2025, which the scorecard reads as a 12-month chance.

The first backtest (a test on past data: the model as of December 31, 2025, scored on the 2026 rules recorded so far) was run locally on November 26, 2026 and is not committed. It gave AUC 0.756 for the band's score, AUC 0.713 for the chance score and ECE 0.002, all within the pilot targets, and Brier skill 0.011 against a pilot target of 0.05. The monthly run of December 6, 2026 is set to freeze this backtest and the first live vintage in the repository.

**Stage two: make the 12-month chance accurate.** The low Brier skill is the first gap. Three changes, each tried as a challenger: a label fit to a 12-month window rather than four years; recalibration on the latest full year before each freeze (`docs/headwind_strategy.md`, section 6); and rolling-origin backtests (fit through year Y minus 1, score year Y, for 2022 to 2025), which give four forward periods now for internal decisions. Gate: Brier skill 0.05 or more on at least three of the four rolling years, with AUC no lower than today.

**Stage three: the promotion rule.** A challenger replaces the current model only when it adds at least 0.01 forward AUC on at least three of the four rolling years, keeps the calibration gate, beats the best of ten shuffled controls, and keeps every variable's sign stable. The integrator appends the registration amendment, and the qc-auditor checks the branch. The same stage adds a drift check: a vintage whose ranking correlates below 0.9 with the last one, or that moves more than 10 percent of counties between bands, opens an issue.

**Stage four: the data that moves the score.** In the wide search, more county attributes added nothing to the score, so the next inputs are dated records. In order of need: dates for the 1,064 undated rule rows (a small daily slice in the Renewable Daily Check, R3); cropland share read from the farmland file data-centers already fetches, through the pin, so no NASS key is needed; and state siting law effective dates from LegiScan.

**Stage five: the project part decision.** At the end of 2027 the project part either meets the pilot targets on a forward test or is retired. Grid cost (the LBNL cost studies) stays deferred until its license is known.

## 4. Stages: cost model

**Stage C1: the shared core.** Pin `cost_core.py` from data-centers with a `config/cost_format.lock`, move `scripts/cost_ledger.py` onto it, and delete the copied code. This closes the gap the staff admin page lists.

**Stage C2: spec 039 parity in the ledger.** Market-scoped anchors and the carrying cost on deployed capital.

**Stage C3: what staff read.** Per-site cost cards and a staff-only cost page.

**Stage C4: upkeep with no person.** The weekly cost job already keeps one issue open for stale anchors. Each stale anchor becomes a card for a reading agent and a blind reviewer, and the record-editor applies what both readings agree on. A coverage check accounts for every decided contested project with dates, priced or withheld with a reason.

Three calls in spec 039 belong to Price and shape C2 and C3: which anchors take markets and from which publishers, where the staff page lives, and whether the cost files stay in this public repository.

## 5. Cost per run

| Part | Actions minutes | Claude usage |
|---|---|---|
| Stage one: freeze and scorecard | under 1 minute a month, inside the monthly job | none |
| Stage two: rolling-origin backtests | an estimated 5 to 10 minutes a month, inside the same job | none |
| Challenger trials | one proof run per trial | inside the weekly build session, only when a pick exists |
| Dating undated rules | none beyond the daily job | a few items a day inside the Daily Check, capped in its config |
| Cost upkeep | the weekly cost job (existing) | a reading pair only when an anchor is stale |

## 6. Sharing with data-centers

`config/model_program.json`, the vintage files and `data/model/vintages/manifest.csv` make up a shared format (no script is shared). The data center models can adopt the same entries and pin the format, as `variable_core.py` is pinned, without either repository copying the other's scripts.
