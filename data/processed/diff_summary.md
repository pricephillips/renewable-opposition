# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 10 | 12 |
| contested_projects | 0 | 0 | 7 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_061f1152b8 (Torrington Solar Project, CT) | outcome | pending | advanced_confirmed |
| contested_projects | con_061f1152b8 (Torrington Solar Project, CT) | finality_evidence | none | resolution: https://portal.ct.gov/-/media/csc/3_petitions-medialibrary/petitions_medialibrary/mediapetitionnos1601-1700/pe1638/decision_staffreport/pe1638_dcltr_a.pdf |
| contested_projects | con_061f1152b8 (Torrington Solar Project, CT) | severity_score | 2 | 1 |
| contested_projects | con_840276bc68 (Goose Creek Wind Project / Prosperity Wind Farm, IL) | outcome | pending | advanced_confirmed |
| contested_projects | con_840276bc68 (Goose Creek Wind Project / Prosperity Wind Farm, IL) | finality_evidence | none | resolution: https://ipmnewsroom.org/the-piatt-county-board-with-reluctance-approves-the-countys-first-wind-farm/ |
| contested_projects | con_840276bc68 (Goose Creek Wind Project / Prosperity Wind Farm, IL) | severity_score | 2 | 1 |
| contested_projects | con_fadc9fbe4a (Platteview Solar Project, NE) | outcome | pending | advanced_confirmed |
| contested_projects | con_fadc9fbe4a (Platteview Solar Project, NE) | finality_evidence | none | resolution: https://oppdthewire.com/oppds-first-utility-scale-solar-project-platteview-solar-is-a-major-milestone/ |
| contested_projects | con_fadc9fbe4a (Platteview Solar Project, NE) | severity_score | 2 | 1 |
| contested_projects | con_ddc69b564b (Border Basin Solar Farm, OH) | outcome | pending | advanced_confirmed |
| contested_projects | con_ddc69b564b (Border Basin Solar Farm, OH) | finality_evidence | none | resolution: https://www.eia.gov/electricity/data/eia860m/archive/xls/august_generator2026.xlsx |
| contested_projects | con_ddc69b564b (Border Basin Solar Farm, OH) | severity_score | 2 | 1 |
| contested_projects | con_9220d499e5 (Great Bend Solar, OH) | outcome | pending | advanced_confirmed |
| contested_projects | con_9220d499e5 (Great Bend Solar, OH) | finality_evidence | none | resolution: https://www.eia.gov/electricity/data/eia860m/archive/xls/august_generator2026.xlsx |
| contested_projects | con_9220d499e5 (Great Bend Solar, OH) | severity_score | 2 | 1 |
| contested_projects | con_6d4269c691 (Yellow Wood Solar, OH) | outcome | pending | advanced_confirmed |
| contested_projects | con_6d4269c691 (Yellow Wood Solar, OH) | finality_evidence | none | resolution: https://farmanddairy.com/?p=777001 |
| contested_projects | con_6d4269c691 (Yellow Wood Solar, OH) | severity_score | 2 | 1 |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|
| -> | res_af963b1c8d | KS | Brown County | ->confirmed | ->opened | ->https://www.brcoks.org/AgendaCenter/ViewFile/Minutes/_03022026-94 | 2026-03-02->2026-10-31 | compiled_record->primary_source | unverified->verified | ->2026-10-31 |
| -> | res_0d2122ecfe | KS | Brown County | ->confirmed | ->opened | ->https://www.brcoks.org/AgendaCenter/ViewFile/Minutes/_03022026-94 | 2026-03-02->2026-10-31 | compiled_record->primary_source | unverified->verified | ->2026-10-31 |
| --- | res_9067dae7ce | NY | Glenville |  |  |  | 2026-09-23 | compiled_record | unverified |  |
| --- | res_b72bf56143 | ND | McIntosh County |  |  |  | 2026-09-23 | compiled_flagged | unverified |  |
| --- | res_f3749e9168 | ND | McIntosh County |  |  |  | 2026-09-23 | compiled_flagged | unverified |  |
| -> | res_d2bfcfdb18 | IN | Huntington County | ->confirmed | ->opened | ->https://www.huntington.in.us/egov/documents/1746035240_84899.pdf | ->2026-10-31 | report_citation->primary_source | unverified->verified | ->2026-10-31 |
| -> | res_3c9d7ced89 | KS | Labette | ->confirmed | ->opened | ->https://www.labettecounty.com/documents/260/March_14__2022_minutes.pdf | ->2026-11-03 | report_citation->primary_source | unverified->verified | ->2026-11-03 |
| -> | res_ad72a12ba7 | KY | Ohio County | ->confirmed | ->opened | ->https://eec.ky.gov/Energy/Documents/Ohio%20County%20Solar%20Ordinance.pdf | ->2026-11-03 | report_citation->primary_source | unverified->verified | ->2026-11-03 |
| -> | res_30547fe7f1 | KY | Trigg County | ->confirmed | ->opened | ->https://eec.ky.gov/Energy/Documents/Trigg%20County%20Solar%20Ordinance.pdf | ->2026-11-03 | report_citation->primary_source | unverified->verified | ->2026-11-03 |
| -> | res_8ca919ee1c | KY | Calloway County | ->confirmed | ->opened | ->https://callowaycountyky.gov/wp-content/uploads/2024/10/24-0417-A-rev1.pdf | ->2026-10-31 | compiled_flagged->primary_source | unverified->verified | ->2026-10-31 |
| --- | res_c210a89238 | KY | Mercer County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_70b923d02b | KY | Ohio County | ->confirmed | ->opened | ->https://eec.ky.gov/Energy/Documents/Ohio%20County%20Solar%20Ordinance.pdf | ->2026-10-31 | compiled_flagged->primary_source | unverified->verified | ->2026-10-31 |
| -> | res_4b9d4d1068 | KY | Spencer County | ->confirmed | ->opened | ->https://www.spencercountyky.gov/ORDINANCE%20NO%2020%20SOLAR%20ENERGY.pdf | ->2026-11-02 | compiled_flagged->primary_source | unverified->verified | ->2026-11-02 |
| -> | res_89b6f8514f | KY | Trigg County | ->confirmed | ->opened | ->https://eec.ky.gov/Energy/Documents/Trigg%20County%20Solar%20Ordinance.pdf | ->2026-10-31 | compiled_flagged->primary_source | unverified->verified | ->2026-10-31 |
| --- | res_243f6f3918 | KS | Ellis County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_fce2df6e9e | KS | Ford County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_bd6cea17e1 | KS | Labette County | ->confirmed | ->opened | ->https://www.labettecounty.com/documents/260/Labette_County_Zoning_Regs_FINAL_071224.pdf | ->2026-10-31 | compiled_flagged->primary_source | unverified->verified | ->2026-10-31 |
| -> | res_23b0d613f8 | KY | Mason County | ->confirmed | ->opened | ->https://cms5.revize.com/revize/maysville/Document%20Center/Department/Code%20Enforcement/Land-Use-Management-Ordinance-December-2020.pdf | ->2026-10-31 | compiled_flagged->primary_source | unverified->verified | ->2026-10-31 |
| --- | res_eaf25fde36 | MI | Kalkaska County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_543bfcbb32 | MN | Benton County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_467cb2d929 | MN | Clay County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_bf75974b05 | MN | Dodge County |  |  |  |  | compiled_flagged | unverified |  |

