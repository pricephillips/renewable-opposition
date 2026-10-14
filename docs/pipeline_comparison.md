# Pipeline comparison: data-center-map → renewable-opposition

Written 2026-09-25 from a read of `pricephillips/data-center-map` at `b903f0f`.
That repository has run a nightly opposition pipeline since mid-2026 and has
written down most of what went wrong along the way (`ARCHITECTURE.md`,
`README.md`, module docstrings). This page lists which of its practices apply
here, what this repository did before, and what changed.

The two repositories stay independent, as both READMEs say. Where code is
reused, it is copied with an attribution line, not imported.

## Adopted in this change

| Practice in data-center-map | This repo before | Now |
|---|---|---|
| **An outcome ladder that separates confirmed from unverified** (`CODEBOOK.md`). The rule is "outcome_label_only is never sufficient for *_confirmed". | Every Sabin row with status `cancelled`/`rejected` was published as `blocked_confirmed`, backed by the extraction's word alone. | `blocked_unverified` / `advanced_unverified` by default. A row becomes `*_confirmed` only when a seeded court case linked to the same record was decided the same way. `finality_evidence` says which applies. Today that is 4 blocked and 5 advanced confirmed, with 52 blocked and 11 advanced unverified. |
| **A QC gate with issue codes, severities and a quarantine** (`qc/qc_pipeline.py`). HIGH and CRITICAL issues block a row; lower severities are reported only. | Structural validation only (required fields, severity range, state code). | `scripts/qc_gate.py` runs inside the build. It checks coordinates against the state named, URL validity, status/outcome/case vocabularies, future enactment dates, pending rows scored above 2, and confirmed outcomes without evidence. Blocked rows go to `data/processed/quarantine.json`, and `data/processed/qc_report.md` lists every finding. The current data passes with 0 findings. |
| **Coordinates checked against state bounding boxes** (`state_bounds.py`). This check was added after an id collision placed Pennsylvania projects in Louisiana for weeks. | Not checked. The 295 Moratorium Nation rows carry coordinates. | `scripts/state_bounds.py`, copied verbatim with attribution; its own 20-check selftest runs in pytest. |
| **Dated, hashed snapshots of published outputs** (`snapshots/manifest.csv`). | None. A count quoted on a given day could not be traced to the file behind it. | `scripts/snapshot_manifest.py` appends one row per published file only when its hash changes. It runs in `build-data.yml`. |
| **`-merge` on regenerated files** (`.gitattributes`). The reason given: a clean three-way merge of two regenerations produces a file neither run wrote, which is worse than a conflict. | Two branches that both ran the build could have their `data/processed/` outputs spliced together. | `.gitattributes` marks `data/processed/**` and `docs/coverage_audit.md` `-merge`. To resolve, rerun `build_seed_outputs.py`. |
| **Publishing hardening for the workflow that commits** (`harden-pipeline-publishing.yml`): serialized runs, rebase-and-retry push, never force-push. It also opens an issue on failure (`update-opposition-csv.yml`). | A bare `git push` that fails if anything else moved the branch, and no notification. | `build-data.yml` now has a concurrency group, three rebase-and-retry attempts, the QC report in the job summary, and an issue opened when a main-branch build fails. |
| **A front-end gate in CI** (`scripts/check_inline_js.py`, syntax only). | Nothing. The map and map-audit pages crashed at load on 2026-09-25 and nothing noticed. | `scripts/smoke_frontend.py` goes further than a syntax check: it loads every page in headless Chromium and fails on any page error, or if no nonzero record count appears. I checked it against the pre-fix versions of both pages, and it fails on both with the exact errors. It runs as the `frontend` job in `validate.yml`. |

## Recommended next, in order

