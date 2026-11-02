# County record score

Written by `scripts/county_record_score.py` from `config/county_record_score.json` (version 2026-10-30). Do not edit by hand.

**What the score is.** How restrictive a county is for wind, solar and battery storage, on one rubric, read from its own record: the restriction instruments placed in it, a listed move from no zoning to zoning, and the outcomes of its contested projects. A county with no record is scored on its resemblance score (`data/model/county_restriction_scores.csv`) as a prior. Internal: no page, county report or headline figure reads it.

## Counties by tier

| Tier | Counties | Meaning |
|---|---:|---|
| closed | 101 | Closed: a moratorium or ban in force, or rules that act as one, county-wide |
| severe | 276 | Severe: rules likely to block most projects |
| restrictive | 347 | Restrictive: material rules, or blocked projects |
| regulated | 743 | Regulated but open: rules in force, projects approved under them |
| open | 450 | Open: nothing restrictive on record |
| no_record | 1227 | No record and no negative check: scored on the profile prior alone |

## Reference counties

| County | Tier | Combined (U.S. percentile) | Record points | Instruments | Zoning | Blocked | Approval credit | Resemblance score (decile) | Top instrument |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| Nicholas, KY | closed | 57.5 (99.5) | 57.5 | 57.5 | 0.0 | 0 | 0.0 | 0.0483 (1) | queue:q_ef439d5e2f-2 (moratorium, severity 4, in_force, Nicholas County) |
| Cherokee, KS | closed | 64.5 (99.8) | 64.5 | 55.5 | 9.0 | 0 | 0.0 | 0.1346 (5) | queue:q_011039b3ee (moratorium, severity 4, in_force, Cherokee County) |
| Harris, TX | restrictive | 12.5 (74.4) | 12.5 | 15.0 | 0.0 | 5 | 7.5 | 0.3596 (8) | queue:q_bbb012a590-2 (setback, severity 3, in_force, Pasadena) |
| Linn, IA | regulated | 7.88 (57.7) | 7.88 | 15.75 | 0.0 | 0 | 7.88 | 0.4041 (9) | queue:q_82dfad9133 (setback, severity 2, in_force, Linn County) |

## State preemption

Each rule in `state_preemption` caps the severity a local instrument counts at (1 where a state permit replaces local approval, 2 where statute caps local rules or a state body may set them aside), for the governments it binds and a project of 100 MW. `tier_local` and `combined_local` are the score with no cap.

| Rule | Mechanism | Ceiling | Binds | Technologies (smallest project reached) | Counties capped | Points removed |
|---|---|---:|---|---|---:|---:|
| IL-local_preemption-1 | statutory_ceiling | 2 | county | solar (any), wind (any) | 27 | 605.21 |
| IL-local_preemption-2 | statutory_ceiling | 2 | county | battery_storage (any) | 1 | 28.0 |
| IL-local_preemption-3 | discretionary_override | 2 | county | solar (50 MW), wind (50 MW), battery_storage (50 MW) | 28 | 633.21 |
| MD-local_preemption-1 | statutory_ceiling | 2 | all_local | solar (1 MW) | 2 | 56.0 |
| MD-local_preemption-2 | statutory_ceiling | 2 | all_local | battery_storage (any) | 0 | 0 |
| WI-local_preemption-1 | replaces_local | 1 | all_local | solar (100 MW), wind (100 MW) | 26 | 376.12 |
| WI-local_preemption-2 | statutory_ceiling | 2 | all_local | solar (any), wind (any) | 0 | 0 |
| MA-local_preemption-1 | statutory_ceiling | 2 | all_local | solar (any) | 0 | 0 |
| MA-local_preemption-2 | replaces_local | 1 | all_local | solar (25 MW), wind (25 MW), battery_storage (100 MWh) | 13 | 451.55 |
| MA-local_preemption-2 | statutory_ceiling | 2 | all_local | solar (any), wind (any), battery_storage (any) | 13 | 451.55 |
| FL-local_preemption-1 | replaces_local | 1 | all_local | solar (75 MW) | 10 | 43.1 |
| FL-local_preemption-2 | statutory_ceiling | 2 | county | solar (any) | 0 | 0 |
| MN-local_preemption-1 | replaces_local | 1 | all_local | solar (50 MW), wind (5 MW), battery_storage (10 MW) | 61 | 1446.9 |
| IA-local_preemption-1 | discretionary_override | 2 | all_local | solar (25 MW), battery_storage (25 MWh) | 25 | 543.42 |
| MI-local_preemption-1 | replaces_local | 1 | all_local | solar (50 MW), wind (100 MW), battery_storage (50 MW) | 68 | 1375.97 |
| OH-local_preemption-1 | replaces_local | 1 | non_county | solar (50 MW), wind (5 MW) | 2 | 37.8 |
| RI-local_preemption-1 | replaces_local | 1 | all_local | solar (40 MW), wind (40 MW) | 4 | 79.2 |
| CT-local_preemption-1 | replaces_local | 1 | all_local | solar (1 MW), wind (1 MW), battery_storage (any) | 7 | 126.24 |
| VT-local_preemption-1 | replaces_local | 1 | all_local | solar (any), wind (any), battery_storage (any) | 13 | 313.96 |
| CA-local_preemption-1 | replaces_local | 1 | all_local | solar (50 MW), wind (50 MW), battery_storage (200 MWh) | 32 | 624.52 |
| WA-local_preemption-1 | discretionary_override | 2 | all_local | solar (any), wind (any), battery_storage (any) | 10 | 244.25 |
| NY-local_preemption-1 | discretionary_override | 2 | all_local | solar (25 MW), wind (25 MW) | 50 | 524.11 |
| NM-local_preemption-1 | discretionary_override | 2 | all_local | solar (300 MW), wind (300 MW) | 0 | 0 |
| SC-local_preemption-1 | discretionary_override | 2 | all_local | solar (75 MW), wind (75 MW) | 4 | 77.05 |
| OR-local_preemption-1 | replaces_local | 1 | all_local | wind (300 MW) | 0 | 0 |

