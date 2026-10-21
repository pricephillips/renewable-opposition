# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 7 | 2 |
| contested_projects | 0 | 0 | 3 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_8b55fa65cb (Salt Creek Wind, IA) | outcome | needs_review | advanced_confirmed |
| contested_projects | con_8b55fa65cb (Salt Creek Wind, IA) | finality_evidence | none | resolution: https://www.eia.gov/electricity/data/eia860m/xls/august_generator2026.xlsx |
| contested_projects | con_a01883c584 (Elkhart County Solar Project, IN) | outcome | pending | advanced_confirmed |
| contested_projects | con_a01883c584 (Elkhart County Solar Project, IN) | finality_evidence | none | resolution: https://www.eia.gov/electricity/data/eia860m/xls/august_generator2026.xlsx |
| contested_projects | con_a01883c584 (Elkhart County Solar Project, IN) | severity_score | 2 | 1 |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|
| --- | res_3bae9ed0d4 | NE | Perkins County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_0a4931e383 | CA | Lake County | ->confirmed | ->opened | ->https://www.lakecountyca.gov/DocumentCenter/View/17119/Article-27---Uses-Generally-Permitted-updated-6426-clean-PDF | ->2026-10-21 | compiled_flagged->primary_source | unverified->verified | ->2026-10-21 |
| --- | res_24fe682d57 | ID | Bingham County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_cde1d38773 | KS | Jefferson County | ->confirmed | ->opened | ->https://www.jfcountyks.com/AgendaCenter/ViewFile/Minutes/_05042026-870 | ->2026-10-21 | compiled_flagged->primary_source | unverified->verified | ->2026-10-21 |
| --- | res_f7a02c3bf8 | MN | Brown County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_3351d69028 | OR | Marion County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_8a382258de | PA | Hermitage City |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_29055c3d7f | WI | Waupaca County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_226a2e8b73 | WI | Waushara County |  |  |  |  | compiled_flagged | unverified |  |

### contested_projects

| @@ | id | state | project_name | severity_score | outcome | finality_evidence | evidence_level | verification | county_severe_restriction_ids | resolution_url | resolution_access | resolution_date | facility_conflict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_8b55fa65cb | IA | Salt Creek Wind | 3 | needs_review->advanced_confirmed | none->resolution: https://www.eia.gov/electricity/data/eia860m/xls/august_generator2026.xlsx | report_citation->confirmed | unverified->verified |  | ->https://www.eia.gov/electricity/data/eia860m/xls/august_generator2026.xlsx | ->opened | ->2025-12 | outcome needs_review, but the plant is operating-> |
| -> | con_8f0bd40d9a | ID | Blue Ribbon Energy Project | 3 | needs_review | none | report_citation | unverified | nrel:wind:16011-> |  |  |  |  |
| -> | con_a01883c584 | IN | Elkhart County Solar Project | 2->1 | pending->advanced_confirmed | none->resolution: https://www.eia.gov/electricity/data/eia860m/xls/august_generator2026.xlsx | report_citation->confirmed | unverified->verified |  | ->https://www.eia.gov/electricity/data/eia860m/xls/august_generator2026.xlsx | ->opened | ->2026-03 | outcome pending, but the plant is operating-> |
