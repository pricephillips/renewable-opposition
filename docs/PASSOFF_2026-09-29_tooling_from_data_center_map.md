# Handoff: porting the data-center-map tooling upgrade

**Date:** 2026-09-29. **From:** `pricephillips/data-center-map`, session 1 (spec 004) and
the tool registry (`configs/integrations.json`, 52 selected tools across sessions 0 to 8).
**To:** a Claude Code session working in this repository.

`docs/pipeline_comparison.md` already covers the first round of borrowed practices:
the QC gate, state bounds, snapshots, `-merge`, and publishing hardening. This manual
is the second round. Part A is the CI and safety layer that data-center-map finished
this week. Part B is the later tools, in order, adapted to this repo. Part C is what
went wrong there, so it does not go wrong here.

The rule from `pipeline_comparison.md` still holds: **copy with an attribution line,
never import across repositories.** The two repos stay independent.

---

## How to use this document

Work Part A in order: each step is small and has a check at the end. Part B is a
menu; take items only when their trigger applies. Start the session with:

> Read `docs/PASSOFF_2026-09-29_tooling_from_data_center_map.md`. Do Part A, steps
> A1 to A9, in order. After each step run its check. Copy files from
> `pricephillips/data-center-map` with an attribution line; do not import. Open one
> PR per step group (A1 to A3, A4 to A6, A7 to A9). Workflow changes: if you
> cannot commit under `.github/workflows/`, stage them as
> `docs/pending_ci_hygiene.patch` with a matching `.md`.

Both repos are in the same Claude environment, so network access (Census, OpenFreeMap,
unpkg, jsdelivr) and the setup script (ast-grep, DuckDB) already apply here.

---

## Where this repo stands today (measured 2026-09-29 at `9685142`)

| Area | Today | After Part A |
|---|---|---|
| Python deps | `requirements.txt` lists `requests>=2.31`, `PyYAML>=6.0` and `pytest>=8.0`, all unpinned | pinned constraints file, installed with uv, updated weekly by Dependabot |
| Actions | `actions/checkout@v4`, `setup-python@v5`, `github-script@v7`, `upload-artifact@v4` on moving tags | pinned to commit SHAs, linted by actionlint, security-audited by zizmor |
| Local gates | none | pre-commit: CSV line endings, em-dash in deliverables, pytest on touched code, node syntax on pages |
| Line endings | 11 of 13 tracked CSVs contain CR bytes (Python `csv.writer` defaults to `\r\n`) | new CR blocked; the repo-wide fix proposed separately (A5) |
| Em-dashes | present in README, all three pages, and the seed and processed CSVs | decision needed (A6), then gated |
| Tests | pytest suite plus two `--selftest` modules (`qc_gate.py`, `state_bounds.py`) | unchanged, plus ruff's syntax-class rules |
| Change review | none; a rebuild silently rewrites `data/processed/` | `data/processed/diff_summary.md` on every build, keyed on the stable `id` |
| Basemap | `tile.openstreetmap.org` hard-coded in two pages | OpenFreeMap vector tiles with a raster fallback (Part B, B6) |

---

## Part A: the CI and safety layer (port now)

Every source file below lives in `pricephillips/data-center-map` on `main`.

### A1. Pinned dependencies with uv

- **What:** create `requirements/ci.in` listing `requests`, `PyYAML`, `pytest` and
  `ruff`, then compile `requirements/ci.txt` with:
  ```
  uv pip compile requirements/ci.in --python-version 3.11 -o requirements/ci.txt
  ```
  Keep `requirements.txt` as the human-facing list, or have it reference the
  constraints file.
- **Workflows:** add a hash-pinned `astral-sh/setup-uv` step. Replace
  `pip install -r requirements.txt` with
  `uv pip install --system -c requirements/ci.txt -r requirements.txt`.
- **Lesson carried over:** in data-center-map, Dependabot bumped numpy and scipy to
  versions that need Python 3.12 while every workflow ran 3.11, and installs broke.
  If you pin anything with a Python floor, add a Dependabot `ignore` for it until
  the workflows move.
- **Check:** `uv pip install --system -c requirements/ci.txt -r requirements.txt`
  succeeds, and `python -m pytest -q` passes.

### A2. Dependabot

- **Copy:** `.github/dependabot.yml` from data-center-map. It has two ecosystems,
  `github-actions` at `/` and `pip` at `/requirements`, weekly on Monday, each with
  one `groups: all` entry so there is at most one PR per ecosystem per week.
