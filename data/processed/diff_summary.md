# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 2 | 2 |
| contested_projects | 0 | 0 | 0 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Column changes

- restrictions: added `status_checked_on`, `status_evidence_url`

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| restrictions | res_a1b4c0d533 (Oswego City, NY) | status | unknown | active |
| restrictions | res_7624c83c5e (Furnas County, NE) | status | unknown | active |

## Detail

### restrictions

| @@ | id | state | status | jurisdiction | currency | status_as_of |
|---|---|---|---|---|---|---|
| --- | res_25577a956a | IA | unknown | Clarke County | unknown |  |
| -> | res_a1b4c0d533 | NY | unknown->active | Oswego City | unknown->in_force | ->2026-10-19 |
| -> | res_7624c83c5e | NE | unknown->active | Furnas County | unknown->in_force | ->2026-10-19 |
| --- | res_2ffe152111 | SD | unknown | Pennington County | unknown |  |
