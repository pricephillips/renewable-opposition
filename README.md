# renewable-opposition

Research-grade ingestion, normalization, and dashboard pipeline for local opposition to renewable energy projects in the United States.

Inspired by the Columbia Sabin Center's work:
- *Opposition to Renewable Energy Facilities in the United States*
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

### Severity scale (1–4)
- **1** – Mild procedural friction
- **2** – Material burden, not obviously project-blocking
- **3** – Likely de facto ban (e.g., extreme setbacks, height limits)
- **4** – Explicit moratorium or outright ban

For map layers and headline stats, default to severity ≥ 3.

### Restrictions: how severity is assigned

- **Moratorium Nation** rows: an active or extended moratorium scores 4, a pending one 2.
- **Sabin** rows: a ban scores 4, and so does an in-force moratorium. These score 3: a wind setback of at least half a mile or 5× turbine height, any wind height limit, a wind noise limit of 35 dBA or less, and a solar or storage setback of at least 1,000 ft. Every other restricting mechanism scores 2, and a pending instrument is capped at 2. Each row's `severity_basis` column names the rule that set its score.

`scripts/build_sabin_seeds.py` documents every rule, and every row it holds back goes to `data/review/sabin_restrictions_review.csv` with the reason.

### Contested projects: outcome and severity

`contested_projects` rows carry an `outcome` from the outcome ladder shared with `data-center-map`: `blocked_confirmed` / `blocked_unverified`, `restricted_conditional`, `advanced_confirmed` / `advanced_unverified`, `pending`, plus `needs_review` when the source status can't be mapped. A status label from the source is never enough for `*_confirmed`; that takes independent evidence, which today means a seeded court case, linked to the same record, that was decided the same way. `finality_evidence` records which applies: `court_ruling: <case>`, `outcome_label_only` or `none`. Their `severity_score` measures how hard opposition hit the project:

- **4** – Project blocked (cancelled or permit denied)
- **3** – Litigation filed, project not (yet) blocked
- **2** – Resident or organized opposition, no litigation, not yet approved
- **1** – Project advanced despite opposition, no litigation

`scripts/build_sabin_seeds.py` documents the exact status → outcome mapping.

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
Every processed row carries an `instrument_id` (`scripts/classify.py`), and the
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

A snippet row stays on the worklists below, with its URL in `located_url`,
until someone opens or archives the source and changes `access`.

Pushing any of these files rebuilds the published data. A resolution that
names a record that does not exist, has no evidence URL, or has a blank or
unknown `access` (or `archived` with no `archived_url`) stops the build.

**Column coverage.** `scripts/coverage_delta.py` fails the build when a
well-filled column loses more than 20 percent of its values against the
previous commit, which is what an upstream format change looks like. A
deliberate drop is declared in `config/coverage_exceptions.json`.

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
```

Every record has a stable `id` that doesn't change between runs, plus the `source_id` of its source. In the JSON files, each record also has a `sources` array that the dashboard renders as links.

Both formats are required. JSON is used by downstream apps and dashboards; CSV is the human-readable source of truth.

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
│   ├── renewable_opposition_records.csv    ← Sabin report extraction (input to build_sabin_seeds.py)
│   ├── seed/
│   │   ├── restrictions_seed.csv           ← Moratorium Nation + Sabin local restrictions
│   │   ├── contested_projects_seed.csv     ← Sabin contested-projects section
│   │   └── cases_seed.csv                  ← cases with a court record (via promote_reviewed.py)
│   ├── review/
│   │   ├── cases_candidates.csv            ← litigated projects/restrictions awaiting docket research
│   │   ├── sabin_restrictions_review.csv   ← Sabin restriction rows held back, with reasons
│   │   ├── coverage_gaps.csv               ← moratoria found in only one source
│   │   ├── place_overrides.csv             ← reviewer counties with evidence (hand-edited)
│   │   ├── local_knowledge.csv             ← unverified local reports, never published (hand-edited)
│   │   └── queue.csv                       ← extractor candidates (written by parse.py)
│   ├── raw/                                ← fetched documents keyed by content hash (fetch.py)
│   └── processed/                          ← canonical CSV + JSON outputs
├── docs/
│   ├── coverage_audit.md                   ← Sabin vs Moratorium Nation recall
│   └── pipeline_comparison.md              ← practices adopted from data-center-map, and what's next
├── scripts/
│   ├── common.py                           ← shared helpers (state codes, technology vocabulary, source ids)
│   ├── fetch_moratorium_nation.py          ← refreshes the Moratorium Nation rows of restrictions_seed.csv
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
│   └── build_seed_outputs.py               ← validates seeds, runs QC, writes processed/
└── tests/                                  ← pytest suite (run in CI by .github/workflows/validate.yml)
```

