# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 11 | 121 |
| contested_projects | 0 | 0 | 8 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_a1a6ea95bb (Granite Mountain Wind Energy Project, CA) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_a1a6ea95bb (Granite Mountain Wind Energy Project, CA) | finality_evidence | outcome_label_only | resolution: https://www.pbssocal.org/redefine/another-california-wind-energy-project-canceled |
| contested_projects | con_0c57b822fa (Silurian Valley Solar Development, CA) | outcome | blocked_unverified | pending |
| contested_projects | con_0c57b822fa (Silurian Valley Solar Development, CA) | finality_evidence | outcome_label_only | resolution: https://www.pbssocal.org/redefine/firm-appeals-feds-no-go-of-silurian-valley-solar |
| contested_projects | con_0c57b822fa (Silurian Valley Solar Development, CA) | severity_score | 4 | 2 |
| contested_projects | con_2e46813b3e (Beautiful Hill Wind Farm, WI) | outcome | blocked_unverified | pending |
| contested_projects | con_2e46813b3e (Beautiful Hill Wind Farm, WI) | finality_evidence | outcome_label_only | resolution: https://manitowoccountywi.gov/wp-content/uploads/2021/03/planning-2013.pdf |
| contested_projects | con_2e46813b3e (Beautiful Hill Wind Farm, WI) | severity_score | 4 | 2 |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | status_as_of | months_in_force | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | res_683dbf36c2 | CA | Imperial |  |  |  | 2026-09-23 | 5.6->5.7 | compiled_record | unverified |  |
| -> | res_d800b671a0 | CA | Morgan Hill |  |  |  | 2026-09-23 | 2.8->2.9 | compiled_record | unverified |  |
| -> | res_d15e0601e4 | CA | San Juan Capistrano | confirmed | opened | https://ecode360.com/44277491 | 2026-10-08 | 20.1->20.2 | primary_source | verified | 2026-10-08 |
| -> | res_e9f1af5f5d | CO | Grand County | confirmed | archived | https://www.co.grand.co.us/AgendaCenter/ViewFile/Minutes/_06242025-2747 | 2026-10-08 | 16.9->17.0 | primary_source | verified | 2026-10-08 |
| -> | res_1ba648b44c | CO | Grand County | confirmed | archived | https://www.co.grand.co.us/AgendaCenter/ViewFile/Minutes/_06242025-2747 | 2026-10-08 | 16.9->17.0 | primary_source | verified | 2026-10-08 |
| -> | res_b0a803b9a1 | CO | Grand County | confirmed | archived | https://www.co.grand.co.us/AgendaCenter/ViewFile/Minutes/_06242025-2747 | 2026-10-08 | 16.9->17.0 | primary_source | verified | 2026-10-08 |
| -> | res_5003f748a1 | IL | City of West Chicago |  |  |  | 2026-07-20 | 4.0->4.1 | compiled_record | unverified |  |
| -> | res_c71cadf8a3 | IL | Sterling |  |  |  | 2026-09-23 | 2.4->2.5 | compiled_record | unverified |  |
| -> | res_aa0244cd30 | IL | Utica | confirmed | opened | https://utica-il.gov/wp-content/uploads/2026/01/BOARD-MEETING-11-13-25.pdf | 2026-10-08 | 7.4->7.5 | primary_source | verified | 2026-10-08 |
| -> | res_2e44b5dd8f | IL | Utica | confirmed | opened | https://utica-il.gov/wp-content/uploads/2026/01/BOARD-MEETING-11-13-25.pdf | 2026-10-08 | 7.4->7.5 | primary_source | verified | 2026-10-08 |
| -> | res_3b1b9e57c3 | IN | Dearborn County |  |  |  | 2026-04-29 | 8.9->9.0 | compiled_record | unverified |  |
| -> | res_7f59df981c | IN | Dearborn County |  |  |  | 2026-04-29 | 8.9->9.0 | compiled_record | unverified |  |
| -> | res_fb7e366860 | IN | Elkhart |  |  |  | 2026-09-23 | 2.8->2.9 | compiled_record | unverified |  |
| -> | res_7b36d14b7f | IN | Huntington County | ->confirmed | ->opened | ->https://www.huntington.in.us/egov/documents/1774460864_7215.pdf | 2026-09-23->2026-11-21 | 7.2 | compiled_record->primary_source | unverified->verified | ->2026-11-21 |
| -> | res_474c83417c | IN | Putnam County |  |  |  | 2025-11-17 | 12.1->12.2 | compiled_record | unverified |  |
| -> | res_c1fc1fefb8 | IN | Putnam County |  |  |  | 2025-11-17 | 12.1->12.2 | compiled_record | unverified |  |
| -> | res_5ed8f61ebb | IA | Adair County |  |  |  | 2026-09-23 | 8.1->8.2 | compiled_record | unverified |  |
| -> | res_eb3be1294e | IA | Audubon County |  |  |  | 2026-09-23 | 15.3->15.4 | compiled_record | unverified |  |
| -> | res_55a77dd03c | IA | Henry County |  |  |  | 2026-09-23 | 6.2->6.3 | compiled_record | unverified |  |
| -> | res_3d9daa14e1 | IA | Jackson County |  |  |  | 2026-09-23 | 34.6->34.7 | compiled_record | unverified |  |
| -> | res_f2c9ca8cc1 | IA | Madison County |  |  |  | 2026-09-23 | 5.8->5.9 | compiled_flagged | unverified |  |
| -> | res_2e86541afe | IA | Shelby County | confirmed | archived | https://shelbycounty.iowa.gov/files/meetings/2026-03-17_minutes_2701.pdf | 2026-10-08 | 8.1->8.2 | primary_source | verified | 2026-10-08 |
| -> | res_652e45dcbf | IA | Shelby County | confirmed | archived | https://shelbycounty.iowa.gov/files/meetings/2026-03-17_minutes_2701.pdf | 2026-10-08 | 8.1->8.2 | primary_source | verified | 2026-10-08 |
| -> | res_2ba4ec788f | IA | Shelby County | confirmed | archived | https://shelbycounty.iowa.gov/files/meetings/2026-03-17_minutes_2701.pdf | 2026-10-08 | 8.1->8.2 | primary_source | verified | 2026-10-08 |
| -> | res_527a1dc866 | IA | Story County |  |  |  | 2026-09-23 | 17.1->17.2 | compiled_record | unverified |  |
| -> | res_af963b1c8d | KS | Brown County | confirmed | opened | https://www.brcoks.org/AgendaCenter/ViewFile/Minutes/_03022026-94 | 2026-10-31 | 8.6->8.7 | primary_source | verified | 2026-10-31 |
| -> | res_0d2122ecfe | KS | Brown County | confirmed | opened | https://www.brcoks.org/AgendaCenter/ViewFile/Minutes/_03022026-94 | 2026-10-31 | 8.6->8.7 | primary_source | verified | 2026-10-31 |
| -> | res_4386dd0d91 | KS | Dickinson County |  |  |  | 2026-09-23 | 3.7->3.8 | compiled_record | unverified |  |
| -> | res_faab116695 | KS | Dickinson County |  |  |  | 2026-09-23 | 3.7->3.8 | compiled_record | unverified |  |
| -> | res_e4af898e31 | KS | Dickinson County |  |  |  | 2026-09-23 | 3.7->3.8 | compiled_record | unverified |  |
| -> | res_0110318ca3 | KS | Lyon County |  |  |  | 2026-07-31 | 3.9->4.0 | compiled_record | unverified |  |
| -> | res_ac1d7084ff | KS | Marion County |  |  |  | 2026-09-23 | 8.6->8.7 | compiled_record | unverified |  |
| -> | res_5c78669185 | KS | Riley County | confirmed | opened | https://rileycoks.api.civicclerk.com/v1/Meetings/GetMeetingFileStream(fileId=6663,plainText=false) | 2026-10-08 | 6.1->6.2 | primary_source | verified | 2026-10-08 |
| -> | res_6a34b6143a | KS | Sedgwick County |  |  |  | 2026-09-23 | 8.3->8.4 | compiled_record | unverified |  |
| -> | res_8b4294e62e | KS | Sedgwick County |  |  |  | 2026-09-23 | 5.1->5.2 | compiled_record | unverified |  |
| -> | res_f9da48d14b | KS | South Hutchinson |  |  |  | 2026-09-23 | 5.8->5.9 | compiled_record | unverified |  |
| -> | res_83d055e0a7 | LA | Iberville Parish |  |  |  | 2026-09-23 | 4.2->4.3 | compiled_record | unverified |  |
| -> | res_8c04d9587b | ME | Warren |  |  |  | 2026-09-23 | 4.4->4.5 | compiled_record | unverified |  |
| -> | res_4a0069a5be | MI | Allendale Township |  |  |  | 2026-07-31 | 5.4->5.5 | compiled_record | unverified |  |
| -> | res_a83d69672e | MI | Allendale Township |  |  |  | 2026-07-31 | 5.4->5.5 | compiled_record | unverified |  |
| -> | res_27db754062 | MI | Allendale Township |  |  |  | 2026-07-31 | 5.4->5.5 | compiled_record | unverified |  |
| --- | res_6658d3c6e4 | MI | Casco Township (Allegan County) |  |  |  | 2026-09-23 | 6.0 | compiled_record | unverified |  |
| --- | res_379a7bcdd7 | MI | Casco Township (Allegan County) |  |  |  | 2026-09-23 | 6.0 | compiled_record | unverified |  |
| -> | res_afc4608b28 | MI | Gun Plain Charter Township |  |  |  | 2026-09-23 | 3.5->3.6 | compiled_record | unverified |  |
| -> | res_c2a43ef06b | MI | Hillsdale Township (Hillsdale County) |  |  |  | 2026-09-23 | 5.4->5.5 | compiled_record | unverified |  |
| -> | res_17332b412a | MI | Hillsdale Township (Hillsdale County) |  |  |  | 2026-09-23 | 5.4->5.5 | compiled_record | unverified |  |
| -> | res_47f6518d82 | MI | Hillsdale Township (Hillsdale County) |  |  |  | 2026-09-23 | 5.4->5.5 | compiled_record | unverified |  |
| -> | res_56fcf2fc81 | MI | Huron County (solar and battery storage) |  |  |  | 2026-09-23 | 6.3->6.4 | compiled_record | unverified |  |
| -> | res_2a180b4ea5 | MI | Huron County (solar and battery storage) |  |  |  | 2026-09-23 | 6.3->6.4 | compiled_record | unverified |  |
| -> | res_daead303c0 | MI | Kalamazoo |  |  |  | 2026-09-23 | 3.1->3.2 | compiled_record | unverified |  |
| -> | res_20b5316c49 | MI | Kalamazoo Township |  |  |  | 2026-09-23 | 3.8->3.9 | compiled_record | unverified |  |
| -> | res_78310c4fca | MI | Oshtemo Charter Township |  |  |  | 2026-09-23 | 3.3->3.4 | compiled_record | unverified |  |
| -> | res_bc38ac7804 | MI | Portage |  |  |  | 2026-09-23 | 8.9->9.0 | compiled_record | unverified |  |
| -> | res_7c97b89755 | MI | Webster Township |  |  |  | 2026-09-23 | 7.0->7.1 | compiled_record | unverified |  |
| -> | res_937d40a25c | MO | Cedar County |  |  |  | 2026-09-23 | 2.4->2.5 | compiled_record | unverified |  |
| -> | res_a986d9d2c2 | MO | Cedar County |  |  |  | 2026-09-23 | 2.4->2.5 | compiled_record | unverified |  |
| -> | res_79b5d401a8 | MO | Cedar County |  |  |  | 2026-09-23 | 2.4->2.5 | compiled_record | unverified |  |
| -> | res_d9e7cf22f1 | MO | City of Independence |  |  |  | 2026-09-23 | 4.5->4.6 | compiled_record | unverified |  |
| -> | res_e843ecae6e | NE | Fillmore County |  |  |  | 2026-09-23 | 4.9->5.0 | compiled_record | unverified |  |
| -> | res_d6473e9e31 | NE | Furnas County | confirmed | opened | https://furnascounty.ne.gov/wp-content/uploads/sites/47/2025/08/MINUTES-8-26-25.pdf | 2026-10-08 | 14.8->14.9 | primary_source | verified | 2026-10-08 |
| -> | res_522547f218 | NE | Furnas County | confirmed | opened | https://furnascounty.ne.gov/wp-content/uploads/sites/47/2025/08/MINUTES-8-26-25.pdf | 2026-10-08 | 14.8->14.9 | primary_source | verified | 2026-10-08 |
| -> | res_f0138898e6 | NY | Amsterdam |  |  |  | 2026-09-23 | 11.6->11.7 | compiled_flagged | unverified |  |
| -> | res_cdad6a0cc5 | NY | Amsterdam |  |  |  | 2026-09-23 | 11.6->11.7 | compiled_flagged | unverified |  |
| -> | res_f2fbb7f97d | NY | Arietta |  |  |  | 2026-09-23 | 5.2->5.3 | compiled_record | unverified |  |
| -> | res_339b87c3bc | NY | Babylon |  |  |  | 2026-09-23 | 29.5->29.6 | compiled_record | unverified |  |
| -> | res_337e1aa287 | NY | Berne |  |  |  | 2026-09-23 | 18.5->18.6 | compiled_record | unverified |  |
| -> | res_db4c9ecfa0 | NY | Berne |  |  |  | 2026-09-23 | 18.5->18.6 | compiled_record | unverified |  |
| -> | res_2c3ebcd3e6 | NY | Byron |  |  |  | 2026-09-23 | 7.4->7.5 | compiled_record | unverified |  |
| -> | res_b0e70bce37 | NY | Byron | confirmed | opened | https://townofbyronny.gov/wp-content/uploads/2026/05/Town-Board-Meeting-4-8-26.pdf | 2026-10-08 | 7.4->7.5 | primary_source | verified | 2026-10-08 |
| -> | res_018eb34b3d | NY | Denmark (Lewis County) |  |  |  | 2026-09-23 | 9.6->9.7 | compiled_record | unverified |  |
| -> | res_cb60d4b791 | NY | Denmark (Lewis County) |  |  |  | 2026-09-23 | 9.6->9.7 | compiled_record | unverified |  |
| -> | res_beaaa41e63 | NY | Hurley |  |  |  | 2026-09-23 | 13.7->13.8 | compiled_record | unverified |  |
| -> | res_d70061dcc7 | NY | Lysander (Onondaga County) | confirmed | opened | https://ecode360.com/35892349 | 2026-10-08 | 38.0->38.1 | primary_source | verified | 2026-10-08 |
| -> | res_415c0abafe | NY | Mina |  |  |  | 2026-09-23 | 18.6->18.7 | compiled_record | unverified |  |
| -> | res_ec8c140b2a | NY | Oswego City | confirmed | opened | https://oswegony.api.civicclerk.com/v1/Meetings/GetMeetingFileStream(fileId=1952,plainText=false) | 2026-10-08 | 15.3->15.4 | primary_source | verified | 2026-10-08 |
| -> | res_c7a491e45b | NY | Oswego City | confirmed | opened | https://oswegony.api.civicclerk.com/v1/Meetings/GetMeetingFileStream(fileId=1952,plainText=false) | 2026-10-08 | 15.3->15.4 | primary_source | verified | 2026-10-08 |
| -> | res_2048a509c2 | NY | Oswego City | confirmed | opened | https://oswegony.api.civicclerk.com/v1/Meetings/GetMeetingFileStream(fileId=1952,plainText=false) | 2026-10-08 | 15.3->15.4 | primary_source | verified | 2026-10-08 |
| -> | res_6d03ba619a | NY | Salem |  |  |  | 2025-10-08 | 13.4->13.5 | compiled_record | unverified |  |
| -> | res_df5a8f6e89 | NY | Spafford |  |  |  | 2026-09-23 | 6.2->6.3 | compiled_record | unverified |  |
| -> | res_827ab8c445 | NY | Stanford | confirmed | opened | https://stanfordny.gov/wp-content/uploads/2024/11/Resolution-of-Adoption-for-LL-2-of-2024-Moratorium.pdf | 2026-10-08 | 24.2->24.3 | primary_source | verified | 2026-10-08 |
| -> | res_301b6660ab | NY | Stanford | confirmed | opened | https://stanfordny.gov/wp-content/uploads/2024/11/Resolution-of-Adoption-for-LL-2-of-2024-Moratorium.pdf | 2026-10-08 | 24.2->24.3 | primary_source | verified | 2026-10-08 |
| -> | res_253610cf32 | NY | Town of Marcellus | confirmed | opened | https://townofmarcellusny.gov/wp-content/uploads/2026-5-6-.pdf | 2026-10-08 | 6.5->6.6 | primary_source | verified | 2026-10-08 |
| -> | res_13585c4d9b | NY | Town of Sherburne |  |  |  | 2026-01-14 | 10.2->10.3 | compiled_record | unverified |  |
| -> | res_72227f0bb2 | NY | Victory |  |  |  | 2024-10-14 | 25.2->25.3 | compiled_record | unverified |  |
| -> | res_75251bd006 | NC | City of Wilson |  |  |  | 2026-09-23 | 6.0->6.1 | compiled_flagged | unverified |  |
| -> | res_121f280a3c | NC | Pasquotank County (solar) |  |  |  | 2026-09-23 | 4.0->4.1 | compiled_record | unverified |  |
| -> | res_a75112e36b | ND | Dunn County |  |  |  | 2026-03-18 | 8.1->8.2 | compiled_record | unverified |  |
| -> | res_f75f6d74fe | ND | Dunn County |  |  |  | 2026-03-18 | 8.1->8.2 | compiled_record | unverified |  |
| -> | res_f56ae22ddd | OH | Village of Lordstown |  |  |  | 2026-09-23 | 4.5->4.6 | compiled_record | unverified |  |
| -> | res_cf0a4c6640 | OR | City of Hillsboro |  |  |  | 2026-07-27 | 3.8->3.9 | compiled_record | unverified |  |
| -> | res_b9948e27eb | PA | Adams Township (Butler County) | ->confirmed | ->opened | ->https://adamstwp.org/wp-content/uploads/2026/07/07-13-26-Supervisors.pdf | 2026-09-23->2026-11-21 | 2.3 | compiled_record->primary_source | unverified->verified | ->2026-11-21 |
| -> | res_243cf763f3 | PA | Bensalem Township |  |  |  | 2026-07-31 | 5.4->5.5 | compiled_record | unverified |  |
| -> | res_91dd06320d | PA | Bensalem Township |  |  |  | 2026-07-31 | 5.4->5.5 | compiled_record | unverified |  |
| -> | res_dfb0e7fab7 | PA | West Mahanoy Township |  |  |  | 2026-09-23 | 2.2->2.3 | compiled_record | unverified |  |
| -> | res_5e4ee7185f | SC | Clarendon County |  |  |  | 2026-09-23 | 2.2->2.3 | compiled_record | unverified |  |
| -> | res_efd77e0084 | SC | Sumter County |  |  |  | 2026-09-23 | 3.3->3.4 | compiled_record | unverified |  |
| -> | res_a433db3007 | SC | Sumter County |  |  |  | 2026-09-23 | 3.3->3.4 | compiled_record | unverified |  |
| -> | res_feb8d9a2ca | SD | Turner County |  |  |  | 2026-09-23 | 14.8->14.9 | compiled_record | unverified |  |
| -> | res_c54aa497ff | SD | Turner County |  |  |  | 2026-09-23 | 14.8->14.9 | compiled_record | unverified |  |
| -> | res_ffe719f142 | TN | Anderson County |  |  |  | 2026-09-23 | 5.2->5.3 | compiled_flagged | unverified |  |
| -> | res_fbd8b99662 | TN | Cocke County |  |  |  | 2026-09-23 | 5.2->5.3 | compiled_record | unverified |  |
| -> | res_b3fc1c63e7 | TX | Austin County | ->confirmed | ->opened | ->https://www.austincounty.com/upload/page/0154/BESS%20and%20DATA%20Center%20Moratorium%20Executed.pdf | 2026-09-23->2026-11-21 | 1.9 | compiled_record->primary_source | unverified->verified | ->2026-11-21 |
| -> | res_feaccae59d | UT | Iron County |  |  |  | 2026-07-31 | 5.8->5.9 | compiled_record | unverified |  |
| -> | res_238bbaf8f5 | WA | Black Diamond |  |  |  | 2026-09-23 | 8.6->8.7 | compiled_record | unverified |  |
| -> | res_31ac77819c | WA | Duvall |  |  |  | 2026-09-23 | 5.6->5.7 | compiled_record | unverified |  |
| -> | res_2b9a846f42 | WA | Enumclaw |  |  |  | 2026-09-23 | 20.9->21.0 | compiled_record | unverified |  |
| -> | res_faf4dafac9 | WA | Kitsap County |  |  |  | 2026-09-23 | 17.3->17.4 | compiled_record | unverified |  |
| -> | res_ea436715ca | WA | Snoqualmie |  |  |  | 2026-09-23 | 5.8->5.9 | compiled_record | unverified |  |
| -> | res_fbc32b9a1a | WI | Door County |  |  |  | 2026-09-23 | 5.8->5.9 | compiled_record | unverified |  |
| -> | res_14d759540f | WI | Monroe County |  |  |  | 2026-07-31 | 4.0->4.1 | compiled_record | unverified |  |
| --- | res_1149ba2f34 | AZ | Navajo County |  |  |  |  |  | report_citation | unverified |  |
| --- | res_ba24fce48f | AZ | Navajo County |  |  |  |  |  | report_citation | unverified |  |
| --- | res_3083700b99 | CO | Mesa County |  |  |  |  | 7.0 | report_citation | unverified |  |
| --- | res_04e99ce656 | CO | San Miguel County |  |  |  |  |  | report_citation | unverified |  |
| -> | res_f58ec65c21 | GA | Oglethorpe County | ->confirmed | ->opened | ->https://www.oglethorpecountyga.gov/_files/ugd/82255b_3f99d8c1d8874242818c0c06bebc413f.pdf | ->2026-11-21 |  | report_citation->primary_source | unverified->verified | ->2026-11-21 |
| --- | res_2a494842cd | GA | Thomas County |  |  |  |  |  | report_citation | unverified |  |
| --- | res_931cdd87e1 | IA | Clinton County |  |  |  |  |  | report_citation | unverified |  |
| --- | res_b1a701e7bc | KS | Shawnee County |  |  |  |  | 13.0 | report_citation | unverified |  |
| --- | res_ae47ea2963 | KS | Shawnee County |  |  |  |  | 13.0 | report_citation | unverified |  |
| -> | res_71a0eb71ef | OH | Allen County | ->confirmed | ->opened | ->http://commissioners.allencountyohio.com/wp-content/uploads/2022/04/M040422-Special.pdf | ->2026-11-21 |  | report_citation->primary_source | unverified->verified | ->2026-11-21 |
| -> | res_70a9395801 | OH | Allen County | ->confirmed | ->opened | ->http://commissioners.allencountyohio.com/wp-content/uploads/2022/04/M040422-Special.pdf | ->2026-11-21 |  | report_citation->primary_source | unverified->verified | ->2026-11-21 |
| -> | res_46a2e0ecd6 | OH | Auglaize County | ->confirmed | ->opened | ->https://www2.auglaizecounty.org/sites/default/files/documents/April%2026%2C%202022.pdf | ->2026-11-21 |  | report_citation->primary_source | unverified->verified | ->2026-11-21 |
| -> | res_31b2a2e1c4 | OH | Auglaize County | ->confirmed | ->opened | ->https://www2.auglaizecounty.org/sites/default/files/documents/April%2026%2C%202022.pdf | ->2026-11-21 |  | report_citation->primary_source | unverified->verified | ->2026-11-21 |
| --- | res_6340504872 | VA | Mecklenburg County |  |  |  |  |  | report_citation | unverified |  |
| -> | res_96ea8a1174 | KY | Nicholas County | confirmed | opened | https://psc.ky.gov/pscscf/2026%20cases/2026-00256/Public%20Comments//20261012_PSC%20Response%20E-Mail%20to%20Nicholas%20County%20Attorney.pdf | 2026-09-18 | 2.1->2.2 | primary_source | verified |  |
| -> | res_6c30dff453 | KY | Nicholas County | confirmed | opened | https://kynewsgroup.com/TCM-08-26-26.pdf | 2026-10-16 | 3.2->3.3 | primary_source | verified |  |
| -> | res_72ef3a10d7 | IA | Mitchell County | confirmed | opened | https://mitchellcounty.iowa.gov/wp-content/uploads/Board-Proceedings-09-29-26.pdf | 2026-09-29 | 1.7->1.8 | primary_source | verified |  |
| -> | res_41dacebc09 | KS | Bourbon County | confirmed | opened | https://www.bourboncountyks.org/wp-content/uploads/2026/07/Commission-Minutes-06.15.26.pdf | 2026-06-15 | 5.2->5.3 | primary_source | verified |  |
| -> | res_fdbf3b9e3d | KS | Bourbon County | confirmed | opened | https://www.bourboncountyks.org/wp-content/uploads/2026/07/Commission-Minutes-06.15.26.pdf | 2026-06-15 | 5.2->5.3 | primary_source | verified |  |
| -> | res_ea5a10d01b | KS | Crawford County | confirmed | opened | https://www.crawfordcountykansas.org/uploads/6/2/7/8/62784259/journal_minutes_for_december_12_2025.pdf | 2025-12-12 | 11.3->11.4 | primary_source | verified |  |
| -> | res_bcee17309a | KS | Crawford County | confirmed | opened | https://www.crawfordcountykansas.org/uploads/6/2/7/8/62784259/journal_minutes_for_december_12_2025.pdf | 2025-12-12 | 11.3->11.4 | primary_source | verified |  |
| -> | res_2ec4bd8184 | IL | Assumption | confirmed | opened | https://www.cityofassumption.org/documents/397/Assumption_Complete_Code_S-8.pdf | 2019-10-02 | 85.6->85.7 | primary_source | verified |  |

