# Ohio SB 52: first pass on 10 counties (2026-10-09)

Ohio SB 52 (Ohio Rev. Code 303.58 and 303.62) lets a board of county
commissioners designate all or part of the unincorporated county a restricted
area for large wind and solar facilities. `data/review/ohio_sb52_worklist.csv`
lists every county. This note records the first pass on 10 of them, so the next
pass starts where this one stopped.

A checking agent (`agent:ohio-sb52-checker`) searched each county, and a second
agent (`agent:ohio-sb52-reviewer`) reviewed the results under
`docs/AGENT_REVIEW.md`. A resolution counts only when the resolution or the
minutes that adopted it are opened; news and agendas only locate it.

## Results

| County | FIPS | Result |
|---|---|---|
| Huron | 39077 | Queue row: Resolution 26-110, adopted 2026-04-07 (minutes opened). Restricts part of the county: large wind and solar in all 19 townships, economically significant wind farms in 17. Corrected after review; a fresh review confirmed it, so it publishes after merge. |
| Sandusky | 39143 | Queue row: Resolution 2025-366, adopted 2025-12-18. The minutes print only the title, so whether it covers all unincorporated territory is not confirmed. Awaiting review; read the resolution or its map first. |
| Mahoning | 39099 | Lead. County agendas list resolutions for Green Township (2023-11-09) and for Austintown, Beaver, Berlin, Canfield, Coitsville, Goshen, Jackson, Milton, Poland and Springfield Townships (2024-03-07); news reports 3-0 votes. Minutes are not posted. |
| Stark | 39151 | Lead. News reports a 2024-07-10 vote restricting 14 townships (Marlboro allows economically significant wind farms). The county posts minutes for 2025 and 2026 only. |
| Champaign | 39021 | Lead. A regional planning document says 11 of 12 unincorporated areas are restricted. Two county filings in the Hillclimber Solar docket (25-0904), dated 2026-01-12 and 2026-04-30, were not opened. |
| Fulton | 39051 | Lead. News (2026-02-16) reports a resolution restricting all unincorporated areas; Resolution 2026-172 appeared on a 2026-03-10 agenda that now returns 404. A "Resolution of Fulton County Commissioners" exhibit sits in the Ritter Station docket (24-0928). |
| Preble | 39135 | Lead. Agendas show township requests and statutory notices for Harrison (2023); Washington, Jefferson, Jackson, Lanier and Dixon (2024); Twin and Israel (2025). The commission journal is not online, so adoption is not confirmed. |
| Pickaway | 39129 | Nothing found in the 2026 minutes; minutes before 2026 are not online. A 2022-06-02 public comment titled "Pickaway County Resolution" in the Chipmunk Solar docket was not opened. No negative check recorded. |
| Defiance | 39039 | The county posts no minutes or resolutions; only two Power Siting Board dockets were searched. No negative check recorded. |
| Meigs | 39105 | No county records could be searched (empty minutes page; two county domains refused by this session's network). No negative check recorded. |

The reviewer rejected all four drafted negative checks (Pickaway, Defiance,
Meigs, Preble): a "nothing found" check needs the county's own records or the
Power Siting Board record to have been searched, and none of the four had that.

## What blocked the pass

- Power Siting Board document PDFs (`dis.puc.state.oh.us`, ViewImage) return a
  bot check; docket lists load, filed documents do not.
- Most counties post only recent minutes; older journals are offline.
- Internet Archive connections were reset or refused from this session.

## Next pass

Ask each county commission clerk for the adopting resolutions and maps
(Mahoning, Stark, Champaign, Fulton, Preble, Sandusky), or open the county
filings in the Power Siting Board dockets named above from a browser.
