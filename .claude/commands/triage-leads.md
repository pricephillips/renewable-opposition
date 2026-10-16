---
description: Triage live-intake leads in the review queue - keep the ones on topic and placed (pending), reject the rest
argument-hint: "[source_id or state filter, e.g. gdelt_renewable_news or IA; blank for all leads]"
---

Triage the live-intake leads in `data/review/queue.csv`. Scope: $ARGUMENTS (when blank, every row whose `review_status` is `lead`, oldest `extracted_at` first).

Before changing anything, read `README.md` ("Live intake", "Reviewing candidates", "Counting and verification"), `docs/AGENTS.md`, and the docstring of the extractor that produced each lead (`scripts/extractors/<source_id>.py`): it says what the lead is and what it is not.

## What a lead is

`parse.py` queued it from a live source (GDELT news, CourtListener, NY ORES, Legistar) with `review_status` `lead` and `access` `snippet`. A lead changes nothing published: `promote_reviewed.py` never promotes it, and the county reports and the public dashboard count only `pending` rows. Triage is the step that lets it count. Its `reviewer_notes` say how it was found, how it was placed and why, and anything `parse.py` blanked.

## Rules

- The repo stays descriptive only. Never guess a value; no em dashes in anything user-facing.
- Do not special-case any county, record or source in code or tests.
- Triage judges two things only: is the lead **on topic** (a local restriction on solar, wind or battery storage siting, a fight over a named project, or a case about one), and is it **placed** (the state, and the county or municipality, are the ones the source names)? Promotion still needs the source read: a triaged lead stays `snippet` until someone opens or archives its source.
- Mark `access` `opened` or `archived` only for a source read in this session.
- Nothing an agent drafted publishes without a second reader (`docs/AGENT_REVIEW.md`): a lead whose source was read and whose fields were filled from it, and which could therefore promote on the next build, is set `confirmed` only once a blind second reading agrees, and `awaiting_review` until then.
- Never commit `data/processed/` or the worklists; the Build dashboard data workflow regenerates them.

## How the work is split

You orchestrate; the agents read and write (`docs/AGENTS.md`). Name the run `<today>-triage`; packets go in `.packets/<run>/lead/`.

1. **Draft.** Split the leads into batches of about ten, by source. For each batch start a `lead-triager` with the rows (their JSON), a signature `agent:lead-triager-<n> (Claude Code, <today>)` and a packet path `.packets/<run>/lead/batch-<n>.draft.json`. Batches can run in parallel; send them in one message.
2. **Second reading.** For each lead the triager drafted as `pending` from a source it read (`read` true, `access` `opened` or `archived`): `python scripts/review_packets.py blind-row lead <queue_id> > .packets/<run>/lead/<queue_id>.blind.json`, and start a `blind-reviewer` with that card only, a different signature, and `<queue_id>.review.json`. It triages independently.
3. **Compare.** The readings agree when the decision, the state, the county or municipality, and every value either put in `set` match. Off-topic and headline-only decisions get no second reading.
4. **Write.** Start the `record-editor` with the triage packet and the review packets. It writes, for each lead (its "Triage decisions" section):
   - **On topic and placed, read, readings agree** → the values from `set`, `access`, `archived_url`, `source_kind`; both signatures in `reviewer_notes`; `review_status` `confirmed`.
   - **On topic and placed, read, readings differ** → the triager's values with "Drafted by" the triager and the reviewer's contradiction in `reviewer_notes`; `review_status` `awaiting_review`.
   - **On topic and placed, judged from the headline** → place, technology and entity corrections only; `access` stays `snippet`; `review_status` `pending`.
   - **The same record as a row already held** (its notes may say "possible duplicate of ...") → if it adds a source, that goes in the held row's notes or the matching review file (`outcome_resolutions.csv`, `restriction_sources.csv`, `group_candidates.csv`); this lead is `rejected` with "duplicate of <id>".
   - **Off topic** (a data center, a rooftop or county-building solar purchase, an unrelated "ban"), or a place the source does not support → `rejected`.

   Every lead's `reviewer_notes` gains the date, what was read (or that the headline alone was judged), and the decision with its reason. What was there is kept.

## Checks, QC, commit, PR

1. Run:

   ```bash
   python scripts/review_lint.py --lane review
   python -m pytest -q tests/test_intake_registry.py tests/test_brain.py tests/test_promote_queue.py
   python scripts/promote_reviewed.py --dry-run
   ```

   The dry run lists what a build would promote; a lead set `confirmed` with a source both readers opened and every field filled may promote on the next build. That is intended: say so in the PR.
2. Commit `data/review/queue.csv` (and any review file a source was added to) with a message that counts the leads kept, rejected and left as leads, by source.
3. Start the `qc-auditor` with the run name and lane `review`; it also re-checks a sample of the rejections. Fix every BLOCKER, commit, audit again.
4. Push, open a PR against `main`, and list at the top every lead set `confirmed`, `awaiting_review` or `pending`, with its source and how it was read, then the qc-auditor's verdict.
