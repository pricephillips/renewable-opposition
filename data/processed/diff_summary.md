# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 1 | 3 |
| contested_projects | 0 | 0 | 0 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

No changes to outcome, status, case_status, finality_evidence, severity_score.

## Detail

### restrictions

| @@ | id | state | jurisdiction | conflicts_with |
|---|---|---|---|---|
| --- | res_0d2da401d5 | IL | Shelby County |  |
| -> | res_75c15f830a | OH | Huron County | ->queue:q_3897eb252a |
| -> | res_f642439160 | IL | Shelby County | ->queue:q_93d5a7953c; queue:q_961a84dda5 |
| -> | res_bf988a9d27 | KS | Crawford County | ->queue:q_a7ea2ffcf0; queue:q_c0783bb26d |
