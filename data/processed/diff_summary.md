# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 8 | 0 |
| contested_projects | 0 | 0 | 5 |
| cases | 0 | 0 | 0 |

## Column changes

- restrictions: added `sectors`, `legal_basis`, `instrument_id`, `scope`, `evidence_level`
- contested_projects: added `instrument_id`, `evidence_level`
- cases: added `instrument_id`, `evidence_level`

## Tracked field changes

No changes to outcome, status, case_status, finality_evidence, severity_score.

## Detail

### restrictions

| @@ | id | state | jurisdiction |
|---|---|---|---|
| --- | res_ed74c81f36 | KS | Lyon County |
| --- | res_2b2ec8577b | KS | Miami County |
| --- | res_1db2edee89 | KS | Miami County |
| --- | res_801654bae6 | KS | Miami County |
| --- | res_cae849b9c8 | KS | Topeka |
| --- | res_f3189af0c4 | NE | Logan County |
| --- | res_7a380d2200 | NE | Logan County |
| --- | res_ec310da5f0 | NE | Logan County |

### contested_projects

| @@ | id | state | project_name | municipality | notes |
|---|---|---|---|---|---|
| -> | con_db343251b7 | MA | SunEdison 2.4-MW solar array on a capped town landfill->Amherst Capped Landfill Solar | Amherst Capped Landfill Solar-> | ->project name recovered from the municipality column |
| -> | con_c2099c575a | MA | 11-MW solar farm in Amherst->ASD Shutesbury MA Solar LLC | ASD Shutesbury MA Solar LLC-> | ->project name recovered from the municipality column |
| -> | con_7ac9fd0b47 | MA | Bullard Farm Solar Plant | Bullard Farm Solar Plant-> | ->project name recovered from the municipality column |
| -> | con_db91d6c999 | MA | 454-MW offshore wind farm->Cape Wind | Cape Wind-> | ->project name recovered from the municipality column |
| -> | con_13940fdba9 | MA | 1,200-MW offshore wind farm->Commonwealth Wind | Commonwealth Wind-> | ->project name recovered from the municipality column |
