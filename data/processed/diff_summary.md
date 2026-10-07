# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 0 | 1 |
| contested_projects | 0 | 0 | 1 |
| cases | 0 | 0 | 0 |

## Column changes

- restrictions: added `primary_source_access`, `primary_source_archived_url`, `placement_url`, `placement_access`
- contested_projects: added `resolution_url`, `resolution_access`, `resolution_archived_url`; removed `resolution_date`

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_d4dbbbd76c (Flemingsburg Wind Project, KY) | outcome | blocked_confirmed | blocked_unverified |
| contested_projects | con_d4dbbbd76c (Flemingsburg Wind Project, KY) | finality_evidence | resolution: https://www.wmky.org/business/2014-05-10/flemingsburg-wind-project-discontinued | lead: https://www.wmky.org/business/2014-05-10/flemingsburg-wind-project-discontinued |

## Detail

### restrictions

| @@ | id | state | jurisdiction | evidence_level |
|---|---|---|---|---|
| -> | res_fd0d691db9 | KS | Cherokee | primary_source->report_citation |

### contested_projects

| @@ | id | state | project_name | outcome | finality_evidence | evidence_level |
|---|---|---|---|---|---|---|
| -> | con_d4dbbbd76c | KY | Flemingsburg Wind Project | blocked_confirmed->blocked_unverified | resolution: https://www.wmky.org/business/2014-05-10/flemingsburg-wind-project-discontinued->lead: https://www.wmky.org/business/2014-05-10/flemingsburg-wind-project-discontinued | confirmed->report_citation |