1. **Verification status on every record** (`verification_status.py`). data-center-map classifies each row (`sourced`, `sourced_no_url`, `headline_only`, `incomplete`) and derives external counts only from the countable set. The equivalent here:
   - Moratorium Nation's `needs_verification` flag (91 rows).
   - The Sabin rows' report-level citation, which points at the whole report rather than a page.
   - Cases confirmed by search result versus from reading the opinion.

   The dashboard headline would then say "530 severe restrictions, N fully sourced".
2. **An automatic intake queue** (`signal_harvest.py` + `promote_signal_candidates.py`). It runs a nightly GDELT query, geotags each hit against a county gazetteer, ranks candidates, and auto-promotes those that pass the QC gate. Promoted rows carry `pending` status with no outcome, tagged so the whole batch can be reverted. This repo's `fetch.py` → `parse.py` → review → promote chain already has the right shape. It needs a GDELT (or CourtListener) source and a promotion step that runs through `qc_gate.py`. GDELT and CourtListener were blocked from agent sessions when this was written; on 2026-10-13 both answered, but throttled per shared IP, so the intake runs in Actions (round eight).
3. **Decision trails that record changes only** (`promotion_trail.py`). This matters as soon as (2) runs nightly. data-center-map's trail grew to 7,342 rows describing 1,947 decisions before it was changed to record only new or changed decisions.
4. **Per-jurisdiction evidence grades** (`restriction_evidence.py`). "No restriction on file" should never read as "checked and clear". Record which sources were consulted per county, and grade by independence class. The coverage audit here already measures the problem: the two sources overlap about 6% each way.
5. **Declared data layers and one writer per file** (`configs/layers.json` + `layer_audit.py`). This repo has a small version of the problem: `restrictions_seed.csv` is written by both `fetch_moratorium_nation.py` and `build_sabin_seeds.py`. Each owns its rows through the `source` column, which is the same "declared exception" data-center-map argues for on `master_opposition.csv`. Write that ownership down in a machine-checked config before a third writer appears.
6. **Shared front-end modules.** `basemap.js` gives one tile provider for every map; five pages broke at once when CARTO started requiring an API key. `map-permalink.js` puts filters in the URL so a claim can cite a view, and `legend-filter.js` makes legends clickable. The three map pages here each hard-code OpenStreetMap tiles and have no permalinks. The handoff's open question (share a library, or keep the two repos separate) is still open. Copying with attribution, as with `state_bounds.py`, keeps them independent.
7. **A generated codebook** (`CODEBOOK.md`, rebuilt every run). This repo's rubrics live in docstrings and the README. Generating the codebook from the same constants the code uses keeps the two from drifting apart.
8. **County FIPS on every row** (`gazetteer.py`, `county_fips_lookup.json`). The map joins counties by name. FIPS codes make the join exact and enable per-county pages later.

## Round two (2026-09-29)

The second round of borrowed practice is the CI and safety layer data-center-map
finished in its spec 004. The manual is
[`PASSOFF_2026-09-29_tooling_from_data_center_map.md`](PASSOFF_2026-09-29_tooling_from_data_center_map.md);
its Part A is now in place:

- Pinned dependencies (`requirements/ci.txt`, compiled with uv) kept current by
  Dependabot, and every action pinned to a commit SHA and linted by actionlint
  and zizmor (`.github/workflows/workflow-lint.yml`).
- ruff on syntax-class rules, and local pre-commit gates
  (`.pre-commit-config.yaml`, `scripts/precommit_gates.py`).
- Every CSV is LF (`.gitattributes`, and `lineterminator="\n"` on every writer).
- No em-dashes in the pages or README; Vale lints client-facing markdown
  (`.vale.ini`, `styles/Hawthorn/`).
- `data/processed/diff_summary.md`, written by `scripts/processed_diff.py` on
  every build and keyed on `id`, so a rebuild can no longer silently rewrite
  the published data.
- A session-start hook (`.claude/hooks/session-start.sh`).

