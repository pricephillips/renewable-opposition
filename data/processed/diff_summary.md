# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 4 | 4 |
| contested_projects | 0 | 0 | 4 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_8c2479c496 (Monmouth Solar, ME) | outcome | pending | advanced_confirmed |
| contested_projects | con_8c2479c496 (Monmouth Solar, ME) | finality_evidence | none | resolution: https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx |
| contested_projects | con_8c2479c496 (Monmouth Solar, ME) | severity_score | 2 | 1 |
| contested_projects | con_9e151f926a (Orangeville Wind Farm, NY) | outcome | needs_review | advanced_confirmed |
| contested_projects | con_9e151f926a (Orangeville Wind Farm, NY) | finality_evidence | none | resolution: https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx |
| contested_projects | con_434f582056 (Icebreaker Wind Project, OH) | outcome | blocked_unverified | advanced_confirmed |
| contested_projects | con_434f582056 (Icebreaker Wind Project, OH) | finality_evidence | outcome_label_only | resolution: https://www.canarymedia.com/articles/offshore-wind/firstenergy-bribery-lawsuit-icebreaker-lake-erie |
| contested_projects | con_434f582056 (Icebreaker Wind Project, OH) | severity_score | 4 | 3 |
| contested_projects | con_ef4c554165 (Republic Wind Farm, OH) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_ef4c554165 (Republic Wind Farm, OH) | finality_evidence | outcome_label_only | resolution: https://www.farmanddairy.com/news/ohio-power-siting-board-denies-rehearing-for-republic-wind/708236.html |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|
| --- | res_2fcfbab247 | GA | Carroll County |  |  |  | 2026-09-23 | compiled_record | unverified |  |
| --- | res_c74e8da3c9 | GA | Carroll County |  |  |  | 2026-09-23 | compiled_record | unverified |  |
| --- | res_d7bd0ac80c | SD | Sully County |  |  |  |  | report_citation | unverified |  |
| -> | res_9b4785696e | IN | Carroll County | ->confirmed | ->opened | ->https://www.in.gov/dA/c96936182f/ORDINANCE-2024-11.pdf?language_id=1 | ->2026-11-16 | compiled_flagged->primary_source | unverified->verified | ->2026-11-16 |
| -> | res_500e1fb0ec | IN | Spencer County | ->confirmed | ->opened | ->https://www.in.gov/dA/6fb2542150/2023-16-Ordinance-Solar-Energy.pdf?language_id=1 | ->2026-11-16 | compiled_flagged->primary_source | unverified->verified | ->2026-11-16 |
| -> | res_0b45c74dc9 | KY | Todd County | ->confirmed | ->opened | ->https://eec.ky.gov/Energy/Documents/Todd%20County%20Solar%20Ordinance.pdf | ->2026-11-16 | compiled_flagged->primary_source | unverified->verified | ->2026-11-16 |
| --- | res_81fba8020a | IN | Franklin County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_a4704ca0bf | WA | Kittitas County | ->confirmed | ->opened | ->https://ecode360.com/45418564 | ->2026-11-16 | compiled_flagged->primary_source | unverified->verified | ->2026-11-16 |

### contested_projects

| @@ | id | state | project_name | severity_score | outcome | finality_evidence | evidence_level | verification | resolution_url | resolution_access | resolution_date | facility_conflict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_8c2479c496 | ME | Monmouth Solar | 2->1 | pending->advanced_confirmed | none->resolution: https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx | report_citation->confirmed | unverified->verified | ->https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx | ->opened | ->2022-03 | outcome pending, but the plant is operating-> |
| -> | con_9e151f926a | NY | Orangeville Wind Farm | 3 | needs_review->advanced_confirmed | none->resolution: https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx | report_citation->confirmed | unverified->verified | ->https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx | ->opened | ->2013-11 | outcome needs_review, but the plant is operating-> |
| -> | con_434f582056 | OH | Icebreaker Wind Project | 4->3 | blocked_unverified->advanced_confirmed | outcome_label_only->resolution: https://www.canarymedia.com/articles/offshore-wind/firstenergy-bribery-lawsuit-icebreaker-lake-erie | report_citation->confirmed | unverified->verified | ->https://www.canarymedia.com/articles/offshore-wind/firstenergy-bribery-lawsuit-icebreaker-lake-erie | ->opened | ->2022 |  |
| -> | con_ef4c554165 | OH | Republic Wind Farm | 4 | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://www.farmanddairy.com/news/ohio-power-siting-board-denies-rehearing-for-republic-wind/708236.html | report_citation->confirmed | unverified->verified | ->https://www.farmanddairy.com/news/ohio-power-siting-board-denies-rehearing-for-republic-wind/708236.html | ->opened | ->2022-03-17 |  |
