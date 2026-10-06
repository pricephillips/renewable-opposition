# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 0 | 18 |
| contested_projects | 0 | 0 | 3 |
| cases | 0 | 0 | 0 |

## Column changes

- restrictions: added `primary_source_url`, `primary_source_verdict`, `primary_source_checked_on`
- contested_projects: added `resolution_date`

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_d4dbbbd76c (Flemingsburg Wind Project, KY) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_d4dbbbd76c (Flemingsburg Wind Project, KY) | finality_evidence | outcome_label_only | resolution: https://www.wmky.org/business/2014-05-10/flemingsburg-wind-project-discontinued |

## Detail

### restrictions

| @@ | id | state | jurisdiction | evidence_level | county_fips_all | county_fips_method |
|---|---|---|---|---|---|---|
| -> | res_66d7f44e41 | HI | Honolulu City | report_citation | ->15003 | ->name |
| -> | res_fd0d691db9 | KS | Cherokee | report_citation->primary_source | 20021 | name |
| -> | res_d343965aee | MI | Augusta Township | report_citation | ->26161 | place_ambiguous->override |
| -> | res_9a50f2622b | MI | Beaver Township | report_citation | ->26017 | place_ambiguous->override |
| -> | res_a8fef03b0a | MI | Beaver Township | report_citation | ->26017 | place_ambiguous->override |
| -> | res_3cd890360d | MI | Berlin Charter Township | report_citation | ->26115 | place_ambiguous->override |
| -> | res_1740547994 | MN | Scandia | report_citation | ->27163 | place_ambiguous->place_text |
| -> | res_634e7b90cf | NC | Herndon | report_citation | ->37091 | ->override |
| -> | res_8b84934ed9 | NE | Franklin Township | report_citation | ->31023 | place_ambiguous->place_text |
| -> | res_9f60f3f636 | NJ | Atlantic County | report_citation | ->34001 | ->name |
| -> | res_91aea95c72 | NY | Clinton | report_citation | ->36027 | place_ambiguous->override |
| -> | res_d05eb227e2 | NY | Florida | report_citation | ->36057 | place_ambiguous->override |
| -> | res_a400f633e0 | NY | Florida | report_citation | ->36057 | place_ambiguous->override |
| -> | res_99aed426dc | WI | Cleveland | report_citation | ->55073 | place_ambiguous->place_text |
| -> | res_965dba7e81 | WI | Deerfield | report_citation | ->55025 | place_ambiguous->override |
| -> | res_481bb45a2c | WI | Green Valley | report_citation | ->55073 | place_ambiguous->place_text |
| -> | res_e9185a1856 | WI | Springfield | report_citation | ->55025 | place_ambiguous->override |
| -> | res_4393c67d8b | WI | Union | report_citation | ->55105 | place_ambiguous->override |

### contested_projects

| @@ | id | state | project_name | outcome | finality_evidence | municipality | notes | evidence_level | county_fips_all | county_fips_method |
|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_6ed1a05d09 | CT | Ellington Airport Solar Project | pending | none | ->Ellington | ->municipality from the record's text | report_citation | ->09110 | ->place |
| -> | con_f1fc80a098 | CT | TRITEC America’s Carter Street Solar Project | pending | none | ->Manchester | ->municipality from the record's text | report_citation | ->09110 | ->place |
| -> | con_d4dbbbd76c | KY | Flemingsburg Wind Project | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://www.wmky.org/business/2014-05-10/flemingsburg-wind-project-discontinued | Flemingsburg |  | report_citation->confirmed | 21069;21161 | names |
