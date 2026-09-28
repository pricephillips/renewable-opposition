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
2. **An automatic intake queue** (`signal_harvest.py` + `promote_signal_candidates.py`). It runs a nightly GDELT query, geotags each hit against a county gazetteer, ranks candidates, and auto-promotes those that pass the QC gate. Promoted rows carry `pending` status with no outcome, tagged so the whole batch can be reverted. This repo's `fetch.py` → `parse.py` → review → promote chain already has the right shape. It needs a GDELT (or CourtListener) source and a promotion step that runs through `qc_gate.py`. GDELT and CourtListener are both blocked from agent sessions, so this needs to run in Actions.
3. **Decision trails that record changes only** (`promotion_trail.py`). This matters as soon as (2) runs nightly. data-center-map's trail grew to 7,342 rows describing 1,947 decisions before it was changed to record only new or changed decisions.
4. **Per-jurisdiction evidence grades** (`restriction_evidence.py`). "No restriction on file" should never read as "checked and clear". Record which sources were consulted per county, and grade by independence class. The coverage audit here already measures the problem: the two sources overlap about 6% each way.
5. **Declared data layers and one writer per file** (`configs/layers.json` + `layer_audit.py`). This repo has a small version of the problem: `restrictions_seed.csv` is written by both `fetch_moratorium_nation.py` and `build_sabin_seeds.py`. Each owns its rows through the `source` column, which is the same "declared exception" data-center-map argues for on `master_opposition.csv`. Write that ownership down in a machine-checked config before a third writer appears.
6. **Shared front-end modules.** `basemap.js` gives one tile provider for every map; five pages broke at once when CARTO started requiring an API key. `map-permalink.js` puts filters in the URL so a claim can cite a view, and `legend-filter.js` makes legends clickable. The three map pages here each hard-code OpenStreetMap tiles and have no permalinks. The handoff's open question (share a library, or keep the two repos separate) is still open. Copying with attribution, as with `state_bounds.py`, keeps them independent.
7. **A generated codebook** (`CODEBOOK.md`, rebuilt every run). This repo's rubrics live in docstrings and the README. Generating the codebook from the same constants the code uses keeps the two from drifting apart.
8. **County FIPS on every row** (`gazetteer.py`, `county_fips_lookup.json`). The map joins counties by name. FIPS codes make the join exact and enable per-county pages later.

## Deliberately not adopted

- **Predictive models** (landmark, survival, county policy). They need a decided-project universe with dates, which this repo does not have yet.
- **Open States bill sync and stakeholder positions.** State-level restrictions are still held for review here, and the positions layer's withhold-by-default gate exists because it names identifiable people. It is not worth taking on before the state rows are verified.