---

## Quickstart

```bash
pip install -r requirements.txt
python scripts/fetch_moratorium_nation.py   # refresh Moratorium Nation restrictions (run before the Sabin build: it dedups against them)
python scripts/build_sabin_seeds.py         # rebuild Sabin restrictions + contested projects
python scripts/coverage_audit.py            # optional: recompute the cross-source audit
python scripts/build_seed_outputs.py        # validate and write data/processed/
python -m pytest -q
```

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

Promotion is automatic. The Build dashboard data workflow runs `scripts/promote_reviewed.py` before every build and commits what it promotes, so nobody promotes anything by hand. A row goes into its seed as soon as it is complete; `review_status` only holds a row back (`rejected`), and a promoted row is marked `promoted`. A row promoted without `review_status=confirmed` says so in its seed notes ("promoted automatically ... not reviewed by hand"), and every promoted row still passes the QC gate. Nothing is filled in to make a row complete: an incomplete row stays where it is, and the workflow's summary lists what it lacks.

- **Cases.** `data/review/cases_candidates.csv` lists every project or restriction the source says was litigated. A candidate is complete once `case_name`, `court`, `court_level` and an http(s) `case_source_url` are filled from a court record (a docket, an opinion, or a court's own page). If one project has several cases, duplicate the row. Rebuilding with `build_sabin_seeds.py` keeps these edits.
- **Queue.** Extractors such as the CourtListener one, and anyone adding a candidate by hand, write to `data/review/queue.csv`. A row is complete once every field its seed requires is filled, including an http(s) `source_url`. Queue columns are mapped onto the seed's own columns (`adopted_date` becomes `date_enacted_iso`, a blank restriction status becomes `unknown`), so a promoted row never adds a column. Set `review_status=rejected` to keep a row out.
- **How the queue source was seen.** Every queue row has `access` (`opened`, `archived` with its `archived_url`, or `snippet`). The CourtListener extractor writes `snippet`, because a search API result is index text. A `snippet` row is never promoted: it waits, and the workflow summary says its source has to be opened or archived first. A blank or unknown `access` is reported the same way.
- **Restriction candidates.** List every mechanism in `mechanisms`, separated by semicolons, in the vocabulary of `build_sabin_seeds.MECHANISM_TYPE` (for example `setback; height limit; noise limit`). Put their values (distances, dBA and hours, acreage, caps) in `mechanism_detail`; a promoted row carries it in the seed's `long_description`. On promotion, `severity_score`, `severity_basis` and `restriction_type` are computed per technology by the same rules as published Sabin rows (`restriction_severity`, `driving_type`), run on `mechanism_detail` plus `description`. A `status` of `pending` caps the score at 2, as for Sabin rows; blank means unknown. A typed `severity_score` is optional: one that disagrees with the computed score is reported as a conflict and the row is not promoted. An unknown mechanism stops the run before anything is written.

Outputs will be written to `data/processed/`.

---

## Site profiles

`scripts/site_profile.py` lists everything the data records about one county.
It is descriptive only: no scores and no predictions.

```bash
python scripts/site_profile.py --state KS --county Cherokee
python scripts/site_profile.py --fips 19113 --radius 40 --notes "what local contacts report"
python scripts/site_profile.py --sites sites.csv --out profiles.md   # columns: name,state,county,fips,lat,lon,notes
python scripts/site_profile.py --state KS --county Cherokee --no-local   # leaves out local knowledge
```

Each profile has these sections:

- **In the county:** published records whose `county_fips_all` includes the county.
- **Local knowledge on file:** the county's rows in `data/review/local_knowledge.csv`, printed as entered, each labelled "reported, not verified". See below.
- **Adjacent counties:** the same for every county that shares a border, across state lines, plus one line for each pending review-queue candidate there.
- **Within a radius:** optional.
- **Not published:** rows the build held back that name the county (lifted or duplicate Sabin rows, QC quarantine, coverage gaps, case candidates), and every `data/review/queue.csv` candidate of any entity type with `review_status` = `pending` that concerns the county. A candidate concerns the county when its `county` is the county's name, its `municipality` is a town the place index puts in this county alone, or its text says "<Name> County". Each shows its entity type, technology, mechanisms and their values, adoption date and `access`, labelled "pending review, not published".
- **Named in the text:** records placed elsewhere whose text names the county.
- **Flags:** moratoria past their end date, report-only evidence, same-name counties in other states, states with no contested-project coverage, and one "Evidence still to read" flag that counts the items the profile shows whose source was seen only as search-index text (a primary source, an outcome source, a county placement or a pending candidate with `access` = `snippet`).

Every record line names its sources. A record with a primary source prints it on the "Source" line with how it was seen ("located, not yet read" for `snippet`), and the compiled source it came from (the Sabin report or Moratorium Nation) as "Compiled from". A contested project with a resolution row also prints an "Outcome source" line the same way. A record placed by a reviewer override says how that evidence was seen.

The state line under the flags counts unplaced rows (nothing the build could match) apart from ambiguous ones (a town name shared by several counties).

An empty section means nothing is recorded. It does not mean nothing happened.

**Placement.** `county_fips` stays the one county a county-level record covers, and it is the only code the map paints. `county_fips_all` lists every county a record touches, and `county_fips_method` says how each was found:

- `name`: the county named in the record. This includes a jurisdiction typed as a municipality whose name ends in County or Parish ("Atlantic County", NJ), and a consolidated city-county such as Honolulu (`classify.CITY_COUNTIES`, or a record that says "City and County of"). Neither changes `county_fips`.
- `names`: a multi-county name split into its parts.
- `point`: the record's coordinates fall inside a 2024 county polygon.
- `place`: a town name that sits in exactly one county of its state, in the Census place index.
- `place_text`: a town name shared by several counties, where the record's own text names exactly one of them as "<Name> County".
- `override`: a reviewer's county from `data/review/place_overrides.csv`, applied last.

A town name shared by several counties, where the text does not settle it, is marked `place_ambiguous` and left unplaced. Neighbors are never used to infer a county.

**Reviewer overrides.** `data/review/place_overrides.csv` is hand-edited, one row per instrument: `instrument_id`, `county_fips`, `evidence_url`, `evidence_note`, `reviewer`, `checked_on`, `access`, `archived_url`. Any `access` value places the record; the profile prints it. Add a row only when the evidence (the ordinance, minutes or a news story) names the town together with its county. The build stops if `evidence_url` or `access` is blank, if `county_fips` is not a 2024 county, or if no record has the `instrument_id`. An override sets `county_fips_all` and never `county_fips`, so it changes where a profile finds a record, not what the map paints. Connecticut rows get no overrides: a Connecticut record is placed in its 2022 planning region only when its own text or source names the town.

**Local knowledge.** `data/review/local_knowledge.csv` records what people report about a county: `county_fips`, `state`, `county`, `topic` (`restriction`, `project`, `litigation`, `sentiment` or `other`), `claim`, `source_type` (`local_contact`, `meeting_attended` or `document_seen`), `source_note`, `date_reported` and `reporter`. It is hand-edited, never verified and never published: the build does not read it, and only `site_profile.py` prints it, matching rows on `county_fips` alone. Pass `--no-local` for a profile that leaves THG; the section is omitted and the file is not read.

The place index is built with `python scripts/build_place_index.py`. The script downloads the Census 2024 Gazetteer and writes `data/place_county_index.json`. Without the index, town-level rows with no coordinates stay unplaced, and each profile says so.

---

## Pipeline layers (roadmap)

1. **Source registry**: `config/sources.yaml` (crawl targets) and `config/source_registry.csv` (datasets).
2. **Crawler/fetcher**: `scripts/fetch.py` fetches each active source and stores an immutable raw copy keyed by content hash. Not scheduled yet.
3. **Parser/extractor**: `scripts/parse.py` plus one module per source in `scripts/extractors/`. The CourtListener extractor is the first.
4. **Review queue**: `data/review/*.csv`. `scripts/promote_reviewed.py` promotes complete rows on every data build.
5. **Canonical outputs**: `scripts/build_seed_outputs.py` writes CSV + JSON + the Sources table to `data/processed/`.
6. **Pages**: `index.html`, `dashboard.html`, `renewable-opposition-map.html` and `map-audit.html` all read `data/processed/` through `processed-data.js`. Each counts instruments, not rows, and quotes its totals from `headline_metrics.json`; restrictions that also cover data centers are always a separate figure.

---

## Relation to pricephillips/data-center-map

This repo is fully independent. It reuses the same pipeline pattern (CSV-first, static dashboards) but the domains are separate: data centers vs. renewable energy facilities. No code sharing is assumed.


