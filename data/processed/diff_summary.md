# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 3 | 8 |
| contested_projects | 0 | 0 | 6 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_7ce3b818ed (Genesis Solar Energy Project, CA) | outcome | pending | advanced_confirmed |
| contested_projects | con_7ce3b818ed (Genesis Solar Energy Project, CA) | finality_evidence | none | resolution: https://www.eia.gov/electricity/data/eia860m/archive/xls/august_generator2026.xlsx |
| contested_projects | con_692860e2d2 (Milligan 1 Wind Project, NE) | finality_evidence | none | resolution: https://www.1011now.com/2023/08/01/milligan-1-wind-farm-files-action-against-saline-county/ |
| contested_projects | con_57c65794e7 (Dixie Valley Geothermal Project, NV) | finality_evidence | none | resolution: https://www.narf.org/nill/bulletins/federal/documents/2026/ormat_v_usdoi.pdf |
| contested_projects | con_6a548e3ff1 (Spring Valley Wind Farm, NV) | outcome | pending | advanced_confirmed |
| contested_projects | con_6a548e3ff1 (Spring Valley Wind Farm, NV) | finality_evidence | none | resolution: https://www.renewableenergyworld.com/wind-power/pattern-spring-valley-wind-project-reaches-settlement-agreement/ |
| contested_projects | con_d6604dd7ee (Alle-Catt Wind Farm, NY) | outcome | pending | advanced_confirmed |
| contested_projects | con_d6604dd7ee (Alle-Catt Wind Farm, NY) | finality_evidence | none | resolution: https://www.eia.gov/electricity/data/eia860m/archive/xls/september_generator2026.xlsx |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|
| -> | res_f6fc0b95ca | IA | Cedar County | ->confirmed | ->opened | ->https://cedarcounty.iowa.gov/files/county_ordinances/65_regulations_for_utilityscale_solar_energy_systems_usses_912.pdf | ->2026-10-24 | compiled_flagged->primary_source | unverified->verified | ->2026-10-24 |
| -> | res_c8df02e854 | ND | McKenzie County | ->confirmed | ->opened | ->https://storage.googleapis.com/proudcity/mckenziecountynd/2024/09/mckenzie-county-land-development-ordinance_20261016-465379c6.pdf | 2026-10-21->2026-10-24 | compiled_flagged->primary_source | unverified->verified | ->2026-10-24 |
| --- | res_54f2333d31 | CA | Sonoma County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_05d6c5372e | IA | Buena Vista County | ->confirmed | ->opened | ->https://buenavistacounty.iowa.gov/wp-content/uploads/2024/12/Buena-Vista-County-Wind-Energy-Conversion-System-Ordinance-6.9.pdf | ->2026-10-24 | compiled_flagged->primary_source | unverified->verified | ->2026-10-24 |
| -> | res_2cb8acebfa | IA | Butler County | ->confirmed | ->opened | ->https://butlercounty.iowa.gov/images/docs/departments/zoning/ordinances/Butler_County_Zoning_Ordinance_No_28_7-18-23.pdf | ->2026-10-24 | compiled_flagged->primary_source | unverified->verified | ->2026-10-24 |
| -> | res_c80e0da07e | IA | Calhoun County | ->confirmed | ->opened | ->https://calhouncounty.iowa.gov/document_center/County%20Board%20Minutes/2024/BOS%20MINUTES%2012-31-2024.pdf | ->2026-10-24 | compiled_flagged->primary_source | unverified->verified | ->2026-10-24 |
| --- | res_abc7331c92 | IA | Dickinson County |  |  |  | 2026-10-21 | compiled_flagged | unverified |  |
| --- | res_46a336b437 | IA | Greene County |  |  |  | 2026-10-21 | compiled_flagged | unverified |  |
| -> | res_b368ecce65 | IA | Jefferson County | ->confirmed | ->opened | ->https://jeffersoncounty.iowa.gov/wp-content/uploads/filr/250558/minutes24-09-16.pdf | ->2026-10-24 | compiled_flagged->primary_source | unverified->verified | ->2026-10-24 |
| -> | res_bf0e045843 | IA | Lyon County | ->confirmed | ->opened | ->https://lyoncounty.iowa.gov/files/zoning/zoning_ord_2012_43366.pdf | ->2026-10-24 | compiled_flagged->primary_source | unverified->verified | ->2026-10-24 |
| -> | res_bf988a9d27 | KS | Crawford County | ->confirmed | ->opened | ->https://www.crawfordcountykansas.org/uploads/6/2/7/8/62784259/zon_article_16_conditional_uses.pdf | ->2026-10-24 | compiled_flagged->primary_source | unverified->verified | ->2026-10-24 |

### contested_projects

| @@ | id | state | project_name | outcome | finality_evidence | evidence_level | verification | county_severe_restriction_ids | resolution_url | resolution_access | resolution_date | facility_conflict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_7ce3b818ed | CA | Genesis Solar Energy Project | pending->advanced_confirmed | none->resolution: https://www.eia.gov/electricity/data/eia860m/archive/xls/august_generator2026.xlsx | report_citation->confirmed | unverified->verified |  | ->https://www.eia.gov/electricity/data/eia860m/archive/xls/august_generator2026.xlsx | ->opened | ->2013-11 | outcome pending, but the plant is operating-> |
| -> | con_8219e87432 | IA | Red Rock Wind Energy Center | pending | none | report_citation | unverified | nrel:wind:19059-> |  |  |  |  |
| -> | con_692860e2d2 | NE | Milligan 1 Wind Project | pending | none->resolution: https://www.1011now.com/2023/08/01/milligan-1-wind-farm-files-action-against-saline-county/ | report_citation | unverified->verified | sabin:S26R-5771 | ->https://www.1011now.com/2023/08/01/milligan-1-wind-farm-files-action-against-saline-county/ | ->opened | ->2023-08-01 | outcome pending, but the plant is operating |
| -> | con_57c65794e7 | NV | Dixie Valley Geothermal Project | pending | none->resolution: https://www.narf.org/nill/bulletins/federal/documents/2026/ormat_v_usdoi.pdf | report_citation | unverified->verified |  | ->https://www.narf.org/nill/bulletins/federal/documents/2026/ormat_v_usdoi.pdf | ->opened | ->2026-03-20 | outcome pending, but the plant is operating |
| -> | con_6a548e3ff1 | NV | Spring Valley Wind Farm | pending->advanced_confirmed | none->resolution: https://www.renewableenergyworld.com/wind-power/pattern-spring-valley-wind-project-reaches-settlement-agreement/ | report_citation->confirmed | unverified->verified |  | ->https://www.renewableenergyworld.com/wind-power/pattern-spring-valley-wind-project-reaches-settlement-agreement/ | ->opened | ->2012-03-29 | outcome pending, but the plant is operating-> |
| -> | con_d6604dd7ee | NY | Alle-Catt Wind Farm | pending->advanced_confirmed | none->resolution: https://www.eia.gov/electricity/data/eia860m/archive/xls/september_generator2026.xlsx | report_citation->confirmed | unverified->verified | nrel:wind:3600302154;nrel:wind:3600312243;nrel:wind:3600337297;nrel:wind:3600901297;nrel:wind:3600902759;nrel:wind:3600927441;nrel:wind:3600944237;nrel:wind:3600957298;nrel:wind:3600957331;nrel:wind:3600960587;nrel:wind:3612102418;nrel:wind:3612155222;nrel:wind:3612166773;sabin:REC-0303 | ->https://www.eia.gov/electricity/data/eia860m/archive/xls/september_generator2026.xlsx | ->opened | ->2026-09 | outcome pending, but the plant is under construction-> |
