# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 1 | 27 |
| contested_projects | 0 | 0 | 8 |
| cases | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_f6cc30a9f4 (Noccalula Wind Energy Center, AL) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_f6cc30a9f4 (Noccalula Wind Energy Center, AL) | finality_evidence | outcome_label_only | resolution: https://www.gadsdentimes.com/story/news/local/2014/08/20/wind-farm-project-dead-leases-with-land-owners-terminated/32100439007/ |
| contested_projects | con_f1b7d028b5 (Shinbone Ridge Wind, AL) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_f1b7d028b5 (Shinbone Ridge Wind, AL) | finality_evidence | outcome_label_only | resolution: https://www.gadsdentimes.com/story/news/local/2014/08/20/wind-farm-project-dead-leases-with-land-owners-terminated/32100439007/ |
| contested_projects | con_b3b739c415 (Turkey Heaven Mountain Wind, AL) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_b3b739c415 (Turkey Heaven Mountain Wind, AL) | finality_evidence | outcome_label_only | resolution: https://www.annistonstar.com/news/wind-turbine-company-has-no-plans-for-alabama-after-lawsuit-from-cleburne-county-homeowners/article_30289b7e-775c-11e5-a572-f775a9d8f777.html |
| contested_projects | con_a27dc93458 (Cajun Crescent Energy Center, LA) | outcome | pending | blocked_confirmed |
| contested_projects | con_a27dc93458 (Cajun Crescent Energy Center, LA) | finality_evidence | none | resolution: https://caselaw.findlaw.com/court/la-court-of-appeal/219220.html |
| contested_projects | con_a27dc93458 (Cajun Crescent Energy Center, LA) | severity_score | 3 | 4 |
| contested_projects | con_7249412564 (White Castle Solar Farm, LA) | outcome | pending | blocked_confirmed |
| contested_projects | con_7249412564 (White Castle Solar Farm, LA) | finality_evidence | none | resolution: https://www.postsouth.com/story/news/local/2025/08/28/news-local-iberville-parish-government-chris-daigle-nextera-coastal-prairie-solar-project/85856726007/ |
| contested_projects | con_7249412564 (White Castle Solar Farm, LA) | severity_score | 2 | 4 |
| contested_projects | con_deca33e478 (AtlanDc Wind Project, PA) | outcome | needs_review | blocked_confirmed |
| contested_projects | con_deca33e478 (AtlanDc Wind Project, PA) | finality_evidence | none | resolution: https://www.tnonline.com/20220903/atlantic-wind-walks-away-from-watershed-plans/ |
| contested_projects | con_deca33e478 (AtlanDc Wind Project, PA) | severity_score | 2 | 4 |
| contested_projects | con_1882b23cd4 (Greenfield Township Solar Farm, PA) | outcome | pending | blocked_confirmed |
| contested_projects | con_1882b23cd4 (Greenfield Township Solar Farm, PA) | finality_evidence | none | resolution: https://www.thetimes-tribune.com/2023/02/28/greenfield-twp-zoning-board-denies-solar-farm/ |
| contested_projects | con_1882b23cd4 (Greenfield Township Solar Farm, PA) | severity_score | 2 | 4 |
| contested_projects | con_839157a24b (Runnymeade Solar Project, SC) | outcome | pending | advanced_confirmed |
| contested_projects | con_839157a24b (Runnymeade Solar Project, SC) | finality_evidence | none | resolution: https://www.wistv.com/2022/08/11/homeowners-contend-solar-farm-public-hearing/ |

## Detail

### restrictions

