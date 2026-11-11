# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 8 | 4 |
| contested_projects | 0 | 0 | 5 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_5b0b98fcde (Kenowa Ridge Wind Farm, MI) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_5b0b98fcde (Kenowa Ridge Wind Farm, MI) | finality_evidence | outcome_label_only | resolution: https://www.okenergytoday.com/2020/01/another-aep-wind-farm-project-is-canceled |
| contested_projects | con_19743b49ea (Rio Lago Solar, TX) | outcome | pending | advanced_confirmed |
| contested_projects | con_19743b49ea (Rio Lago Solar, TX) | finality_evidence | none | resolution: https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx |
| contested_projects | con_44a7ecb6f3 (Dairy Air Wind Farm, VT) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_44a7ecb6f3 (Dairy Air Wind Farm, VT) | finality_evidence | outcome_label_only | resolution: https://vtdigger.org/2020/03/26/holland-wind-turbine-project-officially-over/ |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|
| -> | res_0fbddfd48f | OR | Umatilla County | ->confirmed | ->opened | ->https://www.umatillacounty.gov/fileadmin/user_upload/Community_Development/Planning/Umatilla_County_Development_Code_October_21__2026.pdf | ->2026-11-11 | report_citation->primary_source | unverified->verified | ->2026-11-11 |
| --- | res_18c5e688f9 | ID | Madison County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_efeb3bba7c | IL | Brown County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_b3cf384c66 | IL | Ford County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_c89a8e4cd0 | IL | Lake County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_699ef9b5b9 | IL | McLean County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_648ebef9a5 | IL | Macon County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_2bb7b0f2ee | PA | East Berlin Borough |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_46270a824f | PA | Penn Forest Township | ->confirmed | ->opened | ->https://pennforesttownship.org/wp-content/uploads/2021/05/ORDINANCE-NO-1-OF-2019-Admend-to-PFT-Zoning-Ord-Wind-Turbines.pdf | ->2026-11-11 | compiled_flagged->primary_source | unverified->verified | ->2026-11-11 |
| -> | res_117bbdb499 | PA | Wharton Township | ->confirmed | ->opened | ->https://whartontownship.com/downloadable-files/all-downloads/1-ordinances/5-zoning-ordinances?download=3:zoning-ordinances | ->2026-11-11 | compiled_flagged->primary_source | unverified->verified | ->2026-11-11 |
| --- | res_d3365a1760 | PA | Warriors Mark Township |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_a2e9915bcb | SC | Cherokee County | ->confirmed | ->opened | ->https://cherokeecountysc.gov/wp-content/uploads/2021/12/Cherokee-County-SC-Code-of-Ordinances-thru-47-1.pdf | ->2026-11-11 | compiled_flagged->primary_source | unverified->verified | ->2026-11-11 |

### contested_projects

| @@ | id | state | project_name | outcome | finality_evidence | evidence_level | verification | county_severe_restriction_ids | resolution_url | resolution_access | resolution_date | facility_conflict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_f586701f99 | IL | Ford Ridge Wind Farm | advanced_confirmed | resolution: https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx | confirmed | verified | nrel:wind:17053-> | https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx | opened | 2022-03 |  |
| -> | con_cef4cac718 | IL | Radford’s Run Wind Farm | advanced_unverified | outcome_label_only | report_citation | unverified | nrel:wind:17115-> |  |  |  |  |
| -> | con_5b0b98fcde | MI | Kenowa Ridge Wind Farm | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://www.okenergytoday.com/2020/01/another-aep-wind-farm-project-is-canceled | report_citation->confirmed | unverified->verified | sabin:S26R-5887 | ->https://www.okenergytoday.com/2020/01/another-aep-wind-farm-project-is-canceled | ->opened | ->2019-12 |  |
| -> | con_19743b49ea | TX | Rio Lago Solar | pending->advanced_confirmed | none->resolution: https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx | report_citation->confirmed | unverified->verified |  | ->https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx | ->opened | ->2026-09 | outcome pending, but the plant is under construction-> |
| -> | con_44a7ecb6f3 | VT | Dairy Air Wind Farm | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://vtdigger.org/2020/03/26/holland-wind-turbine-project-officially-over/ | report_citation->confirmed | unverified->verified | nrel:wind:5001903550;nrel:wind:5001946450;sabin:S26R-5478 | ->https://vtdigger.org/2020/03/26/holland-wind-turbine-project-officially-over/ | ->opened | ->2020-03 |  |
