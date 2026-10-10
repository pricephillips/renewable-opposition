# renewable-opposition

Research-grade ingestion, normalization, and dashboard pipeline for local opposition to renewable energy projects in the United States.

Inspired by the Columbia Sabin Center's work:
- *Opposition to Renewable Energy Facilities in the United States* (the data is built on the September 2026 edition, the 6th, with data through December 31, 2025)
- *Local laws and lawsuits targeting renewables becoming more prevalent*

---

## Provenance-first philosophy

Every record is traceable to a specific source: an ordinance, court docket, meeting minutes, news article or curated dataset. No record exists without a `source_url`, and `build_seed_outputs.py` refuses to build if one is missing. Each distinct source document gets a `source_id` (a hash of its normalized URL) and one row in `data/processed/sources.csv`, however many records cite it.

---

## Core entities

The ontology explicitly separates three types of opposition:

| Entity | What it captures |
|---|---|
| **Restrictions** | Local/state laws that materially constrain renewable deployment (moratoria, bans, setbacks, zoning amendments) |
| **Contested projects** | Project-level opposition events (hearings, permit denials, campaigns, cancellations) |
| **Cases** | Litigation and formal administrative proceedings |
| **Siting standards** | Every feature of a local wind or solar siting ordinance in NREL's 2025 databases (setbacks, height, noise, shadow flicker, lot size, prohibitions and the rest), one row per jurisdiction, technology and feature |
| **State policies** | State siting law, one row per state and policy: who decides and above what size, state preemption, local opt-out powers, state setback standards, state moratoria |

### Severity scale (1–4)
- **1** – Mild procedural friction
- **2** – Material burden, not obviously project-blocking
- **3** – Likely de facto ban (e.g., extreme setbacks, height limits)
- **4** – Explicit moratorium or outright ban

For map layers and headline stats, default to severity ≥ 3.

### Restrictions: how severity is assigned

- **Moratorium Nation** rows: an active or extended moratorium scores 4, a pending one 2.
- **Sabin** rows: a ban scores 4, and so does an in-force moratorium or an entry the 2026 edition labels "Ban / Moratorium" without saying which (`restriction_type` `ban_or_moratorium`). These score 3: a wind setback of at least half a mile or 5× turbine height, any wind height limit, a wind noise limit of 35 dBA or less, and a solar or storage setback of at least 1,000 ft. Every other restricting mechanism scores 2, and a pending instrument is capped at 2. Each row's `severity_basis` column names the rule that set its score.

- **NREL** rows: the same rules (`restriction_severity`) run on the jurisdiction's combined ordinance features; see "NREL siting ordinance databases" below.

`scripts/build_sabin_seeds.py` documents every rule, and every row it holds back goes to `data/review/sabin_restrictions_review.csv` with the reason.

### Contested projects: outcome and severity

`contested_projects` rows carry an `outcome` from the outcome ladder shared with `data-center-map`: `blocked_confirmed` / `blocked_unverified`, `restricted_conditional`, `advanced_confirmed` / `advanced_unverified`, `pending`, plus `needs_review` when the source status can't be mapped. A status label from the source is never enough for `*_confirmed`; that takes independent evidence, which today means a seeded court case, linked to the same record, that was decided the same way. `finality_evidence` records which applies: `court_ruling: <case>`, `outcome_label_only` or `none`. Their `severity_score` measures how hard opposition hit the project:

- **4** – Project blocked (cancelled or permit denied)
- **3** – Litigation filed, project not (yet) blocked
- **2** – Resident or organized opposition, no litigation, not yet approved
- **1** – Project advanced despite opposition, no litigation

`scripts/build_sabin_seeds.py` documents the exact status → outcome mapping.

Each contested project is also matched to the federal plant inventories (see "Federal plant inventories" below). A strong match publishes what the inventory records for the plant (`facility_status`: operating, under construction, planned, cancelled or retired) beside the outcome, and flags a contradiction in `facility_conflict`. It never changes the outcome.

### Cases: status and verification

Each case row links to the project (or restriction) it concerns through `source_record_id`. One case can therefore appear twice if it concerns two records. `case_status` uses one of:

- `pending`
- `dismissed`
- `ruled_for_developer`
- `ruled_for_opposition`, meaning the ruling favored the project's opponents
- `settled`
- `withdrawn`

`severity_score` defaults to 3, the contested-projects score for "litigation filed".

A case goes into `cases_seed.csv` only once a court record names the case and its court: an opinion, a docket, or a court's own page, found on CourtListener, Justia, govinfo, a court website or an equivalent case-law host. Promotion is automatic as soon as the candidate row has `case_name`, `court`, `court_level` and that record's URL in `case_source_url` (see Reviewing candidates). The row's `reviewer_notes` say how it was found. Partial finds stay in `data/review/cases_candidates.csv` as `review_status=lead`, with what is known so far.

## Counting and verification

