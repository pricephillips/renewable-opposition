# Source scan, October 28, 2026

This page records a search for sources the pipeline does not yet read: what each offers, and why one was added to live intake and the rest were not. Every check below ran on October 28, 2026, from a cloud session, with the pipeline's own user agent (`scripts/fetch.py`).

## What a source had to offer

Four questions decided each candidate:

1. **Can the pipeline read it?** A script with the pipeline's user agent must get the data. A site that answers such a request with HTTP 403 or 404, or that needs a key the repository does not hold, cannot run in the weekly intake.
2. **May the pipeline use it?** Government records and openly licensed data qualify. A site whose terms limit it to personal, non-commercial use, or forbid automated access, does not.
3. **Does it say what holds now?** A list that gives each item's current state (a law filed, an application denied) can feed the review queue. A list of past milestones cannot, without a reviewer reading every entry against the record.
4. **Does it add records, and does it bring the evidence?** The evidence standard counts a restriction as verified only when it is checked against the instrument itself (an ordinance, resolution, moratorium, zoning amendment or state law) or the minutes that adopted it. A source that links to the instrument does more than one that only names it.

## Added to live intake: New York local law filings

Every local law a New York county, city, town or village adopts is filed with the Department of State under Municipal Home Rule Law section 27, and the Department's local laws database (https://dos.ny.gov/local-laws) holds the filed copy: the filing form and the law's text, as a PDF. The database's search runs on a JSON interface (`https://locallaws.static-assets.ny.gov/api/search`) that a script can read with no key. Each result gives the government, law number, year, filing date and the law's title as filed.

New York holds more restriction instruments than any other state in `data/processed/restrictions.csv`, and the database gives the instrument itself for each new filing, so it was the strongest candidate the scan found.

- **Source:** `ny_dos_local_laws` in `config/sources.yaml`, read by `scripts/extractors/ny_dos_local_laws.py` and tested offline in `tests/test_intake_ny_dos_local_laws.py` on 32 results saved from the live search (`tests/fixtures/intake/ny_dos_local_laws.json`).
- **Query:** the newest 100 filings whose title names solar, photovoltaic, wind, battery, energy storage, BESS or renewable. On October 28, 2026, it matched 3,551 filings in all. The newest 100 ran from August 14 to October 21, 2026 (about ten weeks), so each weekly run overlaps the last. The query leaves out the county code compilations (`-(countyMunicipalType:County)`), as the site's own search does; local laws filed by counties stay in.
- **What becomes a lead:** a local law on siting solar, wind or battery storage (a moratorium or its extension, a prohibition, or a siting or zoning law). The extractor drops tax and payment-in-lieu laws (including the Real Property Tax Law section 487 opt-outs), repeals that adopt nothing new, laws on small or residential systems only, and rezonings of a single site. Two filings of one law (a corrected copy filed beside the first) become one lead.
- **Evidence:** a lead's `source_url` is the filed PDF, so its `source_kind` is `official_copy`. A reviewer who opens it reads the instrument, and a restriction promoted after that reading is verified against its primary source. Until then the lead's `access` is `snippet` (located, not yet read), as for every lead.
- **Placement:** a town, village or city filing takes the county the Department of State adds in parentheses to a name several towns share ("CLINTON (CLINTON COUNTY)"), else the one county `data/census_governments_2024.csv` gives a government of that kind and name, else the county the law's title names. A filing that fits none of these, or whose title names a county other than the one the census gives, is left without a county.
- **Trial run:** of the newest 300 filings (back to March 23, 2026), the extractor kept 282 and dropped 18, and the 282 became 278 leads. `parse.dedupe` found none of their documents already held in the queue, the seeds or the review files. It gave 32 leads a "possible duplicate" note: the same government and technology as a held record, or as another lead in the run.

The newest 100 filings on October 28, 2026, gave 93 leads, about what the first weekly run will add to `data/review/queue.csv`. Like every lead, they count in no published figure until they are triaged (`/triage-leads`). Many filed copies are scans, so the lead-triager guidance (`.claude/agents/lead-triager.md`) now says to read them with `pdftoppm` and RapidOCR when `pdftotext` returns nothing.

