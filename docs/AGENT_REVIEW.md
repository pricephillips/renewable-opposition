# Agent review

How a reviewing agent (a Claude Code subagent, or any automated reviewer)
checks a record before it publishes, and how the review is recorded. A person
reviewing follows the same rules. The rules in `README.md` ("Counting and
verification") still hold; this file adds who may review and what a review
must record.

## Rules

1. **Nothing publishes without a recorded review.** A row drafted in this
   repository (a `state_policies` row, a review-queue candidate, a negative
   check) publishes only once a review row names its reviewer, the date, how
   the document was seen (`access`) and the verdict.
2. **No self-review.** The reviewer is never the agent or person that drafted
   the row. Drafters sign `drafted_by`, reviewers sign `reviewer`, and the
   build refuses a row where the two are the same. Two subagents of one
   session are different reviewers; the session that wrote a row may not
   review it.
3. **Read the document itself.** A restriction or a state policy is checked
   against the instrument, the statute (state code or session law) or the
   minutes that adopted it. A news article, a tracker or a compiled database
   (NREL, Laws in Order, the Sabin report) locates the document but never
   verifies it. Opposition activity may rest on a news article.
4. **Say how it was seen.** `access` is `opened` (the document itself was
   read), `archived` (an Internet Archive copy was read; its URL goes in
   `archived_url`) or `snippet` (only search-index text was seen). Only
   `opened` and `archived` can make a row `verified`.
5. **Never guess.** A value the document does not state is left blank and the
   note says so. A reviewer who finds an error does not fix the drafted
   fields: the verdict says what is wrong, the drafter corrects the row, and
   the corrected row needs a fresh review.
6. **Write down what failed.** When a document cannot be read, the note lists
   every URL tried, the date and what each returned (HTTP status, Cloudflare
   challenge, egress block). The row stays unverified.
7. **No em dashes** in anything a reviewer writes that a reader will see.

## Verdicts

| Verdict | Meaning |
|---|---|
| `confirmed` | Every field checked matches the document. |
| `contradicts` | The document disagrees with at least one field; the note names the field, the row's value and the document's. |
| `unverifiable` | The document could not be read, or does not contain the provision. |

## Reviewer names

`reviewer` and `drafted_by` name the role and the run, for example
`agent:nrel-sample-reviewer-2 (Claude Code, 2026-10-09)` or
`agent:state-policy-drafter-3 (Claude Code, 2026-10-09)`. A person signs with
their name.

## Where reviews are recorded

| What | Drafted in | Reviewed in |
|---|---|---|
| State siting law (`state_policies`) | `data/review/state_policies_candidates.csv` (`drafted_by`) | the same row: `reviewer`, `reviewed_on`, `review_access`, `review_archived_url`, `review_verdict`, `review_note` |
| NREL accuracy sample | `data/review/nrel_sample.csv` (drawn by `scripts/nrel_sample.py`, seed recorded) | `data/review/nrel_sample_review.csv`, one row per sampled feature; a sampled restriction whose features all pass gets a `restriction_sources.csv` row (`verdict` confirmed) and becomes `verified` |
| Restriction instruments | `data/review/restriction_worklist.csv` | `data/review/restriction_sources.csv` |
| Review-queue candidates | `data/review/queue.csv` (`reviewer_notes` names the drafter) | `review_status` `confirmed`, with the reviewer named in `reviewer_notes` |
| Negative checks | `data/review/negative_checks.csv` | the `reviewer` column |

## Samples

When a review covers a sample rather than every row (the NREL accuracy
check), the sample is drawn by code with a fixed, recorded seed, from a sorted
list, so anyone can draw it again. Every sampled row gets a review row, even
when its document cannot be read (`unverifiable`). The error rate for a
feature is the number of `contradicts` verdicts divided by the number of
reviewed rows with a verdict of `confirmed` or `contradicts`; `unverifiable`
rows are reported apart and never counted as passes.
