# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 1 | 3 | 1 |
| contested_projects | 0 | 0 | 1 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

No changes to outcome, status, case_status, finality_evidence, severity_score.

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | primary_source_archived_url | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|---|
| --- | res_1af87a75b9 | NV | Douglas County |  |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_b9c5151e53 | NV | Elko County |  |  |  |  |  | compiled_flagged | unverified |  |
| +++ | res_16579c2a8e | NH | Randolph Town |  |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_9793a67d5c | NM | San Miguel County | ->confirmed | ->archived | ->http://new.smcounty.net/_WebDocs/_CommMinutes/MINUTES%202011/RM_03_15_11.pdf | ->https://web.archive.org/web/2023id_/http://new.smcounty.net/_WebDocs/_CommMinutes/MINUTES%202011/RM_03_15_11.pdf | ->2026-11-08 | compiled_flagged->primary_source | unverified->verified | ->2026-11-08 |
| --- | res_417a9a8e36 | OK | El Reno City |  |  |  |  |  | compiled_flagged | unverified |  |

### contested_projects

| @@ | id | state | project_name | county_severe_restriction_ids |
|---|---|---|---|---|
| -> | con_81e9f94eb3 | NH | Granite Reliable Wind Farm | ->nrel:wind:3300763860 |