354 counties have record points removed and 108 without a record have their prior capped; 303 change tier.

| Tier with no cap | closed | severe | restrictive | regulated | open | no_record |
|---|---:|---:|---:|---:|---:|---:|
| closed | 101 | 19 | 17 | 27 | 0 | 0 |
| severe | 0 | 257 | 42 | 64 | 3 | 0 |
| restrictive | 0 | 0 | 288 | 69 | 17 | 0 |
| regulated | 0 | 0 | 0 | 583 | 45 | 0 |
| open | 0 | 0 | 0 | 0 | 385 | 0 |
| no_record | 0 | 0 | 0 | 0 | 0 | 1227 |

Rows are the tier with no cap, columns the tier scored.

### Largest reductions

| County | Tier (no cap to scored) | Combined (no cap to scored) | Record points removed | Rules |
|---|---|---|---:|---|
| Worcester, MA | closed to restrictive | 67.0 to 13.6 | 53.4 | MA-local_preemption-2 |
| Clinton, MI | closed to regulated | 53.02 to 3.85 | 49.17 | MI-local_preemption-1 |
| Huron, MI | closed to restrictive | 62.82 to 15.9 | 55.25 | MI-local_preemption-1 |
| Monroe, MI | closed to regulated | 51.77 to 5.96 | 57.65 | MI-local_preemption-1 |
| Kalamazoo, MI | closed to regulated | 48.92 to 4.55 | 54.3 | MI-local_preemption-1 |
| Pine, MN | closed to regulated | 48.92 to 5.7 | 43.22 | MN-local_preemption-1 |
| Yolo, CA | closed to regulated | 47.96 to 6.23 | 52.22 | CA-local_preemption-1 |
| Aitkin, MN | closed to regulated | 47.96 to 6.23 | 52.22 | MN-local_preemption-1 |
| Traverse, MN | closed to regulated | 47.22 to 5.77 | 52.78 | MN-local_preemption-1 |
| Marathon, WI | closed to regulated | 50.87 to 9.43 | 55.25 | WI-local_preemption-1 |
| Allegan, MI | closed to regulated | 48.39 to 7.01 | 47.85 | MI-local_preemption-1 |
| Essex, MA | closed to regulated | 49.22 to 8.19 | 47.39 | MA-local_preemption-2 |
| Hampden, MA | closed to regulated | 47.08 to 6.32 | 47.02 | MA-local_preemption-2 |
| Freeborn, MN | closed to regulated | 46.06 to 5.59 | 50.53 | MN-local_preemption-1 |
| Franklin, MA | closed to regulated | 46.94 to 7.31 | 45.52 | MA-local_preemption-2 |
| Berrien, MI | closed to regulated | 46.38 to 7.12 | 39.26 | MI-local_preemption-1 |
| Mower, MN | closed to regulated | 42.22 to 3.17 | 44.76 | MN-local_preemption-1 |
| Genesee, MI | closed to regulated | 44.42 to 5.38 | 39.04 | MI-local_preemption-1 |
| Chisago, MN | closed to regulated | 42.28 to 3.53 | 46.82 | MN-local_preemption-1 |
| Pope, MN | closed to regulated | 42.77 to 5.89 | 47.8 | MN-local_preemption-1 |

### Partial exemptions

The cap still applies in these counties; a site inside the exempt area is not covered by it.

