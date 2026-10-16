# County check: Nicholas County, KY (2026-10-13)

A follow-up to the 2026-10-09 negative check (grade B, web searches only) in
`data/review/negative_checks.csv`, run while profiling the county with
`scripts/site_profile.py`. The aim was to open the county's code and its
fiscal court minutes, the two source classes a grade A check needs
(`docs/COUNTY_CHECK.md`, section 2). Neither is published, so this pass
records a lead, not a new negative check, and the 2026-10-09 row stands.

## Governments

Nicholas County (fiscal court, five magistrates, judge-executive) and the
City of Carlisle, the county's only incorporated place. Nothing read says
whether either has planning and zoning; the Kentucky Resources Council
publishes a separate model siting ordinance for counties without it, and the
county's website has no planning, zoning or building-permit page.

## What was opened (2026-10-13)

| Source | Kind | What it holds |
|---|---|---|
| nicholascounty.ky.gov, home page and site navigation | county website | No code of ordinances, minutes, agendas, resolutions or planning page anywhere in the menu. Sections: elected officials, fiscal court, county services, calendar, links, forms, CodeRED. |
| nicholascounty.ky.gov/FiscalCourt/Pages/default.aspx | county website | The 2026 meeting dates (second Friday of most months, 9:00 a.m., at the courthouse), the magistrates and staff. No documents. |
| nicholascounty.ky.gov/elected/Judge/Pages/PublicNotices.aspx | county website | One undated notice, to landowners and contractors about fence setbacks from county roads. Nothing on energy, zoning or ordinances. |
| nicholascounty.ky.gov/Pages/Forms.aspx | county website | Three occupational-tax and license-fee forms. |
| Kentucky Office of Energy Policy, Solar Ordinances map service (watermaps.ky.gov/arcgis/rest/services/WebMapServices/SolarOrdinances/MapServer), layer 4 "Kentucky Solar Ordinances", queried 2026-10-13 | tracker | Nicholas County's row (OBJECTID 86, last checked 6/23/26) has no ordinance link or title; the state's map records no local solar ordinance for the county. |
| The same service, layer 0 "Solar Projects" (Siting Board cases) | tracker | 49 projects statewide; none in Nicholas County. Fleming has three and Harrison two. |
| Web searches for the county's planning commission, zoning ordinance or a solar ordinance | web search | Only statewide material (the KRC model ordinances, the Kentucky Lantern's 2023 count of adopting counties). The only county documents indexed are a 2013 officials' directory and an economic-development pitch, neither of which mentions zoning. |

Both trackers and the website are `secondary` sources under the procedure:
they locate records but do not read the code or the minutes. The 2013
industrial-development pitch (nicholascounty.ky.gov/FiscalCourt/Documents/)
was opened and has no zoning or energy statement.

## What this means for the profile

The county stays "checked by search, nothing found" (grade B). Two
independent trackers now agree with the searches: the state's own solar
ordinance map lists nothing for Nicholas County as of June 2026, and no
Siting Board case names it. That is stronger than the 2026-10-09 note but
still not a reading of the instrument class or the proceeding class.

## Next pass

- The fiscal court's minutes and ordinances are not online. Ask the
  Judge-Executive's office (125 E. Main Street, Carlisle; the number is on
  the Fiscal Court page) for the ordinance book index and the 2024 to 2026
  minutes, or for a statement that the county has no planning and zoning
  and no energy ordinance.
- Find whether the City of Carlisle has a zoning ordinance (no city website
  turned up in search; the Bluegrass Area Development District may hold it).
- A local contact's answer to either question can be recorded in
  `~/.renewable-opposition/local_knowledge.csv` and will print in the site
  profile; a reviewed negative check needs the documents themselves.

## 2026-10-16: the negative check is withdrawn

The 2026-10-09 negative check (grade B, web searches only) has been deleted
from `data/review/negative_checks.csv`, as section 4 of
`docs/COUNTY_CHECK.md` requires for a rejected check. A blind claim check of
that row (agent:blind-reviewer-4, 2026-10-16) returned contradicts: the
county had adopted three restriction instruments before the check, and a
contested project was before the fiscal court.

- Ordinance No. 06/2024-Solar, adopted on second reading June 14, 2024: a
  county license for intermediate- and large-scale solar and a 2,000-foot
  setback from non-participating property lines and public roads. Its legal
  summary ran in the Carlisle Mercury on June 26, 2024
  (https://kynewsgroup.com/tcm062624.pdf), and the full text is in the
  county attorney's October 12, 2026 filing in Siting Board Case 2026-00256.
- Ordinance No. 26-August-02, a one-year moratorium on wind energy projects
  of any size, adopted August 14, 2026 and printed in the Mercury of
  August 26, 2026 (https://kynewsgroup.com/TCM-08-26-26.pdf).
- Ordinance No. September-2026-18-01, a one-year moratorium on solar systems
  of any size, adopted September 18, 2026 (5-1 on second reading) and filed
  in the same Siting Board case.
- South Fork Solar (Heelstone, about 45 MW on Carpenter Pike): the fiscal
  court voted unanimously on July 10, 2026 against the developer's request
  for a text amendment to the 2024 ordinance.

All three instruments are confirmed in `data/review/queue.csv` (the 2024
ordinance and the wind moratorium in this pass; the solar moratorium is
already published). South Fork Solar is queued and awaiting review.

The earlier passes found none of this. The county posts no ordinances or
minutes online, and the state's solar ordinance map had no entry for the
county as of June 2026. The Carlisle Mercury, whose weekly issues are posted
as PDFs on kynewsgroup.com, prints the county's ordinances as legal notices
and covers fiscal court meetings, and the Siting Board docket holds both
solar instruments. Future checks of small Kentucky counties should
search the local weekly's PDFs and the Siting Board's case files before
recording a negative check.
