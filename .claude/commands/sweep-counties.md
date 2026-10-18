---
description: Sweep unexamined counties in parallel waves with the county-examiner (docs/COUNTY_CHECK.md) - draft, blind review, write, examination log, one pass note, QC, one PR
argument-hint: "[how many counties, default 20; optionally --wave-size N and --state XX]"
---

Sweep the counties nobody has examined, a wave at a time. Scope: $ARGUMENTS (a number of counties, default 20; `--wave-size N`, default 5; `--state XX`, repeatable, to keep to some states).

This runs the `/examine-county` steps on many counties at once. Before starting, read `.claude/commands/examine-county.md` (the steps and rules, which all apply here), `docs/COUNTY_CHECK.md`, `docs/AGENTS.md`, the module docstring of `scripts/examination_batch.py`, and the most recent pass note in `docs/county_checks/`.

## Rules

- Everything in `/examine-county` holds: the procedure in `docs/COUNTY_CHECK.md`, nothing drafted counts until someone else reviews it, no guessed values, no em dashes in anything a reader sees, no reports from local contacts, never commit `data/processed/` or a worklist.
- Every county the sweep starts gets exactly one line in `data/review/examination_log.csv`, whatever its result. That line keeps the next sweep from picking it again for 60 days.
- One sweep, one branch, one pass note, one PR.

## Steps

Name the run `<today>-sweep`; packets go in `.packets/<run>/county/`. Give each agent a signature `agent:<name>-<n> (Claude Code, <today>)`, numbering the examiners across the whole sweep.

1. **Pick.** `python scripts/examination_batch.py --counties <N> --wave-size <W> [--state XX ...]` lists the counties in worklist rank, each with its wave. It skips counties attempted in the last 60 days and any whose negative check is drafted and waiting for review. If the session's network blocks most county sites (`curl -sS "$HTTPS_PROXY/__agentproxy/status"`), stop and tell the user which hosts were denied before starting a wave.
2. **Each wave**, in order, with the `/examine-county` steps:
   1. **Draft.** Start one `county-examiner` per county of the wave, in one message.
   2. **Write the drafts.** The `record-editor` writes the wave's restrictions as `awaiting_review` queue rows and complete negative checks with `reviewer` blank, and appends one `examination_log.csv` line per county: `date`, `county_fips`, `state`, `county`, `run`, `result` (from the packet: `restrictions` if it drafted any restriction, else `negative_check` if it drafted a negative check, else `leads` if it opened any source, else `not_read`), `drafted_by` (the examiner's signature) and `note` (the packet's `note`).
   3. **Review.** A `blind-reviewer` per drafted row (`blind-row queue_row`, `blind-row negative_check`), never the examiner that drafted it. Start them in one message.
   4. **Write the verdicts.** The `record-editor` writes them as in `/examine-county`. A row sent back to its examiner is corrected and reviewed again within the same wave.
   5. Run `python scripts/review_lint.py --lane review` and fix every error before the next wave starts.
3. **Pass note.** One note for the sweep, `docs/county_checks/<today>_sweep.md`, in the form of the most recent pass note: a table with one row per county (FIPS, county, state, result, restrictions confirmed or held, negative check reviewed or held, leads), what blocked the sweep, and where the next one starts. Have the `copy-editor` edit it, then run the `humanizer` skill on it as `CLAUDE.md` requires (copy it to the scratchpad as `before.md` first, and run the number, URL and outcome-code check afterwards).
4. **Checks.** `python scripts/review_lint.py --lane review` and `python scripts/promote_reviewed.py --dry-run`; fix every lint error. Restore generated files: `git checkout -- data/processed data/review/*_worklist.csv data/review/fips_misses.csv`.
5. **Commit, QC, PR.** Commit `data/review/queue.csv`, `data/review/negative_checks.csv`, `data/review/examination_log.csv`, `data/review/profile_requests.csv` and the pass note. Start the `qc-auditor` with the run name and lane `review`; fix every BLOCKER, commit, audit again. Push, open one PR against `main` with, at the top, the counts by result (counties with restrictions drafted, negative checks drafted, leads only, not read), then the pass note's county table, then the qc-auditor's verdict.
