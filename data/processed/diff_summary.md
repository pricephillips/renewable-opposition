# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 6 | 10 |
| contested_projects | 0 | 0 | 4 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_b5e0b42044 (Atlantic Shores South Project, NJ) | outcome | blocked_unverified | pending |
| contested_projects | con_b5e0b42044 (Atlantic Shores South Project, NJ) | finality_evidence | outcome_label_only | resolution: https://storage.courtlistener.com/pdf/2026/08/10/save_long_beach_island_inc._v._u.s._department_of_commerce.pdf |
| contested_projects | con_b5e0b42044 (Atlantic Shores South Project, NJ) | severity_score | 4 | 3 |
| contested_projects | con_c09d76bb9a (Esmeralda Seven Solar Project, NV) | outcome | blocked_unverified | pending |
| contested_projects | con_c09d76bb9a (Esmeralda Seven Solar Project, NV) | finality_evidence | outcome_label_only | resolution: https://www.esgdive.com/news/department-interior-cancels-review-nevada-solar-project-trump/802838/ |
| contested_projects | con_c09d76bb9a (Esmeralda Seven Solar Project, NV) | severity_score | 4 | 3 |
| contested_projects | con_2c16b74f26 (Birch Solar Project, OH) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_2c16b74f26 (Birch Solar Project, OH) | finality_evidence | outcome_label_only | resolution: https://dailystandard.com/archive/2025-01-16/stories/51587/developers-pull-plug-on-auglaize-solar-farm |
| contested_projects | con_5b86fd1934 (Grange Solar Grazing Center, OH) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_5b86fd1934 (Grange Solar Grazing Center, OH) | finality_evidence | outcome_label_only | resolution: https://content.govdelivery.com/accounts/OHPUC/bulletins/3e1afee |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|
| -> | res_a1f40540fe | CA | Calaveras County | ->confirmed | ->opened | ->https://planning.calaverasgov.us/Portals/Planning/Documents/Zoning%20Code%20Updates/Zoning%20Code%20Update%202023/Calaveras%20County%20Zoning%20Code_Adopted%20071624.pdf%20Accessible.pdf | ->2026-11-18 | compiled_flagged->primary_source | unverified->verified | ->2026-11-18 |
| -> | res_8676c8b697 | CA | Napa County | ->confirmed | ->opened | ->https://services.napacounty.gov/AgendaNet/DownloadDocument.aspx?type=BOS&doctype=ATTACHMENT&id=52802 | ->2026-11-18 | compiled_flagged->primary_source | unverified->verified | ->2026-11-18 |
| -> | res_2e666758b3 | CA | Riverside County | ->confirmed | ->opened | ->https://planning.rctlma.org/sites/g/files/aldnop416/files/2023-06/Ord348-04-28-2023-FINAL.pdf | ->2026-11-18 | compiled_flagged->primary_source | unverified->verified | ->2026-11-18 |
| -> | res_19b1f15f9c | CA | Sonoma County | ->confirmed | ->opened | ->https://sonomacounty.gov/Main%20County%20Site/General/Sonoma/Sample%20Dept/Department%20Information/_Ordinances/allowed_uses_requirement-exhibitC_ordinance_6046.pdf | ->2026-11-18 | compiled_flagged->primary_source | unverified->verified | ->2026-11-18 |
| -> | res_780006415f | FL | Union County | ->confirmed | ->opened | ->https://ncfrpc.org/MapsAndPlans/Counties/Union/LDR_Union_20_Canary.pdf | 2026-10-21->2026-11-18 | compiled_flagged->primary_source | unverified->verified | ->2026-11-18 |
| --- | res_d718e836a2 | MN | Pipestone County |  |  |  | 2026-10-21 | compiled_flagged | unverified |  |
| -> | res_3cf98c2cd3 | NC | Columbus County | ->confirmed | ->opened | ->https://columbusco.org/sites/default/files/uploads/planning/land-use-regulation-ordinance.pdf | 2026-10-21->2026-11-18 | compiled_flagged->primary_source | unverified->verified | ->2026-11-18 |
| --- | res_e9a182e229 | NC | Vance County |  |  |  | 2026-10-21 | compiled_flagged | unverified |  |
| -> | res_242aabc924 | CA | Colusa County | ->confirmed | ->opened | ->https://sitesreservoirproject.riptideweb.com/references/REF21/_Ch14_LandUse/Colusa%20County_2014_Zoning%20Code.pdf | ->2026-11-18 | compiled_flagged->primary_source | unverified->verified | ->2026-11-18 |
| --- | res_daae090b3a | CA | Santa Barbara County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_289f54b740 | IA | Black Hawk County | ->confirmed | ->opened | ->https://www.codepublishing.com/IA/BlackHawkCounty/html/BlackHawkCounty18/BlackHawkCounty1870.html | 2026-10-21->2026-11-18 | compiled_flagged->primary_source | unverified->verified | ->2026-11-18 |
| --- | res_5eea1e347b | IA | Carroll County |  |  |  | 2026-10-21 | compiled_flagged | unverified |  |
| -> | res_76fa4908b4 | NM | Santa Fe County | ->confirmed | ->opened | ->https://www.santafecountynm.gov/media/files/Ordinance2016-9-p0001-p0769.pdf | 2026-10-21->2026-11-18 | compiled_flagged->primary_source | unverified->verified | ->2026-11-18 |
| -> | res_e34b4662ac | ND | Stutsman County | ->confirmed | ->opened | ->https://www.stutsmancounty.gov/files/zoning-ordinance.pdf | 2026-10-21->2026-11-18 | compiled_flagged->primary_source | unverified->verified | ->2026-11-18 |
| --- | res_96de5a5c59 | WY | Fremont County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_6856647a80 | WY | Uinta County |  |  |  |  | compiled_flagged | unverified |  |

### contested_projects

| @@ | id | state | project_name | severity_score | outcome | finality_evidence | evidence_level | verification | resolution_url | resolution_access | resolution_date |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_b5e0b42044 | NJ | Atlantic Shores South Project | 4->3 | blocked_unverified->pending | outcome_label_only->resolution: https://storage.courtlistener.com/pdf/2026/08/10/save_long_beach_island_inc._v._u.s._department_of_commerce.pdf | report_citation | unverified->verified | ->https://storage.courtlistener.com/pdf/2026/08/10/save_long_beach_island_inc._v._u.s._department_of_commerce.pdf | ->opened | ->2026-08-10 |
| -> | con_c09d76bb9a | NV | Esmeralda Seven Solar Project | 4->3 | blocked_unverified->pending | outcome_label_only->resolution: https://www.esgdive.com/news/department-interior-cancels-review-nevada-solar-project-trump/802838/ | report_citation | unverified->verified | ->https://www.esgdive.com/news/department-interior-cancels-review-nevada-solar-project-trump/802838/ | ->opened | ->2025-10-14 |
| -> | con_2c16b74f26 | OH | Birch Solar Project | 4 | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://dailystandard.com/archive/2025-01-16/stories/51587/developers-pull-plug-on-auglaize-solar-farm | report_citation->confirmed | unverified->verified | ->https://dailystandard.com/archive/2025-01-16/stories/51587/developers-pull-plug-on-auglaize-solar-farm | ->opened | ->2025-01 |
| -> | con_5b86fd1934 | OH | Grange Solar Grazing Center | 4 | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://content.govdelivery.com/accounts/OHPUC/bulletins/3e1afee | report_citation->confirmed | unverified->verified | ->https://content.govdelivery.com/accounts/OHPUC/bulletins/3e1afee | ->opened | ->2025-05-22 |
