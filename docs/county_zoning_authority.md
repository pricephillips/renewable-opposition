# County zoning authority by state

**Status:** October 23, 2026. The record behind two rules of the county record score (`docs/county_record_score.md`): which states' counties may have no zoning at all, and which states' counties have no general zoning power. The codes, citations and rule flags are in `config/county_zoning_authority.json`; `tests/test_county_record_score.py` checks that `config/county_record_score.json` follows them.

## Why it matters

The record score reads each county's own record. Two kinds of county need more than that record:

- **A county that cannot zone.** Where the county government has no general zoning power, an empty record is evidence in itself: the county cannot adopt a siting rule for its unincorporated land, though its cities can inside their limits. The `no_county_zoning` rule weighs such a county's empty record at 0.6 against its profile prior (item 4 of `docs/county_record_score.md`) instead of scoring it on the prior alone.
- **A county moving from no zoning to zoning.** Where a county may have no zoning, adopting a first zoning code while wind or solar projects are proposed sets up the means to restrict them. The `zoning_transition` rule counts that move as a county-wide severity 3 instrument. Before this survey it covered Kansas only.

## How the states were read

Each state had one research reading on October 23, 2026, from the state's own law (statutes, constitutions, and attorney general or state agency publications) where those could be opened; Limits lists the exceptions. Each reading records the citations it opened. Alabama and Oklahoma, the two states where a rule depended on the answer, had a second reading by a different researcher who was given only the question.

Codes for county zoning power:

- **general:** every county zones unincorporated land, or must.
- **optional:** counties may adopt zoning but need not.
- **limited:** no general power; only named counties (by local act) or named subjects.
- **no county land use role:** towns, townships, cities or the state zone all land.

The zoning transition rule applies where three things hold: counties may stay unzoned, the county is the body that zones unincorporated land, and no statute gives an unzoned county a siting permit or siting power over wind or solar outside zoning (general home-rule or ordinance powers, which Kansas counties also hold, do not count). A state siting body may still review large plants there; the rule turns on what the county can do.

## The states

