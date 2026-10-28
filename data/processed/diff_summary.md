# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 3 | 7 |
| contested_projects | 0 | 0 | 5 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_7c516340ae (Mulqueeney Ranch Wind Repowering Project, CA) | outcome | pending | advanced_confirmed |
| contested_projects | con_7c516340ae (Mulqueeney Ranch Wind Repowering Project, CA) | finality_evidence | none | resolution: https://www.quittingcarbonmedia.com/a-repowered-california-wind-farm-rises-in-a-birthplace-of-the-industry/ |
| contested_projects | con_6446fd1b00 (White Tail Solar Project, a/k/a Railsplitter Solar, MI) | outcome | pending | advanced_confirmed |
| contested_projects | con_6446fd1b00 (White Tail Solar Project, a/k/a Railsplitter Solar, MI) | finality_evidence | none | resolution: https://www.wemu.org/show/issues-of-the-environment/2024-12-11/issues-of-the-environment-white-tail-solar-project-in-washtenaw-county-marks-progress-in-renewable-energy-and-sustainability-goals |
| contested_projects | con_84e14a7d48 (Lane City Wind Project, TX) | outcome | pending | advanced_confirmed |
| contested_projects | con_84e14a7d48 (Lane City Wind Project, TX) | finality_evidence | none | resolution: https://www.eia.gov/electricity/data/eia860m/archive/xls/august_generator2026.xlsx |
| contested_projects | con_77cf655ca9 (Rocky Forge Wind, VA) | outcome | pending | advanced_confirmed |
| contested_projects | con_77cf655ca9 (Rocky Forge Wind, VA) | finality_evidence | none | resolution: https://www.wsls.com/news/local/2026/06/06/rocky-forge-wind-farm-turbine-event/ |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|
| -> | res_dbd8dd38b4 | IA | Butler County | ->confirmed | ->opened | ->https://butlercounty.iowa.gov/images/docs/departments/zoning/ordinances/Butler_County_Zoning_Ordinance_No_28_7-18-23.pdf | ->2026-10-28 | report_citation->primary_source | unverified->verified | ->2026-10-28 |
| -> | res_ff6e1c578d | IA | Mahaska County | ->confirmed | ->opened | ->https://www.mahaskacountyia.gov/files/board_of_supervisors/2026_ordinances_33331.pdf | ->2026-10-28 | report_citation->primary_source | unverified->verified | ->2026-10-28 |
| -> | res_2bac2137c2 | ND | McKenzie County | ->confirmed | ->opened | ->https://storage.googleapis.com/proudcity/mckenziecountynd/2024/09/mckenzie-county-land-development-ordinance_20261016-465379c6.pdf | ->2026-10-28 | report_citation->primary_source | unverified->verified | ->2026-10-28 |
| --- | res_de60d2715a | IL | Champaign County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_340366b6bc | IL | Grundy County | ->confirmed | ->opened | ->https://energyzoning.org/sites/default/files/PDF/17063_Grundy%20_20221017.pdf | ->2026-10-28 | compiled_flagged->primary_source | unverified->verified | ->2026-10-28 |
| -> | res_c50c27d36d | IL | Livingston County | ->confirmed | ->opened | ->https://www.livingstoncountyil.gov/Documents/Department/Regional%20Planning%20%26%20Zoning/WECS-with-BESS-provision-Final-021524.pdf | ->2026-10-28 | compiled_flagged->primary_source | unverified->verified | ->2026-10-28 |
| --- | res_742c05f9e4 | IA | Mills County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_4a00f1ba03 | IA | Monona County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_0526b8d9b3 | IA | Osceola County | ->confirmed | ->opened | ->https://osceolacountyia.gov/wp-content/uploads/2026/06/Osceola-zoning-ordinance-with-amendments-6-2026.pdf | ->2026-10-28 | compiled_flagged->primary_source | unverified->verified | ->2026-10-28 |
| -> | res_29a221c90d | IA | Worth County | ->confirmed | ->opened | ->https://worthcountyiowa.gov/files/county_ordinances/2022.06.27_wind_ordinance_209.pdf | ->2026-10-28 | compiled_flagged->primary_source | unverified->verified | ->2026-10-28 |

### contested_projects

| @@ | id | state | project_name | outcome | finality_evidence | evidence_level | verification | county_severe_restriction_ids | resolution_url | resolution_access | resolution_date | facility_conflict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_7c516340ae | CA | Mulqueeney Ranch Wind Repowering Project | pending->advanced_confirmed | none->resolution: https://www.quittingcarbonmedia.com/a-repowered-california-wind-farm-rises-in-a-birthplace-of-the-industry/ | report_citation->confirmed | unverified->verified |  | ->https://www.quittingcarbonmedia.com/a-repowered-california-wind-farm-rises-in-a-birthplace-of-the-industry/ | ->opened | ->2026-05 | outcome pending, but the plant is under construction-> |
| -> | con_a08570ca0a | IA | Silver Creek Wind Farm | pending | none | report_citation | unverified | nrel:wind:19129;sabin:REC-0106;sabin:S26R-6081->sabin:REC-0106;sabin:S26R-6081 |  |  |  |  |
| -> | con_6446fd1b00 | MI | White Tail Solar Project, a/k/a Railsplitter Solar | pending->advanced_confirmed | none->resolution: https://www.wemu.org/show/issues-of-the-environment/2024-12-11/issues-of-the-environment-white-tail-solar-project-in-washtenaw-county-marks-progress-in-renewable-energy-and-sustainability-goals | report_citation->confirmed | unverified->verified | sabin:REC-0199 | ->https://www.wemu.org/show/issues-of-the-environment/2024-12-11/issues-of-the-environment-white-tail-solar-project-in-washtenaw-county-marks-progress-in-renewable-energy-and-sustainability-goals | ->opened | ->2023 | outcome pending, but the plant is operating-> |
| -> | con_84e14a7d48 | TX | Lane City Wind Project | pending->advanced_confirmed | none->resolution: https://www.eia.gov/electricity/data/eia860m/archive/xls/august_generator2026.xlsx | report_citation->confirmed | unverified->verified |  | ->https://www.eia.gov/electricity/data/eia860m/archive/xls/august_generator2026.xlsx | ->opened | ->2025-10 | outcome pending, but the plant is operating-> |
| -> | con_77cf655ca9 | VA | Rocky Forge Wind | pending->advanced_confirmed | none->resolution: https://www.wsls.com/news/local/2026/06/06/rocky-forge-wind-farm-turbine-event/ | report_citation->confirmed | unverified->verified | nrel:wind:51023 | ->https://www.wsls.com/news/local/2026/06/06/rocky-forge-wind-farm-turbine-event/ | ->opened | ->2026-06 | outcome pending, but the plant is under construction-> |
