---
description: Review LegiScan state bill leads - reject the off-topic ones, watch the pending ones, and draft a state siting law row (with a blind second reading) for each enacted one
argument-hint: "[state filter, e.g. VT or VT,NH; blank for all leads]"
---

Review the state bill leads in `data/review/state_bill_leads.csv`. Scope: $ARGUMENTS (when blank, every row whose `review_status` is `lead`, oldest `first_seen` first).

Before changing anything, read `README.md` ("Live intake" on LegiScan, and the state siting law paragraph), `docs/AGENT_REVIEW.md`, the docstrings of `scripts/fetch_legiscan.py` and `scripts/state_policies.py`, and `config/legiscan.json`.

## What a lead is

`fetch_legiscan.py` keeps a bill when its title, description or subjects name a technology term and a siting term. It is a lead only. It changes nothing published. Only an enacted bill, read in the session law or the codified statute, can change `data/review/state_policies_candidates.csv`, and a candidate row publishes only with a review by someone other than its drafter who read the statute (`scripts/state_policies.py`).

## Rules

- The repo stays descriptive only. Never guess a value. No em dashes in anything user-facing.
- The LegiScan status is a pointer, not evidence. "Enacted" means the state's own page or the session law shows it was signed or became law.
- The fetcher owns every column except `review_status`, `reviewer`, `reviewed_on`, `policy_id` and `review_note`. Change only those five.
- `review_status` values: `lead` (not reviewed), `pending` (on topic, not yet enacted; the weekly feed flags a change), `rejected` (off topic, or failed, vetoed or dead), `confirmed` (enacted, and its `state_policies_candidates.csv` row is written).
- Nothing an agent drafted publishes without a blind second reading (`docs/AGENT_REVIEW.md`).
- Never commit `data/processed/` or the worklists; the Build dashboard data workflow regenerates them.

## How the work is split

You orchestrate; the agents read and write (`docs/AGENTS.md`). No step waits for a person: the two readings and the record-editor decide, and merging the pull request is the only human step, as in the daily routine. Name the run `<today>-state-bills`; packets go in `.packets/<run>/state_bill/`.

1. **Triage.** Split the leads into batches of about ten, by state. For each batch start a `state-law-reader` with the rows (their JSON), a signature `agent:state-law-reader-<n> (Claude Code, <today>)` and a packet path `.packets/<run>/state_bill/batch-<n>.draft.json`. For each bill it opens the state's own page and records whether the bill is on topic and whether it was enacted, failed or is still pending (`.claude/agents/state-law-reader.md`).
2. **Draft.** For each bill that is on topic and enacted, the same reader reads the session law or the codified statute (`text_url`, the state code) and drafts the fields of one `state_policies_candidates.csv` row from it: `state`, `technology`, `policy_type` (one of the types already in that file), `who_decides`, `state_body`, `threshold_mw`, `summary`, `statute_citation`, `statute_url`, `amendments_note`, `draft_access`, `draft_note`. When the bill amends a row that already exists, it drafts the changed fields of that row and names its `policy_id`.
3. **Second reading.** For each draft, build a blind card by hand: the state, the bill number, the session law or statute URL, and the list of fields to fill, never the draft's values. Start a `blind-reviewer` with that card only, a different signature, and `.packets/<run>/state_bill/<bill_id>.review.json`. It reads the statute and fills the same fields itself.
4. **Compare.** The readings agree when `policy_type`, `who_decides`, `state_body`, `threshold_mw` and `statute_citation` match and the two summaries state the same rule.
5. **Write.** Start the `record-editor` with the triage packet and the review packets. It writes:
   - **Off topic, or failed, vetoed or dead** → `review_status` `rejected`, with the reason.
   - **On topic, not yet enacted** → `pending`, with the status read and the date.
   - **Enacted, readings agree** → the candidate row (new, or the named row updated) with `drafted_by` the reader and `reviewer`, `reviewed_on`, `review_access`, `review_verdict` `confirmed` and `review_note` from the blind reviewer; the lead gets `confirmed` and the `policy_id`.
   - **Enacted, readings differ** → the candidate row with `review_verdict` `contradicts` and the difference in `review_note` (it stays held); the lead stays `pending` with a note naming the row.

   Every lead's `review_note` gains the date, what was read, and the decision with its reason. The signatures go in `reviewer` and the notes. What was there is kept.

## Checks, QC, commit, PR

Run `python scripts/review_lint.py` on the branch, the tests for the files changed, and the `qc-auditor`. Commit only `data/review/state_bill_leads.csv`, `data/review/state_policies_candidates.csv` and any pass note. Open one pull request. The Build dashboard data workflow republishes `state_policies` after the merge, and the client portal's State Siting Law section reads that table at its next pin move.
