# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 11 | 4 |
| contested_projects | 0 | 0 | 7 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_77246a00ff (Sundance Solar and Storage Project, CO) | outcome | pending | advanced_confirmed |
| contested_projects | con_77246a00ff (Sundance Solar and Storage Project, CO) | finality_evidence | none | resolution: https://www.elbertcounty-co.gov/DocumentCenter/View/4561/Resolution-25-16-Sundance-Solar-Major-1041-Permit-1041-2024-1310 |
| contested_projects | con_77246a00ff (Sundance Solar and Storage Project, CO) | severity_score | 2 | 1 |
| contested_projects | con_ab7195b98b (Crossvine Solar Project, IN) | outcome | pending | restricted_conditional |
| contested_projects | con_ab7195b98b (Crossvine Solar Project, IN) | finality_evidence | none | resolution: https://duboiscountyfreepress.com/huntingburg-council-approves-crossvine-solar-project-settlement/ |
| contested_projects | con_e5fc646228 (Future Generation Wind, MA) | outcome | needs_review | advanced_confirmed |
| contested_projects | con_e5fc646228 (Future Generation Wind, MA) | finality_evidence | none | resolution: https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx |
| contested_projects | con_7b0fdeffbb (Chenango Solar, NY) | finality_evidence | none | resolution: https://www.fingerlakes1.com/2026/01/08/solar-project-paused-after-town-vote/ |
| contested_projects | con_c2f8d6f1c8 (High Noon Solar, WI) | outcome | needs_review | advanced_confirmed |
| contested_projects | con_c2f8d6f1c8 (High Noon Solar, WI) | finality_evidence | none | resolution: https://www.eia.gov/electricity/data/eia860m/archive/xls/august_generator2026.xlsx |
| contested_projects | con_c2f8d6f1c8 (High Noon Solar, WI) | severity_score | 2 | 1 |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|
| --- | res_a7557c8b03 | MN | Lincoln County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_8d84f9f57a | MO | Cass County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_b43dac3031 | CA | Kern County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_e8a79299e5 | MI | Crawford County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_afa8746c30 | MI | Wexford County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_df5712750b | MN | Meeker County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_36f4387467 | MN | Sibley County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_314beac7fc | MN | Wilkin County | ->confirmed | ->opened | ->https://wilkincounty.gov/vertical/sites/%7B6E7AB7CB-4769-4357-B6C8-90E546FFE488%7D/uploads/Wilkin_County_Land_Use_Ordinance_10.2025(1).pdf | ->2026-11-05 | compiled_flagged->primary_source | unverified->verified | ->2026-11-05 |
| --- | res_3ba3ae554a | MT | Carbon County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_f06d2a3f94 | NE | Chase County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_b2ee3a0b5b | NE | Hitchcock County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_a9b7494288 | NC | Jackson County | ->confirmed | ->opened | ->https://www.jacksonnc.org/DocumentCenter/View/1042/Unified-Development-Ordinance-UDO-PDF | ->2026-11-05 | compiled_flagged->primary_source | unverified->verified | ->2026-11-05 |
| -> | res_da4b0087b2 | NC | Pamlico County | ->confirmed | ->opened | ->https://www.pamlicocounty.org/Documents/County%20Government/Ordinance/ORDINANCE%20-%20WIND%20FARMS.pdf | ->2026-11-05 | compiled_flagged->primary_source | unverified->verified | ->2026-11-05 |
| --- | res_4592fd6efe | NC | Yadkin County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_863b4527bc | ND | Adams County | ->confirmed | ->opened | ->https://www.adamscountynd.com/ADAMS%20COUNTY--APRIL%202026.pdf | ->2026-11-05 | compiled_flagged->primary_source | unverified->verified | ->2026-11-05 |

### contested_projects

| @@ | id | state | project_name | severity_score | outcome | finality_evidence | evidence_level | verification | county_severe_restriction_ids | resolution_url | resolution_access | resolution_date | facility_conflict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_aeefaf09ec | CA | Jawbone Wind Energy | 3 | needs_review | none | report_citation | unverified | nrel:wind:06029-> |  |  |  |  |
| -> | con_e59748fa98 | CA | North Sky River Project | 3 | advanced_unverified | outcome_label_only | report_citation | unverified | nrel:wind:06029-> |  |  |  |  |
| -> | con_77246a00ff | CO | Sundance Solar and Storage Project | 2->1 | pending->advanced_confirmed | none->resolution: https://www.elbertcounty-co.gov/DocumentCenter/View/4561/Resolution-25-16-Sundance-Solar-Major-1041-Permit-1041-2024-1310 | report_citation->confirmed | unverified->verified | nrel:solar:08039 | ->https://www.elbertcounty-co.gov/DocumentCenter/View/4561/Resolution-25-16-Sundance-Solar-Major-1041-Permit-1041-2024-1310 | ->opened | ->2025-05-14 | outcome pending, but the plant is under construction-> |
| -> | con_ab7195b98b | IN | Crossvine Solar Project | 2 | pending->restricted_conditional | none->resolution: https://duboiscountyfreepress.com/huntingburg-council-approves-crossvine-solar-project-settlement/ | report_citation | unverified->verified |  | ->https://duboiscountyfreepress.com/huntingburg-council-approves-crossvine-solar-project-settlement/ | ->opened | ->2026-05-12 | outcome pending, but the plant is under construction-> |
| -> | con_e5fc646228 | MA | Future Generation Wind | 3 | needs_review->advanced_confirmed | none->resolution: https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx | report_citation->confirmed | unverified->verified | nrel:wind:2500107175;nrel:wind:2500119295;nrel:wind:2500139100;nrel:wind:2500170605;nrel:wind:2500174385;nrel:wind:2502328285;nrel:wind:2502333220;nrel:wind:2502333920;nrel:wind:2502338540;nrel:wind:2502354310;nrel:wind:2502357775 | ->https://www.eia.gov/electricity/data/eia860m/xls/september_generator2026.xlsx | ->opened | ->2016-08 | outcome needs_review, but the plant is operating-> |
| -> | con_7b0fdeffbb | NY | Chenango Solar | 2 | pending | none->resolution: https://www.fingerlakes1.com/2026/01/08/solar-project-paused-after-town-vote/ | report_citation | unverified->verified | sabin:S26R-5755 | ->https://www.fingerlakes1.com/2026/01/08/solar-project-paused-after-town-vote/ | ->opened | ->2026-01 | outcome pending, but the plant is operating |
| -> | con_c2f8d6f1c8 | WI | High Noon Solar | 2->1 | needs_review->advanced_confirmed | none->resolution: https://www.eia.gov/electricity/data/eia860m/archive/xls/august_generator2026.xlsx | report_citation->confirmed | unverified->verified |  | ->https://www.eia.gov/electricity/data/eia860m/archive/xls/august_generator2026.xlsx | ->opened | ->2026-08 | outcome needs_review, but the plant is under construction-> |
