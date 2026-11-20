# County record score

Written by `scripts/county_record_score.py` from `config/county_record_score.json` (version 2026-11-20). Do not edit by hand.

**What the score is.** How restrictive a county is for wind, solar and battery storage, on one rubric, read from its own record: the restriction instruments placed in it, a listed move from no zoning to zoning, and the outcomes of its contested projects. A county with no record is scored on its resemblance score (`data/model/county_restriction_scores.csv`) as a prior. Internal: no page, county report or headline figure reads it.

## Counties by tier

| Tier | Counties | Meaning |
|---|---:|---|
| closed | 61 | Closed: a moratorium or ban in force, or rules that act as one, county-wide |
| severe | 299 | Severe: rules likely to block most projects |
| restrictive | 333 | Restrictive: material rules, or blocked projects |
| regulated | 757 | Regulated but open: rules in force, projects approved under them |
| open | 441 | Open: nothing restrictive on record |
| no_record | 1253 | No record and no negative check: scored on the profile prior alone |

## Reference counties

| County | Tier | Combined (U.S. percentile) | Record points | Instruments | Zoning | Blocked | Approval credit | Resemblance score (decile) | Top instrument |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| Nicholas, KY | closed | 43.12 (98.9) | 43.12 | 43.12 | 0.0 | 0 | 0.0 | 0.0468 (1) | queue:q_ef439d5e2f (setback, severity 3, in_force, Nicholas County) |
| Cherokee, KS | closed | 61.66 (99.9) | 61.66 | 52.66 | 9.0 | 0 | 0.0 | 0.2097 (7) | queue:q_011039b3ee (moratorium, severity 4, in_force, Cherokee County) |
| Harris, TX | restrictive | 16.5 (82.6) | 16.5 | 15.0 | 0.0 | 5 | 7.5 | 0.3408 (8) | queue:q_bbb012a590-2 (setback, severity 3, in_force, Pasadena) |
| Linn, IA | restrictive | 14.88 (81.3) | 14.88 | 15.75 | 0.0 | 0 | 7.88 | 0.388 (9) | queue:q_82dfad9133 (setback, severity 2, in_force, Linn County) |

## State preemption

Each rule in `state_preemption` caps the severity a local instrument counts at (1 where a state permit replaces local approval, 2 where statute caps local rules or a state body may set them aside), for the governments it binds. A size threshold is read against the median of the state's recent plants of that technology, or 100 MW where the state has fewer than 5. `tier_local` and `combined_local` are the score with no cap.

| Rule | Mechanism | Ceiling | Binds | Technology: threshold, state reference size | Counties capped | Points removed |
|---|---|---:|---|---|---:|---:|
| IL-local_preemption-1 | statutory_ceiling | 2 | county | solar: any size, 100.0 MW; wind: any size, 192.5 MW | 22 | 589.28 |
| IL-local_preemption-2 | statutory_ceiling | 2 | county | battery_storage: any size, 100 (fallback) MW | 2 | 48.71 |
| IL-local_preemption-3 | discretionary_override | 2 | county | solar: 50 MW, 100.0 MW; wind: 50 MW, 192.5 MW; battery_storage: 50 MW, 100 (fallback) MW | 23 | 612.85 |
| MD-local_preemption-1 | statutory_ceiling | 2 | all_local | solar: 1 MW, 45.0 MW | 5 | 69.5 |
| MD-local_preemption-2 | statutory_ceiling | 2 | all_local | battery_storage: any size, 100 (fallback) MW | 0 | 0 |
| WI-local_preemption-1 | replaces_local | 1 | all_local | solar: 100 MW, 100.0 MW; wind: 100 MW, 100 (fallback) MW | 27 | 346.97 |
| WI-local_preemption-2 | statutory_ceiling | 2 | all_local | solar: any size, 100.0 MW; wind: any size, 100 (fallback) MW | 0 | 0 |
| MA-local_preemption-1 | statutory_ceiling | 2 | all_local | solar: any size, 100 (fallback) MW | 0 | 0 |
| MA-local_preemption-2:large | replaces_local | 1 | all_local | solar: 25 MW, 100 (fallback) MW; wind: 25 MW, 100 (fallback) MW; battery_storage: 100 MWh, 100 (fallback) MW | 13 | 274.66 |
| MA-local_preemption-2:small | statutory_ceiling | 2 | all_local | solar: any size, 100 (fallback) MW; wind: any size, 100 (fallback) MW; battery_storage: any size, 100 (fallback) MW | 0 | 0 |
| FL-local_preemption-1 | replaces_local | 1 | all_local | solar: 75 MW, 74.5 MW | 0 | 0 |
| FL-local_preemption-2 | statutory_ceiling | 2 | county | solar: any size, 74.5 MW | 0 | 0 |
| MN-local_preemption-1 | replaces_local | 1 | all_local | solar: 50 MW, 50.0 MW; wind: 5 MW, 155.0 MW; battery_storage: 10 MW, 100 (fallback) MW | 58 | 1313.38 |
| IA-local_preemption-1 | discretionary_override | 2 | all_local | solar: 25 MW, 100.0 MW; battery_storage: 25 MWh, 100 (fallback) MW | 27 | 432.11 |
| MI-local_preemption-1 | replaces_local | 1 | all_local | solar: 50 MW, 100.0 MW; wind: 100 MW, 159.3 MW; battery_storage: 50 MW, 100 (fallback) MW | 65 | 1237.91 |
| OH-local_preemption-1 | replaces_local | 1 | non_county | solar: 50 MW, 120.0 MW; wind: 5 MW, 100 (fallback) MW | 2 | 21.26 |
| RI-local_preemption-1 | replaces_local | 1 | all_local | solar: 40 MW, 100 (fallback) MW; wind: 40 MW, 100 (fallback) MW | 4 | 68.32 |
| CT-local_preemption-1 | replaces_local | 1 | all_local | solar: 1 MW, 100 (fallback) MW; wind: 1 MW, 100 (fallback) MW; battery_storage: any size, 100 (fallback) MW | 6 | 101.61 |
| VT-local_preemption-1 | replaces_local | 1 | all_local | solar: any size, 100 (fallback) MW; wind: any size, 100 (fallback) MW; battery_storage: any size, 100 (fallback) MW | 12 | 291.0 |
| CA-local_preemption-1 | replaces_local | 1 | all_local | solar: 50 MW, 153.5 MW; wind: 50 MW, 58.85 MW; battery_storage: 200 MWh, 115.8 MW | 30 | 606.39 |
| WA-local_preemption-1 | discretionary_override | 2 | all_local | solar: any size, 100 (fallback) MW; wind: any size, 100 (fallback) MW; battery_storage: any size, 100 (fallback) MW | 9 | 188.52 |
| NY-local_preemption-1 | discretionary_override | 2 | all_local | solar: 25 MW, 20.0 MW; wind: 25 MW, 118.6 MW | 47 | 173.24 |
| NM-local_preemption-1 | discretionary_override | 2 | all_local | solar: 300 MW, 170.0 MW; wind: 300 MW, 315.6 MW | 2 | 19.8 |
| SC-local_preemption-1 | discretionary_override | 2 | all_local | solar: 75 MW, 74.95 MW; wind: 75 MW, 100 (fallback) MW | 3 | 48.6 |
| OR-local_preemption-1 | replaces_local | 1 | all_local | wind: 300 MW, 100 (fallback) MW | 0 | 0 |

