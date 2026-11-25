# County record score

Written by `scripts/county_record_score.py` from `config/county_record_score.json` (version 2026-11-20). Do not edit by hand.

**What the score is.** How restrictive a county is for wind, solar and battery storage, on one rubric, read from its own record: the restriction instruments placed in it, a listed move from no zoning to zoning, and the outcomes of its contested projects. A county with no record is scored on its resemblance score (`data/model/county_restriction_scores.csv`) as a prior. Internal: no page, county report or headline figure reads it.

## Counties by tier

| Tier | Counties | Meaning |
|---|---:|---|
| closed | 56 | Closed: a moratorium or ban in force, or rules that act as one, county-wide |
| severe | 271 | Severe: rules likely to block most projects |
| restrictive | 336 | Restrictive: material rules, or blocked projects |
| regulated | 743 | Regulated but open: rules in force, projects approved under them |
| open | 481 | Open: nothing restrictive on record |
| no_record | 1257 | No record and no negative check: scored on the profile prior alone |

## Reference counties

| County | Tier | Combined (U.S. percentile) | Record points | Instruments | Zoning | Blocked | Approval credit | Resemblance score (decile) | Top instrument |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| Nicholas, KY | closed | 43.15 (99.1) | 43.15 | 43.15 | 0.0 | 0 | 0.0 | 0.033 (1) | queue:q_ef439d5e2f (setback, severity 3, in_force, Nicholas County) |
| Cherokee, KS | closed | 57.3 (100.0) | 57.3 | 48.3 | 9.0 | 0 | 0.0 | 0.2505 (7) | queue:q_011039b3ee (moratorium, severity 4, in_force, Cherokee County) |
| Harris, TX | restrictive | 16.5 (83.6) | 16.5 | 15.0 | 0.0 | 5 | 7.5 | 0.2187 (7) | queue:q_bbb012a590-2 (setback, severity 3, in_force, Pasadena) |
| Linn, IA | restrictive | 14.88 (82.2) | 14.88 | 15.75 | 0.0 | 0 | 7.88 | 0.6005 (10) | queue:q_82dfad9133 (setback, severity 2, in_force, Linn County) |

## State preemption

Each rule in `state_preemption` caps the severity a local instrument counts at (1 where a state permit replaces local approval, 2 where statute caps local rules or a state body may set them aside), for the governments it binds. A size threshold is read against the median of the state's recent plants of that technology, or 100 MW where the state has fewer than 5. `tier_local` and `combined_local` are the score with no cap.

