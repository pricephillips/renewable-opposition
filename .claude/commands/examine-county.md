---
description: Examine counties for local solar, wind and storage restrictions (docs/COUNTY_CHECK.md) - draft, blind review, write, pass note, QC
argument-hint: "[FIPS codes or a state, e.g. 19113 19103 or VT; blank for the top of the examination worklist]"
---

Examine counties for local restrictions on solar, wind and battery storage siting. Scope: $ARGUMENTS (FIPS codes, or a state's counties; when blank, the first five rows of `data/review/examination_worklist.csv`).

Before changing anything, read `docs/COUNTY_CHECK.md` (the procedure), `docs/AGENT_REVIEW.md`, `docs/AGENTS.md`, and the most recent pass note in `docs/county_checks/`.

## Rules

- The procedure in `docs/COUNTY_CHECK.md` decides what a check covers, what counts as read, what counts as a restriction and how results are recorded. Nothing here relaxes it.
- A county is examined once it has a published record or a reviewed negative check. A check that does not cover every government that zones, or rests on search results, is a lead, not a negative check.
- Nothing drafted counts until someone other than its drafter reviews it.
- Never guess a value; no em dashes in anything a reader sees; never read or mention reports from local contacts.
- Never commit `data/processed/` or the worklists.

## How the work is split

Name the run `<today>-counties`; packets go in `.packets/<run>/county/`. Give each agent a signature `agent:<name>-<n> (Claude Code, <today>)`.

1. **Draft.** For each county start a `county-examiner` with its FIPS, name and state, its worklist row, a signature and `.packets/<run>/county/<fips>.draft.json`. Counties are independent; start them in one message, a few at a time.
2. **Write the drafts.** Start the `record-editor` with the packets. Each restriction becomes a `queue.csv` row with `review_status` `awaiting_review` and `reviewer_notes` beginning "Drafted by <examiner>"; a complete negative check becomes a `negative_checks.csv` row with `drafted_by` set and `reviewer` blank. Leads are written nowhere but the pass note.
3. **Review.** For each drafted row, build its blind card and start a `blind-reviewer` (never the examiner that drafted it):
   - `python scripts/review_packets.py blind-row queue_row <queue_id> > .packets/<run>/county/<queue_id>.blind.json`
   - `python scripts/review_packets.py blind-row negative_check <fips> > .packets/<run>/county/<fips>.nc.blind.json`

   The reviewer reopens the sources (at least every code for a negative check) and gives `confirmed`, `contradicts` or `unverifiable` with the field it disagrees with.
4. **Write the verdicts.** The `record-editor` appends each verdict to the row's notes. `confirmed`: the queue row becomes `confirmed`, the negative check gets its `reviewer`. `contradicts` or `unverifiable`: the row stays held; send the examiner the reviewer's packet once to correct, and the corrected row gets a fresh review. A rejected negative check is deleted.
5. **Pass note.** Draft `docs/county_checks/<today>_<name>.md` in the form of `docs/ohio_sb52_first_pass.md` from the packets (counties, the result for each, what blocked the pass, where the next pass starts), and have the `copy-editor` edit it.

## Checks, QC, commit, PR

1. `python scripts/review_lint.py --lane review` and `python scripts/promote_reviewed.py --dry-run`; fix every lint error.
2. Restore generated files (`git checkout -- data/processed data/review/*_worklist.csv data/review/fips_misses.csv`), then commit `data/review/queue.csv`, `data/review/negative_checks.csv`, `data/review/profile_requests.csv` and the pass note.
3. Start the `qc-auditor` with the run name and lane `review`. Fix every BLOCKER, commit, audit again.
4. Push, open a PR against `main` with, at the top, each county and its result (restrictions confirmed or held, a negative check reviewed or held, leads), then the qc-auditor's verdict.
