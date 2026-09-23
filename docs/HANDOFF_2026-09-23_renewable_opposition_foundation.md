# Handoff — renewable-opposition foundation pass (Moratorium Nation integration)

**Date:** 2026-09-23 · **Entry point:** `pricephillips/renewable-opposition` had a scaffold (ontology, folder structure, `build_seed_outputs.py`) but zero seed data committed · **Status:** three files built and validated locally, not yet pushed — this session could not push (see Access note)

Full plan doc (goals, architecture, phased build plan, open questions): https://claude.ai/code/artifact/52ad7898-c782-4dc6-8bd9-d6a20a041475

---

## What this repo is

`pricephillips/renewable-opposition` tracks local/state opposition to renewable energy deployment (solar, wind, battery storage), modeled on the same general approach as `pricephillips/data-center-map` but **not** sharing its schema. Its own README defines:

- **Three entities**, not one unified feed: `restrictions` (moratoria, bans, setbacks, zoning), `contested_projects` (project-level fights: hearings, permit denials, campaigns, cancellations), `cases` (litigation and administrative proceedings). Each has a seed CSV in `data/seed/`, converted to CSV+JSON in `data/processed/` by `scripts/build_seed_outputs.py`.
- **1-4 severity scale** on `restrictions` only (1 = mild procedural friction, 4 = explicit moratorium/ban). Different axis from the data-center platform's outcome vocabulary — severity describes how stringent a restriction is, not what happened to a project.
- **Provenance-first**: README states no record exists without a `source_url`; a canonical `Sources` table with hash dedup is declared "coming in v2" but doesn't exist yet.
- **Declared roadmap** (README's own words): source registry -> crawler/fetcher -> parser/extractor -> human review queue -> canonical outputs -> dashboard.

## What's ready to integrate

Three files, already built and tested against the repo's real `scripts/build_seed_outputs.py` (cloned fresh, ran it, 51/51 records validate clean, idempotency checked with a second run):

| File | Goes to | What it does |
|---|---|---|
| `restrictions_seed.csv` | `data/seed/restrictions_seed.csv` (currently empty -- first real data for this file) | 51 rows: every `active`/`extended`/`pending` local moratorium in Moratorium Nation (`mjbommar/moratorium-data-2026`, CC-BY-4.0) tagged `solar`, `wind`, or `battery_storage`. One row per matching technology (source data is multi-label, target schema is one-technology-per-row). |
| `fetch_moratorium_nation.py` | `scripts/fetch_moratorium_nation.py` (new) | Repeatable version of the pull above -- downloads the current source CSV, filters, maps status to severity, rewrites `restrictions_seed.csv`. `--dry-run` flag. Only touches rows it created (matched by a `source` column value), so hand-added rows from other sources survive a re-run. |
| `source_registry.csv` | `config/source_registry.csv` (new -- create `config/`) | The "source registry" the README's own roadmap calls for as step 1. 10 rows: Moratorium Nation, Sabin Center Legal Defense Initiative + report series, NREL wind/solar ordinance databases, LBNL Queued Up, Open States, GDELT, two commercial BESS trackers (flagged lower-priority). Also a direct Notion CSV import if useful there. |

### Severity mapping and exclusions (the actual judgment calls made)

- `active` / `extended` -> severity 4 (in-force moratorium reads as an explicit ban under the repo's own scale).
- `pending` -> severity 2 (proposed, not yet constraining).
- **Excluded 5 instruments**: 3 `replaced` (superseded by a permanent ordinance whose actual stringency isn't in this dataset -- scoring it would be a guess), 1 `expired`, 1 `rescinded` (no longer in force). Listed by `moratorium_id` in the script's own output when it runs.
- `restrictions_seed.csv`'s required columns (`state`, `technology`, `restriction_type`, `severity_score`, `description`) are satisfied; added `status`, `jurisdiction`, `jurisdiction_type`, `date_enacted_iso`, `moratorium_id`, `source`, `source_url` beyond that, since the README's provenance-first rule isn't yet enforced by the validation script but is a stated repo principle.

## Access note -- read this before trying to push

This session's git proxy refused the push with: `pricephillips/renewable-opposition is not in this session's authorized repository set`. Read access (clone) worked fine; write did not. If Claude Code's session has this repo authorized, push directly. If not, this is a per-session grant Price has to add (not something scriptable from inside a session) -- check for an "add repository" / connected-repos setting before assuming it's broken.

Suggested branch and commit if pushing fresh:

```bash
git checkout -b claude/moratorium-nation-restrictions-seed
# copy the three files into the paths in the table above
git add data/seed/restrictions_seed.csv scripts/fetch_moratorium_nation.py config/source_registry.csv
git commit -m "Add restrictions_seed.csv seeded from Moratorium Nation, plus a refresh script and source registry"
git push -u origin claude/moratorium-nation-restrictions-seed
python scripts/build_seed_outputs.py   # regenerate data/processed/restrictions.json, confirm 51 records
```

## Immediate next steps (from the plan doc's phased build plan)

1. **Build the `Sources` table** (hash-based dedup) the README calls for in v2, before ingesting anything else at volume.
2. **`contested_projects_seed.csv` and `cases_seed.csv` are still empty.** Do not mechanically transform Moratorium Nation into these -- it's a restrictions-only dataset. These two need real per-case research (named projects, actual court dockets, real `source_url`s) from the Sabin Center's opposition reports and Legal Defense Initiative, cross-checked against the NREL ordinance databases for detection recall. No fabricated rows.
3. Cross-check the NREL wind/solar ordinance databases against the 51 ingested rows for detection recall (same role Moratorium Nation plays for the data-center platform's `coverage_audit.py`).
4. Start the source registry -> crawler/fetcher -> parser/extractor -> human review queue chain per the README's own roadmap, using `config/source_registry.csv` as the registry's seed.

## Open decisions still on the table (see plan doc for full context)

- Does `restrictions_seed.csv` need a `status` field formalized in the schema (not just an extra column) before ingesting at volume -- this pass added it informally.
- Share `map-permalink.js` / `legend-filter.js` / `viz-palette.js` with `data-center-map` via a small library, or keep the two repos' JS fully separate as both READMEs currently assume.
- Whether `replaced` moratoria (permanent ordinance now in force) deserve a follow-up pass once the permanent ordinance's own terms can be sourced -- currently excluded rather than guessed.
- Four-tier outcome vocabulary (`advanced_confirmed`/`restricted_conditional`/`blocked_confirmed`/`pending`) maps to `contested_projects` only, not `restrictions`; a parallel litigation-status vocabulary (`pending`/`dismissed`/`ruled_for_developer`/`ruled_for_opposition`/`settled`/`withdrawn`) is proposed for `cases` but not yet built into the schema.

## Files to push

```
data/seed/restrictions_seed.csv       new data (was empty)
scripts/fetch_moratorium_nation.py    new
config/source_registry.csv            new (new folder)
docs/HANDOFF_2026-09-23_renewable_opposition_foundation.md   this file
```
