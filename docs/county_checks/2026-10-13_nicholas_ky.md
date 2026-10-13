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