### contested_projects

| @@ | id | state | project_name | severity_score | outcome | finality_evidence | evidence_level | verification | county_severe_restriction_ids | resolution_url | resolution_access | resolution_date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_a1a6ea95bb | CA | Granite Mountain Wind Energy Project | 4 | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://www.pbssocal.org/redefine/another-california-wind-energy-project-canceled | report_citation->confirmed | unverified->verified | nrel:wind:06071;sabin:REC-0021 | ->https://www.pbssocal.org/redefine/another-california-wind-energy-project-canceled | ->opened | ->2013-08 |
| -> | con_0c57b822fa | CA | Silurian Valley Solar Development | 4->2 | blocked_unverified->pending | outcome_label_only->resolution: https://www.pbssocal.org/redefine/firm-appeals-feds-no-go-of-silurian-valley-solar | report_citation | unverified->verified | sabin:REC-0021 | ->https://www.pbssocal.org/redefine/firm-appeals-feds-no-go-of-silurian-valley-solar | ->opened | ->2014-12 |
| -> | con_532051ea65 | CO | Wright’s Mesa Solar Project | 2 | needs_review | none | report_citation | unverified | sabin:REC-0034-> |  |  |  |
| -> | con_dd617d6622 | VA | 7 Bridges Solar Project | 4 | blocked_unverified | outcome_label_only | report_citation | unverified | sabin:S26R-5447-> |  |  |  |
| -> | con_71ee16e8ff | VA | Antlers Road Solar Farm | 4 | blocked_confirmed | resolution: https://www.mecklenburgva.com/AgendaCenter/ViewFile/Minutes/_06092025-189 | confirmed | verified | sabin:S26R-5447-> | https://www.mecklenburgva.com/AgendaCenter/ViewFile/Minutes/_06092025-189 | opened | 2025-06-09 |
| -> | con_e261469cb2 | VA | Lone Oak Agrisolar Project | 4 | blocked_unverified | outcome_label_only | report_citation | unverified | sabin:S26R-5447-> |  |  |  |
| -> | con_86fcc0dbaf | VA | New Hope Agrisolar Project | 4 | blocked_unverified | outcome_label_only | report_citation | unverified | sabin:S26R-5447-> |  |  |  |
| -> | con_2e46813b3e | WI | Beautiful Hill Wind Farm | 4->2 | blocked_unverified->pending | outcome_label_only->resolution: https://manitowoccountywi.gov/wp-content/uploads/2021/03/planning-2013.pdf | report_citation | unverified->verified | sabin:REC-0476 | ->https://manitowoccountywi.gov/wp-content/uploads/2021/03/planning-2013.pdf | ->opened | ->2013-02-25 |
