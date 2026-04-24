# renewable-opposition

Research-grade ingestion, normalization, and dashboard pipeline for local opposition to renewable energy projects in the United States.

Inspired by the Columbia Sabin Center's work:
- *Opposition to Renewable Energy Facilities in the United States*
- *Local laws and lawsuits targeting renewables becoming more prevalent*

---

## Provenance-first philosophy

Every record is traceable to a specific source: an ordinance, court docket, meeting minutes, or news article. No record exists without a `source_url`. The `Sources` table (coming in v2) will formalize this as a canonical document registry with hash-based deduplication.

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

---

## Outputs

Canonical data lives in `data/processed/` as both CSV and JSON:

```
data/processed/
  restrictions.csv / restrictions.json
  contested_projects.csv / contested_projects.json
  cases.csv / cases.json
```

Both formats are required. JSON is used by downstream apps and dashboards; CSV is the human-readable source of truth.

---

## Repository structure

```
renewable-opposition/
├── README.md
├── requirements.txt
├── data/
│   ├── seed/
│   │   └── sabin_seed_examples.csv   ← manually curated seed records
│   ├── raw/                          ← fetched HTML/PDFs (empty initially)
│   └── processed/                    ← canonical CSV + JSON outputs
└── scripts/
    └── build_seed_outputs.py         ← reads seed, writes processed/
```

---

## Quickstart

```bash
pip install -r requirements.txt
python scripts/build_seed_outputs.py
```

Outputs will be written to `data/processed/`.

---

## Pipeline layers (roadmap)

1. **Source registry** — config describing where to pull from (county code sites, state siting boards, court portals, NGO trackers)
2. **Crawler/fetcher** — periodic fetch + immutable raw storage keyed by URL hash
3. **Parser/extractor** — HTML/PDF parsing, rule-based + NLP classification into restriction / contested_project / case
4. **Human review queue** — candidate extractions requiring confirmation (severity, technology, project linkage)
5. **Canonical outputs** — CSV + JSON in `data/processed/`
6. **Dashboard** — static HTML/JS reading processed data; map/choropleth + timelines + drill-down

---

## Relation to pricephillips/data-center-map

This repo is fully independent. It reuses the same pipeline pattern (CSV-first, static dashboards) but the domains are separate: data centers vs. renewable energy facilities. No code sharing is assumed.


