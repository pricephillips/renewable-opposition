# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 1 | 0 | 0 |
| contested_projects | 0 | 0 | 3 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

No changes to outcome, status, case_status, finality_evidence, severity_score.

## Detail

### restrictions

| @@ | id | state | jurisdiction |
|---|---|---|---|
| +++ | res_da02d1765a | TX | Pasadena |

### contested_projects

| @@ | id | state | project_name | county_severe_restriction_ids |
|---|---|---|---|---|
| -> | con_270a2a4d5c | TX | Pitchford Road BESS | ->queue:q_bbb012a590-2 |
| -> | con_e7913e7fe3 | TX | Massey Energy Storage | ->queue:q_bbb012a590-2 |
| -> | con_f8379528ac | TX | Claire Battery Energy Storage Project | ->queue:q_bbb012a590-2 |
