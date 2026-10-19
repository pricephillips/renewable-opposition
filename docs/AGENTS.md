# Agents

Who does the research work in Claude Code, what each agent sees, what it may
write, and how its work is checked. `docs/AGENT_REVIEW.md` sets the review
rules (nothing publishes without a recorded review, nobody reviews their own
work, read the document itself, say how it was seen, never guess); this file
says how the agents in `.claude/agents/` carry them out, and what enforces
them besides the agents' own instructions.

The work splits four ways, and one agent (`county-analyst`) does analysis
outside them: it reads only published data and writes pattern briefs.

- **Research extraction.** A reader finds the document behind one item and
  reports what it says, field by field, in a packet. Readers write nothing in
  the repository.
- **Editing.** One agent writes review-file rows from agreed packets, and
  another edits the prose a reader sees. Neither can browse, so neither can
  add a fact no reader saw.
- **Compartmentalization.** Each agent works in a lane that a hook enforces
  on every tool call: what it may read, what it may write, which scripts and
  git commands it may run. The second reader never sees the first reader's
  conclusion.
- **Quality control.** A blind second reading of every item, the packet
  checks, the reconciliation of the two readings by code, a lint of every
  review-file change, and an audit of the whole branch before it is pushed.

## Roster

| Agent | Lane | Part | Takes | Returns |
|---|---|---|---|---|
| `instrument-reader` | `reader` | extraction | a restriction card | a draft packet: the instrument, quoted, compared field by field, with a verdict |
| `status-checker` | `reader` | extraction | a status card | a draft packet: the current code or the minutes that acted on an instrument, with the status it has today and any end date |
| `outcome-reader` | `reader` | extraction | an outcome card | a draft packet: the document that states a project's fate, with the outcome it supports |
| `case-researcher` | `reader` | extraction | a case candidate | a draft packet: the court record's case name, court, level, docket and status |
| `lead-triager` | `reader` | extraction | live-intake leads | a draft packet: on topic, placed, and the values a read source states |
| `county-examiner` | `reader` | extraction | a county | a draft packet: governments covered, sources searched, restrictions read or a negative check |
| `blind-reviewer` | `blind` | quality control | a blind card | a review packet: its own reading, or a verdict on each claimed value |
| `record-editor` | `editor` | editing | agreed packets and verdicts | rows in the review files, signed, appended to notes |
| `copy-editor` | `copy` | editing | hand-written markdown | the same, to the house style, every number traced |
| `county-analyst` | `copy` | analysis | a scope: states, a region or the nation | a pattern brief under `deliverables/state_briefs/`, every number traced to `data/processed/` |
| `qc-auditor` | `qc` | quality control | a committed branch | a report: PASS, PASS WITH WARNINGS or FAIL, with every finding |

`tests/test_agents.py` checks this table against `.claude/agents/`, and each
agent's tools against its lane.

## Lanes

Each agent names its lane in its frontmatter (`lane: reader`).
`.claude/settings.json` runs `.claude/hooks/agent_lane.py` before every Bash,
Read, Grep, Glob, Edit and Write call; inside a subagent the call carries the
agent's name (`agent_type`), and the hook checks the call against that
agent's lane. The main session and agents with no lane pass untouched. A
refused call returns the reason and what the lane allows instead.

The hook is registered in settings, not in each agent's frontmatter, because
Claude Code skips a project agent's frontmatter hooks until the workspace
trust dialog is accepted and never runs them in a `-p` session, while
settings hooks also run inside subagents. A trial run found this: with the
hook in frontmatter, a blind reviewer in a `-p` session opened a draft packet
and `data/review/` unopposed.

| Lane | Reads | Writes | Runs |
|---|---|---|---|
| `reader` | the repository and the web | its packet under `.packets/`, or outside the repository | scripts that write nothing (`review_packets.py`, `review_lint.py`, `verification_batch.py`, `examination_batch.py`); git to look |
| `blind` | the web, the published data, code and docs; never `data/review/`, a `*.draft.json` or a `drafts/` folder | its own `*.review.json` | `review_packets.py check` only; no git; searches name a path the hook checks (never the repository root or `data/`); no `xargs` |
| `editor` | the repository; no web tools | the hand-kept review files, packets | the same scripts as a reader, `promote_reviewed.py --dry-run`; git to look |
| `copy` | the repository; no web tools | hand-written markdown (README, docs/, deliverables/); never a generated doc | `precommit_gates.py emdash`, Vale; git to look |
| `qc` | everything | its report under `.packets/` | any check, on a clean checkout of the committed branch; git to look, and `git restore` for what a check regenerated |

