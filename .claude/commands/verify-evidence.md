---
description: Read the sources behind snippet-only review rows, correct the rows against them, then work the verification worklists
argument-hint: "[file or id filter, e.g. place_overrides or sabin:REC-0122; blank for all]"
---

Continue the evidence-verification process for this repository. Scope: $ARGUMENTS (when blank, take every item).

Before changing anything, read `README.md` ("Counting and verification", "Reviewing candidates", "Site profiles"), `scripts/resolutions.py` (the `access` rules), `scripts/promote_reviewed.py` and `scripts/source_archive.py`.

## Rules

- The repo stays descriptive only. Never guess a value. No em dashes in anything user-facing.
- Do not special-case any county, record or instrument id in code or tests.
- `access` says how the evidence was seen: `opened` (the page or document itself was read), `archived` (an Internet Archive copy was read; its URL goes in `archived_url`), `snippet` (only search-index text was seen). Mark a row `opened` or `archived` only for a source you read in this session. Search-result text is always `snippet`, however complete it looks.
- Only `opened` or `archived` evidence upgrades a record. Never loosen that rule to keep a record at a higher level.
- Never commit `data/processed/`, `data/review/fips_misses.csv` or the worklists; the Build dashboard data workflow regenerates them.

## 1. Snippet-only rows

List every row whose `access` is `snippet` in `data/review/restriction_sources.csv`, `data/review/outcome_resolutions.csv`, `data/review/place_overrides.csv` and `data/review/queue.csv` (for the queue, only rows still `pending` or `confirmed`). Each row's note lists the URLs earlier sessions tried.

For each row:

1. Try to read the source itself, in this order:
   - fetch the URL, and the other URLs the note names;
   - if blocked, the Internet Archive: the availability API (`https://archive.org/wayback/available?url=...`) or the CDX API that `scripts/source_archive.py` uses, then read the `web.archive.org` copy;
   - if still blocked, an official mirror: the same document on a state or county site, or an `.org` that hosts the ordinance PDF.
2. If you read it, set `access` to `opened` or `archived` (with `archived_url`) and compare the source against the row field by field.
   - Where the source says something the row does not (an extra setback, a different distance, a noise limit and its hours, a ban on a sub-technology, an acreage or corridor rule, a different instrument type such as resolution versus ordinance, a different date), correct the row and say what changed in its note.
   - Where the row states something the source does not contain, remove it and note the removal.
   - Where the source contradicts the published record itself, set `verdict` to `contradicts` (restriction sources) or correct the `outcome` (outcome resolutions), and say why in the note.
   - For a queue row, also fill or correct `mechanisms` (semicolon-separated, the `build_sabin_seeds.MECHANISM_TYPE` vocabulary) and `mechanism_detail` (distances, dBA and hours, acreage, caps). Leave `review_status` for the human reviewer unless they asked you to change it.
3. If no copy can be read, leave the row `snippet` and append to its note the date, each URL tried, and what each attempt returned (HTTP status, rate limit, connection reset). No field changes.
4. If the session's network blocks most hosts, check `curl -sS "$HTTPS_PROXY/__agentproxy/status"` and tell the user which hosts were denied and that they can allow them under Network access in the environment settings.

## 2. Worklists (only if asked, or once step 1 has nothing left to read)

Run `python scripts/build_seed_outputs.py` and `python scripts/verification_worklist.py`, then take items from the top of `data/review/outcome_worklist.csv` and `data/review/restriction_worklist.csv`. Rows with a `located_url` come first: the source is already located and only needs reading. For each item you can settle from a source you read, add one row to `outcome_resolutions.csv` or `restriction_sources.csv` with every column filled, including `access`. Record what the document says, never what you expect it to say.

## 3. Checks, commit, PR

1. Record the evidence counts before and after: restriction instruments at `evidence_level` = `primary_source`, and contested-project outcomes ending in `_confirmed` (count by `instrument_id` in `data/processed/`).
2. Run everything CI runs:

   ```bash
   pip install -c requirements/ci.txt -r requirements.txt ruff daff
   ruff check .
   python -m pytest -q
   python scripts/build_seed_outputs.py
   python scripts/coverage_delta.py
   python scripts/verification_worklist.py
   python scripts/layer_audit.py
   python scripts/precommit_gates.py --selftest
   vale --no-wrap README.md docs/coverage_audit.md
   ```

   If a newly read source raises a coverage column, raise its floor in `config/coverage_expectations.json` with the reason.
3. Commit the review-file changes with a message that says what was read and what changed. Restore the generated files (`git checkout -- data/processed data/review/*_worklist.csv data/review/fips_misses.csv`) rather than committing them.
4. Push, open a PR against `main`, and wait for CI. The PR description lists, at the top, anything that contradicts the published data, then:
   - the before and after evidence counts;
   - a table with one row per item: file, key, old access, new access, the URLs tried, and the field-level corrections (or "none").