345 counties have record points removed and 65 without a record have their prior lowered by the cap; 269 change tier.

| Tier with no cap | closed | severe | restrictive | regulated | open | no_record |
|---|---:|---:|---:|---:|---:|---:|
| closed | 61 | 10 | 10 | 17 | 1 | 0 |
| severe | 0 | 289 | 44 | 69 | 4 | 0 |
| restrictive | 0 | 0 | 279 | 61 | 14 | 0 |
| regulated | 0 | 0 | 0 | 610 | 39 | 0 |
| open | 0 | 0 | 0 | 0 | 383 | 0 |
| no_record | 0 | 0 | 0 | 0 | 0 | 1253 |

Rows are the tier with no cap, columns the tier scored.

### Largest reductions

| County | Tier (no cap to scored) | Combined (no cap to scored) | Record points removed | Rules |
|---|---|---|---:|---|
| Monroe, MI | closed to regulated | 51.41 to 5.13 | 58.76 | MI-local_preemption-1 |
| Pine, MN | closed to regulated | 48.92 to 4.4 | 44.52 | MN-local_preemption-1 |
| Yolo, CA | closed to regulated | 47.6 to 4.5 | 54.52 | CA-local_preemption-1 |
| Aitkin, MN | closed to regulated | 47.6 to 4.5 | 54.52 | MN-local_preemption-1 |
| Huron, MI | closed to restrictive | 59.06 to 17.06 | 49.87 | MI-local_preemption-1 |
| Freeborn, MN | closed to regulated | 44.4 to 4.5 | 50.26 | MN-local_preemption-1 |
| Berrien, MI | closed to regulated | 46.38 to 6.7 | 39.68 | MI-local_preemption-1 |
| Genesee, MI | closed to regulated | 47.42 to 7.93 | 39.49 | MI-local_preemption-1 |
| Kalamazoo, MI | closed to regulated | 43.06 to 4.22 | 47.46 | MI-local_preemption-1 |
| Clinton, MI | closed to regulated | 41.96 to 3.25 | 38.71 | MI-local_preemption-1 |
| Marathon, WI | closed to regulated | 47.58 to 8.95 | 51.5 | WI-local_preemption-1 |
| Allegan, MI | closed to regulated | 45.34 to 7.01 | 44.98 | MI-local_preemption-1 |
| Pope, MN | closed to regulated | 42.74 to 4.5 | 49.65 | MN-local_preemption-1 |
| Chisago, MN | closed to open | 40.85 to 2.85 | 47.72 | MN-local_preemption-1 |
| Mower, MN | severe to open | 39.98 to 2.85 | 45.18 | MN-local_preemption-1 |
| Wabasha, MN | closed to regulated | 41.52 to 4.5 | 47.52 | MN-local_preemption-1 |
| Chautauqua, NY | closed to severe | 65.0 to 28.0 | 37.0 | NY-local_preemption-1 |
| Orleans, VT | closed to restrictive | 59.4 to 22.43 | 36.97 | VT-local_preemption-1 |
| Carlton, MN | closed to regulated | 41.14 to 4.5 | 44.52 | MN-local_preemption-1 |
| Stevens, MN | closed to regulated | 40.23 to 4.5 | 44.7 | MN-local_preemption-1 |