- **Check:** the file parses as YAML, and Dependabot's first PRs appear the
  following Monday.

### A3. Workflow lint and pinned actions

- **Copy:** `.github/workflows/workflow-lint.yml`. It runs actionlint (blocking,
  with the runner's shellcheck) and zizmor (report-only, written to the job
  summary) on any change under `.github/workflows/`.
- **Pin every `uses:`** to a full commit SHA with a `# vX.Y.Z` comment. Resolve
  each SHA with `git ls-remote --tags https://github.com/actions/<name>`, using the
  peeled `^{}` line for annotated tags. Use the same releases data-center-map runs
  now; its pinned workflows list them. Dependabot keeps the SHAs current.
- **Expect these findings here:**
  - `unpinned-uses` on every action. Pinning fixes them.
  - `artipacked` (medium) on the checkouts. Add `persist-credentials: false` to
    `validate.yml`, which never pushes; leave `build-data.yml`, which does.
  - In `validate.yml`, `python -m playwright install --with-deps chromium` is fine
    on runners. In Claude sessions, Chromium is preinstalled at `/opt/pw-browsers`;
    never run `playwright install` there.
- **Check:** `actionlint` exits 0 with shellcheck installed. `zizmor --offline
  .github/workflows` reports 0 high findings.

### A4. ruff (syntax-class rules only)

- **Copy:** `ruff.toml`, which blocks only on `E9`, `F63`, `F7` and `F82`. In
  data-center-map, the default rule set found 123 style findings across 95 modules;
  blocking on those would have been noise.
- **Wire it:** add `ruff check .` to `validate.yml` before pytest. Optionally add a
  report-only `ruff check --select E,F --exit-zero --statistics . >> "$GITHUB_STEP_SUMMARY"`.
- **Check:** `ruff check .` passes on `main`.

### A5. pre-commit gates

