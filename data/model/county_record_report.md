# County record score

Written by `scripts/county_record_score.py` from `config/county_record_score.json` (version 2026-10-30). Do not edit by hand.

**What the score is.** How restrictive a county is for wind, solar and battery storage, on one rubric, read from its own record: the restriction instruments placed in it, a listed move from no zoning to zoning, and the outcomes of its contested projects. A county with no record is scored on its resemblance score (`data/model/county_restriction_scores.csv`) as a prior. Internal: no page, county report or headline figure reads it.

## Counties by tier

| Tier | Counties | Meaning |
|---|---:|---|
| closed | 108 | Closed: a moratorium or ban in force, or rules that act as one, county-wide |
| severe | 277 | Severe: rules likely to block most projects |
| restrictive | 314 | Restrictive: material rules, or blocked projects |
| regulated | 753 | Regulated but open: rules in force, projects approved under them |
| open | 458 | Open: nothing restrictive on record |
| no_record | 1234 | No record and no negative check: scored on the profile prior alone |

## Reference counties

| County | Tier | Combined (U.S. percentile) | Record points | Instruments | Zoning | Blocked | Approval credit | Resemblance score (decile) | Top instrument |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| Nicholas, KY | closed | 57.5 (99.4) | 57.5 | 57.5 | 0.0 | 0 | 0.0 | 0.0468 (1) | queue:q_ef439d5e2f-2 (moratorium, severity 4, in_force, Nicholas County) |
| Cherokee, KS | closed | 64.5 (99.7) | 64.5 | 55.5 | 9.0 | 0 | 0.0 | 0.2097 (7) | queue:q_011039b3ee (moratorium, severity 4, in_force, Cherokee County) |
| Harris, TX | restrictive | 12.5 (75.3) | 12.5 | 15.0 | 0.0 | 5 | 7.5 | 0.3408 (8) | queue:q_bbb012a590-2 (setback, severity 3, in_force, Pasadena) |
| Linn, IA | regulated | 7.88 (57.7) | 7.88 | 15.75 | 0.0 | 0 | 7.88 | 0.388 (9) | queue:q_82dfad9133 (setback, severity 2, in_force, Linn County) |

## State preemption

Each rule in `state_preemption` caps the severity a local instrument counts at (1 where a state permit replaces local approval, 2 where statute caps local rules or a state body may set them aside), for the governments it binds. A size threshold is read against the median of the state's recent plants of that technology, or 100 MW where the state has fewer than 5. `tier_local` and `combined_local` are the score with no cap.

