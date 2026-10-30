# County record score

**Status:** October 21, 2026; state preemption (rubric item 7) added October 30, 2026. Internal, like the county restriction model: no page, county report or headline figure reads it until Price decides otherwise. Built by `scripts/county_record_score.py` from the rubric in `config/county_record_score.json`; results in `data/model/county_record_scores.csv` and `data/model/county_record_report.md`, refreshed each month with the model (`model-inputs.yml`) or on demand.

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

1. **Instruments.** Each restriction instrument (rows for different technologies under one law are one instrument) scores its severity points (severity 4: 40, 3: 30, 2: 12, 1: 4), times its currency (in force 1, status unknown 0.85, pending 0.3), times its reach (county-wide 1, a city, town, township or village 0.5), times its breadth (1, plus 0.1 for each technology beyond the first). The county's largest instrument counts in full and the rest at a quarter, up to 70. An instrument that also covers data centers or other uses counts in full, as in `scripts/county_typology.py`: a moratorium on wind, solar and data centers is a moratorium on wind and solar.
2. **Zoning transitions.** This rule applies in 19 states where three things hold: a county may have no zoning at all, the county is the body that zones unincorporated land, and no statute gives an unzoned county a siting permit or siting power over wind or solar outside zoning (general home-rule or ordinance powers, which Kansas counties also hold, do not count) (`config/county_zoning_authority.json`, explained in `docs/county_zoning_authority.md`; Kansas is one, K.S.A. 12-741). In those states a county that moves from no zoning to zoning while projects are proposed counts as a county-wide severity 3 instrument, from when drafting began until three years after the code is adopted. The counties are listed by hand in `config/county_record_score.json`, with sources. As of October 23, 2026, all are in Kansas: Bourbon, Brown, Cherokee, Crawford, Kiowa, Labette and Nemaha. A listing counts as a verified instrument once a later reading of the county's own minutes, resolutions or plans confirms it (`second_reading` in the config): Bourbon, Brown, Cherokee, Labette and Nemaha as of October 23, 2026. The other listings count as unverified.
3. **Contested projects.** A blocked project adds 10 points (5 if its outcome is recorded but unconfirmed), up to 25. An approved project takes off 10 (5 unconfirmed), up to 25, and at most half the instrument points, so approvals mark a county as open under its rules without erasing them. Approvals never take a county below the points of a severity 4 county-wide instrument in force: a moratorium in force today outweighs earlier approvals.
   **Plants built without a recorded fight** count as approvals too, at 3 points each, inside the same limits. The record holds only projects that drew opposition, so without them a county that approved projects quietly looks the same as one never asked. They come from EIA-860M (`data/reference/facilities.csv`): solar, wind or storage plants of 20 MW or more, operating or under construction, online (or due online) in 2020 or later and no earlier than the county's latest instrument in force. A county's contested projects that advanced are assumed to be among its plants, so only the plants beyond that number count.
