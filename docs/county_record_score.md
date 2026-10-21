# County record score

**Status:** October 21, 2026. Internal, like the county restriction model: no page, county report or headline figure reads it until Price decides otherwise. Built by `scripts/county_record_score.py` from the rubric in `config/county_record_score.json`; results in `data/model/county_record_scores.csv` and `data/model/county_record_report.md`, refreshed each month with the model (`model-inputs.yml`) or on demand.

## Why a second score

The October 16 case studies (`deliverables/case_study_templates/renewables_2026-10-16/`) carried the county restriction model's score: a resemblance score (how closely a county's population, income, interconnection queue, operating wind and neighbors match the counties with a severe restriction on record, meaning severity 3 or 4). Severity is a score from one to four: one for procedural friction, two for a material burden, three for a likely de facto ban, four for an explicit moratorium or ban. By design the resemblance score never reads the county's own restriction instruments (local or state laws that materially constrain wind, solar or battery storage; one instrument may cover several technologies and is counted once) or contested projects (`config/county_model_registration.json`, `not_used`). It put Linn County, IA in decile 8 and Nicholas County, KY in decile 1 (a decile is one tenth of U.S. counties ranked by resemblance score, decile 1 the lowest), while their records read the other way:

| County | Resemblance score (decile) | Record |
|---|---|---|
| Nicholas, KY | 0.05 (1) | a solar moratorium, a wind moratorium and a 2,000-foot solar setback in force, all verified |
| Cherokee, KS | 0.14 (5) | a moratorium on solar, wind and storage in force, a 5,250-foot wind setback, and a first zoning code being drafted |
| Linn, IA | 0.39 (8) | a severity 2 solar and storage ordinance; two contested solar projects approved (confirmed) |

The October review of the four reports read Nicholas and Cherokee as much less friendly than Linn, and found that the platform holds the right data but does not yet compare counties on it. The record score compares every county on one rubric built from that data. The resemblance score stays as a prior (the starting value for a county with no record; see rubric item 4).

## The rubric

Every weight is in `config/county_record_score.json`.

1. **Instruments.** Each restriction instrument (rows for different technologies under one law are one instrument) scores its severity points (severity 4: 40, 3: 30, 2: 12, 1: 4), times its currency (in force 1, status unknown 0.5, pending 0.3), times its reach (county-wide 1, a city, town, township or village 0.5), times its breadth (1, plus 0.1 for each technology beyond the first). The county's largest instrument counts in full and the rest at a quarter, up to 70. An instrument that also covers data centers or other uses counts in full, as in `scripts/county_typology.py`: a moratorium on wind, solar and data centers is a moratorium on wind and solar.
2. **Zoning transitions.** In Kansas a county without zoning issues no permit for a wind or solar project, and no state body sites them (`state_policies.csv`, K.S.A. 12-741). A county that moves from no zoning to zoning while projects are proposed counts as a county-wide severity 3 instrument, from when drafting began until three years after the code is adopted. The counties are listed by hand in the config, with sources; Cherokee is the first. Other states can be added to the list where the same holds.
3. **Contested projects.** A blocked project adds 10 points (5 if its outcome is recorded but unconfirmed), up to 25. An approved project takes off 10 (5 unconfirmed), up to 25, and at most half the instrument points, so approvals mark a county as open under its rules without erasing them. Approvals never take a county below the points of a severity 4 county-wide instrument in force: a moratorium in force today outweighs earlier approvals.
4. **Evidence and the prior.** Combined score = weight x record points + (1 - weight) x profile points. The weight is 1 for a county with a verified instrument or a confirmed outcome, 0.75 for an unverified record, 0.9 for a negative check (a reviewed record that someone searched the county's codes, minutes and news for a restriction and found none) and 0 for a county with no record. Profile points are the mean record points of all counties in the same decile of the resemblance score (a county with no record counts as zero), so a county not yet examined (examined: it has a published record or a reviewed negative check) takes what the record shows for counties in its decile. Because most counties have never been examined, that is a floor.
5. **Tiers.** Closed (40 or more): a moratorium or ban in force county-wide, or rules that act as one. Severe (25 to 40). Restrictive (12 to 25). Regulated but open (3 to 12). Open (under 3). A county with no record and no negative check is listed as `no_record`.

## The four case-study counties

From `data/model/county_record_report.md`, on the data of October 21, 2026. The U.S. percentile is the share of U.S. counties with a lower combined score, plus half the share tied with it.

| County | Tier | Combined score (U.S. percentile) | What drives it |
|---|---|---|---|
| Cherokee, KS | closed | 64.5 (99.8) | the moratorium in force (48), the wind setback and the zoning transition |
| Nicholas, KY | closed | 57.5 (99.5) | the solar moratorium (40), the wind moratorium and the solar setback |
| Harris, TX | restrictive | 12.5 (68.0) | Pasadena's severity 3 storage rule at city weight (15), one blocked and two approved projects, all unconfirmed |
| Linn, IA | regulated | 7.35 (49.1) | instrument points of 14.7 (the severity 2 ordinance, 13.2, and a quarter of an NREL-compiled wind ordinance of unknown status, 1.5), halved by two confirmed approvals |

Cherokee's moratorium runs through March 31, 2027. Without it, the rubric gives Cherokee 43.5 from the zoning transition and the wind setback, in the closed tier; without the zoning transition as well, it gives 30, in the severe tier.

## Limits

- The rubric is a set of rules, not a fitted model. Its weights are set by hand, not estimated from outcomes, because too few projects have a confirmed outcome and a decision date to fit them (`docs/predictive_foundation_design.md`, section 7).
- It reads the published record, so it inherits the record's gaps. A county with no record is scored on its profile, and a county whose instruments come only from a compiled tracker leans partly on that profile too.
- Instruments with an unknown status (every NREL ordinance until a reviewer settles it) count at half.
- Only one zoning transition is listed so far. Finding the others in Kansas, and in any state where the same holds, needs a county-by-county check.
- Lapsed instruments are not counted, so a county that paused and then reopened (Linn's 2022 to 2023 utility-scale solar moratorium) is scored on what is in force now.
