# County record score

Written by `scripts/county_record_score.py` from `config/county_record_score.json` (version 2026-10-21). Do not edit by hand.

**What the score is.** How restrictive a county is for wind, solar and battery storage, on one rubric, read from its own record: the restriction instruments placed in it, a listed move from no zoning to zoning, and the outcomes of its contested projects. A county with no record is scored on its resemblance score (`data/model/county_restriction_scores.csv`) as a prior. Internal: no page, county report or headline figure reads it.

## Counties by tier

| Tier | Counties | Meaning |
|---|---:|---|
| closed | 132 | Closed: a moratorium or ban in force, or rules that act as one, county-wide |
| severe | 315 | Severe: rules likely to block most projects |
| restrictive | 359 | Restrictive: material rules, or blocked projects |
| regulated | 527 | Regulated but open: rules in force, projects approved under them |
| open | 60 | Open: nothing restrictive on record |
| no_record | 1751 | No record and no negative check: scored on the profile prior alone |

## Reference counties

| County | Tier | Combined (U.S. percentile) | Record points | Instruments | Zoning | Blocked | Approval credit | Resemblance score (decile) | Top instrument |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| Nicholas, KY | closed | 57.5 (99.5) | 57.5 | 57.5 | 0.0 | 0 | 0.0 | 0.0483 (1) | queue:q_ef439d5e2f-2 (moratorium, severity 4, in_force, Nicholas County) |
| Cherokee, KS | closed | 64.5 (99.8) | 64.5 | 55.5 | 9.0 | 0 | 0.0 | 0.1346 (5) | queue:q_011039b3ee (moratorium, severity 4, in_force, Cherokee County) |
| Harris, TX | restrictive | 12.5 (68.0) | 12.5 | 15.0 | 0.0 | 5 | 7.5 | 0.3596 (8) | queue:q_bbb012a590-2 (setback, severity 3, in_force, Pasadena) |
| Linn, IA | regulated | 7.35 (49.1) | 7.35 | 14.7 | 0.0 | 0 | 7.35 | 0.4041 (9) | queue:q_82dfad9133 (setback, severity 2, in_force, Linn County) |

## Highest combined scores

| County | Tier | Combined | Top instrument |
|---|---|---:|---|
| Onondaga, NY | closed | 75.0 | sabin:S26R-5715 (ban_or_moratorium, severity 4, in_force, DeWitt) |
| McLean, ND | closed | 73.0 | sabin:REC-0324 (ban, severity 4, in_force, McLean County) |
| Steuben, NY | closed | 70.0 | mn:ny-cameron-2024 (moratorium, severity 4, in_force, Cameron) |
| Erie, NY | closed | 68.5 | mn:ny-aurora-erie-county-2025 (moratorium, severity 4, in_force, Aurora (Erie County)) |
| Mecklenburg, VA | closed | 66.5 | sabin:S26R-5447 (ban, severity 4, in_force, Mecklenburg County) |
| Chautauqua, NY | closed | 65.0 | sabin:REC-0293 (ban_or_moratorium, severity 4, in_force, Chautauqua County) |
| Cherokee, KS | closed | 64.5 | queue:q_011039b3ee (moratorium, severity 4, in_force, Cherokee County) |
| Washington, PA | closed | 63.75 | sabin:S26R-5535 (ban_or_moratorium, severity 4, in_force, Washington County) |
| Worcester, MA | closed | 62.83 | sabin:REC-0186 (ban, severity 4, in_force, Town of Charlton) |
| Huron, MI | closed | 62.75 | mn:mi-huron-county-solar-and-battery-storage-2026 (moratorium, severity 4, in_force, Huron County (solar and battery storage)) |
| Saratoga, NY | closed | 62.25 | mn:ny-milton-saratoga-county-2024 (moratorium, severity 4, in_force, Milton (Saratoga County)) |
| Chester, PA | closed | 62.12 | sabin:S26R-5557 (ban_or_moratorium, severity 4, in_force, East Pikeland) |
| Westchester, NY | closed | 60.25 | mn:ny-bedford-2024 (moratorium, severity 4, in_force, Bedford) |
| Shelby, IA | closed | 60.0 | mn:ia-shelby-county-2026-2 (moratorium, severity 4, in_force, Shelby County) |
| Navajo, AZ | closed | 59.25 | sabin:S26R-6256 (ban_or_moratorium, severity 4, in_force, Navajo County) |

## Record against resemblance

1392 counties have a record. Of those in the top three resemblance deciles, 228 are open or regulated on their record; of those in the bottom three, 28 are closed or severe. These are the counties where the two scores disagree most.

