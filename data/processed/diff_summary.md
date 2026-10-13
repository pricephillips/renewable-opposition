# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 0 | 1 |
| contested_projects | 0 | 1 | 2 |
| cases | 1 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_9df550d5b2 (Coggon Solar, IA) | outcome | pending | advanced_confirmed |
| contested_projects | con_9df550d5b2 (Coggon Solar, IA) | finality_evidence | none | resolution: https://www.iowacourts.gov/courtcases/20670/embed/CourtAppealsOpinion |
| contested_projects | con_e2cc59f0e7 (Duane Arnold Solar Projects I and II, IA) | outcome | pending | advanced_confirmed |
| contested_projects | con_e2cc59f0e7 (Duane Arnold Solar Projects I and II, IA) | finality_evidence | none | resolution: https://www.eia.gov/electricity/data/eia860m/ |

## Detail

### restrictions

| @@ | id | state | description | jurisdiction |
|---|---|---|---|---|
| -> | res_fd0d691db9 | KS | In August 2021, Cherokee County adopted a 1-year moratorium on wind energy development.->Cherokee County, Kansas adopted Resolution No. 9-2022 on October 3, 2022, regulating industrial-scale wind turbines: a 5,250 ft setback from the nearest property line, a 440 ft maximum turbine height and a 39 dBA noise limit from 10 p.m. to 7 a.m. It followed a one-year wind moratorium adopted in August 2021. | Cherokee County |

### contested_projects

| @@ | id | state | project_name | outcome | finality_evidence | evidence_level | verification | resolution_url | resolution_access | resolution_date | facility_conflict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| --- | con_f906e5d6eb | IA | Coggon Solar | advanced_unverified | outcome_label_only | report_citation | verified |  |  |  |  |
| -> | con_9df550d5b2 | IA | Coggon Solar | pending->advanced_confirmed | none->resolution: https://www.iowacourts.gov/courtcases/20670/embed/CourtAppealsOpinion | report_citation->confirmed | unverified->verified | ->https://www.iowacourts.gov/courtcases/20670/embed/CourtAppealsOpinion | ->opened | ->2024-06-05 | outcome pending, but the plant is under construction-> |
| -> | con_e2cc59f0e7 | IA | Duane Arnold Solar Projects I and II | pending->advanced_confirmed | none->resolution: https://www.eia.gov/electricity/data/eia860m/ | report_citation->confirmed | unverified->verified | ->https://www.eia.gov/electricity/data/eia860m/ | ->opened | ->2024-12 | outcome pending, but the plant is operating-> |

### cases

| @@ | id | state | project_name | case_name |
|---|---|---|---|---|
| +++ | cas_3c5b0f6ab5 | IA | Coggon Solar | Robinson v. Linn County Board of Supervisors |
