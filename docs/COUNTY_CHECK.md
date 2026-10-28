# County check

How to examine a county: search the records that would show a local
restriction on wind, solar or battery storage, and record what was found. A
person or an agent follows the same steps, and the review rules in
`docs/AGENT_REVIEW.md` apply to every row a check drafts.

A county is **examined** once it has a published record, or a reviewed
negative check (`data/review/negative_checks.csv`). Until then the dashboard
shows it as not examined, never as zero. `data/review/examination_worklist.csv`
lists the counties still to check, nearest-to-finished states first.

## 1. Which governments to cover

A check covers every government that can zone land in the county:

- the county itself, where it zones unincorporated land, and
- each city, town, village, township or borough in the county that has its
  own zoning, where the state gives municipalities that power (New England,
  New York, New Jersey, Pennsylvania, Michigan and Wisconsin townships, and
  incorporated places everywhere).

Name them in `governments_checked`, separated by semicolons, for example
`Belknap County (no zoning); Alton; Barnstead; Belmont; ...`. A check that
covers only some of them is not a negative check: write it up as a lead in
the pass note (section 6) and record nothing in `negative_checks.csv`.

Where a state body issues the siting permit (a siting board, the public
utility commission), local rules can still exist and still count. Search the
state body's docket for the county as well, because a county's objection or a
local ordinance often appears there.

## 2. What to search

| Class | What | Counts as read when |
|---|---|---|
| `primary_law` | each covered government's zoning or land-use code (Municode, eCode360, American Legal, General Code, the government's own site), searched for solar, wind, battery or energy storage, and moratorium | the code itself was opened, or an archived copy |
| `proceeding` | the minutes or agendas of the governing body and the planning commission for the last three years, searched for the same words; the state siting docket where one exists | the minutes, agendas or docket were opened |
| `secondary` | a web or news search for the county with solar, wind, battery storage, moratorium and ordinance; the trackers that list moratoria by place with a link to each adopting document (Moratorium Nation, https://mjbommar.github.io/moratorium-data-2026/, and Basepoint's moratoria page, https://www.getbasepoint.com/ordinances/moratoria, with its state pages) | always secondary, whatever it finds; a tracker's link is a lead to the instrument, which counts only once it is opened |

A negative check needs both `primary_law` and `proceeding` sources that were
opened, plus a news search. Search results alone are not enough: a web search
for "ordinance" is a `secondary` source, never `primary_law`.

Write each source in `sources_checked` as `<kind>: <what was searched>
(<URL>, <date range if any>)`, separated by semicolons. The kind decides the
class (`scripts/negative_checks.py`, `family_of`):

| Kind | Class |
|---|---|
| `code`, `ordinance`, `zoning`, `statute` | `primary_law` |
| `minutes`, `agendas`, `docket`, `hearing` | `proceeding` |
| `web search`, `news search`, `tracker` | `secondary` |

## 3. What counts as a restriction

The rules every source already follows (`scripts/nrel_ordinances.py`,
`build_sabin_seeds.MECHANISM_TYPE`). A local instrument is a restriction when
it has any of these for wind, solar or battery storage:

- a moratorium, or an outright ban or prohibition
- a setback from non-participating dwellings, structures or property lines
- a maximum height, a noise limit, a cap on project size, lot size or coverage
- a shadow flicker limit, or districts where the use is prohibited

It has to be a land-use instrument: a zoning or siting ordinance, a local
law or resolution on siting, or a moratorium. Fire, building and electrical
codes (the fire code's clearances for battery storage, for one) apply almost
everywhere and are not counted; the note can record them.

The instrument has to reach commercial, utility-scale or principal-use
facilities, as Sabin's and NREL's records do. Rules written only for small,
accessory or on-site systems (a homeowner's wind turbine, rooftop or
backyard solar) are not restrictions here; the note records them.

A code that only lists the use as permitted or conditional, or sets
standards outside that list (road setbacks, fencing, decommissioning,
screening), has no restriction. Such a county can get a negative check, and
its note says which standards the code does set.

The 2026-10-22 sweep (`docs/county_checks/2026-10-22_sweep.md`) settled three
cases the list above leaves open:

- District standards that apply to every use in a district (yards, lot
  coverage, height) are not restrictions, even where the district is the one
  a wind or solar project would use.
- A county that keeps the state's review thresholds, for example an Oregon
  county opting out of OAR 660-033-0130(44) and keeping the (38) limits, has
  no restriction from that choice.
- A use table that marks a solar, wind or storage use "not allowed" or "not
  permitted" in named districts is a restriction: districts where the use is
  prohibited.

Lapsed or repealed instruments are recorded as such (status `lifted` or
`expired`) and are not published.

## 4. Recording what was found

**A restriction.** One row in `data/review/queue.csv` per instrument:
`entity_type` restriction, `review_status` `awaiting_review`, and
`reviewer_notes` beginning `Drafted by <drafter>`. Fill `technology`,
`mechanisms` and `mechanism_detail` (the build scores severity from them;
never type a severity; a mechanism that applies to only some of the row's
technologies names them in parentheses, joined with `+`, as in
`cap on acreage (battery_storage)`), `description`, `adopted_date`, `status`,
`end_date` (the date the instrument runs to, if the document gives one, or the
date a lifted or expired instrument stopped applying, from the document),
`evidence_text` quoted from the document, `source_url`, `access` and
`source_kind` (`instrument` or `minutes` when the document itself was
read). A second reviewer sets `review_status` to `confirmed`.

**Nothing found.** One row in `data/review/negative_checks.csv`:

| Column | |
|---|---|
| `county_fips`, `state`, `county` | the county |
| `scope` | `restrictions`, `projects` or `both` |
| `governments_checked` | every government covered (section 1) |
| `sources_checked` | each source, as in section 2 |
| `checked_on` | the day of the search |
| `result` | `none_found` |
| `note` | standards the codes do set; anything that could not be opened, with the URL and what it returned |
| `drafted_by` | who ran the check |
| `reviewer` | who reviewed it; never the drafter |

A row with a `drafted_by` and no `reviewer` is held: it is listed, and does
not count until someone else reviews it. A reviewer reopens the sources (at
least the codes) and rejects a check that does not meet section 2. A
rejected check is deleted, not edited, and the pass note says why.

**Something that is neither.** A news report of a moratorium whose minutes
are not posted, or a code that could not be opened, is a lead. It goes in
the pass note with every URL tried, and nothing is recorded in either file.

## 5. Re-checks

A negative check is stale after a year (`negative_checks.STALE_DAYS`); its
`recheck_by` date is `checked_on` plus that. A stale check still counts as
examined, at a lower grade, and goes back on the examination worklist.

## 6. Pass notes

Each pass gets a note, `docs/county_checks/<date>_<name>.md`, in the form of
`docs/ohio_sb52_first_pass.md`: which counties were checked, the result for
each, what blocked the pass, and where the next pass should start.
