# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 6 | 5 |
| contested_projects | 0 | 0 | 7 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_80f44f0995 (Fairbank Wind Farm, IA) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_80f44f0995 (Fairbank Wind Farm, IA) | finality_evidence | outcome_label_only | resolution: https://cleantechnica.com/2018/12/10/court-orders-three-iowa-wind-turbines-dismantled/ |
| contested_projects | con_0703fdd11f (Harvest Wind Project, IN) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_0703fdd11f (Harvest Wind Project, IN) | finality_evidence | outcome_label_only | resolution: https://www.utilitydive.com/news/res-americas-cancels-600-mw-wind-project-in-indiana/532771/ |
| contested_projects | con_80b99e0d09 (Argyle Creek Wind Project, KS) | outcome | blocked_unverified | advanced_confirmed |
| contested_projects | con_80b99e0d09 (Argyle Creek Wind Project, KS) | finality_evidence | outcome_label_only | resolution: https://www.kscourts.gov/KSCourts/media/KsCourts/Opinions/119073.pdf |
| contested_projects | con_80b99e0d09 (Argyle Creek Wind Project, KS) | severity_score | 4 | 3 |
| contested_projects | con_2d35230faf (Searchlight Wind Project, NV) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_2d35230faf (Searchlight Wind Project, NV) | finality_evidence | outcome_label_only | resolution: https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|
| --- | res_c868246e77 | NE | York County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_fcac379fe5 | NV | Washoe County | ->confirmed | ->opened | ->https://www.washoecounty.gov/csd/planning_and_development/code_enforcement/files_forms_reports_manuals/dev_code/Cdc300%20Annotated%2009-25-26.pdf | ->2026-11-07 | compiled_flagged->primary_source | unverified->verified | ->2026-11-07 |
| --- | res_16579c2a8e | NH | Randolph Town |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_9e36fa6212 | NY | Romulus Town |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_2f97a3be6a | OH | Warren County | ->confirmed | ->opened | ->https://warrencountyohio.gov/BldgInsp/doc/ZonInfo/RuralZone/ArticleIII/Chapter2.pdf | ->2026-11-07 | compiled_flagged->primary_source | unverified->verified | ->2026-11-07 |
| -> | res_4dfa9bc2f3 | OR | Umatilla County | ->confirmed | ->opened | ->https://www.umatillacounty.gov/fileadmin/user_upload/Community_Development/Planning/Umatilla_County_Development_Code_October_21__2026.pdf | ->2026-11-07 | compiled_flagged->primary_source | unverified->verified | ->2026-11-07 |
| --- | res_8c544adb89 | OR | Wasco County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_385796d6df | PA | Athens Township | ->confirmed | ->opened | ->https://athenstownship.org/FINAL%20Formatted%20Ordinance_220114.pdf | ->2026-11-07 | compiled_flagged->primary_source | unverified->verified | ->2026-11-07 |
| --- | res_e7e147ebc5 | PA | Castanea Township |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_5220510e3a | PA | Clifford Township |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_8abd60a4d8 | PA | Clinton Township | ->confirmed | ->opened | ->https://clintontownshipwyo.org/wp/wp-content/uploads/2020/10/Clinton-SALDO-compiled-zoning-and-subdivision.pdf | ->2026-11-07 | compiled_flagged->primary_source | unverified->verified | ->2026-11-07 |

### contested_projects

| @@ | id | state | project_name | severity_score | outcome | finality_evidence | evidence_level | verification | county_severe_restriction_ids | resolution_url | resolution_access | resolution_date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_80f44f0995 | IA | Fairbank Wind Farm | 4 | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://cleantechnica.com/2018/12/10/court-orders-three-iowa-wind-turbines-dismantled/ | report_citation->confirmed | unverified->verified |  | ->https://cleantechnica.com/2018/12/10/court-orders-three-iowa-wind-turbines-dismantled/ | ->opened | ->2018-12 |
| -> | con_0703fdd11f | IN | Harvest Wind Project | 4 | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://www.utilitydive.com/news/res-americas-cancels-600-mw-wind-project-in-indiana/532771/ | report_citation->confirmed | unverified->verified | sabin:REC-0100 | ->https://www.utilitydive.com/news/res-americas-cancels-600-mw-wind-project-in-indiana/532771/ | ->opened | ->2018-09 |
| -> | con_80b99e0d09 | KS | Argyle Creek Wind Project | 4->3 | blocked_unverified->advanced_confirmed | outcome_label_only->resolution: https://www.kscourts.gov/KSCourts/media/KsCourts/Opinions/119073.pdf | report_citation->confirmed | unverified->verified |  | ->https://www.kscourts.gov/KSCourts/media/KsCourts/Opinions/119073.pdf | ->opened | ->2020-06-12 |
| -> | con_2279efb258 | NE | K-Junction Solar | 2 | pending | none | report_citation | unverified | nrel:solar:31185-> |  |  |  |
| -> | con_81e9f94eb3 | NH | Granite Reliable Wind Farm | 1 | advanced_confirmed | resolution: https://www.eia.gov/electricity/data/eia860m/ | confirmed | verified | nrel:wind:3300763860-> | https://www.eia.gov/electricity/data/eia860m/ | opened | 2012-02 |
| -> | con_2d35230faf | NV | Searchlight Wind Project | 4 | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx | report_citation->confirmed | unverified->verified |  | ->https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx | ->opened | ->2026-09 |
| -> | con_c36fd3da06 | OR | Summit Ridge Wind | 4 | blocked_confirmed | resolution: https://www.oregon.gov/energy/facilities/Facilities%20library/2024-04-19-SRW-SIGNED-Termination-Order.pdf | confirmed | verified | nrel:wind:41065-> | https://www.oregon.gov/energy/facilities/Facilities%20library/2024-04-19-SRW-SIGNED-Termination-Order.pdf | opened | 2024-04-19 |