| @@ | id | state | jurisdiction | evidence_level | primary_source_url | primary_source_verdict | primary_source_checked_on | primary_source_access |
|---|---|---|---|---|---|---|---|---|
| --- | res_a481e40503 | CO | Washington County | compiled_flagged |  |  |  |  |
| -> | res_967c550313 | GA | Putnam County | compiled_flagged->primary_source | ->https://www.putnamcountyga.us/DocumentCenter/View/1226/2026-08-07-Resolution-for-Moratorium-on-Data-Centers-BESS-Solar-Farms-signed | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_bdac0a4558 | GA | Putnam County | compiled_flagged->primary_source | ->https://www.putnamcountyga.us/DocumentCenter/View/1226/2026-08-07-Resolution-for-Moratorium-on-Data-Centers-BESS-Solar-Farms-signed | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_aa0244cd30 | IL | Utica | compiled_flagged->primary_source | ->https://utica-il.gov/wp-content/uploads/2026/01/BOARD-MEETING-11-13-25.pdf | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_2e44b5dd8f | IL | Utica | compiled_flagged->primary_source | ->https://utica-il.gov/wp-content/uploads/2026/01/BOARD-MEETING-11-13-25.pdf | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_5c78669185 | KS | Riley County | compiled_flagged->primary_source | ->https://rileycoks.api.civicclerk.com/v1/Meetings/GetMeetingFileStream(fileId=6663,plainText=false) | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_0a3624cb01 | MI | Fayette Township (Hillsdale County) | compiled_flagged->primary_source | ->https://www.mipublicnotices.com/#/?noticeId=71ae3fb8-19cf-48c2-be53-42a21154479a | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_eabd8ef980 | MI | Fayette Township (Hillsdale County) | compiled_flagged->primary_source | ->https://www.mipublicnotices.com/#/?noticeId=71ae3fb8-19cf-48c2-be53-42a21154479a | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_d6473e9e31 | NE | Furnas County | compiled_flagged->primary_source | ->https://furnascounty.ne.gov/wp-content/uploads/sites/47/2025/08/MINUTES-8-26-25.pdf | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_522547f218 | NE | Furnas County | compiled_flagged->primary_source | ->https://furnascounty.ne.gov/wp-content/uploads/sites/47/2025/08/MINUTES-8-26-25.pdf | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_e1d2224c2a | NY | Carlton | compiled_flagged->primary_source | ->https://townofcarltonny.gov/wp-content/uploads/2025/07/Largeenergystoragemoratorium638888085374410337.pdf | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_d926683703 | NY | Chester (Orange County) | compiled_flagged->primary_source | ->https://chester-ny.gov/wp-content/uploads/2020/07/Local-Law-3-2026-Extension.pdf | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_9ad9908322 | NY | Concord | compiled_flagged->primary_source | ->https://townofconcordny.gov/files/June%2011%20TB%20(1).pdf | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_d0b2ef55cd | NY | Frankfort | compiled_flagged->primary_source | ->https://www.townoffrankfortny.gov/download/document/370 | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_3612f77e30 | NY | Frankfort | compiled_flagged->primary_source | ->https://www.townoffrankfortny.gov/download/document/370 | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_42692009ee | NY | Frankfort | compiled_flagged->primary_source | ->https://www.townoffrankfortny.gov/download/document/370 | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_6595c95c9a | NY | Halfmoon | compiled_flagged->primary_source | ->https://www.townofhalfmoon-ny.gov/public-notices/files/notice-of-adoption-extending-the-moratorium-on-battery-energy-storage-systems | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_89a27e52ab | NY | Islip | compiled_flagged->primary_source | ->https://ecode360.com/7707027 | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_aef734abb5 | NY | Livingston (Columbia County) | compiled_flagged->primary_source | ->https://townoflivingston.org/wp-content/uploads/2024/06/Local-Law-4-of-2024.pdf | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_d2f7cc44db | NY | Milton (Saratoga County) | compiled_flagged->primary_source | ->https://www.miltonny.gov/Document_center/Town%20Board/2025/Resolutions/76-2025%20-%20Local%20Law%204-2025.pdf?t=202512181055130 | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_9ef0c42509 | NY | Milton (Saratoga County) | compiled_flagged->primary_source | ->https://www.miltonny.gov/Document_center/Town%20Board/2025/Resolutions/76-2025%20-%20Local%20Law%204-2025.pdf?t=202512181055130 | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_6af7cf0cf0 | NY | New Castle | compiled_flagged->primary_source | ->https://www.mynewcastleny.gov/DocumentCenter/View/4973/LOCAL-LAW-1-2025-Six-Month-Moratorium-Prohibiting-Review-and-Approval-of-Applications-and-Permits-Battery-Energy-Systems-PDF | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_3592f44a5f | NY | Schroeppel | compiled_flagged->primary_source | ->https://www.schroeppelny.gov/tfiles/folder3450/2026-02-10%20Town%20Board%20Meeting.pdf | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_827ab8c445 | NY | Stanford | compiled_flagged->primary_source | ->https://stanfordny.gov/wp-content/uploads/2024/11/Resolution-of-Adoption-for-LL-2-of-2024-Moratorium.pdf | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_301b6660ab | NY | Stanford | compiled_flagged->primary_source | ->https://stanfordny.gov/wp-content/uploads/2024/11/Resolution-of-Adoption-for-LL-2-of-2024-Moratorium.pdf | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_ddb63a058c | NY | Town of Day | compiled_flagged->primary_source | ->https://www.townofday.com/uploads/1/4/5/5/145564982/local_law_01-2025.pdf | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_430b703492 | NY | Wilton | compiled_flagged->primary_source | ->https://townofwilton.ny.gov/government/meeting-minutes/town-board-minutes-06-04-26/ | ->confirmed | ->2026-10-08 | ->opened |
| -> | res_53a1ec0208 | OH | Swancreek Township (Fulton County) | compiled_flagged->primary_source | ->https://swancreektwp.org/wp-content/uploads/2026/06/BOT-05-04-26-SPECIAL-AND-REGULAR-MEETING-MINUTES.pdf | ->confirmed | ->2026-10-08 | ->opened |