4. **Evidence and the prior.** Combined score = weight x record points + (1 - weight) x profile points. The weight is 1 for a county with a verified instrument or a confirmed outcome, 0.75 for an unverified record, 0.9 for a negative check (a reviewed record that someone searched the county's codes, minutes and news for a restriction and found none), 0.6 for a county whose only evidence is build-out, 0.6 for a county with no record in a state whose counties have no general zoning power (Texas, Tex. Loc. Gov't Code § 211.003, and Alabama, Ala. Code § 11-3A-2(f): the county government cannot restrict, though its cities can; the 17 Alabama counties with a local act on zoning, planning or wind permits, listed in `no_county_zoning.except_counties`, are scored as in any other state), and 0 for a county with no record. Profile points are the mean record points of all counties in the same decile of the resemblance score (a county with no record counts as zero), so a county not yet examined (examined: it has a published record or a reviewed negative check) takes what the record shows for counties in its decile. Because most counties have never been examined, that is a floor.
5. **Tiers.** Closed (40 or more): a moratorium or ban in force county-wide, or rules that act as one. Severe (25 to 40). Restrictive (12 to 25). Regulated but open (3 to 12). Open (under 3). A county with no record and no negative check is listed as `no_record`.
6. **Normal score and deciles.** The combined score is skewed: most counties have no record and take one of ten prior values, so cutting it at its own deciles gives groups of very different sizes (on the data of October 27, 2026, from 175 to 394 counties). Two columns order the counties instead. `combined_decile` ranks every U.S. county by combined score, breaks ties by resemblance score and then by FIPS code, and splits the ranking into ten groups of equal size (314 or 315 counties). `combined_normal` turns the same rank into a standard normal score (mean 0, standard deviation 1; Blom's formula, rank minus 3/8 over the number of counties plus 1/4), so a histogram of it is a bell curve. Both only order counties: the points and the tiers in item 5 are unchanged, and a county's decile says where it ranks, not how much its score differs from the next decile's.
7. **State preemption.** Some state laws limit how far a local rule can stop a project. Each such law in `data/processed/state_policies.csv` (every row verified against the statute) is a rule in `state_preemption`, and each rule caps the severity a local instrument counts at, technology by technology, before the instrument's points are computed. The cap follows the legal mechanism. It is severity 1 where a state permit replaces local approval, and severity 2 where statute caps local rules at the state's own standards or a state body may set a local rule aside on a finding. Each rule also names the governments it binds and the smallest project it reaches; the score is read for a 100 MW project (`reference_project_mw`). The prior of a county with no record is capped at the same level when a rule reaches county rules on solar, wind and battery storage. The instruments keep their own severity in the record; only the score reads the cap. `combined_local` and `tier_local` give each county's score with no cap.

## The four case-study counties

From `data/model/county_record_report.md`, on the data of October 22, 2026. The U.S. percentile is the share of U.S. counties with a lower combined score, plus half the share tied with it.

| County | Tier | Combined score (U.S. percentile) | What drives it |
|---|---|---|---|
| Cherokee, KS | closed | 64.5 (99.6) | the moratorium in force (48), the wind setback and the zoning transition |
| Nicholas, KY | closed | 57.5 (99.3) | the solar moratorium (40), the wind moratorium and the solar setback |
| Harris, TX | restrictive | 12.5 (67.3) | Pasadena's severity 3 storage rule at city weight (15), one blocked and two approved projects, all unconfirmed |
| Linn, IA | regulated | 7.88 (50.4) | instrument points of 15.75 (the severity 2 ordinance, 13.2, and a quarter of an NREL-compiled wind ordinance of unknown status, 2.55), halved by two confirmed approvals |

Cherokee's moratorium runs through March 31, 2027. Without it, the rubric gives Cherokee 43.5 from the zoning transition and the wind setback, in the closed tier; without the zoning transition as well, it gives 30, in the severe tier.

## State preemption

Added October 30, 2026, at Jared Dubnow's request: a county whose own rules score as restrictive should not score as if those rules decide every project when state law overrides them, as Illinois law does.

**The rules.** The 25 rules in `config/county_record_score.json` cover 18 states, and each cites its `state_policies` row:

| Mechanism | Ceiling | Where (for a 100 MW project) |
|---|---:|---|
| `replaces_local`: a state permit stands in for local approval | 1 | Minnesota, Michigan, Wisconsin (100 MW and up), Massachusetts (from March 1, 2026), Connecticut, Vermont, Rhode Island, Florida solar (75 MW and up), California (if the developer opts in, until June 30, 2030), Ohio townships and cities |
| `statutory_ceiling`: statute caps local rules or bars local bans | 2 | Illinois counties, Maryland, Wisconsin, Massachusetts, Florida agricultural districts |
| `discretionary_override`: a state body may set a local rule aside | 2 | New York, Washington, South Carolina, Iowa solar and storage, Illinois counties (the Commerce Commission certificate) |

Most of the effect turns on how three states' laws read:

- **Illinois.** 55 ILCS 5/5-12020 binds counties ("A county may not..."): no county rule stricter than the statute, no ban "permanently or temporarily" in agricultural or industrial districts, and a compliant application "shall be approved." It does not bind cities, so a city ban keeps its own severity.
- **Ohio.** The Power Siting Board's certificate preempts township and city rules, but under SB 52 county commissioners may bar large wind and solar from all or part of the county, so county instruments are not capped.
- **Iowa.** The statute lets a state certificate override county zoning, but the board counts a wind facility by the turbines on one gathering line (*Mathis v. Iowa Utilities Board*, 2019), so most wind farms fall below the 25 MW threshold and stay with the county; wind is left out. Solar and storage take the discretionary ceiling because Cerro Gordo County is suing over a certificate it says set aside its zoning.

Six preemption rows were read and left out, each with its reason in `not_applied`: Colorado (utilities only), Indiana (limits a moratorium's length, not its reach while in force), Mississippi (decommissioning terms only), New Jersey (industrial and commercial districts, not agricultural land), Nevada (an owner's own system) and Ohio's SB 52 (the reverse of preemption). A test fails if a verified preemption row is in neither list.

**The effect.** On the data of October 30, 2026, 354 counties have record points removed and 108 counties with no record have their prior capped; 303 counties change tier. Counties in the 32 states and the District of Columbia with no rule are unchanged, and no county scores higher. Of the 8 Illinois counties in the closed tier with no cap, 7 move to restrictive; Christian moves to severe.

| County | Tier and combined score with no cap | With the cap | What remains |
|---|---|---|---|
| Christian, IL | closed, 55.38 | severe, 39.55 | the City of Assumption's solar and wind bans, at city weight (20 each), are not preempted; the five county instruments count at severity 2 |
| Shelby, IL | severe, 39.54 | restrictive, 17.94 | the 2026 county ordinance (severity 3, capped at 2) and the pending moratorium |

**Decisions for Price.** Two choices are open: the 100 MW reference project, and whether the cap should also reach blocked projects (it does not now; a denial on record still adds points).

## Limits

- The rubric is a set of rules, not a fitted model. Its weights are set by hand, not estimated from outcomes, because too few projects have a confirmed outcome and a decision date to fit them (`docs/predictive_foundation_design.md`, section 7).
- Build-out shows that plants were built, not how the county decided them; a plant in a city or on land the county does not zone counts the same as one the county approved.
- It reads the published record, so it inherits the record's gaps. A county with no record is scored on its profile, and a county whose instruments come only from a compiled tracker leans partly on that profile too.
- Instruments with an unknown status (every NREL ordinance until a reviewer settles it) count at 0.85. A seeded random sample of 60, read by two readers each on October 21, 2026, found 40 of the 47 it settled still in force (89 percent weighted by group size); four more records matched no adopted instrument, and counting them as not in force gives about 78 percent.
- The Kansas list was compiled from one research reading per county on October 21, 2026, and at that reading some counties could not be settled because their sites blocked automated access. Later readings on October 23, 2026 confirmed five of the seven listings once Cherokee's start date and Labette's adoption date were corrected and Brown's adoption date was given to the day. The later readings contradict the other two listings, which count as unverified. Part of Crawford has been zoned since 1967, and the county has not adopted its countywide zoning, so it is now listed as drafting. No document read names the technologies Kiowa's zoning would cover; its minutes tie the zoning work to data centers and underground gas storage, not to wind, solar or battery storage. The other 18 states where the transition rule applies have no counties listed yet.
- The state survey behind both zoning rules is one research reading per state, with a second for Alabama and Oklahoma. Oklahoma counties also lack general zoning power, but the 0.6 weight in item 4 is not applied there: at least six Oklahoma counties zone through routes in Title 19 of the state's statutes (Oklahoma, Tulsa, Wagoner, Rogers, Creek and Osage), and the list of the rest is incomplete.
- Lapsed instruments are not counted, so a county that paused and then reopened (Linn's 2022 to 2023 utility-scale solar moratorium) is scored on what is in force now.
