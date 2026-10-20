# Operations summary

Generated 2026-10-20 by `scripts/operations_summary.py`. Every number counts rows another module wrote; check it against the file named in the key.

## Published

3352 renewables-only restriction instruments (1367 severe, 89 verified, 1 past their end date with no confirmed extension, 945 severe ones in states whose siting law limits local reach); 579 contested projects (145 confirmed); 39 cases.

Decided projects (events older than 90 days): 333, of which 244 blocked; confirmed outcomes only: 144, 79 blocked. Conditional on opposition being tracked; see headline_metrics.md.

## Held back

11 rows quarantined by the QC gate (`data/processed/qc_report.md` lists each with what releases it): 8 SCOPE_DATA_CENTER_ONLY, 3 PRIMARY_SOURCE_CONTRADICTS.

## Worklists

| Worklist | Rows | Notes |
|---|---:|---|
| outcome_worklist.csv | 428 | 142 overdue, 13 with decision language in their text, 0 with a located source |
| restriction_worklist.csv | 3339 | 2 lapsed, 430 sole severe in a county, 11 with a located source |
| negative_check_worklist.csv | 0 |  |
| adjacency_worklist.csv | 256 | neighbours of blocked projects not yet examined |
| fips_misses.csv | 63 | 50 several_counties, 9 not_a_2024_county, 4 not_in_lookup |

## Review and promotion

Queue: 34 promoted, 2 rejected, 3 confirmed, 2 pending, 1 awaiting_review, 58 lead. Case candidates: 230 (40 promoted, 8 started by a reviewer).

Promotion trail: 97 decisions from 2026-10-13 to 2026-10-20 (new or changed decisions only): 75 promoted, 13 held, 6 awaiting_review, 2 rejected, 1 unpublished.

| Date | File | Action | What | Reason |
|---|---|---|---|---|
| 2026-10-20 | queue.csv | promoted | CO Logan County |  |
| 2026-10-20 | queue.csv | promoted | CO Logan County |  |
| 2026-10-20 | queue.csv | promoted | CO Logan County |  |
| 2026-10-20 | queue.csv | promoted | IA Mitchell County |  |
| 2026-10-18 | queue.csv | unpublished | TX Pasadena | status lifted: the instrument is no longer in force |
| 2026-10-17 | queue.csv | promoted | TX Pasadena |  |
| 2026-10-16 | queue.csv | promoted | TX Baytown |  |
| 2026-10-16 | queue.csv | promoted | TX Baytown |  |

## What checking found

Reviewers' verdicts on primary sources, by the source family of the instrument checked (`data/review/restriction_sources.csv`). A reliability measured on what was checked, never extrapolated to the rows nobody has read.

| Source family | Instruments checked | Confirmed | Contradicted | Opened | Archived | Snippet |
|---|---:|---:|---:|---:|---:|---:|
| Moratorium Nation | 44 | 42 | 2 | 39 | 5 | 0 |
| NREL | 33 | 31 | 2 | 33 | 0 | 0 |
| Sabin | 1 | 1 | 0 | 1 | 0 | 0 |
| review queue | 1 | 0 | 1 | 1 | 0 | 0 |

Outcome resolutions: 140 (75 blocked_confirmed, 63 advanced_confirmed, 2 pending; by access 7 archived, 133 opened).

## Live intake and fetched sources

Per source in `data/raw/manifest.csv`: requests made, new content stored, unchanged and failed; when the content last changed; leads parse.py queued (`data/raw/parse_state.csv`) and what review made of them in the queue. A lead is never published until a reviewer triages it.

| Source | Requests | Stored | Unchanged | Failed | Last fetch | Last changed | Leads queued | Queue now |
|---|---:|---:|---:|---:|---|---|---:|---|
| courtlistener_renewables | 1 | 1 | 0 | 0 | 2026-10-13 | 2026-10-13 | 1 | 1 lead |
| legistar_renewable_matters | 11 | 11 | 0 | 0 | 2026-10-13 | 2026-10-13 | 50 | 50 lead |
| moratorium_nation_upstream | 1 | 0 | 0 | 1 | 2026-10-13 |  |  |  |
| nrel_solar_ordinances_2025 | 1 | 1 | 0 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| nrel_wind_ordinances_2025 | 1 | 1 | 0 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| ny_ores_permit_applications | 1 | 1 | 0 | 0 | 2026-10-13 | 2026-10-13 | 7 | 7 lead |
| sabin_2026_09_landing_html | 1 | 1 | 0 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| sabin_2026_09_projects_csv | 2 | 1 | 1 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| sabin_2026_09_report_html | 2 | 2 | 0 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| sabin_2026_09_report_pdf | 2 | 0 | 0 | 2 | 2026-10-09 |  |  |  |
| sabin_2026_09_restrictions_csv | 2 | 1 | 1 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| sabin_web_database_projects | 1 | 1 | 0 | 0 | 2026-10-13 | 2026-10-13 |  |  |
| sabin_web_database_restrictions | 1 | 1 | 0 | 0 | 2026-10-13 | 2026-10-13 |  |  |

Last error by source: moratorium_nation_upstream (2026-10-13: 403 Client Error: Forbidden for url: https://api.github.com/repos/mjbommar/moratorium-data-2026/commits?path=data/moratorium_inventory.csv&per_page=1); sabin_2026_09_report_pdf (2026-10-09: 403 Client Error: Forbidden for url: https://scholarship.law.columbia.edu/cgi/viewcontent.cgi?article=1281&context=sabin_climate_change).

## History and archive

105 snapshot rows over 5 published files; 10 headline changes recorded (2026-09-29 to 2026-10-20). Sources: 72, of which 22 have an Internet Archive snapshot.