Part B of the manual lists the later tools and the trigger for each. B1
(item 5 above) is done: `config/layers.json` declares every writer, and
`scripts/layer_audit.py` checks it against the code in CI and pre-commit. Writing
it down found a third seed writer (`promote_reviewed.py`) and a rebuild that
would have dropped its contested-project rows; both are now declared and fixed.
B2 is in place too: `.github/workflows/source-archive.yml` archives every cited
source weekly, and the build joins each snapshot into `sources.csv`/`.json` and
the dashboard's source links.

B4, B6 and B7 followed once data-center-map's spec 009 landed. Every page now
reads `data/processed/` through `processed-data.js` and counts instruments,
quoting `headline_metrics.json`. Restrictions and contested projects carry a
derived `county_fips` (misses listed in `data/review/fips_misses.csv`), and the
map's county choropleth draws on the Census 2024 boundaries in `data/geo/`,
joined on that code (items 6 and 8 above). Both maps use `basemap.js`
(OpenFreeMap with a raster fallback chain), and `tests/ui` runs Playwright with
axe in the `ui` job of `validate.yml`.

## Round three (2026-10-13): the rules layer

The third round takes data-center-map's practices for keeping records
current and auditable, adapted to this repo's pure rules layer
(`classify.py`, `qc_gate.py`, `headline_metrics.py`, `verification_worklist.py`,
`negative_checks.py`), with tests in `tests/test_brain.py`. Copied in spirit
with an attribution line in each module, never imported.

| Practice in data-center-map | Here |
|---|---|
| **Mechanism-aware staleness** (`stale_pending_audit.py`): a moratorium proposal is stale after 120 days, anything else after a year, and the list ranks what re-verifying would change. Hamilton County TN sat as "proposing a pause" for four months after it enacted one. | `classify.currency` on every restriction (`in_force`, `lapsed_unconfirmed`, `pending`, `unknown`) from the instrument's own dates, with `status_as_of`. Two Moratorium Nation rows were already past their end dates with no confirmed extension. The headline counts them apart, QC reports `END_DATE_PASSED`, and the restriction worklist lists them first; a pending instrument is flagged after 120 days and a pending project after 365. |
| **Status resolution from the record's own text** (`status_resolution.py`): a pending row whose headline already reports a completed adoption, with FINAL and NOT_FINAL word patterns. Found four Florida counties adopted while every row said pending. | `decision_language` on the outcome worklist: the decision words in a pending or needs_review project's text when nothing says the step was not final. Thirteen such leads on the first run; they sort first within their tier. Proposes only. |
| **A decision trail that records changes only** (`promotion_trail.py`; item 3 above). One trail reached 7,342 rows for 1,947 decisions before the rule. | `scripts/promotion_trail.py`, and `promote_reviewed.py` writes `data/review/promotion_trail.csv`: each queue row's and started case candidate's decision, once, and again only when it changes. |
| **Evidence grades by independence class** (`restriction_evidence.py`; item 4 above): grades count distinct classes (primary law, proceeding, secondary), never distinct sources, because two compilations reading the same press can be wrong together. | `negative_checks.grade`: A to C from the classes a check's `sources_checked` span and its age; `negative_check_grade` in `county_summary.csv` and in site profiles. The frame is the negative check, not the county label, since this repo has no county label to defend. |
| **A generated codebook** (`CODEBOOK.md`, rebuilt by `build_clean_feed.py`; item 7 above). | `scripts/codebook.py` renders `docs/codebook.md` from the constants the code runs on, with severity as truth tables produced by calling the scoring functions; `tests/test_codebook.py` fails when the committed copy is stale. `qc_gate.CHECKS` now lists every check code with its severity, and a test checks the gate emits nothing outside it. |

Not taken from the same modules: data-center-map's county label and its
model-driven ranking of what to re-verify (this repo has no county label or
model), its Google News follow-up search (`status_followup.py`, which needs a
network the build does not have and an intake queue this repo does not run
yet), and its harvest-specific verification statuses.

## Round four (2026-10-13): closing loops

