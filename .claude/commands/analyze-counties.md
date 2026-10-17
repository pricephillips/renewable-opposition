---
description: Write county pattern briefs for states or regions from the published data and the county typology - analyst, copy edit, humanizer, QC
argument-hint: "[state codes, a region name with its states, or blank for a national brief]"
---

Write pattern briefs from the published county data. Scope: $ARGUMENTS (one or more state codes, each its own brief; a named region with its states, one brief; when blank, one national brief).

Before starting, read `scripts/county_typology.py` (the categories and every column), `.claude/agents/county-analyst.md`, and `.claude/agents/copy-editor.md` ("The house style").

## Rules

- A brief describes the published record. It never explains why something happened, never predicts, and never cites the county restriction model's scores (`config/county_model_registration.json`: no score reaches a page or brief without a separate decision by Price).
- Every number traces to a file under `data/processed/`. Counts are by instrument.
- This is a prose branch: it commits only the briefs. Never commit `data/processed/`, `data/db/`, `data/snapshots/` or a worklist.
- No em dashes in anything written.

## Steps

Name the run `<today>-analysis`.

1. **Fresh typology.** Run `python scripts/county_typology.py` so `data/processed/county_typology.csv` matches the processed files in the checkout. If `git status` shows other generated files changed, the processed data is out of date with main: run `git pull` (or `git merge origin/main`) and repeat. The rows you read must be the committed ones.
2. **Analyze.** For each brief, start a `county-analyst` with its scope, the run name and the output path `deliverables/state_briefs/<today>_<scope>.md` (scope: the state code, the region's name in lowercase with underscores, or `national`). Briefs are independent; start them in one message, a few at a time.
3. **Copy edit.** Start the `copy-editor` on each brief. It checks every figure against its file and the house style.
4. **Humanizer pass.** Run the `humanizer` skill on each brief, as `CLAUDE.md` requires for client-facing prose: copy the brief to the scratchpad as `before.md`, run the pass, then the number, URL and outcome-code check from `CLAUDE.md` on the pair. It must print nothing.
5. **Checks.**

   ```bash
   python scripts/precommit_gates.py emdash deliverables/state_briefs/*.md
   vale --no-wrap deliverables/state_briefs/
   python scripts/review_lint.py --lane prose
   git checkout -- data/processed data/review/*_worklist.csv
   ```

   The last line restores the typology and any worklist step 1 rewrote.
6. **Commit, QC, PR.** Commit the briefs. Start the `qc-auditor` with the run name and lane `prose`; fix every BLOCKER, commit, audit again. Push, open a PR against `main`, and list each brief with its scope and the three or four figures it leads with, then the qc-auditor's verdict.
