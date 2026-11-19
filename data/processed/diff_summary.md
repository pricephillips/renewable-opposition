# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 9 | 5 |
| contested_projects | 0 | 0 | 3 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_e3e2d67d23 (Tessera's Saguache County Solar Thermal Project, CO) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_e3e2d67d23 (Tessera's Saguache County Solar Thermal Project, CO) | finality_evidence | outcome_label_only | resolution: https://cleanenergyauthority.com/solar-energy-news/tessera-pulls-plug-on-huge-colorado-solar-plant-071911 |
| contested_projects | con_e7f07ecd73 (Ridgeline Wind Energy Project, ID) | outcome | blocked_unverified | pending |
| contested_projects | con_e7f07ecd73 (Ridgeline Wind Energy Project, ID) | finality_evidence | outcome_label_only | resolution: https://www.wind-watch.org/news-unarchived/WWnews_2010_08.html |
| contested_projects | con_e7f07ecd73 (Ridgeline Wind Energy Project, ID) | severity_score | 4 | 2 |
| contested_projects | con_bcdb34a15a (Valley County Wind Project, MT) | outcome | blocked_unverified | pending |
| contested_projects | con_bcdb34a15a (Valley County Wind Project, MT) | finality_evidence | outcome_label_only | resolution: https://www.spokesman.com/stories/2007/sep/25/montana-wind-farm-revived-but-smaller/ |
| contested_projects | con_bcdb34a15a (Valley County Wind Project, MT) | severity_score | 4 | 2 |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|
| --- | res_967c550313 | GA | Putnam County | confirmed | opened | https://www.putnamcountyga.us/DocumentCenter/View/1226/2026-08-07-Resolution-for-Moratorium-on-Data-Centers-BESS-Solar-Farms-signed | 2026-10-08 | primary_source | verified | 2026-10-08 |
| --- | res_bdac0a4558 | GA | Putnam County | confirmed | opened | https://www.putnamcountyga.us/DocumentCenter/View/1226/2026-08-07-Resolution-for-Moratorium-on-Data-Centers-BESS-Solar-Farms-signed | 2026-10-08 | primary_source | verified | 2026-10-08 |
| --- | res_4abf3784d0 | CO | Eagle County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_45f0b6126f | CO | Lake County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_2d5fbdcdbd | CO | Routt County | ->confirmed | ->opened | ->https://www.co.routt.co.us/DocumentCenter/View/16306/Routt-County-UDC | ->2026-11-19 | compiled_flagged->primary_source | unverified->verified | ->2026-11-19 |
| --- | res_b2b97230f8 | FL | Calhoun County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_db38a5e13c | FL | Dixie County | ->confirmed | ->opened | ->https://ncfrpc.org/MapsAndPlans/Counties/Dixie/LDR_DIXIE_21_Tan.pdf | ->2026-11-19 | compiled_flagged->primary_source | unverified->verified | ->2026-11-19 |
| -> | res_ba9f379959 | FL | Hardee County | ->confirmed | ->opened | ->https://hardeecountyfl.gov/uploads/2024/07/unified-land-development-code.pdf | ->2026-11-19 | compiled_flagged->primary_source | unverified->verified | ->2026-11-19 |
| --- | res_bf9e1e1dac | VA | Patrick County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_dfadb0d510 | CO | Cheyenne County | ->confirmed | ->opened | ->https://www.co.cheyenne.co.us/assets/pdfs/zoning_1041_adopted_regs_2019.pdf | ->2026-11-19 | compiled_flagged->primary_source | unverified->verified | ->2026-11-19 |
| --- | res_cb4c4171d7 | CO | Montezuma County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_fcc5a077c7 | CT | East Haddam Town |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_5952df1b7c | FL | Bay County | ->confirmed | ->opened | ->https://www.baycountyfl.gov/DocumentCenter/View/627/Chapter-35-Land-Development-Regulations | ->2026-11-19 | compiled_flagged->primary_source | unverified->verified | ->2026-11-19 |
| --- | res_9b15e6fc6b | MN | Wright County |  |  |  |  | compiled_flagged | unverified |  |

### contested_projects

| @@ | id | state | project_name | severity_score | outcome | finality_evidence | evidence_level | verification | resolution_url | resolution_access | resolution_date |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_e3e2d67d23 | CO | Tessera's Saguache County Solar Thermal Project | 4 | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://cleanenergyauthority.com/solar-energy-news/tessera-pulls-plug-on-huge-colorado-solar-plant-071911 | report_citation->confirmed | unverified->verified | ->https://cleanenergyauthority.com/solar-energy-news/tessera-pulls-plug-on-huge-colorado-solar-plant-071911 | ->opened | ->2011-07 |
| -> | con_e7f07ecd73 | ID | Ridgeline Wind Energy Project | 4->2 | blocked_unverified->pending | outcome_label_only->resolution: https://www.wind-watch.org/news-unarchived/WWnews_2010_08.html | report_citation | unverified->verified | ->https://www.wind-watch.org/news-unarchived/WWnews_2010_08.html | ->opened | ->2010-08 |
| -> | con_bcdb34a15a | MT | Valley County Wind Project | 4->2 | blocked_unverified->pending | outcome_label_only->resolution: https://www.spokesman.com/stories/2007/sep/25/montana-wind-farm-revived-but-smaller/ | report_citation | unverified->verified | ->https://www.spokesman.com/stories/2007/sep/25/montana-wind-farm-revived-but-smaller/ | ->opened | ->2007-09-24 |