| Practice in data-center-map | Here |
|---|---|
| **Rank re-verification by what it would change** (`stale_pending_audit.py`'s `label_moving`: a stale row whose confirmation would flip a county label goes first). | `county_impact` on the restriction worklist: `sole_severe` (the county's only severe renewables-only instrument) and `sole_record` (its only restriction) sort first within a tier. |
| **Suggested resolution on every review row** (`review_worklists.py`: "so the review pass is triage, not investigation"). | `qc_gate.CHECKS` names what releases a row for each code, and `qc_report.md` lists every quarantined row with that action. The codebook carries the column. |
| **Dated change logs** (`change_log.csv`, `calibration_history.csv`: a number quoted on a day can be found by date). | `data/snapshots/headline_history.csv`, kept by `scripts/headline_history.py` (Phase 5, PR #41, which also backfilled it from git history and charts it on the national view). Round four's own version of the file was dropped in favour of it when the two branches met. |
| **Dedupe against every file, not just the clean one** (Part C lesson 1 of the 2026-09-29 passoff: 4,099 duplicate rows in four days). | `parse.py` checks each candidate against the queue and all three seeds by source document and by name before queueing it; a same-document candidate is dropped and logged, a same-name one is queued with a "possible duplicate" note. |

## Round five (2026-10-13): context and self-description

| Practice in data-center-map | Here |
|---|---|
| **Preemption as a coded stance** (`outcome_defensibility.py` codes preemption of local control as a legislative stance; `bill_taxonomy.py` classes bills by what they do to local authority). | `classify.state_context`: every local restriction carries `state_limits_local` (yes, no, unknown) with the siting authority, size threshold and preemption-rule ids read off the verified `state_policies` rows for its technology. The headline reports severe instruments in limiting states beside the count. Never a judgment on a given ordinance. |
| **Staleness as a property of every claim** (`stale_pending_audit.py`). | A negative check older than a year puts its county back on `negative_check_worklist.csv` with the reason, beside counties never checked. |
| **Corroboration from a sibling record** (`triage_accelerator.py` scores a candidate by evidence the first pass did not consult). | A verified instrument for the same jurisdiction and technology lends its primary-source URL to an unverified sibling on the restriction worklist, as a lead to read, never as verification. |
| **One self-description file** (`operations_summary.py`: "the platform's strongest claim, that it maintains itself and records how, could only be made by assertion"). | `scripts/operations_summary.py` writes `data/processed/operations_summary.json` and `.md` from the quarantine, worklists, promotion trail, review queue, snapshots, headline history and source archive. Counts only; nothing computed anywhere else first. |

## Round six (2026-10-13): what the records say

| Practice in data-center-map | Here |
|---|---|
| **The decided-case block rate with a right-censoring guard** (`headline_metrics.md`: incidents younger than 90 days excluded; the scope note that every rate is conditional on a conflict being visible enough to enter the tracker). | `headline_metrics.decided_rate`: the blocked share of decided projects, all and confirmed-only, by technology, with the same 90-day guard and the same scope note. |
| **A concerns codebook independent of mechanism** (`CODEBOOK.md`: noise, water, light, energy cost, land use and the rest, by keyword triggers). | `classify.CONCERNS`: sixteen concerns matched in a project's own text, published with their patterns in `docs/codebook.md`, counted in the headline. What was raised, never why the project ended as it did. |
| **The county label built from co-located events** (`county_aggregator.py`: a county is restrictive when a record of an enacted restriction sits in it). | `county_severe_restriction_ids` on each project: the severe instruments for its technology in any county it touches. Kept as a fact about the county, not a label and not a link between records. |

## Round seven (2026-10-13): what is visible, what is linked, what was checked

| Practice in data-center-map | Here |
|---|---|
| **A visibility audit** (`visibility_audit.py`, `configs/surfaces.json`: an output no surface reads is unclassified until someone says what it is for). | `config/surfaces.json` and `scripts/surface_audit.py`: every tracked output under `data/processed/`, `data/db/` and `data/snapshots/` is read by a page, a download, or internal with a reason; the audit also catches a declared read the page code no longer makes. Writes `docs/surfaces.md`; runs in `validate.yml`. |
| **Link audits** (`link_disagreement_audit.py`, `project_resolution.py`: an event must resolve to a project). | `qc_gate.check_links`: a case whose `source_record_id` names no published project or restriction is reported (`LINK_MISSING`), with the release action in the CHECKS table. |
| **A generated field dictionary** (the codebook's field tables). | Every column of every published table now has a `datapackage.json` description, and a test fails when a new column lacks one. |
| **Validation samples and verdict counts** (`validation_sample.csv`, `verification_status_report.md`: source reliability measured on checked rows). | The operations summary's "What checking found": reviewers' verdicts on primary sources by source family, and outcome resolutions by outcome and access. Never extrapolated. |

## Round eight (2026-10-13): live intake and Actions minutes

Item 2 of "Recommended next" (an automatic intake queue) and passoff B8 (Legistar), built on the
`fetch.py` -> `parse.py` -> review chain this repository already had. What data-center-map
learned the hard way is built in from the start; its auto-promotion is not.

| Practice in data-center-map | Here |
|---|---|
| **A nightly GDELT harvest** (`signal_harvest.py`). It sent its six queries back to back with no pause, and about a third of its runs came back empty from throttling. | `gdelt_renewable_news`: five queries a week, paced at one request per 6 s, a 429 retried after 20 s and then 60 s, and a body that is not JSON refused (GDELT answers a bad query with HTTP 200 and text). A throttled request is a manifest row with its error, never an empty result that overwrites anything. |
| **Headline placement that refuses rather than guesses** (`locate()`, after 102 rows landed in Power County ID and 78 in a "Texas" County). | `scripts/news_place.py`: a county only from a literal "<Name> County" (with its state, unless the name is unique), a town only with its state named and a single county in the place index, a roundup of three or more places is state only. |
| **Dedupe against every file** (4,099 duplicate rows in four days) and **MinHash clusters for syndication**. | `parse.py` checks the queue, the seeds and every review file that cites evidence, ignores click-tracking parameters, and drops a news headline already queued. |
| **Auto-promotion by the QC gate** (2026-08-12), later walked back for off-topic rows, misplacements and 1,255 rows that needed correction. | Not adopted. Every harvested candidate is a `lead`: never promoted, never counted on a page, until a reviewer triages it. |
| **Legistar clients verified by body name, slugs never guessed across states** (`legistar_probe.py`). It matched on matter titles only for data centers. | `legistar_renewable_matters`: the verified clients that hold renewable records here (`config/legistar_clients.json`), matter titles filtered for siting instruments and project decisions, the county's own energy purchases dropped. |
| **Actions minutes** (spec 004 onwards, and seven efficiency PRs in October 2026), measured here on two weeks of runs as if the repository were private. | The weekly intake job installs, checks its fixtures, fetches and commits in one job with a 15-minute cap and no artifacts. Validate cancels a pull request's superseded run (never a run on `main`); a push to `main` whose tree its pull request already tested green skips the heavy jobs (any doubt gives a full run); the page smoke check runs in the `ui` job on its Chromium and freshly built data, with screenshots kept only on failure, for 7 days. The data build runs on `main` only. Workflow Lint is one job that lints a branch once. The archive job stops itself after 15 minutes and commits what it checkpointed (`max_runtime_s`, after data-center-map). Every job has a timeout; `tests/test_ci_workflows.py` holds these properties. |

## Deliberately not adopted

- **Predictive models** (landmark, survival, county policy). They need a decided-project universe with dates, which this repo does not have yet.
- **Open States bill sync and stakeholder positions.** State-level restrictions are still held for review here, and the positions layer's withhold-by-default gate exists because it names identifiable people. It is not worth taking on before the state rows are verified.
