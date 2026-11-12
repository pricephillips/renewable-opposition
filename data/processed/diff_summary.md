# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 7 | 5 |
| contested_projects | 0 | 0 | 3 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_5cff270095 (Falmouth Wind, MA) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_5cff270095 (Falmouth Wind, MA) | finality_evidence | outcome_label_only | resolution: https://www.capeandislands.org/local-news/2022-09-26/two-falmouth-wind-turbines-sparked-a-lawsuit-now-theyre-being-demolished |
| contested_projects | con_85f3765dd5 (Lighthouse Wind Project, NY) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_85f3765dd5 (Lighthouse Wind Project, NY) | finality_evidence | outcome_label_only | resolution: https://www.yahoo.com/news/wheres-rural-justice-turbine-plans-082721237.html |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|
| --- | res_fca69a84ba | VA | Nottoway County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_d86d946a70 | SC | Fairfield County | ->confirmed | ->opened | ->https://www.fairfieldsc.com/uploads/uploads/Article3_Conditional_Use_Regulations.pdf | ->2026-11-12 | compiled_flagged->primary_source | unverified->verified | ->2026-11-12 |
| --- | res_3b5cc968a2 | SD | Edmunds County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_93bd9c5ec6 | SD | Marshall County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_d7aa0cdc5f | SD | Meade County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_6a49a3f8ae | SD | Sully County | ->confirmed | ->opened | ->https://sully.sdcounty.gov/media/sullycountynet/Notices/Commission/2022/10.04.2022.pdf | ->2026-11-12 | compiled_flagged->primary_source | unverified->verified | ->2026-11-12 |
| --- | res_44a356790b | TN | Union County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_477a102d4c | UT | Box Elder County | ->confirmed | ->opened | ->https://www.boxeldercountyut.gov/DocumentCenter/View/420/-Chapter-5-4-Small--Large-Wind-Systems-PDF | ->2026-11-12 | compiled_flagged->primary_source | unverified->verified | ->2026-11-12 |
| -> | res_41744d4a0f | UT | Daggett County | ->confirmed | ->opened | ->https://www.daggettcounty.gov/DocumentCenter/View/7814 | ->2026-11-12 | compiled_flagged->primary_source | unverified->verified | ->2026-11-12 |
| --- | res_07298999bd | VT | Grand Isle Town |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_fff3731e1e | VA | Rockingham County | ->confirmed | ->opened | ->https://www.rockinghamcountyva.gov/documentcenter/view/390 | ->2026-11-12 | compiled_flagged->primary_source | unverified->verified | ->2026-11-12 |
| --- | res_cba382f558 | WA | Benton County |  |  |  |  | compiled_flagged | unverified |  |

### contested_projects

| @@ | id | state | project_name | outcome | finality_evidence | evidence_level | verification | county_severe_restriction_ids | resolution_url | resolution_access | resolution_date |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_5cff270095 | MA | Falmouth Wind | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://www.capeandislands.org/local-news/2022-09-26/two-falmouth-wind-turbines-sparked-a-lawsuit-now-theyre-being-demolished | report_citation->confirmed | unverified->verified | nrel:wind:2500107175;nrel:wind:2500119295;nrel:wind:2500139100;nrel:wind:2500170605;nrel:wind:2500174385 | ->https://www.capeandislands.org/local-news/2022-09-26/two-falmouth-wind-turbines-sparked-a-lawsuit-now-theyre-being-demolished | ->opened | ->2022-09 |
| -> | con_85f3765dd5 | NY | Lighthouse Wind Project | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://www.yahoo.com/news/wheres-rural-justice-turbine-plans-082721237.html | report_citation->confirmed | unverified->verified | nrel:wind:3606332490;nrel:wind:3606350232;nrel:wind:3606381380;nrel:wind:3606382370;nrel:wind:3607304572;nrel:wind:3607339188;nrel:wind:3607366751;nrel:wind:3607383448;sabin:S26R-5711;sabin:S26R-5719 | ->https://www.yahoo.com/news/wheres-rural-justice-turbine-plans-082721237.html | ->opened | ->2022-09 |
| -> | con_b0437702f8 | WA | Horse Heaven Wind Farm | pending | none | report_citation | unverified | nrel:wind:53005-> |  |  |  |