| Rule | Mechanism | Ceiling | Binds | Technology: threshold, state reference size | Counties capped | Points removed |
|---|---|---:|---|---|---:|---:|
| IL-local_preemption-1 | statutory_ceiling | 2 | county | solar: any size, 100.0 MW; wind: any size, 192.5 MW | 22 | 562.65 |
| IL-local_preemption-2 | statutory_ceiling | 2 | county | battery_storage: any size, 100 (fallback) MW | 2 | 48.77 |
| IL-local_preemption-3 | discretionary_override | 2 | county | solar: 50 MW, 100.0 MW; wind: 50 MW, 192.5 MW; battery_storage: 50 MW, 100 (fallback) MW | 23 | 586.28 |
| MD-local_preemption-1 | statutory_ceiling | 2 | all_local | solar: 1 MW, 45.0 MW | 5 | 69.5 |
| MD-local_preemption-2 | statutory_ceiling | 2 | all_local | battery_storage: any size, 100 (fallback) MW | 0 | 0 |
| WI-local_preemption-1 | replaces_local | 1 | all_local | solar: 100 MW, 100.0 MW; wind: 100 MW, 100 (fallback) MW | 27 | 362.71 |
| WI-local_preemption-2 | statutory_ceiling | 2 | all_local | solar: any size, 100.0 MW; wind: any size, 100 (fallback) MW | 0 | 0 |
| MA-local_preemption-1 | statutory_ceiling | 2 | all_local | solar: any size, 100 (fallback) MW | 0 | 0 |
| MA-local_preemption-2:large | replaces_local | 1 | all_local | solar: 25 MW, 100 (fallback) MW; wind: 25 MW, 100 (fallback) MW; battery_storage: 100 MWh, 100 (fallback) MW | 13 | 276.45 |
| MA-local_preemption-2:small | statutory_ceiling | 2 | all_local | solar: any size, 100 (fallback) MW; wind: any size, 100 (fallback) MW; battery_storage: any size, 100 (fallback) MW | 0 | 0 |
| FL-local_preemption-1 | replaces_local | 1 | all_local | solar: 75 MW, 74.5 MW | 0 | 0 |
| FL-local_preemption-2 | statutory_ceiling | 2 | county | solar: any size, 74.5 MW | 0 | 0 |
| MN-local_preemption-1 | replaces_local | 1 | all_local | solar: 50 MW, 50.0 MW; wind: 5 MW, 155.0 MW; battery_storage: 10 MW, 100 (fallback) MW | 57 | 1291.9 |
| IA-local_preemption-1 | discretionary_override | 2 | all_local | solar: 25 MW, 100.0 MW; battery_storage: 25 MWh, 100 (fallback) MW | 27 | 384.24 |
| MI-local_preemption-1 | replaces_local | 1 | all_local | solar: 50 MW, 100.0 MW; wind: 100 MW, 159.3 MW; battery_storage: 50 MW, 100 (fallback) MW | 65 | 1203.15 |
| OH-local_preemption-1 | replaces_local | 1 | non_county | solar: 50 MW, 120.0 MW; wind: 5 MW, 100 (fallback) MW | 2 | 21.26 |
| RI-local_preemption-1 | replaces_local | 1 | all_local | solar: 40 MW, 100 (fallback) MW; wind: 40 MW, 100 (fallback) MW | 4 | 51.82 |
| CT-local_preemption-1 | replaces_local | 1 | all_local | solar: 1 MW, 100 (fallback) MW; wind: 1 MW, 100 (fallback) MW; battery_storage: any size, 100 (fallback) MW | 6 | 101.62 |
| VT-local_preemption-1 | replaces_local | 1 | all_local | solar: any size, 100 (fallback) MW; wind: any size, 100 (fallback) MW; battery_storage: any size, 100 (fallback) MW | 12 | 291.0 |
| CA-local_preemption-1 | replaces_local | 1 | all_local | solar: 50 MW, 153.5 MW; wind: 50 MW, 58.85 MW; battery_storage: 200 MWh, 115.8 MW | 30 | 606.43 |
| WA-local_preemption-1 | discretionary_override | 2 | all_local | solar: any size, 100 (fallback) MW; wind: any size, 100 (fallback) MW; battery_storage: any size, 100 (fallback) MW | 9 | 181.12 |
| NY-local_preemption-1 | discretionary_override | 2 | all_local | solar: 25 MW, 20.0 MW; wind: 25 MW, 118.6 MW | 47 | 252.48 |
| NM-local_preemption-1 | discretionary_override | 2 | all_local | solar: 300 MW, 170.0 MW; wind: 300 MW, 315.6 MW | 2 | 19.8 |
| SC-local_preemption-1 | discretionary_override | 2 | all_local | solar: 75 MW, 74.95 MW; wind: 75 MW, 100 (fallback) MW | 3 | 48.6 |
| OR-local_preemption-1 | replaces_local | 1 | all_local | wind: 300 MW, 100 (fallback) MW | 0 | 0 |

346 counties have record points removed and 69 without a record have their prior lowered by the cap; 270 change tier.

| Tier with no cap | closed | severe | restrictive | regulated | open | no_record |
|---|---:|---:|---:|---:|---:|---:|
| closed | 56 | 10 | 9 | 16 | 2 | 0 |
| severe | 0 | 261 | 43 | 69 | 4 | 0 |
| restrictive | 0 | 0 | 284 | 64 | 14 | 0 |
| regulated | 0 | 0 | 0 | 594 | 39 | 0 |
| open | 0 | 0 | 0 | 0 | 422 | 0 |
| no_record | 0 | 0 | 0 | 0 | 0 | 1257 |

Rows are the tier with no cap, columns the tier scored.

### Largest reductions

