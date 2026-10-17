---
description: Settle whether restriction instruments of unknown status still apply - status-checker, blind second reading, record-editor writes status_resolutions.csv, QC, PR
argument-hint: "[how many instruments, default 10; or instrument ids separated by spaces]"
---

Settle the status of restriction instruments the published data marks `unknown` or `lapsed_unconfirmed`. Scope: $ARGUMENTS (a number of instruments, default 10; or instrument ids).

Before starting, read `scripts/resolutions.py` (`apply_status_resolutions`, the `access` rules), the module docstring of `scripts/review_packets.py` (the `status` queue), `.claude/agents/status-checker.md` and `docs/AGENTS.md`.

## Why this exists

Most published instruments came from NREL's ordinance compilations, which do not say whether an ordinance is still in force, so `currency` is `unknown` and the county typology files those counties under `restrictions_status_unknown`. Two readings that agree on a status settle it: `data/review/status_resolutions.csv` holds the row, and the next build lays it over the record. An `active` or `extended` reading puts the instrument in force; `lifted` or `expired` takes it out of the published data (it stays in the review file and the log).

## Rules

- A status rests on the instrument, the minutes that acted on it, or an official copy of the code, read in this session (`opened` or `archived`). Never a tracker, a news article or search-result text.
- `expired` only after the minutes around the end date were searched for an extension.
- An `active` or `extended` end date is a full YYYY-MM-DD; a `lifted` or `expired` end date is never after the reading (a repeal that takes effect later is `active` until then).
- Do not special-case any instrument or county in code or tests.
- Never commit `data/processed/`, `data/db/` or a worklist; the Build dashboard data workflow regenerates them.
- No em dashes in anything written.

## Steps

Name the run `<today>-status` and keep its packets in `.packets/<run>/status/`. Give every agent a signature, `agent:<name>-<n> (Claude Code, <today>)`, numbering the agents of one role.

1. **Pick.** `python scripts/verification_batch.py --restrictions 0 --outcomes 0 --statuses <N>` lists the next instruments: those whose source is already located first, then a county's only severe restriction, a county's only restriction, and higher severity. It skips any instrument with a status row already and any attempted in the last 14 days. When ids were given, use those.
2. **Card.** For each: `python scripts/review_packets.py card status <instrument_id> > .packets/<run>/status/<slug>.card.json`.
3. **First reading.** Start a `status-checker` per card with its signature and the draft path `<slug>.draft.json`. Start them in one message, a few at a time.
4. **Second reading.** If the draft's `result` is `read`: `python scripts/review_packets.py blind <card> <draft> > <slug>.blind.json`, then start a `blind-reviewer` with the blind card only (never the draft or its summary), a signature that is not the drafter's, and `<slug>.review.json`.
5. **Reconcile.** `python scripts/review_packets.py reconcile <card> <draft> <review>`. If `disputed`, send the drafter the reviewer's packet once and ask it to re-read; reconcile again. Still disputed: only the log line is written, giving both readings.
6. **Write.** Start the `record-editor` with the reconciled items. It appends each `written` row with `reconcile ... --row >> data/review/status_resolutions.csv` and every item's log line with `--log >> data/review/verification_log.csv`. A `leads` entry (a replacement ordinance, an amendment) goes to the PR description for `/examine-county` or the queue; the record-editor does not add it.
7. **Build and check.**

   ```bash
   python scripts/build_seed_outputs.py
   python scripts/county_typology.py
   python scripts/review_lint.py --lane review
   ```

   The build must print no `status_resolutions.csv` error. Record, before and after: instruments by `currency` (`in_force`, `unknown`, `lapsed_unconfirmed`), and counties by typology `category`. Then restore the generated files: `git checkout -- data/processed data/review/*_worklist.csv data/review/fips_misses.csv`.
8. **Commit, QC, PR.** Commit `data/review/status_resolutions.csv` and `data/review/verification_log.csv`. Start the `qc-auditor` with the run name and lane `review`; fix every BLOCKER, commit, audit again. Push, open a PR against `main`, and list: one row per instrument (id, place, status, end date, document, access), the items not settled and why, the before and after counts, any leads, and the qc-auditor's verdict.
