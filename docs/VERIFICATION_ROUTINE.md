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
reading procedure this routine follows. The agents named below are defined in
`.claude/agents/`; `docs/AGENTS.md` says what each may see and write, and
their packets go in `.packets/verify-<date>/`, which is not committed.

## 0. Setup

Start from `main` of `pricephillips/renewable-opposition` on a new branch
named `claude/verify-<date>`:

```
git fetch origin && git checkout -B claude/verify-<date> origin/main
pip install -q -c requirements/ci.txt -r requirements.txt
python scripts/review_merge.py origin/claude/verify-<earlier date> ...
python scripts/build_seed_outputs.py && python scripts/verification_worklist.py
```

The third line stacks this run on the earlier ones. List the open pull
requests titled `Verification: <date>` and name their branches, oldest first;
when none is open, skip the line. The new branch then holds the earlier
batches, so step 1 skips the items they already read, and the new pull request
merges whether or not the earlier ones are merged first. When the pull request
list cannot be read, `python scripts/review_merge.py --pending --list` names
the verification branches whose log lines are not on `main`; leave out any
whose pull request was closed without merging. If the script stops on a
conflict, do not edit a row to get past it: start from `main` alone and put
the conflict at the top of the pull request description.

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

For each item, write its card
(`python scripts/review_packets.py card <restriction|outcome> <key>`) and start
an `instrument-reader` (restrictions) or `outcome-reader` (outcomes) with it.
The reader follows `.claude/commands/verify-evidence.md`, section 2:

- Find the instrument itself (or the adopting minutes) for a restriction, or
  a news article or court record that states the outcome for a project.
  Official government sites, the county's code publisher, the Internet
  Archive copy of either, and state agency mirrors are all acceptable.
- Read it. Compare it with the published record field by field.
- Write a draft packet: the document, `access` `opened` or `archived`, the
  operative text quoted, each field compared, and the verdict (`confirmed` or
  `contradicts`) or the outcome the source supports.
  `python scripts/review_packets.py check` refuses a packet that claims a
  reading it does not show.

A source that cannot be opened is not read. If a host refuses the request,
try the Internet Archive copy or an official mirror; if none can be opened,
record the item as `not_read` in the log with each URL tried and move on.
Never treat search-result text as a reading, and never mark `access`
`opened` for a page that was not opened in this session.

## 3. Second reading (a separate reviewing agent)

Give each draft that read its document to a `blind-reviewer`, with only
the blind card (`python scripts/review_packets.py blind <card> <draft>`): the
published record, the source URL and the names of the fields the drafter
compared, never the drafter's conclusion or what it found in them. Its lane
keeps it away from the draft packets and `data/review/`. The reviewer opens
the source itself and writes a review packet of the same shape.
`python scripts/review_packets.py reconcile <card> <draft> <review>` compares
the two:

- `written`: the `record-editor` appends the row it prints (`--row`),
  signed `<drafter signature> + <reviewer signature>`.
- `disputed`: send the drafter the reviewer's packet once; if they still
  disagree, write nothing and log the item as `disputed` with both readings.

## 4. Log every attempt

The `record-editor` appends one line per item to
`data/review/verification_log.csv` (`date,queue,key,outcome,note`), as
`reconcile --log` prints it. `queue` is `restriction` or `outcome`, `key`
is the instrument id or source record id, and `outcome` is one of:

- `written`: a row was written after both readings agreed.
- `not_read`: no copy could be opened; the note lists the URLs tried.
- `disputed`: the two readings disagreed; the note gives both.
- `nothing_found`: no instrument or outcome source could be found at all.

## 5. Validate and open the pull request

```
python scripts/review_lint.py --lane review
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

Then start the `qc-auditor` (run `verify-<date>`, lane `review`): it runs
these checks again on the committed branch, re-opens a sample of the sources
read, and reports. Fix every BLOCKER, commit, and audit again; push only on
PASS or PASS WITH WARNINGS.

No em dashes, LF line endings. Push the branch and open a pull request to
`main` titled `Verification: <date>`. Its description lists, at the top,
any source that contradicts the published record, then the earlier open
batches the branch carries (section 0), then each row written
(place, verdict or outcome, source URL), then the items not read with the
reason. If nothing was written, commit the log alone, so tomorrow's run
skips what failed today, and say so in the description.

Stop after the batch. Do not edit code, workflows or any other file.

## When batches wait unmerged

Every run appends to the end of the same three files, and git merges text by
line position, so two batches that were both cut from `main` conflict with
each other even when no row overlaps. From 2026-11-08 to 2026-11-10 three
batches waited this way. Each also re-read the items of the one before,
because its log was not on `main` yet. Section 0 now prevents both: each run
starts from `main` plus the open batches.

- Merging the newest `Verification: <date>` pull request merges every batch
  it carries, and GitHub marks the earlier pull requests merged. Merging them
  oldest first also works. Use a merge commit, not a squash, so the earlier
  branches stay ancestors of `main`.
- When `main` has moved under an open research branch and GitHub reports a
  conflict in a review file, run `python scripts/review_merge.py origin/main`
  on the branch and push. The next morning's run does the same for the open
  verification batches by stacking on them.
- `scripts/review_merge.py` merges the review files by key, not by line. A
  log keeps every line either side added. A keyed file keeps one row per key.
  When two batches each wrote a row for the same item and the rows reach the
  same verdict or outcome, the earlier row is kept and the later reading stays
  in the log. When they disagree, neither row is kept and a `disputed` line
  naming both readings goes into the log, as section 3 has it for two readings
  that disagree. Both sides changing the same existing row differently is a
  real conflict: the script stops and lists the rows.

## When the routine stops

The routine can fail without reading anything and still report success: from
2026-10-13 to 2026-10-19 its session could not push, so every run stopped
after a minute. The `Review pipeline freshness` workflow
(`.github/workflows/pipeline-freshness.yml`) checks daily at 13:37 UTC. When
more than 3 days pass with no new line in `data/review/verification_log.csv`
on `main` and no open `Verification: <date>` pull request, it opens the issue
"Review pipeline stale: no verification runs". The issue closes itself when a
run lands or opens its pull request.
