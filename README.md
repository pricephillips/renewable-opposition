# renewable-opposition

Research-grade pipeline for tracking **local opposition to renewable energy facilities** in the United States, inspired by Columbia's Sabin Center work:

- *Opposition to Renewable Energy Facilities in the United States*
- *Local laws and lawsuits targeting renewables becoming more prevalent*

---

## Philosophy: Provenance First

Every record is traceable to a specific underlying document — an ordinance, docket, meeting minutes, news article, or NGO tracker entry. No unsourced claims enter the canonical outputs.

---

## Core Entities

The data model mirrors the Sabin framing and separates three distinct phenomena:

### 1. Restrictions
Local or state laws that materially constrain renewable deployment.
- Moratoria, bans, extreme setbacks, height limits, zoning amendments
- Severity score 1–4 (4 = explicit ban or moratorium)
- Headline stats and map layers default to severity ≥ 3

### 2. Contested Projects
Opposition events tied to specific facilities.
- Public hearings, permit denials, community campaigns, cancellations
- Severity score reflects opposition intensity

### 3. Cases
Lawsuits and formal administrative proceedings.
- State and federal courts, agency proceedings
- Linked to projects and jurisdictions when applicable

---

## Outputs

Canonical data lives under `data/processed/`:

| File | Description |
|---|---|
| `restrictions.csv` / `.json` | Enacted or proposed restrictive laws/regulations |
| `contested_projects.csv` / `.json` | Project-level opposition events |
| `cases.csv` / `.json` | Litigation and administrative proceedings |

These are what dashboards and external consumers read. Do not depend on intermediate files.

---

## Pipeline Shape

```
data/seed/          ← manually curated seed records (CSV)
     ↓
scripts/build_seed_outputs.py
     ↓
data/processed/     ← canonical CSV + JSON (restrictions, contested_projects, cases)

data/raw/           ← reserved for fetched HTML/PDF (crawlers, added later)
```

Future layers (not yet implemented):
- **Crawler/fetcher** — periodic fetch, immutable raw storage keyed by URL + hash
- **Parser/extractor** — rule-based + NLP; classifies into restriction / contested_project / case
- **Human review queue** — confirm severity, technology, project linkage
- **Dashboard** — static HTML/JS reading `data/processed/` CSV/JSON

---

## Running the Pipeline

```bash
pip install -r requirements.txt
python scripts/build_seed_outputs.py
```

Outputs are written to `data/processed/`. Re-run any time seed records change.

---

## Severity Scale

| Score | Meaning |
|---|---|
| 1 | Mild procedural friction |
| 2 | Material burden, not obviously project-blocking |
| 3 | Likely de facto ban (extreme setbacks, height limits) |
| 4 | Explicit moratorium or outright ban |

Map layers and headline statistics default to severity ≥ 3.

---

## Jurisdiction Fields

Records carry `state`, `county` (nullable), `municipality` (nullable), and `jurisdiction_type`
(state | county | municipality | township | …). Standard IDs (FIPS, GNIS) are not required for v1.

---

## Separation from pricephillips/data-center-map

This repo is **standalone**. It reuses the CSV-pipeline + static-dashboard pattern from the data-center-map project but shares no code and assumes no coupling. The domain is renewable energy opposition; data centers are out of scope.

---

## License / Use

Research and policy analysis use. Underlying source documents retain their own licenses.
