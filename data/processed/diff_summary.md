# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 0 | 0 |
| contested_projects | 0 | 0 | 1 |
| cases | 0 | 0 | 0 |

## Column changes

- contested_projects: added `resolution_date`

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_d4dbbbd76c (Flemingsburg Wind Project, KY) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_d4dbbbd76c (Flemingsburg Wind Project, KY) | finality_evidence | lead: https://www.wmky.org/business/2014-05-10/flemingsburg-wind-project-discontinued | resolution: https://www.wmky.org/business/2014-05-10/flemingsburg-wind-project-discontinued |

## Detail

### contested_projects

| @@ | id | state | project_name | outcome | finality_evidence | evidence_level | resolution_access |
|---|---|---|---|---|---|---|---|
| -> | con_d4dbbbd76c | KY | Flemingsburg Wind Project | blocked_unverified->blocked_confirmed | lead: https://www.wmky.org/business/2014-05-10/flemingsburg-wind-project-discontinued->resolution: https://www.wmky.org/business/2014-05-10/flemingsburg-wind-project-discontinued | report_citation->confirmed | snippet->opened |
