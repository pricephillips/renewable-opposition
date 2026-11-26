# The development scout

The development scout finds solar, wind and battery storage projects that are
being planned or built before the federal plant inventories list them. It adds
them to the project universe that the project models need (Build-Out goal R3;
`docs/predictive_foundation_design.md`, section 5). It has two parts: a script
that finds and sorts candidates (a candidate is one possible project, built
from one or more filings or map tags), and two agents that each read a
document about a candidate on the worklist.

## 1. What it reads

Both sources are open geographic data with no key.

- **FAA obstruction filings (OE/AAA).** A structure taller than 200 feet must
  be filed with the Federal Aviation Administration on Form 7460-1 before it
  is built. Every utility-scale wind turbine is filed. The FAA publishes all
  cases as one CSV file per region and year
  (https://oeaaa.faa.gov/oeaaa/oe3a/main/#/download). Regions WTE and WTW hold
  the wind turbines. Each filing gives coordinates, a county, dates, a status
  and often a sponsor. The files are U.S. government works in the public
  domain.
- **OpenStreetMap.** The Overpass API (https://wiki.openstreetmap.org/wiki/Overpass_API)
  returns the power plants that mappers have tagged as under construction or
  proposed. The scout keeps those whose source is solar, wind or battery. The
  data is licensed under the ODbL 1.0, so the OpenStreetMap rows of the output
  are offered under the same license, with the credit "(c) OpenStreetMap
  contributors".

A filing or a map tag is a lead about a place. It is never a record. An FAA
"No Hazard" determination is an airspace finding, not a permit, and neither
source says anything about opposition.

The data center platform already reads the same two sources for data centers
(`fetch_osm_facilities.py` and `fetch_faa_obstruction.py` in
`pricephillips/data-centers`). Its FAA reader skips the wind turbine regions,
which are the ones this scout reads. No code is shared or copied between the
two.

## 2. Finding and sorting (the script)

`python scripts/development_scout.py` does the following:

1. It reads the FAA files from 2024 (`since` in `config/development_scout.json`)
   to the current year. It also sends one Overpass query per state.
2. It groups the filings into candidates: a filing within 4 km
   (`cluster_km`) of any filing in a group joins that group. A crane filing
   marks construction. A group of cranes with no turbine and no met tower is
   a port or vessel staging area (`crane_only`), so it is not sent to a
   reader.
3. It places each candidate in its county by its coordinates (`geo.county_at`).
4. It sorts each candidate against `data/reference/facilities.csv` (EIA-860M,
   USWTDB, USPVDB) and `data/reference/queue_projects.csv` (Queued Up).
   `known_facility` means that a plant of the same technology lies within the
   distance in `matching.facility_km`. `queue_county` means that no such
   plant does, but an active or suspended interconnection request of the same
   technology is in the same county.
   `new` means neither. The queue has no coordinates, so only a reader can
   decide whether a `queue_county` candidate is that request.

It writes every candidate to `data/reference/development_signals.csv`, and
each file it read to `development_signals_manifest.csv`. The `new` and
`queue_county` candidates that nobody has resolved go to
`data/review/development_worklist.csv`, unless they have no county or their
stage is `terminated`, `withdrawn` or `crane_only`. The worklist puts `new`
candidates first, then sorts by stage (`under_construction` first), then
puts those with more turbines first. When a source cannot be read, its rows from the last run stay and the
manifest records the failure, so an outage never looks like a run that found
nothing.

`build-data.yml` runs the script each month after it refreshes the plant
inventories.

## 3. Reading (the agents)

The daily verification routine takes at most 3 worklist candidates each day
(`per_run` in the config), skipping any logged in the last 14 days
(`skip_days`; `docs/VERIFICATION_ROUTINE.md`, section 5c):

1. `python scripts/development_scout.py card <signal_id>` writes the card. The
   card holds only what the open sources say, so the same card goes to both
   readers.
2. The `development-reader` finds a public document that names the project (a
   county permit or hearing, a state siting docket, the developer's page, or
   a news report), reads it, and drafts a verdict: `new_development`,
   `same_as_queue`, `same_as_facility`, `duplicate_signal` or
   `not_a_development`. It also gives the technology, stage, name and county.
3. A `blind-reviewer` reads the same card on its own and writes its own
   verdict.
4. `python scripts/development_scout.py reconcile <draft> <review>` prints a
   row only when both readings read a document and agree on the verdict,
   technology, stage, county and matched record (`matched_id`). The
   `record-editor` appends it to
   `data/review/development_resolutions.csv`. A resolved candidate leaves the
   worklist and carries its verdict in `development_signals.csv`.

When an agreed row names a document about local opposition to the project
(`opposition_url`), the `record-editor` also adds that document to
`data/review/queue.csv` as a lead. The `lead-triager` then reads it like any
other lead. A lead is not a record until that review accepts it.

## 4. Adding a source or a technology

A new source is one entry under `sources` in `config/development_scout.json`
and one reader function in the script, with its test in
`tests/test_development_scout.py`. A new technology is one entry under
`technologies` (and, for OpenStreetMap, under `technology_by_source`). No
place is named in code or configuration.
