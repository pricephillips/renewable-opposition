# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 0 | 2 |
| contested_projects | 0 | 0 | 0 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Column changes

- restrictions: added `term`, `ends_on`, `ends_on_basis`, `extensions`, `last_extended_on`, `months_in_force`, `drafting`, `drafting_note`, `status_note`

## Tracked field changes

No changes to outcome, status, case_status, finality_evidence, severity_score.

## Detail

### restrictions

| @@ | id | state | jurisdiction | currency |
|---|---|---|---|---|
| -> | res_04ff62e88b | GA | Rockdale County | in_force->lapsed_unconfirmed |
| -> | res_0f2a3e76f6 | WA | Covington | in_force->lapsed_unconfirmed |
