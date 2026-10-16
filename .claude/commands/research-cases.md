---
description: Find the court records behind litigated projects and restrictions (cases_candidates.csv) - draft, blind second reading, write only what both agree on
argument-hint: "[source_record_ids or a state, e.g. REC-0144 or IA; blank for the first ten candidates awaiting docket research]"
---

Research the court records behind `data/review/cases_candidates.csv`. Scope: $ARGUMENTS (when blank, the first ten rows whose `review_status` is `needs_docket_research` or `lead` and whose case fields are empty).

Before changing anything, read `README.md` ("Cases: status and verification", "Reviewing candidates"), `docs/AGENT_REVIEW.md` and `docs/AGENTS.md`.

## Rules

- A case enters the data only once a court record (an opinion, a docket, or a court's own page, on CourtListener, Justia, govinfo, a court website or an equivalent case-law host) names the case and its court. A news article or the candidate's `litigation_context` locates a case; it never verifies one.
- Promotion is automatic: a candidate with `case_name`, `court`, `court_level` and an http(s) `case_source_url` promotes on the next build. So the case fields are written only after a blind second reading agrees on all of them.
- Never guess a value; no em dashes in anything a reader sees.
- Never commit `data/processed/`, the seeds or the worklists.

## How the work is split

Name the run `<today>-cases`; packets go in `.packets/<run>/case/`.

1. **Draft.** For each candidate start a `case-researcher` with the row's JSON, a signature `agent:case-researcher-<n> (Claude Code, <today>)` and `.packets/<run>/case/<slug>.draft.json`, several in one message.
2. **Second reading.** For each draft that names a court record: `python scripts/review_packets.py blind-row case <source_record_id> --draft <draft> > <slug>.blind.json`, and start a `blind-reviewer` with that card only and a different signature.
3. **Compare.** They agree when each case has the same case name (as styled), court, court level, docket number and status. A status the reviewer read later than the drafter (a ruling after an appeal) is a disagreement to resolve by sending the drafter the reviewer's packet once.
4. **Write.** Start the `record-editor`: for agreed candidates it fills the case fields and appends both readings to `reviewer_notes`; for one fight with several cases it duplicates the row, one per case; for disagreements and `not_read` or `nothing_found` it fills nothing and appends the readings and the URLs tried.

## Checks, QC, commit, PR

1. `python scripts/review_lint.py --lane review` and `python scripts/promote_reviewed.py --dry-run` (it lists the cases that will promote); fix every lint error.
2. Commit `data/review/cases_candidates.csv`.
3. Start the `qc-auditor` with the run name and lane `review`. Fix every BLOCKER, commit, audit again.
4. Push, open a PR against `main` listing each case that will promote (case, court, status, the record read), the candidates left unresolved and why, and the qc-auditor's verdict.
