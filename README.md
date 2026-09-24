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

`contested_projects` rows carry an `outcome` from a four-tier vocabulary — `blocked_confirmed`, `restricted_conditional`, `advanced_confirmed`, `pending` — plus `needs_review` when the source status can't be mapped. Their `severity_score` measures how hard opposition hit the project:

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

A case is promoted into `cases_seed.csv` only after it is confirmed. Confirmed means a court record names the case and its court: an opinion, a docket, or a court's own page, found on CourtListener, Justia, govinfo, a court website or an equivalent case-law host. The row's `reviewer_notes` say how and when it was verified. Partial finds stay in `data/review/cases_candidates.csv` as `review_status=lead`, with what is known so far.

---

## Outputs

Canonical data lives in `data/processed/` as both CSV and JSON:

```
data/processed/
  restrictions.csv / restrictions.json
  contested_projects.csv / contested_projects.json
  cases.csv / cases.json
  sources.csv / sources.json        ← one row per source document
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
│   ├── renewable_opposition_records.csv    ← Sabin report extraction (feeds the map/dashboard)
│   ├── seed/
│   │   ├── restrictions_seed.csv           ← Moratorium Nation + Sabin local restrictions
│   │   ├── contested_projects_seed.csv     ← Sabin contested-projects section
│   │   └── cases_seed.csv                  ← confirmed cases (via promote_reviewed.py)
│   ├── review/
│   │   ├── cases_candidates.csv            ← litigated projects/restrictions awaiting docket research
│   │   ├── sabin_restrictions_review.csv   ← Sabin restriction rows held back, with reasons
│   │   ├── coverage_gaps.csv               ← moratoria found in only one source
│   │   └── queue.csv                       ← extractor candidates (written by parse.py)
│   ├── raw/                                ← fetched documents keyed by content hash (fetch.py)
│   └── processed/                          ← canonical CSV + JSON outputs
├── docs/
│   └── coverage_audit.md                   ← Sabin vs Moratorium Nation recall
├── scripts/
│   ├── common.py                           ← shared helpers (state codes, technology vocabulary, source ids)
│   ├── fetch_moratorium_nation.py          ← refreshes the Moratorium Nation rows of restrictions_seed.csv
│   ├── build_sabin_seeds.py                ← Sabin rows of restrictions + contested projects, review files
│   ├── coverage_audit.py                   ← writes docs/coverage_audit.md + coverage_gaps.csv
│   ├── fetch.py                            ← crawler: sources.yaml -> data/raw/
│   ├── parse.py                            ← runs scripts/extractors/<source_id>.py -> review/queue.csv
│   ├── extractors/courtlistener_renewables.py
│   ├── promote_reviewed.py                 ← confirmed review rows -> seed CSVs
│   └── build_seed_outputs.py               ← validates seeds, writes processed/
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

### Reviewing candidates

- **Cases.** `data/review/cases_candidates.csv` lists every project or restriction the source says was litigated. To promote one, fill in `case_name`, `court`, `court_level`, `docket_number` and `case_source_url` from a primary source (a docket, an opinion, or a court's own page), set `review_status` to `confirmed`, then run `python scripts/promote_reviewed.py`. If one project has several cases, duplicate the row. Rebuilding with `build_sabin_seeds.py` keeps these edits.
- **Extractor output.** Each extractor, such as the CourtListener one, writes candidates to `data/review/queue.csv` with `review_status=pending`. Change a row to `confirmed` (filling any blank required fields) or `rejected`, then run `promote_reviewed.py`.

Outputs will be written to `data/processed/`.

---

## Pipeline layers (roadmap)

1. **Source registry** — `config/sources.yaml` (crawl targets) and `config/source_registry.csv` (datasets).
2. **Crawler/fetcher** — `scripts/fetch.py`: fetches each active source and stores an immutable raw copy keyed by content hash. Not scheduled yet.
3. **Parser/extractor** — `scripts/parse.py` plus one module per source in `scripts/extractors/`. The CourtListener extractor is the first.
4. **Human review queue** — `data/review/*.csv`, promoted by `scripts/promote_reviewed.py`.
5. **Canonical outputs** — `scripts/build_seed_outputs.py` writes CSV + JSON + the Sources table to `data/processed/`.
6. **Dashboard** — `index.html` reads `data/processed/`.

---

## Relation to pricephillips/data-center-map

This repo is fully independent. It reuses the same pipeline pattern (CSV-first, static dashboards) but the domains are separate: data centers vs. renewable energy facilities. No code sharing is assumed.