- **Copy and adapt:** `.pre-commit-config.yaml` and `scripts/precommit_gates.py`.
  Every hook is `repo: local`, `language: system`. Keep these hooks:
  - `csv-lf`: blocks a CSV that *introduces* CR bytes relative to its committed
    version; a new CSV must be LF. Use this regression rule, not "fix every CSV".
    In data-center-map, a first run of the fix-everything version rewrote pipeline
    outputs, and those rewrites had to be reverted. Here, every file in
    `data/processed/` is regenerated by `build_seed_outputs.py`; normalize them
    only as part of A5b.
  - `deliverable-emdash`: scoped to deliverables. Here that means `index.html`,
    `dashboard.html`, `renewable-opposition-map.html`, `map-audit.html` and
    anything under `docs/` meant for clients. Turn it on only after A6.
  - `node-check`: `node --check` on inline `<script>` blocks. The gate module
    imports `scripts/check_inline_js.py`, so copy that file too.
  - `touched-tests` (replaces data-center-map's `touched-selftest`): this repo
    tests with pytest, so run `python -m pytest -q` when any `scripts/*.py` or
    `tests/*.py` is staged. The suite is small enough to run whole.
- **Drop for now:** `leak-audit` and `layer-audit`. This repo has neither module.
  See B1 for the layer declaration.
- **Check:** `pre-commit run --all-files` passes. `python
  scripts/precommit_gates.py --selftest` passes after you update its fixtures to
  the kept hooks.

**A5b (decision for Price): repo-wide LF.** Add `*.csv text eol=lf` to
`.gitattributes`, then run `git add --renormalize '*.csv'` once, and set
`lineterminator="\n"` on the writers in `build_seed_outputs.py`,
`build_sabin_seeds.py`, `fetch_moratorium_nation.py` and `promote_reviewed.py`.
Nothing here depends on CRLF. The pages fetch CSVs directly, and all three `parseCSV`
functions (`dashboard.html`, `index.html`, `map-audit.html`) treat `\r\n` and `\n`
alike, checked 2026-09-29. So do pandas and the `csv` module. Unlike data-center-map, this repo has no downstream consumer
fixed to the old bytes, so the change is cheaper here.

### A6. Em-dash policy (decision for Price)

data-center-map's constitution bans em-dashes in deliverables. Here they appear in
the README, all four pages, and in record text: `description` fields in the seeds
and processed files, transported from Sabin and Moratorium Nation.

- **Recommendation:** gate the pages and client docs, and leave record text as the
  source wrote it. Treat transported source content the way data-center-map's
  `INTERNAL_QUOTES` does: it is quoted, not composed.
- **If adopted:** replace em-dashes in the four HTML files and the README, then
  enable `deliverable-emdash` (A5) and the Vale `EmDash` rule (A7).

### A7. Vale for page and report prose

- **Copy:** `.vale.ini` and `styles/Hawthorn/` (`EmDash`, `Causal`, `Undefined`),
  plus the fixtures in `tests/fixtures/vale/`.
- **Adapt:**
  - Point `.vale.ini` at the dashboard copy you extract to markdown, and at
    `docs/coverage_audit.md` if it is client-facing.
  - Vale lints markdown, not HTML script strings, so headline sentences that live
    in JavaScript are not covered. Move them into a small JSON or markdown file if
    you want them linted.
  - `Causal` matters here as much as there: "caused by", "due to opposition" and
    "attributable to" should not describe why a project was cancelled.
  - Skip `Scorekeeping` unless you adopt a vocabulary audit. The outcome ladder is
    already shared.
- **Check:** each fixture produces exactly its intended alert.

### A8. Source-of-truth diff after every build

- **Port:** `master_diff.py` from data-center-map as `scripts/processed_diff.py`.
  It is simpler here, because every processed record has a stable `id`:
  - Run a daff comparison **keyed on `id`** for each of `restrictions.csv`,
    `contested_projects.csv` and `cases.csv`, between `HEAD~1` (via `git show`)
    and the working tree.
  - Write `data/processed/diff_summary.md` with, per entity, the count of added,
    removed and modified rows. Include a table of every change to `outcome`,
    `status`, `case_status`, `finality_evidence` and `severity_score` with both
    values, and up to 200 detail rows.
  - Keep the output path a module constant, not a flag.
  - Add a pytest test that builds two in-memory frames differing in one `outcome`
    cell and asserts the summary names the row and both values.
- **Wire it:** in `build-data.yml`, set `fetch-depth: 2` on checkout, run the diff
  after `build_seed_outputs.py`, `cat` it into `$GITHUB_STEP_SUMMARY`, and include
  it in the `git add`. Add `daff` to `requirements/ci.in`.
- **Check:** after a build that changes one seed row, the summary names that row.

### A9. Session startup hook

- **Copy:** `.claude/hooks/session-start.sh` and `.claude/settings.json`. Change the
  cloud-only install line to this repo's constraints:
  `uv pip install --system -q -c requirements/ci.txt -r requirements.txt pytest ruff daff vale`.
  Keep `playwright` out of it: Chromium is already in the image.
- **Check:** `CLAUDE_CODE_REMOTE=true ./.claude/hooks/session-start.sh` exits 0,
  then `python -m pytest -q` passes.

---

## Part B: later tools, adapted to this repo (take in this order)

Each row names the data-center-map spec that builds it first. Copy it after it
lands and has run there for a week.

| # | Tool | data-center-map spec | Use here | Trigger to start |
|---|---|---|---|---|
| B1 | Declared layers and one writer per file (`configs/layers.json`, `layer_audit.py`) | already built | `restrictions_seed.csv` has two writers, `fetch_moratorium_nation.py` and `build_sabin_seeds.py`, each owning rows by `source`. Declare that before a third writer appears. `pipeline_comparison.md` recommended this as item 5. | Now |
| B2 | Internet Archive Save Page Now 2 and CDX | 006 | Archive every `source_url` in `sources.csv` (28 today) and store the snapshot URL beside it. The provenance-first rule is only as durable as the links, and ordinance pages and county minutes move often. | Now; the source count is small, so one run covers it |
| B3 | Pandera schemas and a coverage-delta gate | 005 | A schema per entity: allowed `outcome`, `case_status`, `severity_score` 1 to 4, a state code, and `source_url` required. The delta gate fails the build when a column that was filled goes mostly blank, which catches upstream format changes in Moratorium Nation or Sabin. It complements `qc_gate.py` (row-level) with column-level checks. | After A-part lands |
| B4 | County FIPS and Census cartographic boundaries 2024 | 009 | Add `county_fips` to restrictions and projects so the map joins exactly, instead of on names (`pipeline_comparison.md` item 8). `renewable-opposition-map.html` loads the same plotly `geojson-counties-fips.json` that, in data-center-map, lacks 13 counties (Connecticut's nine planning regions 09110 to 09190, Alaska 02063, 02066 and 02158, and South Dakota 46102). Any restriction in those counties cannot paint here either. Replace it with the geometry spec 009 builds. | With B6 |
| B5 | trafilatura and datasketch | 006 | Only once an intake queue exists (`pipeline_comparison.md` item 2): trafilatura pulls article text and dates, and datasketch MinHash collapses several articles about one hearing into one candidate. | When GDELT or news intake starts |
| B6 | OpenFreeMap via MapLibre, with raster fallback (`basemap.js`) | 009 | Two pages hard-code `tile.openstreetmap.org`. OSM's tile usage policy discourages relying on its servers for production traffic and allows blocking heavy users without notice, which is a risk for a client-facing map. Copy data-center-map's `basemap.js` once spec 009 lands, including its fallback chain and attribution. | When 009 lands |
| B7 | Playwright plus axe | 009 | `smoke_frontend.py` already loads every page. Add `@axe-core/playwright` for accessibility, and reuse the date slider and side panel if the map needs them. | When 009 lands |
| B8 | civic-scraper, Legistar probe and OCRmyPDF | 007 | Meeting agendas are the main early signal for local renewable moratoria. Reuse data-center-map's `legistar_probe.py` pattern (a client list plus a 60-day miss cache) and add civic-scraper for the other platforms. | When local-meeting intake starts |
| B9 | CourtListener (already here), plus Congress.gov only if federal bills matter | 007 | The existing `extractors/courtlistener_renewables.py` stays the case source. Congress.gov applies only if federal siting bills become in scope. | Optional |
| B10 | docxtpl, WeasyPrint, Great Tables, Altair | 010 | County or project briefs from the processed data. | After 010 lands and a client asks |
| B11 | Datasette, sqlite-utils, Frictionless, Apprise | 011 | A per-client browsable database, and alerts driven by the A8 diff summary. | After 011 lands |

**Not for this repo:** the modeling stack from spec 008 (firthmodels, netcal, esda,
InterpretML, skops). `pipeline_comparison.md` already excludes predictive models
until there is a decided-project universe with dates.

---

## Part C: lessons from data-center-map, so they do not repeat

1. **Dedup against every file, not just the clean one.** data-center-map's
   harvester checked new URLs against the cleaned feed only. The cleaner held most
   harvested rows back, so the same articles were re-promoted every night: 4,099
   exact duplicate rows in four days. When this repo gets an intake queue, check
   candidates against the seeds *and* the review files.
2. **A config reason can break a gate.** `layer_audit.py` copies declared reasons
   into a CSV that the vocabulary audit blocks on. One word in a reason ("lost")
   failed every pipeline run after it. If you add B1, keep reason text free of any
   term a gate blocks.
3. **Static analysis must see the real write path.** Passing an output path as a
   CLI flag, or reassigning an output constant in a test, hid a writer from
   data-center-map's layer audit. Keep output paths as module constants, and patch
   them in tests with `setattr`.
4. **Shellcheck on runners differs from local.** actionlint was clean locally and
   reported 9 findings once shellcheck was installed, as it is on runners. Run
   actionlint with shellcheck before trusting a clean result. Deliberate word
   splitting (`git add $FILES`) gets a scoped `# shellcheck disable=SC2086` with a
   reason, not quotes.
5. **Bot commits land on PR branches.** Workflows that commit (like
   `build-data.yml`) push regenerated files to the branch under review. Merge the
   branch instead of rebasing. Resolve generated-file conflicts by rebuilding, and
   restore `main`'s copies of generated files before opening the PR, so the PR
   shows only the authored change.
6. **Pin to what CI already resolves.** Read the versions from the last green run's
   install log before writing the constraints file, and change nothing else in
   the same step.

---

## Checklist for the session that does Part A

- [x] A1 constraints file compiled; tests pass on it
- [x] A2 `dependabot.yml`
- [x] A3 `workflow-lint.yml`; every `uses:` SHA-pinned; actionlint 0 with shellcheck; zizmor 0 high
- [x] A4 `ruff.toml`; `ruff check .` in `validate.yml`
- [x] A5 pre-commit gates; `pre-commit run --all-files` passes
- [x] A5b LF decision recorded (applied, or deferred with a reason): applied 2026-09-29
- [x] A6 em-dash decision recorded; pages cleaned if adopted: gate pages and docs, record text left as sourced
- [x] A7 Vale fixtures pass
- [x] A8 `data/processed/diff_summary.md` produced by a build and committed by it (verified locally; first CI build pending)
- [x] A9 startup hook runs clean
- [x] `docs/pipeline_comparison.md` gains a "Round two (2026-09-29)" section pointing here