| Rule | Mechanism | Ceiling | Binds | Technology: threshold, state reference size | Counties capped | Points removed |
|---|---|---:|---|---|---:|---:|
| IL-local_preemption-1 | statutory_ceiling | 2 | county | solar: any size, 100.0 MW; wind: any size, 192.5 MW | 27 | 680.99 |
| IL-local_preemption-2 | statutory_ceiling | 2 | county | battery_storage: any size, 100 (fallback) MW | 2 | 55.84 |
| IL-local_preemption-3 | discretionary_override | 2 | county | solar: 50 MW, 100.0 MW; wind: 50 MW, 192.5 MW; battery_storage: 50 MW, 100 (fallback) MW | 28 | 711.69 |
| MD-local_preemption-1 | statutory_ceiling | 2 | all_local | solar: 1 MW, 45.0 MW | 5 | 69.5 |
| MD-local_preemption-2 | statutory_ceiling | 2 | all_local | battery_storage: any size, 100 (fallback) MW | 0 | 0 |
| WI-local_preemption-1 | replaces_local | 1 | all_local | solar: 100 MW, 100.0 MW; wind: 100 MW, 100 (fallback) MW | 27 | 378.08 |
| WI-local_preemption-2 | statutory_ceiling | 2 | all_local | solar: any size, 100.0 MW; wind: any size, 100 (fallback) MW | 0 | 0 |
| MA-local_preemption-1 | statutory_ceiling | 2 | all_local | solar: any size, 100 (fallback) MW | 0 | 0 |
| MA-local_preemption-2:large | replaces_local | 1 | all_local | solar: 25 MW, 100 (fallback) MW; wind: 25 MW, 100 (fallback) MW; battery_storage: 100 MWh, 100 (fallback) MW | 13 | 445.51 |
| MA-local_preemption-2:small | statutory_ceiling | 2 | all_local | solar: any size, 100 (fallback) MW; wind: any size, 100 (fallback) MW; battery_storage: any size, 100 (fallback) MW | 0 | 0 |
| FL-local_preemption-1 | replaces_local | 1 | all_local | solar: 75 MW, 74.5 MW | 0 | 0 |
| FL-local_preemption-2 | statutory_ceiling | 2 | county | solar: any size, 74.5 MW | 0 | 0 |
| MN-local_preemption-1 | replaces_local | 1 | all_local | solar: 50 MW, 50.0 MW; wind: 5 MW, 155.0 MW; battery_storage: 10 MW, 100 (fallback) MW | 59 | 1372.76 |
| IA-local_preemption-1 | discretionary_override | 2 | all_local | solar: 25 MW, 100.0 MW; battery_storage: 25 MWh, 100 (fallback) MW | 27 | 551.82 |
| MI-local_preemption-1 | replaces_local | 1 | all_local | solar: 50 MW, 100.0 MW; wind: 100 MW, 159.3 MW; battery_storage: 50 MW, 100 (fallback) MW | 65 | 1302.98 |
| OH-local_preemption-1 | replaces_local | 1 | non_county | solar: 50 MW, 120.0 MW; wind: 5 MW, 100 (fallback) MW | 2 | 21.6 |
| RI-local_preemption-1 | replaces_local | 1 | all_local | solar: 40 MW, 100 (fallback) MW; wind: 40 MW, 100 (fallback) MW | 4 | 79.52 |
| CT-local_preemption-1 | replaces_local | 1 | all_local | solar: 1 MW, 100 (fallback) MW; wind: 1 MW, 100 (fallback) MW; battery_storage: any size, 100 (fallback) MW | 7 | 126.25 |
| VT-local_preemption-1 | replaces_local | 1 | all_local | solar: any size, 100 (fallback) MW; wind: any size, 100 (fallback) MW; battery_storage: any size, 100 (fallback) MW | 13 | 315.07 |
| CA-local_preemption-1 | replaces_local | 1 | all_local | solar: 50 MW, 153.5 MW; wind: 50 MW, 58.85 MW; battery_storage: 200 MWh, 115.8 MW | 31 | 621.2 |
| WA-local_preemption-1 | discretionary_override | 2 | all_local | solar: any size, 100 (fallback) MW; wind: any size, 100 (fallback) MW; battery_storage: any size, 100 (fallback) MW | 10 | 244.25 |
| NY-local_preemption-1 | discretionary_override | 2 | all_local | solar: 25 MW, 20.0 MW; wind: 25 MW, 118.6 MW | 47 | 310.51 |
| NM-local_preemption-1 | discretionary_override | 2 | all_local | solar: 300 MW, 170.0 MW; wind: 300 MW, 315.6 MW | 2 | 19.8 |
| SC-local_preemption-1 | discretionary_override | 2 | all_local | solar: 75 MW, 74.95 MW; wind: 75 MW, 100 (fallback) MW | 3 | 48.6 |
| OR-local_preemption-1 | replaces_local | 1 | all_local | wind: 300 MW, 100 (fallback) MW | 0 | 0 |

370 counties have record points removed and 61 without a record have their prior lowered by the cap; 282 change tier.

| Tier with no cap | closed | severe | restrictive | regulated | open | no_record |
|---|---:|---:|---:|---:|---:|---:|
| closed | 108 | 17 | 15 | 27 | 2 | 0 |
| severe | 0 | 260 | 33 | 59 | 4 | 0 |
| restrictive | 0 | 0 | 266 | 70 | 15 | 0 |
| regulated | 0 | 0 | 0 | 597 | 40 | 0 |
| open | 0 | 0 | 0 | 0 | 397 | 0 |
| no_record | 0 | 0 | 0 | 0 | 0 | 1234 |

Rows are the tier with no cap, columns the tier scored.

### Largest reductions