In every lane: reports from local contacts (`local_knowledge*`,
`$RO_LOCAL_KNOWLEDGE`, `~/.renewable-opposition`) are out of reach, and
`site_profile.py` runs only with `--no-local`; git never stages, commits,
pushes or moves a branch (the session that started the agents does that); no
file is edited in place from the shell (`sed -i`, `perl -i`); no output is
redirected, copied or downloaded into the repository outside the lane.

The hook is a guardrail, not a sandbox: `python -c` can still open any file.
Two checks look at what actually happened: `scripts/review_lint.py --lane`
fails a branch that changed a file outside its lane, and the qc-auditor runs
it before anything is pushed.

A research branch commits review files and pass notes, never a generated
file. On that branch the national database still matches
`headline_metrics.json`: it reads the negative checks from the copy main's
last build wrote (`data/processed/negative_checks.csv`), not from
`data/review/negative_checks.csv`, so the two count the same checks. The
build on main rewrites both after the merge.

## Packets

Agents pass JSON packets, never free text. A run keeps them under
`.packets/<run>/<queue>/<slug>.<kind>.json` (for example
`.packets/2026-10-16-verify/restriction/mn_ny-glenville-2025.draft.json`).
`.packets/` is not committed; the pull request description carries what a
reader of the repository needs.

| Kind | Written by | Holds |
|---|---|---|
| `card` | `review_packets.py card` | the published record, where to start, earlier attempts |
| `draft` | a reader | the document read, how it was seen, the quote, a field-by-field comparison, the conclusion, every failed URL |
| `blind` | `review_packets.py blind` or `blind-row` | the record or the claimed values, and the source; never a conclusion, note, drafter or earlier attempt |
| `review` | the blind-reviewer | its own reading, in the draft's shape (or the shape the blind card's `expect` gives) |

`scripts/review_packets.py` (module docstring) defines the fields.

- `check` refuses a packet that claims a reading without one: `access`
  snippet as a reading, no quote, a restriction verdict resting on a news
  article or on a different instrument of the same body (`relation` `other`:
  a moratorium is not the siting ordinance a record describes), a `confirmed`
  verdict over a field that disagrees, an em dash in the note.
- `reconcile` compares a draft and a review for restrictions and outcomes:
  `written` when both read the document and agree on the verdict or outcome,
  the event date and the value of every field both checked; `disputed`
  otherwise; `not_read` when either could not open it. When both read the
  same value but differ on whether it matches the record, the field is
  listed in `judgment_differences` and in the row's note and log line, with
  each reader's wording quoted when the two differ, and is not disputed.
  Values count as the same when they differ only in case, spacing,
  punctuation or thousands separators, or when one is the other followed by
  unit words ("297" and "297 MW nameplate"). In a name field, such as
  `project_name`, other annotation may follow too, unless it starts with a
  number or includes a word that changes what the name refers to ("no",
  "except", "formerly"). Any other added word ("until", "through",
  "repealed", "maximum") makes a different reading, and decimal points,
  signs and comparison symbols are part of the value. When the readings
  differ on a field's judgment, a `contradicts` verdict also needs a field
  that both readings mark as disagreeing. Only `written` yields
  a row (`--row`), signed "<drafter> + <reviewer>"; every result yields a
  `verification_log.csv` line (`--log`). A drafter and reviewer with the same
  signature are refused.
- `blind-row` builds the blind card for a lead, a case, a drafted queue row or
  a held negative check from the row itself, without its notes or signers.

## Signatures

`agent:<agent name>-<n> (Claude Code, YYYY-MM-DD)`, with `n` numbering the
agents of one role in a run: `agent:instrument-reader-2 (Claude Code,
2026-10-16)`. Notes start each entry with the date and the signature:
"Triaged 2026-10-16 by ...", "Drafted by ...", "Reviewed 2026-10-16 by ...:
confirmed." `review_lint.py` reads these to refuse a self-review, whatever the
date in the signature.

## Pipelines

