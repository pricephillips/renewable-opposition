---
description: Triage live-intake leads in the review queue - keep the ones on topic and placed (pending), reject the rest
argument-hint: "[source_id or state filter, e.g. gdelt_renewable_news or IA; blank for all leads]"
---

Triage the live-intake leads in `data/review/queue.csv`. Scope: $ARGUMENTS (when blank, every row whose `review_status` is `lead`, oldest `extracted_at` first).

Before changing anything, read `README.md` ("Live intake", "Reviewing candidates", "Counting and verification") and the docstring of the extractor that produced each lead (`scripts/extractors/<source_id>.py`): it says what the lead is and what it is not.

## What a lead is

`parse.py` queued it from a live source (GDELT news, CourtListener, NY ORES, Legistar) with `review_status` `lead` and `access` `snippet`. A lead changes nothing published: `promote_reviewed.py` never promotes it, and the county reports and the public dashboard count only `pending` rows. Triage is the step that lets it count. Its `reviewer_notes` say how it was found, how it was placed and why, and anything `parse.py` blanked.

## Rules

- The repo stays descriptive only. Never guess a value; no em dashes in anything user-facing.
- Do not special-case any county, record or source in code or tests.
- Triage judges two things only: is the lead **on topic** (a local restriction on solar, wind or battery storage siting, a fight over a named project, or a case about one), and is it **placed** (the state, and the county or municipality, are the ones the source names)? Promotion still needs the source read: a triaged lead stays `snippet` until someone opens or archives its source (`/verify-evidence` does that for `pending` rows).
- Mark `access` `opened` or `archived` only for a source you read in this session.
- Never commit `data/processed/` or the worklists; the Build dashboard data workflow regenerates them.

## For each lead

1. Read the source if you can (the article, the case page, the ORES case or the Legistar matter and its attachment). If you cannot, judge from the headline and notes, and say so.
2. Decide:
   - **On topic and placed** → set `review_status` to `pending`. Correct `state`, `county`, `municipality`, `project_name`, `technology`, `entity_type` and `description` to what the source says. If you read the source, set `access` (and `archived_url`), `source_kind` (an article is `news`; the ordinance, the minutes or an official copy is `instrument`, `minutes` or `official_copy`), and fill `status`, `mechanisms` (the `build_sabin_seeds.MECHANISM_TYPE` vocabulary) and `mechanism_detail` only from what you read.
   - **The same record as a row already held** (its notes may say "possible duplicate of ...") → if it adds a source, put that in the held row's notes or the matching review file (`outcome_resolutions.csv`, `restriction_sources.csv`, `group_candidates.csv`), then set this lead `rejected` with "duplicate of <id>".
   - **Off topic** (a data center, a rooftop or county-building solar purchase, an unrelated "ban"), or a place the source does not support → set `review_status` to `rejected`.
3. Append to `reviewer_notes` the date, what you read (or that you judged from the headline), and the decision with its reason. Keep what was there.

## Checks, commit, PR

1. Run:

   ```bash
   python -m pytest -q tests/test_intake_registry.py tests/test_brain.py tests/test_promote_queue.py
   python scripts/promote_reviewed.py --dry-run
   ```

   The dry run lists what a build would promote; a lead you set `pending` with a source you opened and every field filled may promote on the next build. That is intended: say so in the PR.
2. Commit `data/review/queue.csv` (and any review file you added a source to) with a message that counts the leads kept, rejected and left as leads, by source.
3. Push, open a PR against `main`, and list at the top every lead set `pending`, with its source and how it was read.
