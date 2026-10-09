# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 0 | 4 |
| contested_projects | 0 | 0 | 0 |
| cases | 0 | 0 | 0 |
| state_policies | 61 | 0 | 0 |

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

### state_policies

| @@ | id | state |
|---|---|---|
| +++ | HI-siting_authority-1 | HI |
| +++ | HI-other-1 | HI |
| +++ | ID-siting_authority-1 | ID |
| +++ | ID-other-1 | ID |
| +++ | IL-siting_authority-1 | IL |
| +++ | IL-local_preemption-1 | IL |
| +++ | IL-local_preemption-2 | IL |
| +++ | IL-local_preemption-3 | IL |
| +++ | IL-state_setback_standard-1 | IL |
| +++ | IL-state_setback_standard-2 | IL |
| +++ | IN-siting_authority-1 | IN |
| +++ | IN-state_setback_standard-1 | IN |
| +++ | IN-state_setback_standard-2 | IN |
| +++ | KS-siting_authority-1 | KS |
| +++ | KS-other-1 | KS |
| +++ | KY-siting_authority-1 | KY |
| +++ | KY-state_setback_standard-1 | KY |
| +++ | KY-other-1 | KY |
| +++ | LA-siting_authority-1 | LA |
| +++ | LA-state_setback_standard-1 | LA |
| +++ | MA-siting_authority-1 | MA |
| +++ | MA-local_preemption-1 | MA |
| +++ | MA-local_preemption-2 | MA |
| +++ | MD-siting_authority-1 | MD |
| +++ | MD-local_preemption-1 | MD |
| +++ | MD-local_preemption-2 | MD |
| +++ | MD-state_setback_standard-1 | MD |
| +++ | MD-other-1 | MD |
| +++ | ME-state_setback_standard-1 | ME |
| +++ | ME-state_moratorium-1 | ME |
| +++ | ME-other-1 | ME |
| +++ | MI-siting_authority-1 | MI |
| +++ | MI-local_preemption-1 | MI |
| +++ | MI-state_setback_standard-1 | MI |
| +++ | MN-other-1 | MN |
| +++ | MT-siting_authority-1 | MT |
| +++ | MT-state_setback_standard-1 | MT |
| +++ | ND-siting_authority-1 | ND |
| +++ | ND-state_setback_standard-1 | ND |
| +++ | NE-siting_authority-1 | NE |
| +++ | NH-siting_authority-1 | NH |
| +++ | NJ-siting_authority-1 | NJ |
| +++ | NJ-local_preemption-1 | NJ |
| +++ | NJ-other-1 | NJ |
| +++ | NM-siting_authority-1 | NM |
| +++ | NM-local_preemption-1 | NM |
| +++ | NV-siting_authority-1 | NV |
| +++ | NV-local_preemption-1 | NV |
| +++ | NY-local_preemption-1 | NY |
| +++ | OH-siting_authority-1 | OH |
| +++ | OH-local_preemption-1 | OH |
| +++ | OH-state_setback_standard-1 | OH |
| +++ | OH-local_opt_out-1 | OH |
| +++ | OK-siting_authority-1 | OK |
| +++ | OK-state_setback_standard-1 | OK |
| +++ | OR-siting_authority-1 | OR |
| +++ | OR-local_preemption-1 | OR |
| +++ | OR-other-1 | OR |
| +++ | PA-siting_authority-1 | PA |
| +++ | RI-siting_authority-1 | RI |
| +++ | RI-local_preemption-1 | RI |