The session that runs a command orchestrates: it builds cards, starts the
agents (the Agent tool, `subagent_type` the agent's name), passes packets
between them, and commits. It gives every agent its signature and packet path.

**Verification** (`/verify-evidence`, `docs/VERIFICATION_ROUTINE.md`), for
each restriction or outcome item:

1. `review_packets.py card <queue> <key>` into `<slug>.card.json`.
2. `instrument-reader` or `outcome-reader` writes `<slug>.draft.json`.
3. If the draft read the document: `review_packets.py blind` into
   `<slug>.blind.json`, and a `blind-reviewer` writes `<slug>.review.json`.
4. `review_packets.py reconcile`. Disputed: send the drafter the reviewer's
   packet once; if they still differ, log `disputed` with both readings.
5. `record-editor` appends the row (`--row`) and the log line (`--log`).

**Status** (`/check-status`): the same five steps for the `status` queue,
with `verification_batch.py --statuses N` picking instruments whose status
nobody has settled (`currency` `unknown` or `lapsed_unconfirmed`). The
`status-checker` drafts, a `blind-reviewer` reads the same document, and the
`record-editor` appends the agreed row to `status_resolutions.csv`. The next
build lays it over the record: `active` or `extended` makes the instrument
`in_force` unless its end date has passed since the reading and no later
check confirms it, `pending` makes it `pending`, and `lifted` or `expired`
takes it out of the published data.

**Triage** (`/triage-leads`): `lead-triager` drafts decisions for a batch. A
lead it read and filled gets a `blind-reviewer` triage from
`blind-row lead`; agreement makes it `confirmed`, disagreement
`awaiting_review` with "Drafted by" the triager. A lead judged from the
headline alone goes to `pending` (it cannot promote while `snippet`); an off
topic, unplaced or duplicate lead to `rejected`. The `record-editor` writes
every decision.

**Cases** (`/research-cases`): `case-researcher` drafts; a `blind-reviewer`
reads the court records from `blind-row case`; the `record-editor` fills the
candidate only when both agree on case name, court, level, docket and status,
since a filled candidate promotes on the next build.

**County checks** (`/examine-county`): `county-examiner` drafts; the
`record-editor` writes restrictions as `awaiting_review` queue rows and a
negative check with `reviewer` blank; a `blind-reviewer` checks each claim
(`blind-row queue_row`, `blind-row negative_check`); the `record-editor`
writes the verdicts; the `copy-editor` edits the pass note in
`docs/county_checks/`.

**Sweeps** (`/sweep-counties`): the county-check steps for many counties,
in waves. `examination_batch.py` picks counties in worklist rank, skipping any
attempted in the last 60 days and any with a negative check waiting for
review. Each wave runs `county-examiner`, `record-editor`, `blind-reviewer`
and `record-editor` again. The `record-editor` also appends one line per
county to `examination_log.csv`, and the sweep ends with one pass note and
one PR.

**Analysis** (`/analyze-counties`): `county_typology.py` puts each county in
one category from the published data; a `county-analyst` per scope writes a
pattern brief under `deliverables/state_briefs/`, and the `copy-editor`
checks every figure against its file. Nothing is read from `data/review/` or
`data/model/`.

**Every pipeline ends the same way**: commit, then the `qc-auditor`
(`/qc-branch`), then push only on PASS or PASS WITH WARNINGS, with the
report's findings in the pull request description. Merging stays the human
step.

## Quality control, layer by layer

| Layer | Catches |
|---|---|
| the lane hook | a reader writing a review file, a reviewer opening a draft, a commit from an agent, a local report read |
| `review_packets.py check` | a reading claimed without a document, quote or comparison; a verdict that contradicts its own fields |
| the blind second reading | a misread document, a misread field value, a confirmation the document does not support |
| `review_packets.py reconcile` | two readings that differ; a self-review |
| `review_lint.py` | an access raised with no note, a self-review, an unsigned confirmation, triage with no note, an unknown mechanism, a bad date, a file outside the lane, a generated file committed |
| `qc-auditor` | everything above on the committed branch, the CI checks, and a sample of sources re-opened to confirm the quoted text is there |
| CI and the build | the whole-file rules (`resolutions.py`, `promote_reviewed.py`, `qc_gate.py`) |
| merging the pull request | a person's judgment |

## Adding an agent

Write `.claude/agents/<name>.md` with `lane:` set to a lane from the table
above (or add a lane to `agent_lane.py`, with tests in
`tests/test_agent_lane.py`), add its
row to the roster, and give it the rules every lane shares: never guess, say
how a source was seen, no em dash in what it writes, never reach local
reports. `tests/test_agents.py` fails until the roster and the files agree.