**Count instruments, not rows.** A seed row is one technology of one
instrument, so a moratorium on solar, wind and battery storage is three rows.
Every processed row carries an `instrument_id` (`scripts/classify.py`; a promoted
queue row's technology rows share `queue:<queue_id>`), and the
numbers to quote are in `data/processed/headline_metrics.md` / `.json`, counted
by instrument.

**Scope.** Restrictions carry a `scope`: `renewables_only`, or
`multi_sector_data_centers` when the instrument also covers data centers
(Moratorium Nation's `sectors`, or the record's text). Multi-sector instruments
are published and reported beside the renewables figure, never folded into it.
A record whose text names data centers and no renewable technology
(`data_center_only`) is quarantined by the QC gate for review.

**Evidence level.** Every row carries an `evidence_level`, best first:
`primary_source`, `confirmed`, `court_record`, `compiled_record`,
`compiled_flagged`, `report_citation`. The headline metrics break every count
down by it. `primary_source` and an outcome's `confirmed` both need a source
someone actually read; see "How the evidence was seen" below.

**The evidence standard.** Anything on the books (an ordinance, resolution, moratorium, zoning amendment or state law) counts as verified only against the instrument itself, or the minutes or official record that adopted it. A news article or a compiled tracker locates it but does not verify it. Opposition activity (groups, petitions, hearings, campaigns, project fights) may rest on a news article. Every published row carries a derived `verification` field (`scripts/classify.py`) that applies it:

- Restrictions: `verified` when `evidence_level` is `primary_source` (the instrument or its minutes were opened or read in an archived copy), `located` when a primary source URL is attached but was seen only as search-index text, and `unverified` otherwise.
- Contested projects: `verified` when the outcome or event is backed by a news article or other document that was opened or archived (a resolution row, or a promoted queue row whose `source_kind` is news or an official record), or by a court ruling; `unverified` when only a compiled report or tracker is behind it.
- Cases: `verified` when a court record is attached.

`headline_metrics` counts `verification` by instrument for each entity, and for restrictions within each scope. It also breaks every count down by source (Sabin 2026, Sabin 2025 records not in the 2026 edition, NREL, Moratorium Nation, review queue), and reports county coverage: how many counties have any published record, how many have a documented negative check, and how many have neither.

**Closing the gaps.** Each build ranks what to check next in
`data/review/outcome_worklist.csv` (unconfirmed project outcomes, blocked and
advanced claims first) and `data/review/restriction_worklist.csv` (instruments
without a primary source, weakest evidence first). Each row names the evidence
that would settle it and a search query to start from. Record what you find in:

- `data/review/outcome_resolutions.csv`: `source_record_id`, the `outcome` the
  evidence supports, and a required `evidence_url` (plus `evidence_date`,
  `evidence_note`, `reviewer`, `access`, `archived_url`). With `access` of
  `opened` or `archived`, the build sets the outcome, marks
  `finality_evidence` as `resolution: <url>` and rescores severity.
- `data/review/restriction_sources.csv`: `instrument_id`, the
  `primary_source_url` (ordinance, resolution, minutes), a `verdict` of
  `confirmed` or `contradicts`, and `access`. A confirmed instrument whose
  source was opened or archived becomes `primary_source`; a contradicted one
  is quarantined.

**How the evidence was seen.** Every row of `restriction_sources.csv`,
`outcome_resolutions.csv`, `place_overrides.csv` and `queue.csv` has an
`access` column:

- `opened`: the page or document itself was read.
- `archived`: an Internet Archive copy was read. Its URL goes in
  `archived_url`.
- `snippet`: only search-index text was seen, for example because the
  session's network blocked the page.

Only `opened` and `archived` evidence upgrades a record. A `snippet` row is
kept and its URL attached, but nothing moves:

- A restriction keeps its evidence level. Its `primary_source_url` is
  published with `primary_source_access` = `snippet`, which pages show as
  "source located, not yet read". A snippet `contradicts` verdict is a QC
  finding, not a quarantine.
- An outcome keeps its `*_unverified` (or other) value and severity, and
  `finality_evidence` reads `lead: <url>`. Each contested project with a
  resolution row also carries `resolution_url` and `resolution_access`.
- A place override still places the record, since placement is low-stakes,
  and carries `placement_access` so a profile can say how the county was
  found.

**Reading sources that block plain fetches.** Many county sites and newspapers answer a script with HTTP 403. Two open-source tools, installed outside the repository and with no usage cap, read most of them: Crawl4AI (a local headless Chromium that returns the page as Markdown; pin `playwright==1.56.0` in a cloud session so it uses the pre-installed browser at `/opt/pw-browsers`) and, for scanned PDFs, `pdftoppm` plus RapidOCR (`rapidocr_onnxruntime`). Neither is a reader service or proxy: the page is fetched directly, and a row read this way is `opened`.

A snippet row stays on the worklists below, with its URL in `located_url`,
until someone opens or archives the source and changes `access`.
In Claude Code, `/verify-evidence` (`.claude/commands/verify-evidence.md`)
runs this process: it tries to read each snippet row's source, corrects the
row against it, and then works the worklists.

Pushing any of these files rebuilds the published data. A resolution that
names a record that does not exist, has no evidence URL, or has a blank or
unknown `access` (or `archived` with no `archived_url`) stops the build.

**Column coverage.** `scripts/coverage_delta.py` fails the build when a
well-filled column loses more than 20 percent of its values against the
previous commit, which is what an upstream format change looks like. A
deliberate drop is declared in `config/coverage_exceptions.json`.

---

## Sources and editions

### Sabin Center, September 2026 edition

The Sabin rows come from the September 2026 edition of *Opposition to Renewable Energy Facilities in the United States* (published September 2, 2026; at least 888 state and local restrictions and 567 contested projects). `scripts/fetch_sabin_edition.py` stores the Sabin Center's own export of the edition's entries and its web edition (oppositionreport.org) in `data/raw/`, with the URL, date and SHA-256 of each file in `data/raw/manifest.csv`. The report PDF itself could not be downloaded from a script (a Cloudflare challenge on Columbia's Scholarship Archive, and no reachable archive copy); its URL is in the manifest so it can be added by hand. `scripts/extract_sabin_edition.py` writes `data/renewable_opposition_records_2026-09.csv` in exactly the columns of the June 2025 extraction, and `docs/sabin_2026_reconciliation.md` compares the extracted counts, per state, with the totals the Sabin Center publishes.

The edition renumbers its entries. `scripts/sabin_crosswalk.py` maps every 2025 `REC-` id onto its 2026 entry in `data/review/sabin_edition_crosswalk.csv`, by state, jurisdiction or project name, technology and mechanism. Anything short of one clear candidate is `ambiguous` and waits for a reviewer (`review_decision`); nothing is guessed. A matched record keeps its id, its `instrument_id`, its published `id` (`pinned_id`) and every review row attached to it. A new entry gets a new id (`S26R-` for restrictions, `S26P-` for projects). A 2025 record missing from the 2026 edition is never deleted: it keeps its 2025 row, marked `edition_status` `not_in_latest_edition`, and goes on `data/review/sabin_edition_worklist.csv`, since it may have been lifted or merged. Where the 2026 edition changes a status, the new one is published and `diff_summary.md` lists the old and new values.

### NREL siting ordinance databases

Siting standards and the restrictions marked NREL come from NREL's *U.S. Wind Siting Regulation and Zoning Ordinances (2025)* (doi.org/10.25984/3363758) and *U.S. Solar Siting Regulation and Zoning Ordinances (2025)* (doi.org/10.25984/3363739), both licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). The repository reshapes NREL's rows into `siting_standards` and derives restrictions from them; that is the only change. NREL compiled the data with large language models and asks that it be validated, so every NREL row is `compiled_flagged` and `unverified` until its ordinance is read.

`scripts/fetch_nrel_ordinances.py` stores both spreadsheets in `data/raw/` and refuses a file whose sheets, headers or feature names differ from what the code reads. `scripts/nrel_ordinances.py` makes a jurisdiction and technology a restriction only by the shared rules: an outright prohibition or moratorium, or `restriction_severity` scoring its combined restricting features (setbacks from non-participating structures and property lines, height, noise, project and lot size caps, coverage, shadow flicker, prohibited districts, prohibitions) at 2 or more. Every other feature stays in `siting_standards` only. An NREL restriction that agrees with a Sabin, Moratorium Nation or review-queue restriction for the same jurisdiction and technology is not published twice; one that disagrees is kept beside it and listed in `data/review/nrel_restriction_conflicts.csv`.

Before relying on NREL, `scripts/nrel_sample.py` draws a random sample of 60 NREL restrictions with a fixed, recorded seed, a reviewing agent checks each sampled feature against its ordinance (`data/review/nrel_sample_review.csv`, under `docs/AGENT_REVIEW.md`), and `docs/nrel_sample_report.md` reports the error rate by feature. A sampled restriction whose every feature passed becomes `verified`; the rest stay on the restriction worklist.

### Federal plant inventories

What became of a contested project after the fight is often on record in three public-domain federal datasets:

- **EIA-860M**, the Preliminary Monthly Electric Generator Inventory (https://www.eia.gov/electricity/data/eia860m/): every generator of 1 MW or more that is operating, planned, under construction, retired, or cancelled or indefinitely postponed.
- **USWTDB**, the U.S. Wind Turbine Database (USGS, LBNL and ACP; https://energy.usgs.gov/uswtdb/): every built turbine, located from imagery.
- **USPVDB**, the U.S. Large-Scale Solar Photovoltaic Database (USGS and LBNL; https://energy.usgs.gov/uspvdb/): every ground-mounted PV facility of 1 MW or more.

`scripts/fetch_facilities.py` keeps their solar, wind, battery storage and geothermal plants in `data/reference/facilities.csv`, one row per plant and status, each placed in its county by its coordinates. The source files are not committed (the EIA workbook is about 14 MB a month); `data/reference/facilities_manifest.csv` records each file's URL, release and SHA-256. A file whose sheets or headers change is refused. The Build dashboard data workflow refreshes them on the 3rd of each month, after EIA's monthly release.

`scripts/facility_matches.py` matches each contested project to a plant on the distinctive words of its name ("Ripley Road Solar Project" and EIA's "Ripley" are both `ripley`), within the project's state and technology:

- **Strong:** the same distinctive words and a plant in one of the project's counties; or one name contained in the other, in the project's county, with capacities that agree. The strong candidates must all be one plant, and a plant more than three times larger or smaller than the record's capacity is never strong.
- **Possible:** the same words in another county, or a contained name in the project's county.

Checked against the 35 projects whose EIA plant a reviewer had already identified by hand, the matcher finds 28 and names no wrong plant; the 7 it misses have two plants of one name (phases) or a plant named differently from the project.

A strong match publishes `facility_match`, `facility_ids`, `facility_name`, `facility_status`, `facility_capacity_mw`, `facility_year`, `facility_latitude`, `facility_longitude`, `facility_note` (the inventory entry in words) and `facility_conflict` on the project row. The maps place a matched project at its plant. `data/review/facility_matches.csv` lists every strong and possible match, conflicts first (a project published as blocked whose plant is operating; a pending one whose plant is built or cancelled), with a drafted outcome, evidence URL, date and note. A reviewer who checks the inventory entry copies them into `outcome_resolutions.csv`; nothing changes an outcome until then. The inventories say what became of a plant, never whether opposition had anything to do with it.

### State siting law

`state_policies` rows are drafted in `data/review/state_policies_candidates.csv` from Lawrence Berkeley National Laboratory's *Laws in Order: An Inventory of State Renewable Energy Siting Policies* (June 2024, Regulatory Assistance Project; CC BY-NC 4.0) and from the Sabin Center's state-level entries, and each is checked against the statute itself, never the inventory, including amendments since 2024. A row publishes only with a recorded review by someone other than its drafter who read the statute; the rest are listed with the reason in `data/processed/state_policies_held.csv`. `data/review/sabin_state_level_dispositions.csv` says what became of each state-level Sabin row.

`data/review/ohio_sb52_worklist.csv` (`scripts/ohio_sb52_worklist.py`) lists every Ohio county with the records already held, for checking local opt-outs under Ohio SB 52 (Ohio Rev. Code 303.58 and 303.62). `docs/ohio_sb52_first_pass.md` records the first pass on 10 counties and the leads it left.

### Agent review

`docs/AGENT_REVIEW.md` sets out how a reviewing agent checks a record and how the review is recorded. Nothing drafted here publishes without a recorded review, and nobody reviews their own work: a review-queue row drafted by an agent carries `review_status` `awaiting_review`, which holds it back until a different reviewer confirms it.

---

## Outputs

Canonical data lives in `data/processed/` as both CSV and JSON:

```
data/processed/
  restrictions.csv / restrictions.json
  contested_projects.csv / contested_projects.json
  cases.csv / cases.json
  sources.csv / sources.json        ← one row per source document, with its Internet Archive snapshot (archived_url)
  quarantine.json                   ← rows the QC gate blocked, with their issues
  qc_report.md                      ← every QC finding by code and severity
  diff_summary.md                   ← what the last build changed, keyed on id
  headline_metrics.md / .json       ← the numbers to quote, counted by instrument
  coverage_delta.md                 ← column fill rates against the previous commit
  group_registry.csv                ← opposition groups with their sources (scripts/group_registry.py)
  siting_standards.csv / .json      ← NREL ordinance features by jurisdiction, technology and feature (the JSON leaves out NREL's long summary text)
  state_policies.csv / .json        ← state siting law verified against the statute
  county_summary.csv / .json        ← one row per county: records counted by instrument, and coverage (record, negative_check or none)
  datapackage.json                  ← every published table: rows, fields and types, what derived fields mean, sources and licenses
```

The entity JSON files hold one record per line: still one JSON document, and a changed record is one changed line in a diff. A consumer that needs only per-county figures reads `county_summary`, about 3,200 rows, instead of the entity files. It lists every 2024 county, including those with nothing published, and counts a record in every county it touches (`county_fips_all`).

Every record has a stable `id` that doesn't change between runs, plus the `source_id` of its source. In the JSON files, each record also has a `sources` array that the dashboard renders as links.

Both formats are required. JSON is used by downstream apps and dashboards; CSV is the human-readable source of truth.

### National database

`scripts/build_database.py` loads everything in `data/processed/`, with the county boundary file, the negative checks and the data center events, into one DuckDB file, `data/db/renewable_opposition.duckdb`, normalized around the instrument and the county (`db/schema.sql`, `db/load.sql`, `db/views.sql`). The database is derived, and the `.duckdb` file is never committed. `--publish` also writes one Parquet file per table and view in `data/db/parquet/`, and `data/db/state_summary.json` and `data/db/county_summary.json` (each view as `columns` and `rows`); the Build dashboard data workflow runs it and commits those files so GitHub Pages serves them. Their bytes depend only on the data, so a build that changes nothing commits nothing. Before it writes, the script recomputes the headline numbers from the database and compares them with `headline_metrics.json`; any difference stops it. Its `v_county_summary` view gives every county a `coverage_status`: `has_records`, `checked_none` or `not_examined`. Design and roadmap: `docs/national_database_design.md`.

```bash
python scripts/build_database.py --publish
```

---

## Repository structure

```
renewable-opposition/
├── README.md
├── requirements.txt
├── config/
│   ├── sources.yaml                        ← crawler source registry (fetch.py)
│   └── source_registry.csv                 ← dataset/tracker registry
├── data/
│   ├── renewable_opposition_records.csv    ← Sabin June 2025 extraction (read through the edition crosswalk)
│   ├── renewable_opposition_records_2026-09.csv ← Sabin September 2026 extraction (input to build_sabin_seeds.py)
│   ├── reference/
│   │   ├── data_center_events.csv          ← local data center events from data-center-map (sync_data_center_map.py)
│   │   └── facilities.csv                  ← EIA-860M, USWTDB and USPVDB plants (fetch_facilities.py), with facilities_manifest.csv
│   ├── seed/
│   │   ├── restrictions_seed.csv           ← Moratorium Nation + Sabin local restrictions
│   │   ├── contested_projects_seed.csv     ← Sabin contested-projects section
│   │   └── cases_seed.csv                  ← cases with a court record (via promote_reviewed.py)
│   ├── review/
│   │   ├── cases_candidates.csv            ← litigated projects/restrictions awaiting docket research
│   │   ├── sabin_restrictions_review.csv   ← Sabin restriction rows held back, with reasons
│   │   ├── coverage_gaps.csv               ← moratoria found in only one source
│   │   ├── place_overrides.csv             ← reviewer counties with evidence (hand-edited)
│   │   ├── group_candidates.csv            ← groups named in seed or Sabin text, awaiting a read news URL (hand-edited)
│   │   ├── group_review.csv                ← groups held back for want of a source (written by the build)
│   │   ├── negative_checks.csv             ← "checked, nothing found" results per county (hand-edited)
│   │   ├── profile_requests.csv            ← county code and date of every profile run (site_profile.py)
│   │   ├── negative_check_worklist.csv     ← profiled counties still to check (written by the build)
│   │   ├── adjacency_worklist.csv          ← unchecked neighbors of a new restriction (adjacency_worklist.py)
│   │   ├── facility_matches.csv            ← projects matched to federal plant inventories, conflicts first (written by the build)
│   │   └── queue.csv                       ← extractor candidates (written by parse.py)
│   ├── raw/                                ← fetched documents keyed by content hash (fetch.py)
│   ├── processed/                          ← canonical CSV + JSON outputs
│   └── db/                                 ← national database: Parquet + state/county summaries (committed), .duckdb (not)
├── db/                                     ← national database schema, load and views (build_database.py)
├── docs/
│   ├── coverage_audit.md                   ← Sabin vs Moratorium Nation recall
│   ├── national_database_design.md         ← design for the national database and dashboard
│   └── pipeline_comparison.md              ← practices adopted from data-center-map, and what's next
├── scripts/
│   ├── run_pipeline.py                     ← runs the stages in order (build; refresh re-fetches the inputs first)
│   ├── fetch_facilities.py                 ← EIA-860M, USWTDB, USPVDB -> data/reference/facilities.csv (schema guard)
│   ├── facility_matches.py                 ← contested projects -> plants (called by the build)
│   ├── county_summary.py / datapackage.py  ← county_summary and datapackage.json (called by the build)
│   ├── common.py                           ← shared helpers (state codes, technology vocabulary, source ids)
│   ├── fetch_moratorium_nation.py          ← refreshes the Moratorium Nation rows of restrictions_seed.csv
│   ├── fetch_sabin_edition.py              ← stores the Sabin 2026 edition files in data/raw/
│   ├── extract_sabin_edition.py            ← data/raw/ -> renewable_opposition_records_2026-09.csv + reconciliation
│   ├── sabin_crosswalk.py                  ← 2025 REC- ids -> 2026 entries (data/review/sabin_edition_crosswalk.csv)
│   ├── fetch_nrel_ordinances.py            ← stores NREL's wind and solar spreadsheets (schema guard)
│   ├── nrel_ordinances.py                  ← NREL restrictions in restrictions_seed.csv, conflicts worklist
│   ├── nrel_sample.py                      ← NREL accuracy sample: draw, apply, report
│   ├── siting_standards.py / state_policies.py ← the two new published entities (called by the build)
│   ├── ohio_sb52_worklist.py               ← one row per Ohio county for SB 52 checks
│   ├── build_sabin_seeds.py                ← Sabin rows of restrictions + contested projects, review files
│   ├── coverage_audit.py                   ← writes docs/coverage_audit.md + coverage_gaps.csv
│   ├── fetch.py                            ← crawler: sources.yaml -> data/raw/
│   ├── parse.py                            ← runs scripts/extractors/<source_id>.py -> review/queue.csv
│   ├── extractors/courtlistener_renewables.py
│   ├── promote_reviewed.py                 ← complete review rows -> seed CSVs (run by build-data.yml)
│   ├── qc_gate.py                          ← record-level QC gate + quarantine (run by the build)
│   ├── state_bounds.py                     ← state bounding boxes (copied from data-center-map)
│   ├── snapshot_manifest.py                ← dated, hashed record of each published output
│   ├── smoke_frontend.py                   ← loads every page headless; fails on page errors
│   ├── build_seed_outputs.py               ← validates seeds, runs QC, writes processed/
│   └── build_database.py                   ← processed/ -> national DuckDB database + Parquet, checked against headline_metrics
└── tests/                                  ← pytest suite (run in CI by .github/workflows/validate.yml)
```

---

## Quickstart

```bash
pip install -r requirements.txt
python scripts/run_pipeline.py              # build: promote, build, worklists, gates, diff (what CI runs)
python scripts/run_pipeline.py refresh      # re-fetch every input and rebuild the seeds first
python scripts/run_pipeline.py --list       # the stages, in order
python -m pytest -q
```

The stages one by one, in the order `run_pipeline.py refresh` runs them:

```bash
python scripts/fetch_moratorium_nation.py   # refresh Moratorium Nation restrictions (run before the Sabin build: it dedups against them)
python scripts/fetch_sabin_edition.py       # store the Sabin 2026 edition files in data/raw/
python scripts/extract_sabin_edition.py     # extract them, and reconcile the counts
python scripts/sabin_crosswalk.py           # map 2025 ids onto 2026 entries
python scripts/build_sabin_seeds.py         # rebuild Sabin restrictions + contested projects
python scripts/fetch_nrel_ordinances.py     # store NREL's spreadsheets (refuses a changed layout)
python scripts/nrel_ordinances.py           # NREL restrictions (run after the Sabin build: it dedups against them)
python scripts/fetch_facilities.py          # EIA-860M, USWTDB, USPVDB plants (refuses a changed layout)
python scripts/promote_reviewed.py          # complete review rows into the seeds (the build stages start here)
python scripts/build_seed_outputs.py        # validate and write data/processed/
python scripts/verification_worklist.py     # rank what to verify next
python scripts/adjacency_worklist.py        # neighbor watch
python scripts/coverage_delta.py            # column coverage gate
python scripts/snapshot_manifest.py         # dated, hashed record of each output
python scripts/processed_diff.py            # what the build changed
```

`python scripts/coverage_audit.py` (the cross-source audit) is run by hand, outside the stages.

CI installs under the pinned constraints in `requirements/ci.txt`
(`uv pip install --system -c requirements/ci.txt -r requirements.txt`). For the
same checks locally (CSV line endings, em-dashes in pages, inline script
syntax, ruff, pytest, Vale), run `pipx install pre-commit && pre-commit install`
once.

Every cited source gets an Internet Archive snapshot once a week
(`.github/workflows/source-archive.yml`, `scripts/source_archive.py`; state in
`data/source_archive.csv`). The dashboard links the archived copy beside the
live one. `config/layers.json` declares which script writes each data file, and
`scripts/layer_audit.py` checks that declaration against the code.

### Reviewing candidates

Promotion is automatic. The Build dashboard data workflow runs `scripts/promote_reviewed.py` before every build and commits what it promotes, so nobody promotes anything by hand. A row goes into its seed as soon as it is complete; `review_status` only holds a row back (`rejected`, or `awaiting_review` for a row drafted by an agent or person and not yet reviewed by someone else), and a promoted row is marked `promoted`. A row promoted without `review_status=confirmed` says so in its seed notes ("promoted automatically ... not reviewed by hand"), and every promoted row still passes the QC gate. Nothing is filled in to make a row complete: an incomplete row stays where it is, and the workflow's summary lists what it lacks.

- **Cases.** `data/review/cases_candidates.csv` lists every project or restriction the source says was litigated. A candidate is complete once `case_name`, `court`, `court_level` and an http(s) `case_source_url` are filled from a court record (a docket, an opinion, or a court's own page). If one project has several cases, duplicate the row. Rebuilding with `build_sabin_seeds.py` keeps these edits.
- **Queue.** Extractors such as the CourtListener one, and anyone adding a candidate by hand, write to `data/review/queue.csv`. A row is complete once every field its seed requires is filled, including an http(s) `source_url`. Queue columns are mapped onto the seed's own columns (`adopted_date` becomes `date_enacted_iso`). A contested-project candidate with no typed `severity_score` is scored by the same rule as Sabin rows (`project_severity`), from the outcome its status maps to. A promoted row adds only these columns to its seed: `queue_id` (the link back to its queue row, assigned once and stored; rows from one article and place get distinct keys), `pinned_id` (its published id), and the evidence columns `source_kind`, `source_access` (contested projects and cases) or `primary_source_url`, `primary_source_access`, `primary_source_archived_url` and `primary_source_verdict` (restrictions). Set `review_status=rejected` to keep a row out.
- **Restriction status.** A restriction candidate needs a `status`: `active`, `extended`, `pending`, `lifted` or `expired`. A blank status stops its promotion and the workflow summary says so. A `lifted` or `expired` instrument is not in force and is not published; it stays in the queue.
- **What the source is.** `source_kind` says what `source_url` is: `instrument`, `minutes`, `official_copy` (an official copy of either), `court_record`, `news`, `tracker` or `other`. A restriction whose `access` is `opened` or `archived` and whose `source_kind` is `instrument`, `minutes` or `official_copy` publishes with that URL as its primary source, so it is `evidence_level` `primary_source` and `verification` `verified`. A restriction backed only by a news or tracker URL publishes as `unverified`.
- **Corrections after promotion.** Every run re-syncs each row whose `review_status` is `promoted`: it recomputes the seed rows from the current queue row (description, `mechanisms`, `mechanism_detail`, `severity_basis`, `restriction_type`, status, severity by `restriction_severity` and `driving_type`, source and evidence), and the workflow summary lists every field that changed. The seed rows keep their published id (`pinned_id`), a technology the queue row no longer lists loses its row, and a new one gains a row.
- **How the queue source was seen.** Every queue row has `access` (`opened`, `archived` with its `archived_url`, or `snippet`). The CourtListener extractor writes `snippet`, because a search API result is index text. A `snippet` row is never promoted: it waits, and the workflow summary says its source has to be opened or archived first. A blank or unknown `access` is reported the same way.
- **Restriction candidates.** List every mechanism in `mechanisms`, separated by semicolons, in the vocabulary of `build_sabin_seeds.MECHANISM_TYPE` (for example `setback; height limit; noise limit`). Put their values (distances, dBA and hours, acreage, caps) in `mechanism_detail`; a promoted row carries it in the seed's `long_description`. On promotion, `severity_score`, `severity_basis` and `restriction_type` are computed per technology by the same rules as published Sabin rows (`restriction_severity`, `driving_type`), run on `mechanism_detail` plus `description`. A `status` of `pending` caps the score at 2, as for Sabin rows. A typed `severity_score` is optional: one that disagrees with the computed score is reported as a conflict and the row is not promoted. An unknown mechanism stops the run before anything is written.

Outputs will be written to `data/processed/`.

---

## Data center activity

The same county governments often act on both data centers and renewables. `scripts/sync_data_center_map.py` reads `pricephillips/data-center-map`'s `master_opposition.csv` from `--dc-map`, or the `RO_DATA_CENTER_MAP` environment variable, by default `../data-center-map/master_opposition.csv`, and writes `data/reference/data_center_events.csv`: `state`, `county`, `county_fips`, `jurisdiction`, `date`, `event_type`, `status`, `summary`, `source_urls`, `opposition_groups`, `dc_row_ref` (the source row and its headline).

```bash
python scripts/sync_data_center_map.py --dc-map ../data-center-map/master_opposition.csv
```

Each row is placed by this repository's own county logic (`classify.county_fips_all`: the county named, a multi-county name, coordinates, the Census place index); a row that places nowhere is left out. Also left out: `signal_harvest_auto` rows with no state, no type, or a generic or unrelated headline (fewer than four words, or text that names no data center), and any row with no type whose text names no data center.

Profiles have a "Data center activity" section for the county and its neighbors: date, type, status, a one-line summary and source links, labelled "verified" only when a source is the instrument or official minutes (a government host and a document path, or a municipal records host such as Legistar) and "reported" otherwise. These events never enter the renewable counts.

Attribution: most data-center-map rows come from Data Center Tracker (https://datacentertracker.org), whose data is licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). `data_center_events.csv` reuses those rows' summaries, sources and groups, shortened to one line and placed by this repository's county logic; that adaptation is the only change. Their opposition groups, with their source URLs, feed the group registry.

## Neighbor watch

A county that adopts a moratorium or siting rules is often followed by its neighbors. `scripts/adjacency_worklist.py`, run by the Build dashboard data workflow, takes every published restriction instrument enacted in the last 18 months (`date_enacted_iso`; an extension counts only through that date, since no separate extension date is recorded) and lists each adjacent county, across state lines (`geo.neighbors`), that has no published restriction and no `negative_checks.csv` row covering restrictions. It writes `data/review/adjacency_worklist.csv`: `county_fips`, `state`, `county`, the triggering instrument (`trigger_instrument_id`, `trigger_jurisdiction`, `trigger_state`, `trigger_type`, `trigger_status`, `trigger_date`, `trigger_technologies`) and a `suggested_query`, newest trigger first. It is a worklist only and never publishes anything.

## Opposition groups

Contested projects (the seed and `data/review/queue.csv`) carry `opposition_groups`, a semicolon list of the groups a record names, and `group_sources`, a semicolon list of one or more URLs (news articles) that name them. Every URL on a row applies to every group on the row. `scripts/group_registry.py`, run by every build, writes `data/processed/group_registry.csv`: `canonical_id`, `canonical_name`, `variants`, `n_projects`, `states`, `first_seen`, `last_seen`, `source_urls`. Case, punctuation, a leading "The", an "Inc." or "LLC" suffix and a leading "Citizens for" do not make a new group; "Stop", "Save" and "No" prefixes are kept. Generic labels such as "local residents" are not groups. The registry also takes the groups named in `data/reference/data_center_events.csv`, with their source URLs.

A group with no source URL is held for review, never published: the build blanks it from the published row and lists it in `data/review/group_review.csv`. No per-group outcome or success rate is computed or published.

`data/review/group_candidates.csv` (hand-edited) holds groups named in the seeds' and Sabin records' text, one per row: `source_record_id`, `entity`, `state`, `record_name`, `group_name`, `excerpt`, `group_source_url`, `access`, `archived_url`, `note`. A row publishes once `group_source_url` is a news article naming the group and `access` is `opened` or `archived`; until then it is held.

## Site profiles

`scripts/site_profile.py` lists everything the data records about one county.
It is descriptive only: no scores and no predictions.

```bash
python scripts/site_profile.py --state KS --county Cherokee
python scripts/site_profile.py --fips 19113 --radius 40 --notes "what local contacts report"
python scripts/site_profile.py --sites sites.csv --out profiles.md   # columns: name,state,county,fips,lat,lon,notes
python scripts/site_profile.py --state KS --county Cherokee --no-local   # leaves out local knowledge
python scripts/site_profile.py --fips 19113 --verified-only               # only restrictions verified against the instrument
```

Each profile has these sections:

- **State framework:** at the top, the state's siting law from `state_policies`: who decides and above what size, any local opt-out power, state setback standards and other state rules, each with its verification label. Rows still held for review are shown as not verified, with the reason.
- **In the county:** published records whose `county_fips_all` includes the county.
- **Local knowledge on file:** the county's rows in the local-knowledge file (outside the repository, see below), printed as entered, each labelled "reported, not verified".
- **Adjacent counties:** the same for every county that shares a border, across state lines, plus one line for each pending review-queue candidate there.
- **Local siting standards:** the NREL `siting_standards` rows for the county and its neighbors, one line per jurisdiction and technology, with NREL's attribution. Rows not checked against the ordinance are labelled unverified.
- **Within a radius:** optional.
- **Not published:** rows the build held back that name the county (lifted or duplicate Sabin rows, QC quarantine, coverage gaps, case candidates), and every `data/review/queue.csv` candidate of any entity type with `review_status` = `pending` that concerns the county. A candidate concerns the county when its `county` is the county's name, its `municipality` is a town the place index puts in this county alone, or its text says "<Name> County". Each shows its entity type, technology, mechanisms and their values, adoption date and `access`, labelled "pending review, not published".
- **Named in the text:** records placed elsewhere whose text names the county.
- **Flags:** moratoria past their end date, report-only evidence, same-name counties in other states, states with no contested-project coverage, and one "Evidence still to read" flag that counts the items the profile shows whose source was seen only as search-index text (a primary source, an outcome source, a county placement or a pending candidate with `access` = `snippet`).

Every restriction line says in plain words how it stands under the evidence standard: verified against the instrument or the minutes that adopted it, instrument located but not yet read, or not verified. Every contested-project line says whether a news article or court record that was read backs it. `--verified-only` leaves restrictions that are not verified out of the county and adjacent sections and states how many it left out, split into located and unverified. It also leaves out unverified siting standards and state framework rows still held for review, and counts them.

Each contested-project line lists its groups and the sources that name them, and each profile has a "Groups active nearby" line: every sourced group on a record the profile shows, where it was active, and its sources.

Every record line names its sources. A record with a primary source prints it on the "Source" line with how it was seen ("located, not yet read" for `snippet`), and the compiled source it came from (the Sabin report or Moratorium Nation) as "Compiled from". A contested project with a resolution row also prints an "Outcome source" line the same way. A record placed by a reviewer override says how that evidence was seen.

The state line under the flags counts unplaced rows (nothing the build could match) apart from ambiguous ones (a town name shared by several counties).

An empty section means nothing is recorded. It does not mean nothing happened, unless someone checked: see below.

**Checked, nothing found.** `data/review/negative_checks.csv` is hand-edited, one row per check: `county_fips`, `state`, `county`, `scope` (`restrictions`, `projects` or `both`), `sources_checked` (a semicolon list of exactly what was searched, such as the county code library, the commission minutes archive for a date range, a named news search, or state PSC dockets), `checked_on` (YYYY-MM-DD), `result` (always `none_found`), `note` and `reviewer`. The build validates it (a 2024 county whose state matches, a date, at least one source checked) and stops on a bad row; it is never published as a record. When a county's restrictions or projects are empty and a matching check exists, the profile prints "Checked <sources> on <date>: none found" instead of "Nothing published", with a "stale" flag once the check is more than 12 months old. An adjacent county with nothing published prints its newest check the same way.

Every profile run records the county code and the date, and nothing else (not who asked or why), in `data/review/profile_requests.csv`. Each build writes `data/review/negative_check_worklist.csv` from it: the profiled counties with no published restriction and no check covering restrictions, most recent request first, with the sources a check should cover.

**Placement.** `county_fips` stays the one county a county-level record covers, and it is the only code the map paints. `county_fips_all` lists every county a record touches, and `county_fips_method` says how each was found:

- `name`: the county named in the record. This includes a jurisdiction typed as a municipality whose name ends in County or Parish ("Atlantic County", NJ), and a consolidated city-county such as Honolulu (`classify.CITY_COUNTIES`, or a record that says "City and County of"). Neither changes `county_fips`.
- `names`: a multi-county name split into its parts.
- `point`: the record's coordinates fall inside a 2024 county polygon.
- `place`: a town name that sits in exactly one county of its state, in the Census place index.
- `place_text`: a town name shared by several counties, where the record's own text names exactly one of them as "<Name> County".
- `override`: a reviewer's county from `data/review/place_overrides.csv`, applied last.

A town name shared by several counties, where the text does not settle it, is marked `place_ambiguous` and left unplaced. Neighbors are never used to infer a county.

**Reviewer overrides.** `data/review/place_overrides.csv` is hand-edited, one row per instrument: `instrument_id`, `county_fips`, `evidence_url`, `evidence_note`, `reviewer`, `checked_on`, `access`, `archived_url`. Any `access` value places the record; the profile prints it. Add a row only when the evidence (the ordinance, minutes or a news story) names the town together with its county. The build stops if `evidence_url` or `access` is blank, if `county_fips` is not a 2024 county, or if no record has the `instrument_id`. An override sets `county_fips_all` and never `county_fips`, so it changes where a profile finds a record, not what the map paints. Connecticut rows get no overrides: a Connecticut record is placed in its 2022 planning region only when its own text or source names the town.

**Local knowledge.** Reports from local contacts never go in this repository, which is public. `site_profile.py` reads them from the path in the `RO_LOCAL_KNOWLEDGE` environment variable, by default `~/.renewable-opposition/local_knowledge.csv`. The file records what people report about a county: `county_fips`, `state`, `county`, `topic` (`restriction`, `project`, `litigation`, `sentiment` or `other`), `claim`, `source_type` (`local_contact`, `meeting_attended` or `document_seen`), `source_note`, `date_reported` and `reporter`. It is hand-edited, never verified and never published: the build does not read it, and only `site_profile.py` prints it, matching rows on `county_fips` alone. Pass `--no-local` for a profile that leaves THG; the section is omitted and the file is not read. `.gitignore` lists `data/review/local_knowledge.csv` and `local_knowledge*`, and the precommit gate `python scripts/precommit_gates.py private` refuses any staged file whose name starts with `local_knowledge`.

The place index is built with `python scripts/build_place_index.py`. The script downloads the Census 2024 Gazetteer and writes `data/place_county_index.json`. Without the index, town-level rows with no coordinates stay unplaced, and each profile says so.

---

## Pipeline layers (roadmap)

1. **Source registry**: `config/sources.yaml` (crawl targets) and `config/source_registry.csv` (datasets).
2. **Crawler/fetcher**: `scripts/fetch.py` fetches each active source and stores an immutable raw copy keyed by content hash. Not scheduled yet.
3. **Parser/extractor**: `scripts/parse.py` plus one module per source in `scripts/extractors/`. The CourtListener extractor is the first.
4. **Review queue**: `data/review/*.csv`. `scripts/promote_reviewed.py` promotes complete rows on every data build.
5. **Canonical outputs**: `scripts/build_seed_outputs.py` writes CSV + JSON + the Sources table to `data/processed/`.
6. **Pages**: `index.html`, `dashboard.html`, `renewable-opposition-map.html` and `map-audit.html` all read `data/processed/` through `processed-data.js`. Each counts instruments, not rows, and quotes its totals from `headline_metrics.json`; restrictions that also cover data centers are always a separate figure.

**Rules for any future news intake.** Harvested news never writes to a seed or a published file. A news harvester or extractor writes candidates to `data/review/queue.csv` only, and every candidate goes through the same review and promotion gates as a hand-entered row: `access` (a snippet never promotes), a required status, `source_kind` (a news URL locates an instrument but never verifies it), and the QC gate. `tests/test_news_intake.py` asserts that `parse.py` and every module in `scripts/extractors/` write only to `data/review/` (apart from `parse.py`'s own record of which raw files it has parsed, `data/raw/parse_state.csv`), and that no seed lists either as a writer.

---

## Relation to pricephillips/data-center-map

This repo is fully independent. It reuses the same pipeline pattern (CSV-first, static dashboards) but the domains are separate: data centers vs. renewable energy facilities. No code sharing is assumed.