### contested_projects

| @@ | id | state | project_name | severity_score | outcome | finality_evidence | evidence_level | verification | county_severe_restriction_ids | resolution_url | resolution_access | resolution_date | facility_conflict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_061f1152b8 | CT | Torrington Solar Project | 2->1 | pending->advanced_confirmed | none->resolution: https://portal.ct.gov/-/media/csc/3_petitions-medialibrary/petitions_medialibrary/mediapetitionnos1601-1700/pe1638/decision_staffreport/pe1638_dcltr_a.pdf | report_citation->confirmed | unverified->verified |  | ->https://portal.ct.gov/-/media/csc/3_petitions-medialibrary/petitions_medialibrary/mediapetitionnos1601-1700/pe1638/decision_staffreport/pe1638_dcltr_a.pdf | ->opened | ->2025-01-23 | outcome pending, but the plant is operating-> |
| -> | con_840276bc68 | IL | Goose Creek Wind Project / Prosperity Wind Farm | 2->1 | pending->advanced_confirmed | none->resolution: https://ipmnewsroom.org/the-piatt-county-board-with-reluctance-approves-the-countys-first-wind-farm/ | report_citation->confirmed | unverified->verified | sabin:REC-0081 | ->https://ipmnewsroom.org/the-piatt-county-board-with-reluctance-approves-the-countys-first-wind-farm/ | ->opened | ->2023-10-13 | outcome pending, but the plant is operating-> |
| -> | con_d22367e571 | KY | Savion’s Mercer County Solar Farm | 4 | blocked_unverified | outcome_label_only | report_citation | unverified | nrel:solar:21167-> |  |  |  |  |
| -> | con_fadc9fbe4a | NE | Platteview Solar Project | 2->1 | pending->advanced_confirmed | none->resolution: https://oppdthewire.com/oppds-first-utility-scale-solar-project-platteview-solar-is-a-major-milestone/ | report_citation->confirmed | unverified->verified |  | ->https://oppdthewire.com/oppds-first-utility-scale-solar-project-platteview-solar-is-a-major-milestone/ | ->opened | ->2024-07-11 | outcome pending, but the plant is operating-> |
| -> | con_ddc69b564b | OH | Border Basin Solar Farm | 2->1 | pending->advanced_confirmed | none->resolution: https://www.eia.gov/electricity/data/eia860m/archive/xls/august_generator2026.xlsx | report_citation->confirmed | unverified->verified | sabin:REC-0351 | ->https://www.eia.gov/electricity/data/eia860m/archive/xls/august_generator2026.xlsx | ->opened | ->2026-08 | outcome pending, but the plant is under construction-> |
| -> | con_9220d499e5 | OH | Great Bend Solar | 2->1 | pending->advanced_confirmed | none->resolution: https://www.eia.gov/electricity/data/eia860m/archive/xls/august_generator2026.xlsx | report_citation->confirmed | unverified->verified |  | ->https://www.eia.gov/electricity/data/eia860m/archive/xls/august_generator2026.xlsx | ->opened | ->2025-12 | outcome pending, but the plant is operating-> |
| -> | con_6d4269c691 | OH | Yellow Wood Solar | 2->1 | pending->advanced_confirmed | none->resolution: https://farmanddairy.com/?p=777001 | report_citation->confirmed | unverified->verified | sabin:S26R-5627 | ->https://farmanddairy.com/?p=777001 | ->opened | ->2023-06 | outcome pending, but the plant is under construction-> |