- Lee, IL: 55 ILCS 5/5-12020(u)(3) exempts land in a certified enterprise zone, classified industrial by 2023-01-27, within 4 miles of the I-88/I-39 interchange.
- Ogle, IL: the same carve-out as Lee (55 ILCS 5/5-12020(u)(3)); the interchange is in Ogle County.
- Madison, IL: 55 ILCS 5/5-12020(u)(4) exempts the area bounded by Drexelius, Fosterburg and Wolf Roads.

### Read and not applied

- CO-local_preemption-1: Covers only facilities proposed by a public utility or power authority; independent developers do not get it.
- IN-local_preemption-1: Limits a local moratorium to one year with no renewal; it shortens the instrument, which its currency already records, but does not cap its severity while in force.
- MS-local_preemption-1: Limits only local decommissioning and financial assurance terms.
- NJ-local_preemption-1: Makes these facilities a permitted use only in industrial and commercial districts and on rooftops, landfills, brownfields and similar sites; a rule on agricultural land, where most projects go, is not reached.
- NV-local_preemption-1: Protects an owner's own solar or wind system on the owner's property, not utility-scale projects.
- OH-local_opt_out-1: Gives county commissioners power to bar projects, the reverse of preemption; it is why OH-local_preemption-1 does not reach county instruments.

## Combined score by decile

Deciles of U.S. counties ranked by combined score, ties broken by resemblance score. `combined_normal` is the same rank as a standard normal score.

| Decile | Counties | Combined score (lowest to highest) | Normal score (lowest to highest) |
|---:|---:|---|---|
| 1 | 315 | 0.0 to 1.8 | -3.542 to -1.281 |
| 2 | 314 | 1.8 to 2.64 | -1.279 to -0.842 |
| 3 | 315 | 2.64 to 3.57 | -0.841 to -0.524 |
| 4 | 314 | 3.57 to 4.8 | -0.523 to -0.253 |
| 5 | 314 | 4.8 to 6.04 | -0.253 to 0.0 |
| 6 | 315 | 6.04 to 8.92 | 0.0 to 0.253 |
| 7 | 314 | 8.92 to 11.42 | 0.254 to 0.524 |
| 8 | 315 | 11.42 to 15.09 | 0.525 to 0.842 |
| 9 | 314 | 15.09 to 27.47 | 0.843 to 1.281 |
| 10 | 314 | 27.47 to 73.34 | 1.283 to 3.542 |

## Highest combined scores

| County | Tier | Combined | Top instrument |
|---|---|---:|---|
| Lancaster, PA | closed | 73.34 | nrel:wind:4207121344 (moratorium, severity 4, unknown, East Lampeter Township) |
| McLean, ND | closed | 73.0 | sabin:REC-0324 (ban, severity 4, in_force, McLean County) |
| Lackawanna, PA | closed | 72.29 | nrel:wind:4206971872 (ban, severity 4, unknown, South Abington Township) |
| Chester, PA | closed | 70.0 | sabin:S26R-5557 (ban_or_moratorium, severity 4, in_force, East Pikeland) |
| Washington, PA | closed | 70.0 | sabin:S26R-5535 (ban_or_moratorium, severity 4, in_force, Washington County) |
| Erie, NY | closed | 69.78 | mn:ny-aurora-erie-county-2025 (moratorium, severity 4, in_force, Aurora (Erie County)) |
| Chautauqua, NY | closed | 65.0 | mn:ny-ellery-2026 (moratorium, severity 4, in_force, Ellery) |
| Cherokee, KS | closed | 64.5 | queue:q_011039b3ee (moratorium, severity 4, in_force, Cherokee County) |
| Onondaga, NY | closed | 61.35 | mn:ny-camillus-2026 (moratorium, severity 4, in_force, Camillus) |
| Luzerne, PA | closed | 61.09 | nrel:solar:4207906672 (setback, severity 3, unknown, Black Creek Township) |
| Westchester, NY | closed | 60.42 | mn:ny-bedford-2024 (moratorium, severity 4, in_force, Bedford) |
| Apache, AZ | closed | 59.55 | sabin:S26R-6258 (ban_or_moratorium, severity 4, in_force, Apache County) |
| Brown, KS | closed | 59.38 | mn:ks-brown-county-2026 (moratorium, severity 4, in_force, Brown County) |
| Saratoga, NY | closed | 58.92 | mn:ny-milton-saratoga-county-2024 (moratorium, severity 4, in_force, Milton (Saratoga County)) |
| Mecklenburg, VA | closed | 58.55 | sabin:S26R-5447 (ban, severity 4, in_force, Mecklenburg County) |
## Build-out

763 counties have at least one uncontested plant counted as an approval (1766 plants); for 371 of them it is the only evidence on record.


## Record against resemblance

1398 counties have a record. Of those in the top three resemblance deciles, 290 are open or regulated on their record; of those in the bottom three, 27 are closed or severe. These are the counties where the two scores disagree most.

