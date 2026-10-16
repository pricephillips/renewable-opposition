---
description: Read the sources behind snippet-only review rows, correct the rows against them, then work the verification worklists
argument-hint: "[file or id filter, e.g. place_overrides or sabin:REC-0122; blank for all]"
---

Continue the evidence-verification process for this repository. Scope: $ARGUMENTS (when blank, take every item).

Before changing anything, read `README.md` ("Counting and verification", "Reviewing candidates", "County reports"), `docs/AGENTS.md`, `scripts/resolutions.py` (the `access` rules), `scripts/promote_reviewed.py` and `scripts/source_archive.py`.

## Rules

- The repo stays descriptive only. Never guess a value. No em dashes in anything user-facing.
- Do not special-case any county, record or instrument id in code or tests.
- `access` says how the evidence was seen: `opened` (the page or document itself was read), `archived` (an Internet Archive copy was read; its URL goes in `archived_url`), `snippet` (only search-index text was seen). Mark a row `opened` or `archived` only for a source read in this session. Search-result text is always `snippet`, however complete it looks.
- Only `opened` or `archived` evidence upgrades a record. Never loosen that rule to keep a record at a higher level.
- Never commit `data/processed/`, `data/review/fips_misses.csv` or the worklists; the Build dashboard data workflow regenerates them.

## How the work is split

You orchestrate; the agents in `.claude/agents/` read and write (`docs/AGENTS.md`). Name the run `<today>-verify` and keep its packets in `.packets/<run>/`. Give every agent a signature, `agent:<name>-<n> (Claude Code, <today>)`, numbering the agents of one role, and a packet path.

For each item:

1. **Card.** `python scripts/review_packets.py card <restriction|outcome> <key> > .packets/<run>/<queue>/<slug>.card.json`.
2. **First reading.** Start an `instrument-reader` (restrictions) or `outcome-reader` (outcomes) with the card path, its signature and the draft path `<slug>.draft.json`. Independent items can run in parallel; send them in one message.
3. **Second reading.** If the draft's `result` is `read`: `python scripts/review_packets.py blind <card> <draft> > <slug>.blind.json`, then start a `blind-reviewer` with the blind card only (never the draft or its summary), a signature that is not the drafter's, and `<slug>.review.json`.
4. **Reconcile.** `python scripts/review_packets.py reconcile <card> <draft> <review>`. If `disputed`, send the drafter the reviewer's packet once and ask it to re-read; reconcile again. Still disputed: write nothing but the log line, which gives both readings.
5. **Write.** Start the `record-editor` with the reconciled items. It appends rows with `--row`, edits an existing snippet row in place when `--row` says the key is held, and appends every log line with `--log`.

## 1. Snippet-only rows

List every row whose `access` is `snippet` in `data/review/restriction_sources.csv`, `data/review/outcome_resolutions.csv`, `data/review/place_overrides.csv` and `data/review/queue.csv` (for the queue, only rows still `pending` or `confirmed`). Each row's note lists the URLs earlier sessions tried; the card's `prior` carries them to the reader.

- `restriction_sources.csv` and `outcome_resolutions.csv`: the steps above. The reader compares the source with the published record field by field. Where the source says something the row does not (an extra setback, a different distance, a noise limit and its hours, a ban on a sub-technology, an acreage or corridor rule, a different instrument type such as resolution versus ordinance, a different date), its `fields` say so and the note records the change; where the row states something the source does not contain, the note records the removal; where the source contradicts the published record itself, the verdict is `contradicts` (restriction sources) or the outcome is corrected (outcome resolutions), with the reason.
- `queue.csv` rows: the reader that matches the row's `entity_type` reads its `source_url` and drafts corrections to `mechanisms` (semicolon-separated, `build_sabin_seeds.MECHANISM_TYPE`), `mechanism_detail` (distances, dBA and hours, acreage, caps) and the other fields. The `record-editor` writes them with "Drafted by" the reader and `review_status` `awaiting_review`; then `python scripts/review_packets.py blind-row queue_row <queue_id>` gives a `blind-reviewer` the claims to check, and the `record-editor` writes its verdict. Leave a `pending` row's status for the human reviewer unless they asked you to change it.
- `place_overrides.csv`: the claim is that the evidence names the town together with its county. A reader reads the `evidence_url`; a `blind-reviewer` gets the override's `instrument_id`, `county_fips` and `evidence_url` (never its note) as a claim check.

If no copy can be read, the row stays `snippet` and the `record-editor` appends to its note the date, each URL tried and what each attempt returned (HTTP status, rate limit, connection reset). No field changes.

If the session's network blocks most hosts, check `curl -sS "$HTTPS_PROXY/__agentproxy/status"` and tell the user which hosts were denied and that they can allow them under Network access in the environment settings.

## 2. Worklists: records still waiting on a source (only if asked, or once step 1 has nothing left to read)

Run `python scripts/build_seed_outputs.py` and `python scripts/verification_worklist.py`, then take items from the top of `data/review/outcome_worklist.csv` and `data/review/restriction_worklist.csv` (or `python scripts/verification_batch.py`). Rows with a `located_url` come first: the source is already located and only needs reading. Outcome rows with a `facility_conflict` come before them: `data/review/facility_matches.csv` has a drafted outcome, evidence URL and note from the federal plant inventories for each; the `outcome-reader` opens the inventory and checks the entry, and the row is written only if both readings match it. Each item goes through the steps above. Record what the document says, never what you expect it to say.

## 3. Checks, QC, commit, PR

1. Record the evidence counts before and after: restriction instruments at `evidence_level` = `primary_source`, and contested-project outcomes ending in `_confirmed` (count by `instrument_id` in `data/processed/`).
2. Run `python scripts/review_lint.py --lane review` and fix every error.
3. If a newly read source raises a coverage column, raise its floor in `config/coverage_expectations.json` with the reason.
4. Restore the generated files (`git checkout -- data/processed data/review/*_worklist.csv data/review/fips_misses.csv`) and commit the review-file changes with a message that says what was read and what changed.
5. Start the `qc-auditor` with the run name and lane `review`. It runs the same checks GitHub Actions runs (ruff, pytest, the build, the worklists, the layer and surface audits, the gate selftests, Vale), re-opens a sample of the sources, and reports. Fix every BLOCKER, commit, and audit again; push only on PASS or PASS WITH WARNINGS.
6. Push, open a PR against `main`, and wait for the GitHub Actions checks to finish. Have the `copy-editor` edit the PR description draft (`.packets/<run>/pr.md`) first. The description lists, at the top, anything that contradicts the published data, then:
   - the before and after evidence counts;
   - a table with one row per item: file, key, old access, new access, the URLs tried, and the field-level corrections (or "none");
   - the qc-auditor's verdict and any warnings it left.