### contested_projects

| @@ | id | state | project_name | severity_score | outcome | finality_evidence | evidence_level | resolution_url | resolution_access | resolution_date |
|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_f6cc30a9f4 | AL | Noccalula Wind Energy Center | 4 | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://www.gadsdentimes.com/story/news/local/2014/08/20/wind-farm-project-dead-leases-with-land-owners-terminated/32100439007/ | report_citation->confirmed | ->https://www.gadsdentimes.com/story/news/local/2014/08/20/wind-farm-project-dead-leases-with-land-owners-terminated/32100439007/ | ->opened | ->2014-08 |
| -> | con_f1b7d028b5 | AL | Shinbone Ridge Wind | 4 | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://www.gadsdentimes.com/story/news/local/2014/08/20/wind-farm-project-dead-leases-with-land-owners-terminated/32100439007/ | report_citation->confirmed | ->https://www.gadsdentimes.com/story/news/local/2014/08/20/wind-farm-project-dead-leases-with-land-owners-terminated/32100439007/ | ->opened | ->2014-08 |
| -> | con_b3b739c415 | AL | Turkey Heaven Mountain Wind | 4 | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://www.annistonstar.com/news/wind-turbine-company-has-no-plans-for-alabama-after-lawsuit-from-cleburne-county-homeowners/article_30289b7e-775c-11e5-a572-f775a9d8f777.html | report_citation->confirmed | ->https://www.annistonstar.com/news/wind-turbine-company-has-no-plans-for-alabama-after-lawsuit-from-cleburne-county-homeowners/article_30289b7e-775c-11e5-a572-f775a9d8f777.html | ->opened | ->2015-10-20 |
| -> | con_a27dc93458 | LA | Cajun Crescent Energy Center | 3->4 | pending->blocked_confirmed | none->resolution: https://caselaw.findlaw.com/court/la-court-of-appeal/219220.html | report_citation->confirmed | ->https://caselaw.findlaw.com/court/la-court-of-appeal/219220.html | ->opened | ->2026-07-15 |
| -> | con_7249412564 | LA | White Castle Solar Farm | 2->4 | pending->blocked_confirmed | none->resolution: https://www.postsouth.com/story/news/local/2025/08/28/news-local-iberville-parish-government-chris-daigle-nextera-coastal-prairie-solar-project/85856726007/ | report_citation->confirmed | ->https://www.postsouth.com/story/news/local/2025/08/28/news-local-iberville-parish-government-chris-daigle-nextera-coastal-prairie-solar-project/85856726007/ | ->opened | ->2025-08 |
| -> | con_deca33e478 | PA | AtlanDc Wind Project | 2->4 | needs_review->blocked_confirmed | none->resolution: https://www.tnonline.com/20220903/atlantic-wind-walks-away-from-watershed-plans/ | report_citation->confirmed | ->https://www.tnonline.com/20220903/atlantic-wind-walks-away-from-watershed-plans/ | ->opened | ->2022-09 |
| -> | con_1882b23cd4 | PA | Greenfield Township Solar Farm | 2->4 | pending->blocked_confirmed | none->resolution: https://www.thetimes-tribune.com/2023/02/28/greenfield-twp-zoning-board-denies-solar-farm/ | report_citation->confirmed | ->https://www.thetimes-tribune.com/2023/02/28/greenfield-twp-zoning-board-denies-solar-farm/ | ->opened | ->2023-02 |
| -> | con_839157a24b | SC | Runnymeade Solar Project | 3 | pending->advanced_confirmed | none->resolution: https://www.wistv.com/2022/08/11/homeowners-contend-solar-farm-public-hearing/ | report_citation->confirmed | ->https://www.wistv.com/2022/08/11/homeowners-contend-solar-farm-public-hearing/ | ->opened | ->2022-08-10 |
