# Operations summary

Generated 2026-11-21 by `scripts/operations_summary.py`. Every number counts rows another module wrote; check it against the file named in the key.

## Published

3255 renewables-only restriction instruments (1280 severe, 203 verified, 76 past their end date with no confirmed extension, 884 severe ones in states whose siting law limits local reach); 579 contested projects (190 confirmed); 39 cases.

Decided projects (events older than 90 days): 356, of which 235 blocked; confirmed outcomes only: 189, 94 blocked. Conditional on opposition being tracked; see headline_metrics.md.

## Held back

127 rows quarantined by the QC gate (`data/processed/qc_report.md` lists each with what releases it): 119 PRIMARY_SOURCE_CONTRADICTS, 8 SCOPE_DATA_CENTER_ONLY.

## Worklists

| Worklist | Rows | Notes |
|---|---:|---|
| outcome_worklist.csv | 374 | 123 overdue, 10 with decision language in their text, 0 with a located source |
| restriction_worklist.csv | 3140 | 82 lapsed, 294 sole severe in a county, 6 with a located source |
| negative_check_worklist.csv | 8 | 8 no check on record |
| adjacency_worklist.csv | 251 | neighbours of blocked projects not yet examined |
| fips_misses.csv | 63 | 50 several_counties, 9 not_a_2024_county, 4 not_in_lookup |

## Review and promotion

Queue: 54 promoted, 4 rejected, 6 confirmed, 2 pending, 4 awaiting_review, 199 lead. Case candidates: 230 (40 promoted, 8 started by a reviewer).

Promotion trail: 125 decisions from 2026-10-13 to 2026-11-05 (new or changed decisions only): 95 promoted, 16 held, 9 awaiting_review, 4 rejected, 1 unpublished.

| Date | File | Action | What | Reason |
|---|---|---|---|---|
| 2026-11-05 | queue.csv | promoted | MN Wilkin County |  |
| 2026-10-30 | queue.csv | promoted | IL Assumption |  |
| 2026-10-30 | queue.csv | promoted | IL Assumption |  |
| 2026-10-30 | queue.csv | promoted | IL Christian County |  |
| 2026-10-30 | queue.csv | promoted | IL Christian County |  |
| 2026-10-30 | queue.csv | promoted | IL Christian County |  |
| 2026-10-29 | queue.csv | promoted | IL Shelby County |  |
| 2026-10-29 | queue.csv | promoted | IL Shelby County |  |

## What checking found

Reviewers' verdicts on primary sources, by the source family of the instrument checked (`data/review/restriction_sources.csv`). A reliability measured on what was checked, never extrapolated to the rows nobody has read.

| Source family | Instruments checked | Confirmed | Contradicted | Opened | Archived | Snippet |
|---|---:|---:|---:|---:|---:|---:|
| Moratorium Nation | 60 | 47 | 13 | 55 | 5 | 0 |
| NREL | 201 | 104 | 97 | 199 | 2 | 0 |
| Sabin | 22 | 17 | 5 | 22 | 0 | 0 |
| review queue | 1 | 0 | 1 | 1 | 0 | 0 |

Outcome resolutions: 194 (93 advanced_confirmed, 90 blocked_confirmed, 9 pending, 2 restricted_conditional; by access 7 archived, 187 opened).

## Live intake and fetched sources

Per source in `data/raw/manifest.csv`: requests made, new content stored, unchanged and failed; when the content last changed; leads parse.py queued (`data/raw/parse_state.csv`) and what review made of them in the queue. A lead is never published until a reviewer triages it.

| Source | Requests | Stored | Unchanged | Failed | Last fetch | Last changed | Leads queued | Queue now |
|---|---:|---:|---:|---:|---|---|---:|---|
| courtlistener_renewables | 6 | 6 | 0 | 0 | 2026-11-17 | 2026-11-17 | 11 | 11 lead |
| gdelt_renewable_news | 25 | 12 | 0 | 13 | 2026-11-17 | 2026-11-10 | 21 | 21 lead |
| legistar_renewable_matters | 66 | 12 | 52 | 2 | 2026-11-17 | 2026-11-17 | 50 | 50 lead |
| moratorium_nation_upstream | 6 | 3 | 2 | 1 | 2026-11-17 | 2026-11-17 |  |  |
| nrel_solar_ordinances_2025 | 1 | 1 | 0 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| nrel_wind_ordinances_2025 | 1 | 1 | 0 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| ny_dos_local_laws | 3 | 3 | 0 | 0 | 2026-11-17 | 2026-11-17 | 109 | 109 lead |
| ny_ores_permit_applications | 6 | 5 | 1 | 0 | 2026-11-17 | 2026-11-17 | 8 | 8 lead |
| sabin_2026_09_landing_html | 1 | 1 | 0 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| sabin_2026_09_projects_csv | 2 | 1 | 1 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| sabin_2026_09_report_html | 2 | 2 | 0 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| sabin_2026_09_report_pdf | 2 | 0 | 0 | 2 | 2026-10-09 |  |  |  |
| sabin_2026_09_restrictions_csv | 2 | 1 | 1 | 0 | 2026-10-09 | 2026-10-09 |  |  |
| sabin_web_database_projects | 6 | 1 | 5 | 0 | 2026-11-17 | 2026-10-13 |  |  |
| sabin_web_database_restrictions | 6 | 2 | 4 | 0 | 2026-11-17 | 2026-11-03 |  |  |

Last error by source: gdelt_renewable_news (2026-11-17: 429 Client Error: Too Many Requests for url: https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22solar+farm%22+OR+%22solar+project%22+OR+%22wind+farm%22+OR+); legistar_renewable_matters (2026-11-17: 500 Server Error: Internal Server Error for url: https://webapi.legistar.com/v1/sanbernardino/matters?%24filter=substringof%28%27solar%27%2CMatterTitle%29+or+su); moratorium_nation_upstream (2026-10-13: 403 Client Error: Forbidden for url: https://api.github.com/repos/mjbommar/moratorium-data-2026/commits?path=data/moratorium_inventory.csv&per_page=1); sabin_2026_09_report_pdf (2026-10-09: 403 Client Error: Forbidden for url: https://scholarship.law.columbia.edu/cgi/viewcontent.cgi?article=1281&context=sabin_climate_change).

## History and archive

212 snapshot rows over 5 published files; 26 headline changes recorded (2026-09-29 to 2026-11-20). Sources: 87, of which 44 have an Internet Archive snapshot.