| County | Tier (no cap to scored) | Combined (no cap to scored) | Record points removed | Rules |
|---|---|---|---:|---|
| Monroe, MI | closed to regulated | 52.55 to 5.13 | 58.76 | MI-local_preemption-1 |
| Pine, MN | closed to regulated | 48.92 to 4.4 | 44.52 | MN-local_preemption-1 |
| Aitkin, MN | closed to regulated | 48.74 to 4.5 | 54.52 | MN-local_preemption-1 |
| Yolo, CA | closed to regulated | 46.67 to 4.5 | 54.52 | CA-local_preemption-1 |
| Freeborn, MN | closed to regulated | 45.56 to 4.5 | 50.28 | MN-local_preemption-1 |
| Kalamazoo, MI | closed to regulated | 44.51 to 4.22 | 47.51 | MI-local_preemption-1 |
| Berrien, MI | closed to regulated | 46.38 to 6.7 | 39.68 | MI-local_preemption-1 |
| Pope, MN | closed to regulated | 44.12 to 4.5 | 49.65 | MN-local_preemption-1 |
| Genesee, MI | closed to regulated | 47.42 to 7.92 | 39.5 | MI-local_preemption-1 |
| Chisago, MN | closed to open | 41.99 to 2.85 | 47.72 | MN-local_preemption-1 |
| Marathon, WI | closed to regulated | 48.59 to 9.96 | 51.5 | WI-local_preemption-1 |
| Wabasha, MN | closed to regulated | 42.53 to 4.5 | 47.52 | MN-local_preemption-1 |
| Mower, MN | closed to open | 40.09 to 2.85 | 45.18 | MN-local_preemption-1 |
| Chautauqua, NY | closed to severe | 65.0 to 28.0 | 37.0 | NY-local_preemption-1 |
| Orleans, VT | closed to restrictive | 59.4 to 22.43 | 36.97 | VT-local_preemption-1 |
| Carlton, MN | closed to regulated | 41.24 to 4.5 | 44.52 | MN-local_preemption-1 |
| Huron, MI | closed to restrictive | 53.55 to 17.06 | 42.45 | MI-local_preemption-1 |
| Allegan, MI | closed to regulated | 42.6 to 6.6 | 41.8 | MI-local_preemption-1 |
| Stevens, MN | closed to regulated | 40.41 to 4.5 | 44.7 | MN-local_preemption-1 |
| St. Clair, MI | closed to regulated | 43.09 to 7.61 | 41.1 | MI-local_preemption-1 |

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
| 1 | 315 | 0.0 to 0.99 | -3.542 to -1.281 |
| 2 | 314 | 0.99 to 2.2 | -1.279 to -0.842 |
| 3 | 315 | 2.2 to 3.0 | -0.841 to -0.524 |
| 4 | 314 | 3.0 to 4.0 | -0.523 to -0.253 |
| 5 | 314 | 4.0 to 5.74 | -0.253 to 0.0 |
| 6 | 315 | 5.74 to 7.56 | 0.0 to 0.253 |
| 7 | 314 | 7.56 to 9.91 | 0.254 to 0.524 |
| 8 | 315 | 9.91 to 14.35 | 0.525 to 0.842 |
| 9 | 314 | 14.35 to 25.5 | 0.843 to 1.281 |
| 10 | 314 | 25.5 to 57.3 | 1.283 to 3.542 |

## Highest combined scores

| County | Tier | Combined | Top instrument |
|---|---|---:|---|
| Cherokee, KS | closed | 57.3 | queue:q_011039b3ee (moratorium, severity 4, in_force, Cherokee County) |
| Mason, KY | closed | 55.55 | nrel:wind:21161 (setback, severity 3, in_force, Mason County) |
| Allen, OH | closed | 54.0 | sabin:REC-0340 (ban, severity 4, in_force, Allen County) |
| Auglaize, OH | closed | 54.0 | sabin:REC-0341 (ban_or_moratorium, severity 4, in_force, Auglaize County) |
| Logan, OH | closed | 54.0 | sabin:REC-0355 (ban, severity 4, in_force, Logan County) |
| Lancaster, PA | closed | 53.0 | nrel:wind:4207121344 (moratorium, severity 4, in_force, East Lampeter Township) |
| Brown, KS | closed | 51.6 | mn:ks-brown-county-2026 (moratorium, severity 4, in_force, Brown County) |
| Lackawanna, PA | closed | 50.0 | nrel:wind:4206971872 (ban, severity 4, unknown, South Abington Township) |
| Fulton, NY | closed | 48.13 | sabin:S26R-5738 (ban, severity 4, in_force, Fulton County) |
| Miami, IN | closed | 48.1 | sabin:REC-0100 (setback, severity 3, in_force, Miami County) |
| Hertford, NC | closed | 47.2 | sabin:S26R-5658 (ban_or_moratorium, severity 4, in_force, Hertford County) |
| Crawford, KS | closed | 47.04 | queue:q_c0783bb26d (moratorium, severity 4, in_force, Crawford County) |
| Knox, NE | closed | 47.03 | sabin:S26R-5782 (ban, severity 4, in_force, Knox County) |
| Madison, IN | closed | 46.38 | sabin:S26R-6134 (setback, severity 3, in_force, Madison County) |
| Greene, OH | closed | 45.54 | sabin:REC-0350 (ban, severity 4, in_force, Greene County) |
## Build-out

756 counties have at least one uncontested plant counted as an approval (1761 plants); for 375 of them it is the only evidence on record.


## Record against resemblance

1364 counties have a record. Of those in the top three resemblance deciles, 309 are open or regulated on their record; of those in the bottom three, 21 are closed or severe. These are the counties where the two scores disagree most.

