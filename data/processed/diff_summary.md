# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 11 | 8 |
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

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|
| -> | res_7b36d14b7f | IN | Huntington County | ->confirmed | ->opened | ->https://www.huntington.in.us/egov/documents/1774460864_7215.pdf | 2026-09-23->2026-11-21 | compiled_record->primary_source | unverified->verified | ->2026-11-21 |
| --- | res_6658d3c6e4 | MI | Casco Township (Allegan County) |  |  |  | 2026-09-23 | compiled_record | unverified |  |
| --- | res_379a7bcdd7 | MI | Casco Township (Allegan County) |  |  |  | 2026-09-23 | compiled_record | unverified |  |
| -> | res_b9948e27eb | PA | Adams Township (Butler County) | ->confirmed | ->opened | ->https://adamstwp.org/wp-content/uploads/2026/07/07-13-26-Supervisors.pdf | 2026-09-23->2026-11-21 | compiled_record->primary_source | unverified->verified | ->2026-11-21 |
| -> | res_b3fc1c63e7 | TX | Austin County | ->confirmed | ->opened | ->https://www.austincounty.com/upload/page/0154/BESS%20and%20DATA%20Center%20Moratorium%20Executed.pdf | 2026-09-23->2026-11-21 | compiled_record->primary_source | unverified->verified | ->2026-11-21 |
| --- | res_1149ba2f34 | AZ | Navajo County |  |  |  |  | report_citation | unverified |  |
| --- | res_ba24fce48f | AZ | Navajo County |  |  |  |  | report_citation | unverified |  |
| --- | res_3083700b99 | CO | Mesa County |  |  |  |  | report_citation | unverified |  |
| --- | res_04e99ce656 | CO | San Miguel County |  |  |  |  | report_citation | unverified |  |
| -> | res_f58ec65c21 | GA | Oglethorpe County | ->confirmed | ->opened | ->https://www.oglethorpecountyga.gov/_files/ugd/82255b_3f99d8c1d8874242818c0c06bebc413f.pdf | ->2026-11-21 | report_citation->primary_source | unverified->verified | ->2026-11-21 |
| --- | res_2a494842cd | GA | Thomas County |  |  |  |  | report_citation | unverified |  |
| --- | res_931cdd87e1 | IA | Clinton County |  |  |  |  | report_citation | unverified |  |
| --- | res_b1a701e7bc | KS | Shawnee County |  |  |  |  | report_citation | unverified |  |
| --- | res_ae47ea2963 | KS | Shawnee County |  |  |  |  | report_citation | unverified |  |
| -> | res_71a0eb71ef | OH | Allen County | ->confirmed | ->opened | ->http://commissioners.allencountyohio.com/wp-content/uploads/2022/04/M040422-Special.pdf | ->2026-11-21 | report_citation->primary_source | unverified->verified | ->2026-11-21 |
| -> | res_70a9395801 | OH | Allen County | ->confirmed | ->opened | ->http://commissioners.allencountyohio.com/wp-content/uploads/2022/04/M040422-Special.pdf | ->2026-11-21 | report_citation->primary_source | unverified->verified | ->2026-11-21 |
| -> | res_46a2e0ecd6 | OH | Auglaize County | ->confirmed | ->opened | ->https://www2.auglaizecounty.org/sites/default/files/documents/April%2026%2C%202022.pdf | ->2026-11-21 | report_citation->primary_source | unverified->verified | ->2026-11-21 |
| -> | res_31b2a2e1c4 | OH | Auglaize County | ->confirmed | ->opened | ->https://www2.auglaizecounty.org/sites/default/files/documents/April%2026%2C%202022.pdf | ->2026-11-21 | report_citation->primary_source | unverified->verified | ->2026-11-21 |
| --- | res_6340504872 | VA | Mecklenburg County |  |  |  |  | report_citation | unverified |  |

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
