# Operations summary

Generated 2026-10-13 by `scripts/operations_summary.py`. Every number counts rows another module wrote; check it against the file named in the key.

## Published

3350 renewables-only restriction instruments (1364 severe, 83 verified, 1 past their end date with no confirmed extension, 942 severe ones in states whose siting law limits local reach); 576 contested projects (123 confirmed); 38 cases.

Decided projects (events older than 90 days): 309, of which 234 blocked; confirmed outcomes only: 122, 70 blocked. Conditional on opposition being tracked; see headline_metrics.md.

## Held back

9 rows quarantined by the QC gate (`data/processed/qc_report.md` lists each with what releases it): 8 SCOPE_DATA_CENTER_ONLY, 1 PRIMARY_SOURCE_CONTRADICTS.

## Worklists

| Worklist | Rows | Notes |
|---|---:|---|
| outcome_worklist.csv | 452 | 160 overdue, 13 with decision language in their text, 0 with a located source |
| restriction_worklist.csv | 3343 | 2 lapsed, 431 sole severe in a county, 13 with a located source |
| negative_check_worklist.csv | 0 |  |
| adjacency_worklist.csv | 235 | neighbours of blocked projects not yet examined |
| fips_misses.csv | 63 | 50 several_counties, 9 not_a_2024_county, 4 not_in_lookup |

## Review and promotion

Queue: 22 promoted, 3 pending, 1 awaiting_review. Case candidates: 230 (39 promoted, 7 started by a reviewer).

Promotion trail: 72 decisions from 2026-10-13 to 2026-10-13 (new or changed decisions only): 61 promoted, 10 held, 1 awaiting_review.

| Date | File | Action | What | Reason |
|---|---|---|---|---|
| 2026-10-13 | queue.csv | promoted | WY Carbon County |  |
| 2026-10-13 | queue.csv | promoted | WY Carbon County |  |
| 2026-10-13 | queue.csv | promoted | NH Moultonborough |  |
| 2026-10-13 | queue.csv | promoted | NH Durham |  |
| 2026-10-13 | queue.csv | promoted | NH Belmont |  |
| 2026-10-13 | queue.csv | promoted | DE New Castle County |  |
| 2026-10-13 | queue.csv | promoted | MD Prince George's County |  |
| 2026-10-13 | queue.csv | promoted | MD Prince George's County |  |

## What checking found

Reviewers' verdicts on primary sources, by the source family of the instrument checked (`data/review/restriction_sources.csv`). A reliability measured on what was checked, never extrapolated to the rows nobody has read.

| Source family | Instruments checked | Confirmed | Contradicted | Opened | Archived | Snippet |
|---|---:|---:|---:|---:|---:|---:|
| Moratorium Nation | 44 | 43 | 1 | 39 | 5 | 0 |
| NREL | 31 | 31 | 0 | 31 | 0 | 0 |
| Sabin | 1 | 1 | 0 | 1 | 0 | 0 |

Outcome resolutions: 116 (66 blocked_confirmed, 50 advanced_confirmed; by access 7 archived, 109 opened).

## History and archive

72 snapshot rows over 5 published files; 7 headline changes recorded (2026-09-29 to 2026-10-13). Sources: 61, of which 11 have an Internet Archive snapshot.