| State | County zoning power | Counties may stay unzoned | Zoning transition rule | First citation |
|---|---|---|---|---|
| AK | general | unknown | no: counties must zone, or hold general zoning power with no unzoned counties found | [Alaska Const. art. X, sec. 6](https://ltgov.alaska.gov/information/alaskas-constitution/) |
| AL | limited | yes | no: counties have no general zoning power (see no_county_zoning) | [Ala. Code 11-3A-2(f)](https://alison.legislature.state.al.us/code-of-alabama?section=11-3A-2) |
| AR | optional | yes | applies | [A.C.A. 14-17-209(a)](https://case-law.vlex.com/vid/bolen-v-wash-cnty-893732211) |
| AZ | optional | yes | applies | [A.R.S. 11-802(A)](https://www.azleg.gov/ars/11/00802.htm) |
| CA | general | unknown | no: counties must zone, or hold general zoning power with no unzoned counties found | [Gov. Code 65300](https://lci.ca.gov/wp-content/uploads/OPR_C1_final.pdf) |
| CO | optional | yes | no: a county may require its own permit for power plants under its 1041 powers (C.R.S. 24-65.1-203) | [C.R.S. 30-28-102](https://leg.colorado.gov/sites/default/files/images/olls/crs2024-title-30.pdf) |
| CT | no county land use role | unknown | no: towns, cities or the state zone all land; counties have no land use role | [Connecticut Secretary of the State, State Register and Manual, Section VI: Counties](https://portal.ct.gov/SOTS/Register-Manual/Section-VI/Counties---Table-of-Contents) |
| DE | general | no | no: counties must zone, or hold general zoning power with no unzoned counties found | [9 Del. C. 2601(a)](https://delcode.delaware.gov/title9/c026/sc01/index.html) |
| FL | general | no | no: counties must zone, or hold general zoning power with no unzoned counties found | [Fla. Stat. 125.01(1)(h)](https://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0100-0199/0125/Sections/0125.01.html) |
| GA | optional | yes | applies | [Ga. Const. art. IX, sec. II, para. IV](https://statecourtreport.org/sites/default/files/2025-10/supreme_court_of_georgia-opinion.pdf) |
| HI | general | no | no: counties must zone, or hold general zoning power with no unzoned counties found | [HRS 46-4(a)](https://data.capitol.hawaii.gov/hrscurrent/Vol02_Ch0046-0115/HRS0046/HRS_0046-0004.htm) |
| IA | optional | yes | applies | [Iowa Code 335.1](https://www.legis.iowa.gov/docs/code/335.1.pdf) |
| ID | general | no | no: counties must zone, or hold general zoning power with no unzoned counties found | [Idaho Code 67-6503](https://legislature.idaho.gov/statutesrules/idstat/Title67/T67CH65/SECT67-6503/) |
| IL | optional | yes | no: a county may regulate wind farm siting without county zoning (55 ILCS 5/5-12020) | [55 ILCS 5/5-12001](https://law.onecle.com/illinois/55ilcs5/5-12001.html) |
| IN | optional | yes | applies | [IC 36-7-4-801(a)](https://law.justia.com/codes/indiana/title-36/article-7/chapter-4/section-36-7-4-801) |
| KS | optional | yes | applies | [K.S.A. 12-741(a)](https://www.ksrevisor.org/statutes/chapters/ch12/012_007_0041.html) |
| KY | optional | yes | applies | [KRS 100.113](https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=26681) |
| LA | optional | yes | applies | [La. Const. art. VI, sec. 17](https://ag.louisiana.gov/opinion/download/25-0151) |
| MA | no county land use role | unknown | no: towns, cities or the state zone all land; counties have no land use role | [M.G.L. c. 40A, s. 1A](https://malegislature.gov/Laws/GeneralLaws/PartI/TitleVII/Chapter40A/Section1A) |
| MD | optional | yes | applies | [Md. Code, Land Use 4-102](https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText?article=glu&section=4-102&enactments=false) |
| ME | no county land use role | yes | no: towns, cities or the state zone all land; counties have no land use role | [30-A M.R.S. 4352](https://legislature.maine.gov/statutes/30-A/title30-Asec4352.html) |
| MI | optional | yes | no: towns or townships zone unincorporated land, alone or alongside the county | [MCL 125.3201(1)](https://www.legislature.mi.gov/Laws/MCL?objectName=mcl-125-3201) |
| MN | optional | yes | no: towns or townships zone unincorporated land, alone or alongside the county | [Minn. Stat. 394.21 subd. 1](https://www.revisor.mn.gov/statutes/cite/394.21) |
| MO | optional | yes | applies | [RSMo 64.090.1](https://revisor.mo.gov/main/OneSection.aspx?section=64.090) |
| MS | optional | yes | applies | [Miss. Code Ann. 17-1-3(1)](https://www.laurelms.com/wp-content/uploads/2023/07/APPENDIX-A-LOCAL-GOVERNMENT-PROVISIONS-TO-COUNTIES-AND-MUNICIPALITIES.pdf) |
| MT | optional | yes | applies | [MCA 76-2-201(1)](https://leg.mt.gov/bills/mca/title_0760/chapter_0020/part_0020/section_0010/0760-0020-0020-0010.html) |
| NC | optional | yes | applies | [G.S. 160D-702(a)](https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_160D/GS_160D-702.html) |
| ND | optional | yes | no: towns or townships zone unincorporated land, alone or alongside the county | [NDCC 11-33-01](https://ndlegis.gov/cencode/t11c33.pdf) |
| NE | optional | yes | no: towns or townships zone unincorporated land, alone or alongside the county | [Neb. Rev. Stat. 23-114(1)](https://nebraskalegislature.gov/laws/statutes.php?statute=23-114) |
| NH | limited | yes | no: counties zone only unincorporated places; towns zone everywhere else | [RSA 674:16, I](https://gc.nh.gov/rsa/html/LXIV/674/674-16.htm) |
| NJ | no county land use role | unknown | no: towns, cities or the state zone all land; counties have no land use role | [N.J.S.A. 40:55D-62a](https://codes.findlaw.com/nj/title-40-municipalities-and-counties/nj-st-sect-40-55d-62/) |
| NM | optional | yes | applies | [NMSA 1978, 3-21-1(A)](https://www.nmlegis.gov/Sessions/26%20Regular/bills/house/HB0138.PDF) |
| NV | general | unknown | no: counties must zone, or hold general zoning power with no unzoned counties found | [NRS 278.020(1)](https://www.leg.state.nv.us/NRS/NRS-278.html) |
| NY | no county land use role | yes | no: towns, cities or the state zone all land; counties have no land use role | [NY Town Law 261](https://www.nysenate.gov/legislation/laws/TWN/261) |
| OH | optional | yes | no: towns or townships zone unincorporated land, alone or alongside the county | [ORC 303.02](https://codes.ohio.gov/ohio-revised-code/section-303.02) |
| OK | limited | yes | no: counties have no general zoning power (see no_county_zoning) | [19 O.S. 863.2](https://www.oklegislature.gov/OK_Statutes/CompleteTitles/os19.rtf) |
| OR | general | no | no: counties must zone, or hold general zoning power with no unzoned counties found | [ORS 215.050(1)](https://www.oregonlegislature.gov/bills_laws/ors/ors215.html) |
| PA | optional | yes | no: towns or townships zone unincorporated land, alone or alongside the county | [MPC](https://www.palegis.us/statutes/unconsolidated/law-information/view-statute?txtType=PDF&SessYr=1968&ActNum=0247&SessInd=0) |
| RI | no county land use role | yes | no: towns, cities or the state zone all land; counties have no land use role | [R.I. Gen. Laws 45-24-27](https://webserver.rilegislature.gov/Statutes/TITLE45/45-24/45-24-27.htm) |
| SC | optional | yes | applies | [S.C. Code 6-29-720(A)](https://www.scstatehouse.gov/code/t06c029.php) |
| SD | optional | yes | applies | [SDCL 11-2-13](https://sdlegislature.gov/api/Statutes/11-2-13.html) |
| TN | optional | yes | applies | [T.C.A. 13-7-101(a)(1)](https://farmlandinfo.org/wp-content/uploads/sites/2/2019/09/TN_13-7-101_1.htm) |
| TX | limited | yes | no: counties have no general zoning power (see no_county_zoning) | [Tex. Loc. Gov't Code 211.003(a)](https://tcss.legis.texas.gov/resources/LG/htm/LG.211.htm) |
| UT | optional | unknown | no: the survey did not settle whether a Utah county may stay unzoned | [Utah Code 17-79-505(1)(a)](https://le.utah.gov/xcode/Title17/Chapter79/C17-79-S505_2025110620251206.html) |
| VA | optional | yes | applies | [Va. Code 15.2-2280](https://law.lis.virginia.gov/vacode/title15.2/chapter22/section15.2-2280/) |
| VT | no county land use role | unknown | no: towns, cities or the state zone all land; counties have no land use role | [24 V.S.A. 4303(12)](https://legislature.vermont.gov/statutes/section/24/117/04303) |
| WA | general | yes | no: counties must zone, or hold general zoning power with no unzoned counties found | [Wash. Const. art. XI, sec. 11](https://leg.wa.gov/media/o3fg0ey1/washington-state-constitution.pdf) |
| WI | optional | yes | no: towns or townships zone unincorporated land, alone or alongside the county | [UW-Madison Division of Extension, 'Types of Zoning'](https://fyi.extension.wisc.edu/landusetraining/?p=2660) |
| WV | optional | yes | applies | [W. Va. Code 8A-7-1(a)](https://code.wvlegislature.gov/8A-7-1/) |
| WY | optional | yes | no: every county must permit wind and solar facilities, zoned or not (W.S. 18-5-502) | [W.S. 18-5-201(a)](https://wyoleg.gov/statutes/compress/title18.pdf) |

## Notes on particular states

- **Alabama.** Counties have no general zoning power (Ala. Code § 11-3A-2(f)); some have it by local act. Both readings agree. The `no_county_zoning` rule now applies to Alabama, except in 17 counties listed in `config/county_record_score.json`: nine with zoning by local act that the second reading read (Baldwin, Jefferson, Shelby, Lee, Macon, Russell, Limestone, Mobile in two named areas, and Tuscaloosa subject to a 2002 referendum whose result was not found), five that the Local Laws Index lists with older acts not read (Barbour, Chambers, Houston, Dale, St. Clair), and three where a local act requires a permit for any wind system (Cherokee, DeKalb, Etowah). The second reading found no enacted Alabama local act on solar facilities through the 2026 regular session.
- **Oklahoma.** Counties also lack general zoning power, but zone under five Title 19 routes: a metropolitan area planning commission, a city-county commission, a county planning commission approved by countywide vote, counties of more than 500,000 people, and lake area commissions. Whether the county planning commission route carries zoning power is disputed. At least six counties zone through these routes (Oklahoma, Tulsa, Wagoner, Rogers, Creek, Osage), and the list of the rest is incomplete, so the `no_county_zoning` rule is not applied to Oklahoma.
- **Texas.** Confirmed: zoning belongs to municipalities (Tex. Loc. Gov't Code § 211.003), and Chapter 231 lets counties zone only named areas.
- **Kentucky.** Counties zone only through a planning unit, formed alone or jointly with their cities (KRS 100.113, 100.117). Under KRS 278.704(3) only counties with planning and zoning may set their own setbacks for merchant plants that need a Siting Board certificate; elsewhere the statutory setbacks apply. Fiscal courts can still adopt ordinances outside zoning (KRS 67.083(3)). Nicholas County adopted a solar licensing ordinance in 2024 and moratoriums on wind and on solar in 2026; its county check did not establish whether the county has planning and zoning (`docs/county_checks/2026-10-13_nicholas_ky.md`).
- **Illinois, Wyoming and Colorado.** Counties may stay unzoned, but the transition rule does not apply, because an unzoned county can still act on wind or solar: an Illinois county may regulate wind farm siting without zoning (55 ILCS 5/5-12020, read in its version before 2023), every Wyoming county must permit wind and solar facilities (W.S. 18-5-502), and a Colorado county may require its own permit for power plants under its 1041 powers (C.R.S. 24-65.1-203).
- **Township and town states.** In Michigan, Minnesota, North Dakota, Ohio, Pennsylvania and Wisconsin, towns or townships zone unincorporated land alone or alongside the county; in Connecticut, Maine, Massachusetts, Rhode Island, Vermont, New Jersey and New York counties have no land use role; New Hampshire counties zone only unincorporated places. A transition there would happen at the township or town level, which the rule does not model.

## Leads found during the survey

- **Cedar County, MO** has no voter-approved zoning. KY3 reported on September 15, 2026 that the commission adopted a 12-month moratorium on large solar, wind, battery storage and data center projects outside city limits on September 8, 2026, citing RSMo 49.650 and the county health statute, and that no court had ruled on it. The moratorium itself has not been read, and it is not yet in the review queue.
- **Wythe County, VA** was seeking public comment on a proposed first zoning ordinance (Cardinal News, March 30, 2026). It is a candidate for the transition list; the outcome has not been checked.
- **Craig County, OK.** Search results report that voters rejected a county zoning proposition on November 5, 2024, which news coverage described as aimed at wind turbines. The result article was not opened, so this is located, not yet read.

## Lists of which counties zone

For most states the survey found no current state agency list. Sources found: the National Zoning Atlas (a nonprofit map of which jurisdictions have zoning, complete for Utah, Vermont, Virginia and Wyoming and in progress elsewhere; Vermont's covers towns, not counties), Georgia's Department of Community Affairs survey of local governments (seen only in a search snippet; the map's link no longer works), a 2012 UNC School of Government count for North Carolina, a 2010 Kentucky Transportation Cabinet list of planning units, and a 2021 Kansas Senate testimony list known to be unreliable. A county-level file built from these would let the transition rule find candidates instead of relying on hand entries.

## Limits

- One reading per state except Alabama and Oklahoma. Some official code sites blocked automated access, so a few states rest on court opinions, agency summaries or codification mirrors; each citation records whether it was opened.
- The survey settles what counties may do, not what each county has done. Only Kansas has been read county by county.
