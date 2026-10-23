# Operations summary

Generated 2026-10-23 by `scripts/operations_summary.py`. Every number counts rows another module wrote; check it against the file named in the key.

## Published

3334 renewables-only restriction instruments (1355 severe, 96 verified, 1 past their end date with no confirmed extension, 936 severe ones in states whose siting law limits local reach); 579 contested projects (148 confirmed); 39 cases.

Decided projects (events older than 90 days): 335, of which 244 blocked; confirmed outcomes only: 147, 80 blocked. Conditional on opposition being tracked; see headline_metrics.md.

## Held back

21 rows quarantined by the QC gate (`data/processed/qc_report.md` lists each with what releases it): 13 PRIMARY_SOURCE_CONTRADICTS, 8 SCOPE_DATA_CENTER_ONLY.

## Worklists

| Worklist | Rows | Notes |
|---|---:|---|
| outcome_worklist.csv | 425 | 141 overdue, 12 with decision language in their text, 0 with a located source |
| restriction_worklist.csv | 3313 | 1 lapsed, 420 sole severe in a county, 4 with a located source |
| negative_check_worklist.csv | 0 |  |
| adjacency_worklist.csv | 256 | neighbours of blocked projects not yet examined |
| fips_misses.csv | 63 | 50 several_counties, 9 not_a_2024_county, 4 not_in_lookup |

## Review and promotion

Queue: 34 promoted, 2 rejected, 3 confirmed, 2 pending, 1 awaiting_review, 70 lead. Case candidates: 230 (40 promoted, 8 started by a reviewer).

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
| Moratorium Nation | 45 | 43 | 2 | 40 | 5 | 0 |
| NREL | 45 | 33 | 12 | 45 | 0 | 0 |
| Sabin | 6 | 6 | 0 | 6 | 0 | 0 |
| review queue | 1 | 0 | 1 | 1 | 0 | 0 |

Outcome resolutions: 143 (76 blocked_confirmed, 65 advanced_confirmed, 2 pending; by access 7 archived, 136 opened).

## Live intake and fetched sources

Per source in `data/raw/manifest.csv`: requests made, new content stored, unchanged and failed; when the content last changed; leads parse.py queued (`data/raw/parse_state.csv`) and what review made of them in the queue. A lead is never published until a reviewer triages it.

| Source | Requests | Stored | Unchanged | Failed | Last fetch | Last changed | Leads queued | Queue now |
|---|---:|---:|---:|---:|---|---|---:|---|
| courtlistener_renewables | 2 | 2 | 0 | 0 | 2026-10-20 | 2026-10-20 | 9 | 9 lead |
| gdelt_renewable_news | 5 | 3 | 0 | 2 | 2026-10-20 | 2026-10-20 | 3 | 3 lead |
| legistar_renewable_matters | 22 | 11 | 11 | 0 | 2026-10-20 | 2026-10-13 | 50 | 50 lead |
| moratorium_nation_upstream | 2 | 1 | 0 | 1 | 2026-10-20 | 2026-10-20 |  |  |
| nrel_solar_ordinances_2025 | 1 | 1 | 0 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| nrel_wind_ordinances_2025 | 1 | 1 | 0 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| ny_ores_permit_applications | 2 | 2 | 0 | 0 | 2026-10-20 | 2026-10-20 | 8 | 8 lead |
| sabin_2026_09_landing_html | 1 | 1 | 0 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| sabin_2026_09_projects_csv | 2 | 1 | 1 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| sabin_2026_09_report_html | 2 | 2 | 0 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| sabin_2026_09_report_pdf | 2 | 0 | 0 | 2 | 2026-10-09 |  |  |  |
| sabin_2026_09_restrictions_csv | 2 | 1 | 1 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| sabin_web_database_projects | 2 | 1 | 1 | 0 | 2026-10-20 | 2026-10-13 |  |  |
| sabin_web_database_restrictions | 2 | 1 | 1 | 0 | 2026-10-20 | 2026-10-13 |  |  |

Last error by source: gdelt_renewable_news (2026-10-20: 429 Client Error: Too Many Requests for url: https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22solar+farm%22+OR+%22solar+project%22+OR+%22wind+farm%22+OR+); moratorium_nation_upstream (2026-10-13: 403 Client Error: Forbidden for url: https://api.github.com/repos/mjbommar/moratorium-data-2026/commits?path=data/moratorium_inventory.csv&per_page=1); sabin_2026_09_report_pdf (2026-10-09: 403 Client Error: Forbidden for url: https://scholarship.law.columbia.edu/cgi/viewcontent.cgi?article=1281&context=sabin_climate_change).

## History and archive

119 snapshot rows over 5 published files; 13 headline changes recorded (2026-09-29 to 2026-10-23). Sources: 72, of which 22 have an Internet Archive snapshot.
