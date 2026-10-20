# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 3 | 6 |
| contested_projects | 0 | 0 | 2 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_93f14cda8f (West Bridgewater Solar, MA) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_93f14cda8f (West Bridgewater Solar, MA) | finality_evidence | outcome_label_only | resolution: https://www.bostonglobe.com/metro/regionals/south/2013/05/04/solar-farm-projects-hit-roadblocks-some-communities-solar-projects-meet-resistance-locally/jUFUAxSZEpK4swEcCa9hPM/story.html |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | currency | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | res_04ff62e88b | GA | Rockdale County | ->confirmed | ->opened | ->https://www.rockdalecountyga.gov/wp-content/uploads/2026/09/R-2026-24.pdf | lapsed_unconfirmed->in_force | 2026-09-23->2026-10-20 | compiled_record->primary_source | unverified->verified | ->2026-10-20 |
| -> | res_9772dad354 | IA | Fremont County | ->confirmed | ->opened | ->https://www.fremontcountyia.gov/vimages/shared/vnews/stories/5caebb278b3cf/2020-1.pdf | in_force | ->2026-10-20 | report_citation->primary_source | unverified->verified | ->2026-10-20 |
| -> | res_42e2698168 | KY | Breckinridge County | ->confirmed | ->opened | ->https://breckinridgeky.com/wp-content/uploads/2025/12/Solar-Energy-Systems-Ordinance-2025-0121.pdf | in_force | ->2026-10-20 | report_citation->primary_source | unverified->verified | ->2026-10-20 |
| -> | res_37c30949e2 | NY | Nichols | ->confirmed | ->opened | ->https://townofnicholsny.gov/post/_docs/SolarEnergySystemsLocalLaw.pdf | in_force | ->2026-10-20 | report_citation->primary_source | unverified->verified | ->2026-10-20 |
| -> | res_848c9c1f4c | TX | Hallsville | ->confirmed | ->opened | ->https://cityofhallsvilletx.com/wp-content/uploads/2018/02/Ordinance-2016-06-Zoning-Ordinance-web.pdf | in_force | ->2026-10-20 | report_citation->primary_source | unverified->verified | ->2026-10-20 |
| -> | res_d691a91f5a | WY | Sweetwater County | ->confirmed | ->opened | ->https://cms7files.revize.com/sweetwaterwy24/document_center/Land%20Use/Development%20Codes/2015%20Zoning%20Resolution%20Amended%202.18.25.pdf | in_force | ->2026-10-20 | report_citation->primary_source | unverified->verified | ->2026-10-20 |
| --- | res_12732a2c15 | NY | Frankfort Town |  |  |  | unknown |  | compiled_flagged | unverified |  |
| --- | res_2b245a9f03 | IA | Franklin County |  |  |  | unknown |  | compiled_flagged | unverified |  |
| --- | res_7624c83c5e | NE | Furnas County |  |  |  | in_force | 2026-10-19 | compiled_flagged | unverified |  |

### contested_projects

| @@ | id | state | project_name | outcome | finality_evidence | evidence_level | verification | county_severe_restriction_ids | resolution_url | resolution_access | resolution_date | facility_conflict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_93f14cda8f | MA | West Bridgewater Solar | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://www.bostonglobe.com/metro/regionals/south/2013/05/04/solar-farm-projects-hit-roadblocks-some-communities-solar-projects-meet-resistance-locally/jUFUAxSZEpK4swEcCa9hPM/story.html | report_citation->confirmed | unverified->verified |  | ->https://www.bostonglobe.com/metro/regionals/south/2013/05/04/solar-farm-projects-hit-roadblocks-some-communities-solar-projects-meet-resistance-locally/jUFUAxSZEpK4swEcCa9hPM/story.html | ->opened | ->2013-04-23 | outcome blocked_unverified, but the plant is operating->outcome blocked_confirmed, but the plant is operating |
| -> | con_fd8ac5329d | NY | Columbia Solar | blocked_confirmed | resolution: https://townofcolumbiany.gov/vertical/sites/%7B24861145-D94D-4C05-9EA4-8E0A9CA2F226%7D/uploads/PB_Minutes_May_2025.pdf | confirmed | verified | mn:ny-german-flatts-2025;nrel:solar:3604327199->mn:ny-german-flatts-2025 | https://townofcolumbiany.gov/vertical/sites/%7B24861145-D94D-4C05-9EA4-8E0A9CA2F226%7D/uploads/PB_Minutes_May_2025.pdf | opened | 2025-05 |  |
