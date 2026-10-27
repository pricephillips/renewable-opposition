# Operations summary

Generated 2026-10-27 by `scripts/operations_summary.py`. Every number counts rows another module wrote; check it against the file named in the key.

## Published

3340 renewables-only restriction instruments (1354 severe, 117 verified, 1 past their end date with no confirmed extension, 933 severe ones in states whose siting law limits local reach); 579 contested projects (151 confirmed); 39 cases.

Decided projects (events older than 90 days): 338, of which 244 blocked; confirmed outcomes only: 150, 80 blocked. Conditional on opposition being tracked; see headline_metrics.md.

## Held back

25 rows quarantined by the QC gate (`data/processed/qc_report.md` lists each with what releases it): 17 PRIMARY_SOURCE_CONTRADICTS, 8 SCOPE_DATA_CENTER_ONLY.

## Worklists

| Worklist | Rows | Notes |
|---|---:|---|
| outcome_worklist.csv | 420 | 136 overdue, 12 with decision language in their text, 0 with a located source |
| restriction_worklist.csv | 3298 | 1 lapsed, 407 sole severe in a county, 7 with a located source |
| negative_check_worklist.csv | 8 | 8 no check on record |
| adjacency_worklist.csv | 261 | neighbours of blocked projects not yet examined |
| fips_misses.csv | 63 | 50 several_counties, 9 not_a_2024_county, 4 not_in_lookup |

## Review and promotion

Queue: 46 promoted, 4 rejected, 6 confirmed, 2 pending, 4 awaiting_review, 83 lead. Case candidates: 230 (40 promoted, 8 started by a reviewer).

Promotion trail: 117 decisions from 2026-10-13 to 2026-10-23 (new or changed decisions only): 87 promoted, 16 held, 9 awaiting_review, 4 rejected, 1 unpublished.

| Date | File | Action | What | Reason |
|---|---|---|---|---|
| 2026-10-23 | queue.csv | promoted | CA San Joaquin County |  |
| 2026-10-23 | queue.csv | promoted | CA San Joaquin County |  |
| 2026-10-23 | queue.csv | promoted | KS Crawford County |  |
| 2026-10-23 | queue.csv | promoted | KS Crawford County |  |
| 2026-10-23 | queue.csv | promoted | KS Bourbon County |  |
| 2026-10-23 | queue.csv | held | KS Bourbon County | status expired: the instrument is no longer in force, so it is not published |
| 2026-10-23 | queue.csv | awaiting_review | KS Bourbon County | awaiting review by someone other than its drafter |
| 2026-10-23 | queue.csv | held | KS Bourbon County | status lifted: the instrument is no longer in force, so it is not published |

## What checking found

Reviewers' verdicts on primary sources, by the source family of the instrument checked (`data/review/restriction_sources.csv`). A reliability measured on what was checked, never extrapolated to the rows nobody has read.

| Source family | Instruments checked | Confirmed | Contradicted | Opened | Archived | Snippet |
|---|---:|---:|---:|---:|---:|---:|
| Moratorium Nation | 46 | 44 | 2 | 41 | 5 | 0 |
| NREL | 59 | 43 | 16 | 59 | 0 | 0 |
| Sabin | 6 | 6 | 0 | 6 | 0 | 0 |
| review queue | 1 | 0 | 1 | 1 | 0 | 0 |

Outcome resolutions: 148 (76 blocked_confirmed, 68 advanced_confirmed, 4 pending; by access 7 archived, 141 opened).

## Live intake and fetched sources

Per source in `data/raw/manifest.csv`: requests made, new content stored, unchanged and failed; when the content last changed; leads parse.py queued (`data/raw/parse_state.csv`) and what review made of them in the queue. A lead is never published until a reviewer triages it.

| Source | Requests | Stored | Unchanged | Failed | Last fetch | Last changed | Leads queued | Queue now |
|---|---:|---:|---:|---:|---|---|---:|---|
| courtlistener_renewables | 3 | 3 | 0 | 0 | 2026-10-27 | 2026-10-27 | 9 | 9 lead |
| gdelt_renewable_news | 10 | 5 | 0 | 5 | 2026-10-27 | 2026-10-27 | 16 | 16 lead |
| legistar_renewable_matters | 33 | 11 | 21 | 1 | 2026-10-27 | 2026-10-13 | 50 | 50 lead |
| moratorium_nation_upstream | 3 | 1 | 1 | 1 | 2026-10-27 | 2026-10-20 |  |  |
| nrel_solar_ordinances_2025 | 1 | 1 | 0 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| nrel_wind_ordinances_2025 | 1 | 1 | 0 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| ny_ores_permit_applications | 3 | 3 | 0 | 0 | 2026-10-27 | 2026-10-27 | 8 | 8 lead |
| sabin_2026_09_landing_html | 1 | 1 | 0 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| sabin_2026_09_projects_csv | 2 | 1 | 1 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| sabin_2026_09_report_html | 2 | 2 | 0 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| sabin_2026_09_report_pdf | 2 | 0 | 0 | 2 | 2026-10-09 |  |  |  |
| sabin_2026_09_restrictions_csv | 2 | 1 | 1 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| sabin_web_database_projects | 3 | 1 | 2 | 0 | 2026-10-27 | 2026-10-13 |  |  |
| sabin_web_database_restrictions | 3 | 1 | 2 | 0 | 2026-10-27 | 2026-10-13 |  |  |

Last error by source: gdelt_renewable_news (2026-10-27: 429 Client Error: Too Many Requests for url: https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22solar+farm%22+OR+%22solar+project%22+OR+%22wind+farm%22+OR+); legistar_renewable_matters (2026-10-27: 500 Server Error: Internal Server Error for url: https://webapi.legistar.com/v1/sanbernardino/matters?%24filter=substringof%28%27solar%27%2CMatterTitle%29+or+su); moratorium_nation_upstream (2026-10-13: 403 Client Error: Forbidden for url: https://api.github.com/repos/mjbommar/moratorium-data-2026/commits?path=data/moratorium_inventory.csv&per_page=1); sabin_2026_09_report_pdf (2026-10-09: 403 Client Error: Forbidden for url: https://scholarship.law.columbia.edu/cgi/viewcontent.cgi?article=1281&context=sabin_climate_change).

## History and archive

132 snapshot rows over 5 published files; 14 headline changes recorded (2026-09-29 to 2026-10-27). Sources: 83, of which 28 have an Internet Archive snapshot.
