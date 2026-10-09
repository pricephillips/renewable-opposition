# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 0 | 4 |
| contested_projects | 0 | 0 | 0 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

No changes to outcome, status, case_status, finality_evidence, severity_score.

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|
| -> | res_42b4a46830 | NY | New Lisbon Town | ->confirmed | ->opened | ->https://townofnewlisbonny.gov/wp-content/uploads/2012/04/Local-Law-2-of-2017.pdf | compiled_flagged->primary_source | unverified->verified | ->2026-10-09 |
| -> | res_69535de7dc | IA | Fremont County | ->confirmed | ->opened | ->https://fremontia.socs.net/vimages/shared/vnews/stories/5cad3edf734e1/Wind_Energy_Conversion_Systems_-_Final_Draft.pdf | compiled_flagged->primary_source | unverified->verified | ->2026-10-09 |
| -> | res_b0f2b57d5e | OR | Crook County | ->confirmed | ->opened | ->https://www.codepublishing.com/OR/CrookCounty/html/CrookCounty18/CrookCounty18161.html | compiled_flagged->primary_source | unverified->verified | ->2026-10-09 |
| -> | res_1d1d612c38 | TX | Hallsville City | ->confirmed | ->opened | ->https://cityofhallsvilletx.com/wp-content/uploads/2018/02/Ordinance-2016-06-Zoning-Ordinance-web.pdf | compiled_flagged->primary_source | unverified->verified | ->2026-10-09 |
