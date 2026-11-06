# Processed data diff

What the last build changed in `data/processed/`, compared with the previous commit. Rows are matched on `id`.

## Row counts

| Entity | Added | Removed | Modified |
|---|---|---|---|
| restrictions | 0 | 10 | 5 |
| contested_projects | 0 | 0 | 3 |
| cases | 0 | 0 | 0 |
| state_policies | 0 | 0 | 0 |

## Tracked field changes

| Entity | Row | Column | Before | After |
|---|---|---|---|---|
| contested_projects | con_99f95a0203 (Calico Solar Project, CA) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_99f95a0203 (Calico Solar Project, CA) | finality_evidence | outcome_label_only | resolution: https://www.renewableenergyworld.com/solar/k-road-gives-up-on-calico-solar-project/ |
| contested_projects | con_4f5282b549 (EverPower Wind Farm, NY) | outcome | blocked_unverified | blocked_confirmed |
| contested_projects | con_4f5282b549 (EverPower Wind Farm, NY) | finality_evidence | outcome_label_only | resolution: https://greatlakesecho.org/2014/04/16/new-york-court-leaves-turbine-project-dangling-in-the-wind |
| contested_projects | con_18be77447d (Staten Island Battery Storage Project, NY) | outcome | pending | advanced_confirmed |
| contested_projects | con_18be77447d (Staten Island Battery Storage Project, NY) | finality_evidence | none | resolution: https://ny1.com/nyc/staten-island/human-interest/2025/12/17/battery-energy-storage-system-sparks-controversy-on-staten-island |
| contested_projects | con_18be77447d (Staten Island Battery Storage Project, NY) | severity_score | 2 | 1 |

## Detail

### restrictions

| @@ | id | state | jurisdiction | primary_source_verdict | primary_source_access | primary_source_url | status_as_of | evidence_level | verification | primary_source_checked_on |
|---|---|---|---|---|---|---|---|---|---|---|
| --- | res_53a1ec0208 | OH | Swancreek Township (Fulton County) | confirmed | opened | https://swancreektwp.org/wp-content/uploads/2026/06/BOT-05-04-26-SPECIAL-AND-REGULAR-MEETING-MINUTES.pdf | 2026-10-08 | primary_source | verified | 2026-10-08 |
| -> | res_9a4b351fcf | NC | Pamlico County | ->confirmed | ->opened | ->https://www.pamlicocounty.org/Documents/County%20Government/Ordinance/ORDINANCE%20-%20WIND%20FARMS.pdf | ->2026-11-06 | report_citation->primary_source | unverified->verified | ->2026-11-06 |
| --- | res_11f814a51d | NE | Cherry County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_16ab35422c | ND | Mercer County | ->confirmed | ->opened | ->https://mercercountynd.com/image/cache/7-15-2026_Mercer_Co_Solar_Energy_Ordinance.pdf | ->2026-11-06 | compiled_flagged->primary_source | unverified->verified | ->2026-11-06 |
| --- | res_9e87f9edb3 | NE | Frontier County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_464012316a | NE | Pierce County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_13b2a49828 | NE | Saunders County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_3aa8b9aa5e | NE | Sioux County | ->confirmed | ->opened | ->https://siouxcountyne.gov/wp-content/uploads/sites/24/2025/01/Zoning-Regulations.pdf | ->2026-11-06 | compiled_flagged->primary_source | unverified->verified | ->2026-11-06 |
| --- | res_f94af94e1b | NE | Stanton County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_f36d2dbc33 | NE | Thayer County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_6fc65e4800 | ND | Barnes County |  |  |  |  | compiled_flagged | unverified |  |
| --- | res_4d25c10f97 | ND | Bowman County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_c7016c12df | ND | Burke County | ->confirmed | ->opened | ->https://www.burkecountynd.com/s/Zoning-Ordinance-Updated-3-2026-with-TOC.pdf | ->2026-11-06 | compiled_flagged->primary_source | unverified->verified | ->2026-11-06 |
| --- | res_f72bdf3c62 | ND | Pierce County |  |  |  |  | compiled_flagged | unverified |  |
| -> | res_0128f4fd42 | ND | Wells County | ->confirmed | ->opened | ->https://www.wellscountynd.com/image/cache/Commission_Approved_Wind_Turbine_Ordinance_7-8-25_no_resolution.pdf | ->2026-11-06 | compiled_flagged->primary_source | unverified->verified | ->2026-11-06 |

### contested_projects

| @@ | id | state | project_name | severity_score | outcome | finality_evidence | evidence_level | verification | resolution_url | resolution_access | resolution_date | facility_conflict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -> | con_99f95a0203 | CA | Calico Solar Project | 4 | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://www.renewableenergyworld.com/solar/k-road-gives-up-on-calico-solar-project/ | report_citation->confirmed | unverified->verified | ->https://www.renewableenergyworld.com/solar/k-road-gives-up-on-calico-solar-project/ | ->opened | ->2013 |  |
| -> | con_4f5282b549 | NY | EverPower Wind Farm | 4 | blocked_unverified->blocked_confirmed | outcome_label_only->resolution: https://greatlakesecho.org/2014/04/16/new-york-court-leaves-turbine-project-dangling-in-the-wind | report_citation->confirmed | unverified->verified | ->https://greatlakesecho.org/2014/04/16/new-york-court-leaves-turbine-project-dangling-in-the-wind | ->opened | ->2014 |  |
| -> | con_18be77447d | NY | Staten Island Battery Storage Project | 2->1 | pending->advanced_confirmed | none->resolution: https://ny1.com/nyc/staten-island/human-interest/2025/12/17/battery-energy-storage-system-sparks-controversy-on-staten-island | report_citation->confirmed | unverified->verified | ->https://ny1.com/nyc/staten-island/human-interest/2025/12/17/battery-energy-storage-system-sparks-controversy-on-staten-island | ->opened | ->2025-12 | outcome pending, but the plant is cancelled or indefinitely postponed->outcome advanced_confirmed, but the plant is cancelled or indefinitely postponed |
