# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 0 | 29 |
| contested_projects | 0 | 0 | 0 |
| cases | 0 | 0 | 0 |

## Tracked field changes

No changes to outcome, status, case_status, finality_evidence, severity_score.

## Detail

### restrictions

| @@ | id | state | jurisdiction | evidence_level | primary_source_url | primary_source_verdict | primary_source_checked_on | primary_source_access | primary_source_archived_url |
|---|---|---|---|---|---|---|---|---|---|
| -> | res_d15e0601e4 | CA | San Juan Capistrano | compiled_flagged->primary_source | ->https://ecode360.com/44277491 | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_e9f1af5f5d | CO | Grand County | compiled_record->primary_source | ->https://www.co.grand.co.us/AgendaCenter/ViewFile/Minutes/_06242025-2747 | ->confirmed | ->2026-10-08 | ->archived | ->https://web.archive.org/web/20261008172009/https://www.co.grand.co.us/AgendaCenter/ViewFile/Minutes/_06242025-2747 |
| -> | res_1ba648b44c | CO | Grand County | compiled_record->primary_source | ->https://www.co.grand.co.us/AgendaCenter/ViewFile/Minutes/_06242025-2747 | ->confirmed | ->2026-10-08 | ->archived | ->https://web.archive.org/web/20261008172009/https://www.co.grand.co.us/AgendaCenter/ViewFile/Minutes/_06242025-2747 |
| -> | res_b0a803b9a1 | CO | Grand County | compiled_record->primary_source | ->https://www.co.grand.co.us/AgendaCenter/ViewFile/Minutes/_06242025-2747 | ->confirmed | ->2026-10-08 | ->archived | ->https://web.archive.org/web/20261008172009/https://www.co.grand.co.us/AgendaCenter/ViewFile/Minutes/_06242025-2747 |
| -> | res_c0d909e774 | IL | Lee County | compiled_flagged->primary_source | ->https://leecountyil.com/AgendaCenter/ViewFile/Minutes/_05212026-1185 | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_2e86541afe | IA | Shelby County | compiled_record->primary_source | ->https://shelbycounty.iowa.gov/files/meetings/2026-03-17_minutes_2701.pdf | ->confirmed | ->2026-10-08 | ->archived | ->https://web.archive.org/web/20261008172226/https://shelbycounty.iowa.gov/files/meetings/2026-03-17_minutes_2701.pdf |
| -> | res_652e45dcbf | IA | Shelby County | compiled_record->primary_source | ->https://shelbycounty.iowa.gov/files/meetings/2026-03-17_minutes_2701.pdf | ->confirmed | ->2026-10-08 | ->archived | ->https://web.archive.org/web/20261008172226/https://shelbycounty.iowa.gov/files/meetings/2026-03-17_minutes_2701.pdf |
| -> | res_2ba4ec788f | IA | Shelby County | compiled_record->primary_source | ->https://shelbycounty.iowa.gov/files/meetings/2026-03-17_minutes_2701.pdf | ->confirmed | ->2026-10-08 | ->archived | ->https://web.archive.org/web/20261008172226/https://shelbycounty.iowa.gov/files/meetings/2026-03-17_minutes_2701.pdf |
| -> | res_a3d035aa67 | IA | Tama County | compiled_record->primary_source | ->https://tamacounty.iowa.gov/files/meetings/2025-11-10_minutes_4129.pdf | ->confirmed | ->2026-10-08 | ->archived | ->https://web.archive.org/web/20260521041845/https://tamacounty.iowa.gov/files/meetings/2025-11-10_minutes_4129.pdf |
| -> | res_4f04d73fe8 | NY | Athens | compiled_flagged->primary_source | ->https://townofathensny.gov/minutes/2026/797-08-17-2026-reg-meeting/file.html | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_b0e70bce37 | NY | Byron | compiled_record->primary_source | ->https://townofbyronny.gov/wp-content/uploads/2026/05/Town-Board-Meeting-4-8-26.pdf | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_696d66789d | NY | Claverack | compiled_flagged->primary_source | ->https://www.claverackny.gov/DocumentCenter/View/276/75-TOC-LL2-of-2025-BESS-Moratorium-PDF | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_37c3bfed00 | NY | Concord | compiled_record->primary_source | ->https://ecode360.com/41645757 | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_b32907bff7 | NY | Cortlandt | compiled_record->primary_source | ->https://www.townofcortlandtny.gov/documents/RESOLUTION-ADOPTLL2026-01-168-2026.pdf | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_b9c1c9eff7 | NY | Eden | compiled_record->primary_source | ->https://ecode360.com/ED1729/laws/LF2564855.pdf | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_d70061dcc7 | NY | Lysander (Onondaga County) | compiled_record->primary_source | ->https://ecode360.com/35892349 | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_8a9ca78001 | NY | Mentz | compiled_flagged->primary_source | ->https://www.cayugacounty.gov/DocumentCenter/View/31233/06-30-25-Town-of-Mentz-Special-Board-Meeting-Minutes | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_739028e13e | NY | Norfolk | compiled_flagged->primary_source | ->https://norfolkny.com/wp-content/uploads/2025/09/Town-Board-June-12-2025.pdf | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_108995efdf | NY | North Hempstead | compiled_record->primary_source | ->https://ecode360.com/45818643 | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_ec8c140b2a | NY | Oswego City | compiled_record->primary_source | ->https://oswegony.api.civicclerk.com/v1/Meetings/GetMeetingFileStream(fileId=1952,plainText=false) | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_c7a491e45b | NY | Oswego City | compiled_record->primary_source | ->https://oswegony.api.civicclerk.com/v1/Meetings/GetMeetingFileStream(fileId=1952,plainText=false) | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_2048a509c2 | NY | Oswego City | compiled_record->primary_source | ->https://oswegony.api.civicclerk.com/v1/Meetings/GetMeetingFileStream(fileId=1952,plainText=false) | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_ebb9baf26f | NY | Smithtown | compiled_record->primary_source | ->https://ecode360.com/SM0115/laws/LF2488743.pdf | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_253610cf32 | NY | Town of Marcellus | compiled_record->primary_source | ->https://townofmarcellusny.gov/wp-content/uploads/2026-5-6-.pdf | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_7e763cc34f | NY | Westfield | compiled_record->primary_source | ->https://westfieldny.com/sites/default/files/town/2026/04/15/3-26.pdf | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_5fad04fc44 | NY | Yonkers | compiled_record->primary_source | ->https://yonkersny.legistar.com/LegislationDetail.aspx?ID=7445163&GUID=A14CD804-AF3D-4D10-9F65-79D89AE738CD&FullText=1 | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_9aa8e37604 | SD | Pennington County | compiled_record->primary_source | ->https://www.pennco.org/government/ordinances/ordinance_741.php | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_c228a38a3e | SD | Pennington County | compiled_record->primary_source | ->https://www.pennco.org/government/ordinances/ordinance_741.php | ->confirmed | ->2026-10-08 | ->opened |  |
| -> | res_19a328607d | TX | Pasadena | compiled_flagged->primary_source | ->https://pasadenatx.gov/AgendaCenter/ViewFile/Minutes/_01072025-554 | ->confirmed | ->2026-10-08 | ->opened |  |
