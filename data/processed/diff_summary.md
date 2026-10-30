# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 4 | 7 |
| contested_projects | 0 | 0 | 3 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_cb0d940ce2 (Jacumba Solar Project, CA) | outcome | pending | advanced_confirmed |
| contested_projects | con_cb0d940ce2 (Jacumba Solar Project, CA) | finality_evidence | none | resolution: https://cetient.com/case/9926024/save-jacumba-v-san-diego-county-bd-of-supervisors-ca41 |
| contested_projects | con_f586701f99 (Ford Ridge Wind Farm, IL) | outcome | pending | advanced_confirmed |
| contested_projects | con_f586701f99 (Ford Ridge Wind Farm, IL) | finality_evidence | none | resolution: https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx |
| contested_projects | con_f586701f99 (Ford Ridge Wind Farm, IL) | severity_score | 2 | 1 |
| contested_projects | con_f38d052d45 (Gibson Solar Project, IN) | outcome | pending | advanced_confirmed |
| contested_projects | con_f38d052d45 (Gibson Solar Project, IN) | finality_evidence | none | resolution: https://insideindianabusiness.com/?p=174086 |
| contested_projects | con_f38d052d45 (Gibson Solar Project, IN) | severity_score | 2 | 1 |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|
| -> | res_7ab402377c | IN | Huntington County | ->confirmed | ->opened | ->https://www.huntington.in.us/egov/documents/1746035240_84899.pdf | ->2026-10-30 | compiled_flagged->primary_source | unverified->verified | ->2026-10-30 |
| -> | res_23c200a308 | KS | Brown County | ->confirmed | ->opened | ->https://www.brcoks.org/DocumentCenter/View/2032/Resolution-2025-20-Commercial-Solar-Regulation | ->2026-10-30 | compiled_flagged->primary_source | unverified->verified | ->2026-10-30 |
| -> | res_4c04b60cb6 | KS | Butler County | ->confirmed | ->opened | ->https://www.bucoks.com/DocumentCenter/View/154 | ->2026-10-30 | compiled_flagged->primary_source | unverified->verified | ->2026-10-30 |
| -> | res_62b8126a54 | IL | Mercer County | ->confirmed | ->opened | ->https://www.mercercountyil.org/Ordinances/Mercer%20County%20Zoning%20Ordinances.pdf | ->2026-10-30 | compiled_flagged->primary_source | unverified->verified | ->2026-10-30 |
| -> | res_f642439160 | IL | Shelby County | ->confirmed | ->opened | ->https://www.shelbycounty-il.gov/documents/Zoning/Ordinance/Zoning%20Ordinance%20For%20Shelby%20County.pdf | ->2026-10-30 | compiled_flagged->primary_source | unverified->verified | ->2026-10-30 |
| --- | res_e7aa3f8709 | IL | Warren County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_f8f6fcf845 | IN | DeKalb County | ->confirmed | ->opened | ->https://energyzoning.org/sites/default/files/PDF/18033_DeKalb_20221014.pdf | ->2026-10-30 | compiled_flagged->primary_source | unverified->verified | ->2026-10-30 |
| --- | res_9e51afd8d7 | IN | Fountain County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_f321c6cd59 | IN | Gibson County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_334c0c0f14 | IN | Hendricks County | ->confirmed | ->opened | ->https://www.co.hendricks.in.us/egov/documents/1614954326_51353.pdf | ->2026-10-30 | compiled_flagged->primary_source | unverified->verified | ->2026-10-30 |
| --- | res_f3b7a55986 | IN | Jay County |  |  |  |  | compiled_flagged | unverified |  |

### contested_projects

| @@ | id | state | project_name | severity_score | outcome | finality_evidence | evidence_level | verification | resolution_url | resolution_access | resolution_date | facility_conflict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_cb0d940ce2 | CA | Jacumba Solar Project | 3 | pending->advanced_confirmed | none->resolution: https://cetient.com/case/9926024/save-jacumba-v-san-diego-county-bd-of-supervisors-ca41 | report_citation->confirmed | unverified->verified | ->https://cetient.com/case/9926024/save-jacumba-v-san-diego-county-bd-of-supervisors-ca41 | ->opened | ->2024-01-23 | outcome pending, but the plant is operating-> |
| -> | con_f586701f99 | IL | Ford Ridge Wind Farm | 2->1 | pending->advanced_confirmed | none->resolution: https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx | report_citation->confirmed | unverified->verified | ->https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx | ->opened | ->2022-03 | outcome pending, but the plant is operating-> |
| -> | con_f38d052d45 | IN | Gibson Solar Project | 2->1 | pending->advanced_confirmed | none->resolution: https://insideindianabusiness.com/?p=174086 | report_citation->confirmed | unverified->verified | ->https://insideindianabusiness.com/?p=174086 | ->opened | ->2024-08 | outcome pending, but the plant is operating-> |
