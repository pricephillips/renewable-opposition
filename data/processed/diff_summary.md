# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 1 | 8 |
| contested_projects | 0 | 0 | 1 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_57c65794e7 (Dixie Valley Geothermal Project, NV) | finality_evidence | resolution: https://www.narf.org/nill/bulletins/federal/documents/2026/ormat_v_usdoi.pdf | resolution: https://abc17news.com/news/2023/07/14/us-to-reopen-review-of-nevada-geothermal-plant-near-endangered-toad-while-legal-battle-is-on-hold/ |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | currency | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | res_0f2a3e76f6 | WA | Covington | ->confirmed | ->opened | ->https://www.covingtonwa.gov/Ordinance%20No.%2002-2026.pdf | lapsed_unconfirmed->in_force | 2026-09-23->2026-10-26 | compiled_record->primary_source | unverified->verified | ->2026-10-26 |
| -> | res_16170be505 | CO | Lincoln County | ->confirmed | ->opened | ->https://coagritourismbiz.org/wp-content/uploads/2023/10/Zoning-Regulations.Lincoln.pdf | unknown | ->2026-10-23 | compiled_flagged->primary_source | unverified->verified | ->2026-10-23 |
| -> | res_f6fc0b95ca | IA | Cedar County | confirmed | opened | https://cedarcounty.iowa.gov/files/county_ordinances/65_regulations_for_utilityscale_solar_energy_systems_usses_912.pdf | unknown | 2026-10-24->2026-10-23 | primary_source | verified | 2026-10-24->2026-10-23 |
| -> | res_c8df02e854 | ND | McKenzie County | confirmed | opened | https://storage.googleapis.com/proudcity/mckenziecountynd/2024/09/mckenzie-county-land-development-ordinance_20261016-465379c6.pdf | in_force | 2026-10-24->2026-10-23 | primary_source | verified | 2026-10-24->2026-10-23 |
| -> | res_05d6c5372e | IA | Buena Vista County | confirmed | opened | https://buenavistacounty.iowa.gov/wp-content/uploads/2024/12/Buena-Vista-County-Wind-Energy-Conversion-System-Ordinance-6.9.pdf | unknown | 2026-10-24->2026-10-23 | primary_source | verified | 2026-10-24->2026-10-23 |
| -> | res_b368ecce65 | IA | Jefferson County | confirmed | opened | https://jeffersoncounty.iowa.gov/wp-content/uploads/filr/250558/minutes24-09-16.pdf->https://jeffersoncounty.iowa.gov/wp-content/uploads/wind-energy-ord.pdf | unknown | 2026-10-24->2026-10-23 | primary_source | verified | 2026-10-24->2026-10-23 |
| -> | res_bf0e045843 | IA | Lyon County | confirmed | opened | https://lyoncounty.iowa.gov/files/zoning/zoning_ord_2012_43366.pdf | unknown | 2026-10-24->2026-10-23 | primary_source | verified | 2026-10-24->2026-10-23 |
| -> | res_21df352f00 | IA | Mahaska County | ->confirmed | ->opened | ->https://www.mahaskacountyia.gov/files/board_of_supervisors/2026_ordinances_33331.pdf | unknown | ->2026-10-23 | compiled_flagged->primary_source | unverified->verified | ->2026-10-23 |
| --- | res_5cee8f39bd | OH | Franklin County |  |  |  | in_force | 2026-10-21 | compiled_flagged | unverified |  |

### contested_projects

| @@ | id | state | project_name | finality_evidence | resolution_url | resolution_date |
|---|---|---|---|---|---|---|
| -> | con_57c65794e7 | NV | Dixie Valley Geothermal Project | resolution: https://www.narf.org/nill/bulletins/federal/documents/2026/ormat_v_usdoi.pdf->resolution: https://abc17news.com/news/2023/07/14/us-to-reopen-review-of-nevada-geothermal-plant-near-endangered-toad-while-legal-battle-is-on-hold/ | https://www.narf.org/nill/bulletins/federal/documents/2026/ormat_v_usdoi.pdf->https://abc17news.com/news/2023/07/14/us-to-reopen-review-of-nevada-geothermal-plant-near-endangered-toad-while-legal-battle-is-on-hold/ | 2026-03-20->2023-07-14 |