| County | Tier (no cap to scored) | Combined (no cap to scored) | Record points removed | Rules |
|---|---|---|---:|---|
| Worcester, MA | closed to regulated | 67.0 to 10.92 | 56.08 | MA-local_preemption-2:large |
| Clinton, MI | closed to regulated | 53.02 to 3.25 | 49.77 | MI-local_preemption-1 |
| Huron, MI | closed to restrictive | 63.04 to 14.81 | 56.7 | MI-local_preemption-1 |
| Monroe, MI | closed to regulated | 51.54 to 5.13 | 58.76 | MI-local_preemption-1 |
| Kalamazoo, MI | closed to regulated | 48.8 to 4.22 | 54.74 | MI-local_preemption-1 |
| Pine, MN | closed to regulated | 48.92 to 4.4 | 44.52 | MN-local_preemption-1 |
| Yolo, CA | closed to regulated | 47.73 to 4.5 | 54.52 | CA-local_preemption-1 |
| Aitkin, MN | closed to regulated | 47.73 to 4.5 | 54.52 | MN-local_preemption-1 |
| Traverse, MN | closed to regulated | 46.93 to 4.8 | 54.08 | MN-local_preemption-1 |
| Hampden, MA | closed to regulated | 47.29 to 5.69 | 47.86 | MA-local_preemption-2:large |
| Allegan, MI | closed to regulated | 48.61 to 7.01 | 47.85 | MI-local_preemption-1 |
| Marathon, WI | closed to regulated | 50.58 to 9.14 | 55.25 | WI-local_preemption-1 |
| Freeborn, MN | closed to regulated | 45.83 to 4.5 | 51.98 | MN-local_preemption-1 |
| Essex, MA | closed to regulated | 49.44 to 8.19 | 47.39 | MA-local_preemption-2:large |
| Franklin, MA | closed to regulated | 47.16 to 7.31 | 45.52 | MA-local_preemption-2:large |
| Berrien, MI | closed to regulated | 46.38 to 6.7 | 39.68 | MI-local_preemption-1 |
| Genesee, MI | closed to regulated | 44.42 to 4.92 | 39.5 | MI-local_preemption-1 |
| Pope, MN | closed to regulated | 42.86 to 4.5 | 49.65 | MN-local_preemption-1 |
| Chisago, MN | closed to open | 40.98 to 2.85 | 47.72 | MN-local_preemption-1 |
| Mower, MN | closed to open | 40.26 to 2.85 | 45.18 | MN-local_preemption-1 |

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
| 1 | 315 | 0.0 to 1.98 | -3.542 to -1.281 |
| 2 | 314 | 1.98 to 2.28 | -1.279 to -0.842 |
| 3 | 315 | 2.28 to 3.72 | -0.841 to -0.524 |
| 4 | 314 | 3.72 to 4.58 | -0.523 to -0.253 |
| 5 | 314 | 4.58 to 5.82 | -0.253 to 0.0 |
| 6 | 315 | 5.83 to 8.94 | 0.0 to 0.253 |
| 7 | 314 | 8.94 to 11.07 | 0.254 to 0.524 |
| 8 | 315 | 11.07 to 14.28 | 0.525 to 0.842 |
| 9 | 314 | 14.4 to 27.82 | 0.843 to 1.281 |
| 10 | 314 | 27.83 to 75.0 | 1.283 to 3.542 |

## Highest combined scores

| County | Tier | Combined | Top instrument |
|---|---|---:|---|
| Onondaga, NY | closed | 75.0 | sabin:S26R-5715 (ban_or_moratorium, severity 4, in_force, DeWitt) |
| Lancaster, PA | closed | 73.34 | nrel:wind:4207121344 (moratorium, severity 4, unknown, East Lampeter Township) |
| McLean, ND | closed | 73.0 | sabin:REC-0324 (ban, severity 4, in_force, McLean County) |
| Lackawanna, PA | closed | 72.29 | nrel:wind:4206971872 (ban, severity 4, unknown, South Abington Township) |
| Erie, NY | closed | 70.0 | mn:ny-aurora-erie-county-2025 (moratorium, severity 4, in_force, Aurora (Erie County)) |
| Chester, PA | closed | 70.0 | sabin:S26R-5557 (ban_or_moratorium, severity 4, in_force, East Pikeland) |
| Washington, PA | closed | 70.0 | sabin:S26R-5535 (ban_or_moratorium, severity 4, in_force, Washington County) |
| Saratoga, NY | closed | 65.92 | mn:ny-milton-saratoga-county-2024 (moratorium, severity 4, in_force, Milton (Saratoga County)) |
| Chautauqua, NY | closed | 65.0 | mn:ny-ellery-2026 (moratorium, severity 4, in_force, Ellery) |
| Cherokee, KS | closed | 64.5 | queue:q_011039b3ee (moratorium, severity 4, in_force, Cherokee County) |
| Westchester, NY | closed | 63.92 | mn:ny-bedford-2024 (moratorium, severity 4, in_force, Bedford) |
| Luzerne, PA | closed | 63.16 | nrel:solar:4207906672 (setback, severity 3, unknown, Black Creek Township) |
| Apache, AZ | closed | 59.55 | sabin:S26R-6258 (ban_or_moratorium, severity 4, in_force, Apache County) |
| Brown, KS | closed | 59.38 | mn:ks-brown-county-2026 (moratorium, severity 4, in_force, Brown County) |
| Sedgwick, KS | closed | 58.73 | sabin:S26R-6046 (moratorium, severity 4, in_force, Sedgwick County) |
## Build-out

756 counties have at least one uncontested plant counted as an approval (1759 plants); for 373 of them it is the only evidence on record.


## Record against resemblance

1389 counties have a record. Of those in the top three resemblance deciles, 281 are open or regulated on their record; of those in the bottom three, 31 are closed or severe. These are the counties where the two scores disagree most.