## Assessed and not added

| Source | What it offers | Why not now | What would change that |
|---|---|---|---|
| Federal Register API, Bureau of Land Management and Bureau of Ocean Energy Management notices | Notices of intent, impact statements and records of decision for named projects on federal land and offshore; public domain, no key | It records federal milestones, not a project's current status. Of the newest 100 notices from each bureau naming solar, wind or energy storage (back to 2022), no title terminates a named project's review, withdraws its approval or cancels it, so a lead would mostly restate an old milestone. | The outcome-reader agent can cite a record of decision as outcome evidence when a federal-land or offshore project comes up. |
| CourtListener federal dockets (RECAP), `type=r` on the search `courtlistener_renewables` already uses | A federal case and its court before any opinion is written | The search answers anonymous requests with HTTP 401. | Setting the `COURTLISTENER_API_TOKEN` repository secret, which the intake workflow already passes; a fixture can then be fetched. |
| Google News and Bing News RSS search | Local papers that GDELT misses | Bing's feed states its results may be used only for personal, non-commercial reading in a feed reader, and Google's News terms page limits its content to personal, non-commercial use. | A licensed news search. |
| Basepoint's moratoria and ordinance pages (getbasepoint.com) | Moratoria and bans in force (77 on the moratoria page), each with the adopting document and the date it was checked | A commercial developer platform whose terms do not license reuse of its content. A weekly intake source would store copies of its pages in this public repository. | Price's decision on the terms. Meanwhile the research agents read it as a tracker, as they read Moratorium Nation: it points them to the adopting document, and they read that document (`docs/COUNTY_CHECK.md`, section 2). |
| CleanPowerDaily's opposition tracker | Counts of restrictive actions by state and county | Its terms forbid automated access without permission, and the research agents are automated, so nothing in the pipeline reads it. | Permission from the publisher. |
| States Newsroom outlets and News From The States | State-capital reporting, republishable under Creative Commons, that covers siting law and county fights | Their search pages and JSON interface answer a script with HTTP 403, and the feeds that do answer carry only the latest stories (one outlet's feed was 1.15 MB of full text). | A search the outlets open to scripts. |
| Publisher feeds (Inside Climate News, Canary Media, Utility Dive) | Energy reporting with links to the original articles | The Inside Climate News and Utility Dive feeds each held 10 items, one to three days of stories, so a weekly run would miss most of them. | A daily intake job. |
| Ohio Power Siting Board | Ohio's siting cases and decisions | The site answers the pipeline with HTTP 404, and its case bulletins have no public list. | A reachable case list. |
| Michigan, Minnesota and Wisconsin commission dockets | State siting dockets | Each answers the pipeline with HTTP 403. | Access for scripts. |
| Washington Energy Facility Site Evaluation Council | About 20 facilities with their review stages | Too few to automate. | None needed: an agent can read the council's facility pages when a Washington project comes up. |
| Connecticut Siting Council | Petitions and dockets for solar facilities | Its lists are split across pages by number range, and reading each case's status from them needs more work than this scan gave it. | A single list with status. |
| National Wind Watch | A news feed about opposition to wind and solar, worldwide | An advocacy site that republishes others' articles on its own pages. | None. |
| Open States | State bills | A key is needed, and `docs/pipeline_comparison.md` records the decision not to adopt it before the state rows are verified. | That decision. |
| CivicClerk, PrimeGov and other agenda platforms | Meeting agendas, which can show a proposed local moratorium before it is adopted | Each county's tenant (its own site on the platform) must be found and verified, as the Legistar clients were. | Passoff item B8 (`docs/PASSOFF_2026-09-29_tooling_from_data_center_map.md`). |

`config/source_registry.csv` lists the New York source as integrated and records the Federal Register, CourtListener dockets, Basepoint, CleanPowerDaily and the news search feeds with the reasons above.