### Partial exemptions

The cap still applies in these counties; a site inside the exempt area is not covered by it.

- Lee, IL: 55 ILCS 5/5-12020(u)(3) exempts land in a certified enterprise zone, classified industrial by 2023-01-27, within 4 miles of the I-88/I-39 interchange.
- Ogle, IL: the same carve-out as Lee (55 ILCS 5/5-12020(u)(3)); the interchange is in Ogle County.
- Madison, IL: 55 ILCS 5/5-12020(u)(4) exempts the area bounded by Drexelius, Fosterburg and Wolf Roads.

### Read and not applied

- CO-local_preemption-1: Covers only facilities proposed by a public utility or power authority; independent developers do not get it.
- KY-local_preemption-1: A Court of Appeals ruling (May 29, 2026), not a statute, and not final while the county's motion for Supreme Court review is pending. It holds that only a county with a planning and zoning commission can adopt rules that take priority over a siting board certificate; it does not address moratoriums. Recorded as context and not applied, so Kentucky county instruments keep their full severity until the ruling is final.
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
| 2 | 314 | 1.8 to 2.12 | -1.279 to -0.842 |
| 3 | 315 | 2.12 to 3.52 | -0.841 to -0.524 |
| 4 | 314 | 3.52 to 4.37 | -0.523 to -0.253 |
| 5 | 314 | 4.37 to 5.76 | -0.253 to 0.0 |
| 6 | 315 | 5.77 to 8.81 | 0.0 to 0.253 |
| 7 | 314 | 8.81 to 10.3 | 0.254 to 0.524 |
| 8 | 315 | 10.3 to 13.63 | 0.525 to 0.842 |
| 9 | 314 | 13.63 to 26.05 | 0.843 to 1.281 |
| 10 | 314 | 26.05 to 70.5 | 1.283 to 3.542 |

## Highest combined scores

| County | Tier | Combined | Top instrument |
|---|---|---:|---|
| McLean, ND | closed | 70.5 | sabin:REC-0324 (ban, severity 4, in_force, McLean County) |
| Washington, PA | closed | 70.0 | sabin:S26R-5535 (ban_or_moratorium, severity 4, in_force, Washington County) |
| Cherokee, KS | closed | 61.66 | queue:q_011039b3ee (moratorium, severity 4, in_force, Cherokee County) |
| Apache, AZ | closed | 59.55 | sabin:S26R-6258 (ban_or_moratorium, severity 4, in_force, Apache County) |
| Seneca, OH | closed | 59.0 | sabin:S26R-5606 (ban, severity 4, in_force, Seneca County) |
| Mecklenburg, VA | closed | 58.55 | sabin:S26R-5447 (ban, severity 4, in_force, Mecklenburg County) |
| Allen, OH | closed | 54.0 | sabin:REC-0340 (ban, severity 4, in_force, Allen County) |
| Auglaize, OH | closed | 54.0 | sabin:REC-0341 (ban_or_moratorium, severity 4, in_force, Auglaize County) |
| Logan, OH | closed | 54.0 | sabin:REC-0355 (ban, severity 4, in_force, Logan County) |
| Navajo, AZ | closed | 53.92 | sabin:S26R-6256 (ban_or_moratorium, severity 4, in_force, Navajo County) |
| Crawford, KS | closed | 53.21 | queue:q_c0783bb26d (moratorium, severity 4, in_force, Crawford County) |
| Lancaster, PA | closed | 53.0 | nrel:wind:4207121344 (moratorium, severity 4, unknown, East Lampeter Township) |
| Henry, IN | closed | 51.58 | sabin:REC-0093 (ban_or_moratorium, severity 4, in_force, Henry County) |
| Brown, KS | closed | 51.53 | mn:ks-brown-county-2026 (moratorium, severity 4, in_force, Brown County) |
| Mason, KY | closed | 51.05 | nrel:wind:21161 (setback, severity 3, unknown, Mason County) |
## Build-out

754 counties have at least one uncontested plant counted as an approval (1757 plants); for 375 of them it is the only evidence on record.


## Record against resemblance

1368 counties have a record. Of those in the top three resemblance deciles, 276 are open or regulated on their record; of those in the bottom three, 28 are closed or severe. These are the counties where the two scores disagree most.

