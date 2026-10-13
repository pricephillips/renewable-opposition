# County check: 20 counties in nearly finished states (2026-10-13)

The first pass under `docs/COUNTY_CHECK.md`. It took the 20 unexamined
counties in DC and the nine states closest to having every county examined
(CT, DE, HI, MD, NV, NH, NY, VT, WY). Six drafting agents
(`agent:county-checker-A` to `-F`) ran the procedure; separate reviewing
agents (`agent:county-reviewer-*`) re-opened every document under
`docs/AGENT_REVIEW.md`. A row that a review contradicted went back to its
drafter and got a fresh review by another agent before it was recorded.

## Results so far

| County | FIPS | Result |
|---|---|---|
| District of Columbia | 11001 | Restriction: 11-U DCMR 201.1(c) (Z.C. Order No. 19-04, adopted 2019-07-29) allows ground-mounted community solar as of right in R zones only at 20 ft or lower, 1.5 acres of panels or less, and 40 ft from adjacent R, RF or RA-1 property; otherwise a BZA special exception. Confirmed. Filed as a county-equivalent so it places in 11001. |
| Bronx and New York (Manhattan), NY | 36005, 36061 | Restriction: New York City Zoning Resolution 22-142 caps energy infrastructure equipment (principal-use solar, wind and battery storage) at 10,000 sq ft of lot area in every Residence District; larger sites need a BZA special permit (ZR 73-147). Confirmed. One citywide instrument, placed in the city's five counties by a place override. The FDNY battery clearance (3 RCNY 608-01) is a fire code and is not counted. |
| Prince George's, MD | 24033 | Two restrictions from Zoning Ordinance Subtitle 27 (CB-013-2018, enacted 2018-10-23). Solar: 65 percent coverage and 20 ft height for large-scale systems, prohibited in ROS and six of eight residential zones. Since 2025-07-01, Maryland Public Utilities 7-218 overrides these limits for most ground-mounted solar over 1 MW that sells wholesale or is community solar. Wind: setback of at least tower-plus-blade height from property lines, 450 ft, 55 dBA. The solar row was corrected twice (zone list, then the 7-218 sentence) and confirmed on its third review; the wind row was confirmed. |
| New Castle, DE | 10003 | Restriction: UDC 40.03.337 (Ord. 17-044, 2017-10-10): large-scale solar 50 ft from property lines and 150 ft from dwellings, 1,000 acres in the SR district, barred in several districts. Confirmed after a wording fix. |
| Belknap, NH | 33001 | Restriction: Belmont Zoning Ordinance, Article 5 Table 1: commercial solar not permitted in three districts, special exception in Rural. It reaches grid-scale solar under the Commercial Solar definition adopted 2026-03-10. Confirmed after a page-citation fix. |
| Strafford, NH | 33017 | Restriction: Durham Solar Energy Systems Ordinance (2023-02-06): utility-scale ground-mounted solar barred in most districts and in the wetland and shoreland overlays, 25 ft height. Confirmed. |
| Carroll, NH | 33003 | Restriction: Moultonborough Zoning Ordinance Art. 10.2: larger solar classes prohibited in named districts, a 150-acre cap on stations over 30 MW, lot-line setbacks. Confirmed. |
| Greater Bridgeport, CT | 09120 | Lead. Monroe and Trumbull (opened) and Fairfield (a 2021 copy) have no restriction on principal-use facilities; Stratford was seen only on a third-party copy, and its use table keeps "power plants" 500 ft from residential and commercial districts without defining them. Bridgeport's and Easton's regulations were not found, and no minutes or Siting Council dockets were searched. |
| Lamoille, VT | 50015 | Lead. Every bylaw opened (Stowe, Wolcott, Morristown, Hyde Park, Elmore, Johnson) exempts state-permitted (30 V.S.A. 248) facilities and requires only screening. Four towns, the current Morristown bylaws, all minutes and the PUC docket were not covered. |
| Eureka, NV | 32011 | Negative check, grade A: the pilot's first. The county has no zoning and no incorporated town (its 2026 hazard plan, 2010 master plan, 2024-12-03 minutes and the District Attorney at the 2026-06-18 meeting say so). Its code titles, all 138 commission minutes from 2022-01 to 2026-09 (five scanned ones read by OCR), the 2026 agenda packets and the PUCN dockets naming the county hold no restriction. A 2023-02-21 resolution saying the county does not support large wind projects is policy only. Only two Planning Commission minutes are posted; the commission is advisory and reviews land divisions, so a siting rule would come through the commissioners' records, which were covered. Accepted on review. |
| Hawaii, HI | 15001 | Lead. Zoning Code 25-4-22(e) (Ord. 96-160) lets wind machines exceed district height limits only with a property-line setback equal to their height, and a 1999 variance shows it applied to the Kamaoa Wind Farm. The reviewer could not open the current Chapter 25 (the county site returns 403) to confirm the section is unchanged, so it was not recorded (unverifiable). Opening the current code in a browser would settle it. |
| Kauai, HI | 15007 | Lead. The zoning ordinance is only on eCode360. A 2026 Planning Commission decision quotes a 10 percent or 20 acre limit on solar on B and C soils, which the reviewer read as a by-right tier copying state law, not a county cap. |
| Kalawao, HI | 15005 | Lead. No county government and no zoning: under HRS 326-34 the state Department of Health administers it. The procedure assumes a local government that zones, so it has no way to examine this county; see below. |
| Big Horn, Carbon, Johnson, Teton, Washakie and Weston, WY | 56003, 56007, 56019, 56039, 56043, 56045 | Drafting in progress. |

The eight confirmed instruments are in `data/review/queue.csv` as
`confirmed`, source `county_check_2026-10-13`, with the drafter's and the
reviewer's notes in `reviewer_notes`. The data build promotes them; each
publishes as `verified`, because the instrument itself was opened.

## Rules settled during the pass

- Rules written only for small, accessory or on-site systems are not
  restrictions (Laconia's and Dover's small wind sections, Moultonborough's
  Art. 10.1, Dover's accessory solar height): section 3, scale rule.
- Fire, building and electrical codes are not restrictions (the FDNY battery
  clearance): section 3, land-use rule.
- One restriction examines a county; a negative check needs every
  government that zones.

## Open question

Kalawao County has no local government, so no check under section 1 can
cover it. It could be examined by searching the bodies that do govern its
land (the Land Use Commission, DLNR, Hawaiian Home Lands, the National Park
Service), or left outside the coverage universe as Puerto Rico is. That is a
maintainer's decision; until then it stays on the worklist.

## What blocked the pass

- eCode360 and American Legal return 403 to every tool available here; most
  of Conway's, Wolfeboro's, Dover's, Stratford's and Kauai's codes are only
  there. Firecrawl had no credits.
- The Internet Archive reset or refused connections.
- Many towns post scanned minutes, which need OCR.

## Next pass

Open the eCode360-only codes from a browser (Conway, Wolfeboro, Dover,
Stratford, Kauai), search the Lamoille towns' minutes and the Vermont PUC
docket, and find Bridgeport's and Easton's zoning regulations.
