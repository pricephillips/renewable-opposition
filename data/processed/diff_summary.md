# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 8 | 5 |
| contested_projects | 0 | 0 | 6 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_6cd4fea06c (Carina Solar, IN) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_6cd4fea06c (Carina Solar, IN) | finality_evidence | outcome_label_only | resolution: https://www.columbus.in.gov/planning/wp-content/uploads/sites/9/2024/03/County-Carina-Findings-1.pdf |
| contested_projects | con_1f641ee426 (Fox Islands Wind, ME) | outcome | needs_review | advanced_confirmed |
| contested_projects | con_1f641ee426 (Fox Islands Wind, ME) | finality_evidence | none | resolution: https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx |
| contested_projects | con_f84197e7e8 (Mars Hill Wind, ME) | outcome | blocked_unverified | advanced_confirmed |
| contested_projects | con_f84197e7e8 (Mars Hill Wind, ME) | finality_evidence | outcome_label_only | resolution: https://www.nhpr.org/2022-09-21/15-years-ago-a-small-aroostook-town-went-first-on-wind-power-and-hit-turbulence-along-the-way |
| contested_projects | con_f84197e7e8 (Mars Hill Wind, ME) | severity_score | 4 | 1 |
| contested_projects | con_0680cece0f (Pegasus Wind, MI) | outcome | blocked_unverified | restricted_conditional |
| contested_projects | con_0680cece0f (Pegasus Wind, MI) | finality_evidence | outcome_label_only | resolution: https://www.courts.michigan.gov/siteassets/case-documents/uploads/opinions/final/sct/164261_63_01.pdf |
| contested_projects | con_0680cece0f (Pegasus Wind, MI) | severity_score | 4 | 3 |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|
| --- | res_d3cb1a7ae7 | IN | Spencer County |  |  |  |  | report_citation | unverified |  |
| -> | res_0bc40dab32 | KY | Calloway County | ->confirmed | ->opened | ->https://callowaycountyky.gov/wp-content/uploads/2024/04/24-0417-A.pdf | ->2026-11-17 | report_citation->primary_source | unverified->verified | ->2026-11-17 |
| -> | res_ed8c0ae08d | KY | Todd County | ->confirmed | ->opened | ->https://eec.ky.gov/Energy/Documents/Todd%20County%20Solar%20Ordinance.pdf | ->2026-11-17 | report_citation->primary_source | unverified->verified | ->2026-11-17 |
| --- | res_27015b2964 | NY | Schroeppel Town |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_75c15f830a | OH | Huron County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_f7d31163a7 | CA | Shasta County | ->confirmed | ->opened | ->https://efiling.energy.ca.gov/GetDocument.aspx?tn=253290-1&DocumentContentId=88506 | ->2026-11-17 | compiled_flagged->primary_source | unverified->verified | ->2026-11-17 |
| --- | res_ab13b3ead4 | GA | Monroe County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_9d4174b2f9 | MI | Otsego County | ->confirmed | ->opened | ->https://www.otsegocountymi.gov/DocumentCenter/View/2917/Otsego-County-Zoning-Ordinance---Amended-August-12-2025 | ->2026-11-17 | compiled_flagged->primary_source | unverified->verified | ->2026-11-17 |
| --- | res_4160976e9e | PA | Windsor Borough |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_ce01cc829d | WV | Greenbrier County | ->confirmed | ->opened | ->https://www.greenbrierwv.gov/document_center_uploads/qa_greenbrier-county-zoning-ordinance-effective-10-13-2026.pdf | ->2026-11-17 | compiled_flagged->primary_source | unverified->verified | ->2026-11-17 |
| --- | res_5c66b2b5c0 | WI | Pierce County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_01c122dacc | WI | Sauk County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_5e7ce243dc | WY | Converse County |  |  |  |  | compiled_flagged | unverified |  |

### contested_projects

| @@ | id | state | project_name | severity_score | outcome | finality_evidence | evidence_level | verification | county_severe_restriction_ids | resolution_url | resolution_access | resolution_date | facility_conflict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_6cd4fea06c | IN | Carina Solar | 4 | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://www.columbus.in.gov/planning/wp-content/uploads/sites/9/2024/03/County-Carina-Findings-1.pdf | report_citation->confirmed | unverified->verified |  | ->https://www.columbus.in.gov/planning/wp-content/uploads/sites/9/2024/03/County-Carina-Findings-1.pdf | ->opened | ->2024-02-26 |  |
| -> | con_1f641ee426 | ME | Fox Islands Wind | 3 | needs_review->advanced_confirmed | none->resolution: https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx | report_citation->confirmed | unverified->verified | nrel:wind:2301315780;nrel:wind:2301333840;nrel:wind:2301363660;nrel:wind:2301376365;nrel:wind:2301378115;nrel:wind:2301379130;nrel:wind:2301380425 | ->https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx | ->opened | ->2009-11 | outcome needs_review, but the plant is operating-> |
| -> | con_f84197e7e8 | ME | Mars Hill Wind | 4->1 | blocked_unverified->advanced_confirmed | outcome_label_only->resolution: https://www.nhpr.org/2022-09-21/15-years-ago-a-small-aroostook-town-went-first-on-wind-power-and-hit-turbulence-along-the-way | report_citation->confirmed | unverified->verified | nrel:wind:2300301710;nrel:wind:2300360825;sabin:S26R-6017 | ->https://www.nhpr.org/2022-09-21/15-years-ago-a-small-aroostook-town-went-first-on-wind-power-and-hit-turbulence-along-the-way | ->opened | ->2007 | outcome blocked_unverified, but the plant is operating-> |
| -> | con_0680cece0f | MI | Pegasus Wind | 4->3 | blocked_unverified->restricted_conditional | outcome_label_only->resolution: https://www.courts.michigan.gov/siteassets/case-documents/uploads/opinions/final/sct/164261_63_01.pdf | report_citation | unverified->verified | sabin:S26R-5862;sabin:S26R-5865 | ->https://www.courts.michigan.gov/siteassets/case-documents/uploads/opinions/final/sct/164261_63_01.pdf | ->opened | ->2024-04-09 | outcome blocked_unverified, but the plant is operating-> |
| -> | con_16950d2943 | WY | Pioneer Wind Parks I and II | 3 | advanced_confirmed | resolution: https://www.eia.gov/electricity/data/eia860m/ | confirmed | verified | nrel:wind:56009-> | https://www.eia.gov/electricity/data/eia860m/ | opened | 2016-10 |  |
| -> | con_bff147d3f9 | WY | Pronghorn Wind and Solar | 3 | pending | none | report_citation | unverified | nrel:wind:56009-> |  |  |  |  |
