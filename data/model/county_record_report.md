# County record score

Written by `scripts/county_record_score.py` from `config/county_record_score.json` (version 2026-10-21). Do not edit by hand.

**What the score is.** How restrictive a county is for wind, solar and battery storage, on one rubric, read from its own record: the restriction instruments placed in it, a listed move from no zoning to zoning, and the outcomes of its contested projects. A county with no record is scored on its resemblance score (`data/model/county_restriction_scores.csv`) as a prior. Internal: no page, county report or headline figure reads it.

## Counties by tier

| Tier | Counties | Meaning |
|---|---:|---|
| closed | 117 | Closed: a moratorium or ban in force, or rules that act as one, county-wide |
| severe | 308 | Severe: rules likely to block most projects |
| restrictive | 342 | Restrictive: material rules, or blocked projects |
| regulated | 685 | Regulated but open: rules in force, projects approved under them |
| open | 317 | Open: nothing restrictive on record |
| no_record | 1375 | No record and no negative check: scored on the profile prior alone |

## Reference counties

| County | Tier | Combined (U.S. percentile) | Record points | Instruments | Zoning | Blocked | Approval credit | Resemblance score (decile) | Top instrument |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| Nicholas, KY | closed | 57.5 (99.5) | 57.5 | 57.5 | 0.0 | 0 | 0.0 | 0.0483 (1) | queue:q_ef439d5e2f-2 (moratorium, severity 4, in_force, Nicholas County) |
| Cherokee, KS | closed | 64.5 (99.8) | 64.5 | 55.5 | 9.0 | 0 | 0.0 | 0.1346 (5) | queue:q_011039b3ee (moratorium, severity 4, in_force, Cherokee County) |
| Harris, TX | restrictive | 12.5 (71.9) | 12.5 | 15.0 | 0.0 | 5 | 7.5 | 0.3596 (8) | queue:q_bbb012a590-2 (setback, severity 3, in_force, Pasadena) |
| Linn, IA | regulated | 7.35 (55.9) | 7.35 | 14.7 | 0.0 | 0 | 7.35 | 0.4041 (9) | queue:q_82dfad9133 (setback, severity 2, in_force, Linn County) |

## Highest combined scores

| County | Tier | Combined | Top instrument |
|---|---|---:|---|
| Onondaga, NY | closed | 75.0 | sabin:S26R-5715 (ban_or_moratorium, severity 4, in_force, DeWitt) |
| McLean, ND | closed | 73.0 | sabin:REC-0324 (ban, severity 4, in_force, McLean County) |
| Erie, NY | closed | 68.5 | mn:ny-aurora-erie-county-2025 (moratorium, severity 4, in_force, Aurora (Erie County)) |
| Steuben, NY | closed | 67.0 | mn:ny-cameron-2024 (moratorium, severity 4, in_force, Cameron) |
| Chautauqua, NY | closed | 65.0 | sabin:REC-0293 (ban_or_moratorium, severity 4, in_force, Chautauqua County) |
| Cherokee, KS | closed | 64.5 | queue:q_011039b3ee (moratorium, severity 4, in_force, Cherokee County) |
| Washington, PA | closed | 63.75 | sabin:S26R-5535 (ban_or_moratorium, severity 4, in_force, Washington County) |
| Saratoga, NY | closed | 62.25 | mn:ny-milton-saratoga-county-2024 (moratorium, severity 4, in_force, Milton (Saratoga County)) |
| Chester, PA | closed | 62.12 | sabin:S26R-5557 (ban_or_moratorium, severity 4, in_force, East Pikeland) |
| Huron, MI | closed | 60.26 | mn:mi-huron-county-solar-and-battery-storage-2026 (moratorium, severity 4, in_force, Huron County (solar and battery storage)) |
| Westchester, NY | closed | 60.25 | mn:ny-bedford-2024 (moratorium, severity 4, in_force, Bedford) |
| Shelby, IA | closed | 60.0 | mn:ia-shelby-county-2026-2 (moratorium, severity 4, in_force, Shelby County) |
| Worcester, MA | closed | 59.83 | sabin:REC-0186 (ban, severity 4, in_force, Town of Charlton) |
| Lewis, NY | closed | 58.2 | mn:ny-greig-lewis-county-2026 (moratorium, severity 4, in_force, Greig (Lewis County)) |
| Madison, IN | closed | 57.5 | sabin:REC-0098 (moratorium, severity 4, in_force, Madison County) |
## Build-out

769 counties have at least one uncontested plant counted as an approval (1782 plants); for 376 of them it is the only evidence on record.


## Record against resemblance

1392 counties have a record. Of those in the top three resemblance deciles, 245 are open or regulated on their record; of those in the bottom three, 28 are closed or severe. These are the counties where the two scores disagree most.

