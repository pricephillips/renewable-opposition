# Daily verification routine

A scheduled Claude Code routine runs this procedure every morning. It reads
the documents behind records that are not yet verified: the ordinance,
resolution or minutes behind a restriction, and the article or court record
behind a contested project's outcome. It opens one pull request per run, and
merging it is the only human step. Every row it writes carries the source URL,
how the source was seen, and a note saying what the document says, so each
row can be checked from the pull request.

Adapted from `pricephillips/data-center-map` `docs/research_routine.md`. The
evidence rules are this repository's own (README, "Counting and
verification"), and `.claude/commands/verify-evidence.md` holds the full
reading procedure this routine follows.

## 0. Setup

Start from `main` of `pricephillips/renewable-opposition` on a new branch
named `claude/verify-<date>`:

```
git fetch origin main && git checkout -B claude/verify-<date> origin/main
pip install -q -c requirements/ci.txt -r requirements.txt
python scripts/build_seed_outputs.py && python scripts/verification_worklist.py
```

## 1. Take the batch

```
python scripts/verification_batch.py
```

This prints 20 restriction instruments and 5 contested-project outcomes:
instruments whose source is already located come first, then worklist order.
It skips anything logged in `data/review/verification_log.csv` in the last
14 days, so a source that could not be read yesterday does not take today's
slot.

## 2. Read each item (the drafting agent)

Follow `.claude/commands/verify-evidence.md`, section 2, for each item:

- Find the instrument itself (or the adopting minutes) for a restriction, or
  a news article or court record that states the outcome for a project.
  Official government sites, the county's code publisher, the Internet
  Archive copy of either, and state agency mirrors are all acceptable.
- Read it. Compare it with the published record field by field.
- Draft one row for `data/review/restriction_sources.csv` (verdict
  `confirmed` or `contradicts`) or `data/review/outcome_resolutions.csv`
  (the outcome the source supports), with every column filled, `access`
  `opened` or `archived`, and a note that quotes the operative text.

A source that cannot be opened is not read. If a host refuses the request,
try the Internet Archive copy or an official mirror; if none can be opened,
record the item as `not_read` in the log with each URL tried and move on.
Never treat search-result text as a reading, and never mark `access`
`opened` for a page that was not opened in this session.

## 3. Second reading (a separate reviewing agent)

Give each drafted row to a separate reviewing agent (the Agent tool), with
only the row, its source URL and the published record, never the drafter's
conclusion. The reviewer opens the source itself and either agrees or names
the field it disagrees with.

- Agreed: write the row. Set `reviewer` to
  `agent:verify-drafter + agent:verify-reviewer (Claude Code)`.
- Disagreed: send it back to the drafter once with the reviewer's reading;
  if they still disagree, write nothing and log the item as `disputed` with
  both readings.

## 4. Log every attempt

Append one line per item to `data/review/verification_log.csv`
(`date,queue,key,outcome,note`). `queue` is `restriction` or `outcome`, `key`
is the instrument id or source record id, and `outcome` is one of:

- `written`: a row was written after both readings agreed.
- `not_read`: no copy could be opened; the note lists the URLs tried.
- `disputed`: the two readings disagreed; the note gives both.
- `nothing_found`: no instrument or outcome source could be found at all.

## 5. Validate and open the pull request

```
ruff check .
python -m pytest -q
python scripts/build_seed_outputs.py
python scripts/verification_worklist.py
python scripts/layer_audit.py
```

Commit only `data/review/restriction_sources.csv`,
`data/review/outcome_resolutions.csv` and `data/review/verification_log.csv`.
Restore every generated file
(`git checkout -- data/processed data/review/*_worklist.csv data/review/fips_misses.csv`);
the Build dashboard data workflow regenerates them after the merge.

No em dashes, LF line endings. Push the branch and open a pull request to
`main` titled `Verification: <date>`. Its description lists, at the top,
any source that contradicts the published record, then each row written
(place, verdict or outcome, source URL), then the items not read with the
reason. If nothing was written, commit the log alone, so tomorrow's run
skips what failed today, and say so in the description.

Stop after the batch. Do not edit code, workflows or any other file.
