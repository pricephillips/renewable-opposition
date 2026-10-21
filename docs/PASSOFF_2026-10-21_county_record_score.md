# Passoff: the county record score and its inputs

**Date:** 2026-10-21. **From:** the Claude Code session that built the county record score (pull requests 91 and 93). **To:** the next session working on county scoring in this repository.

Start the next session with:

> Read `docs/PASSOFF_2026-10-21_county_record_score.md` and `docs/county_record_score.md`. Pick up step 1 under "Next steps", then go down the list. Run `/humanizer` on any prose before it is committed.

---

## Why this work exists

The October 16 case studies (`deliverables/case_study_templates/renewables_2026-10-16/`) printed the county restriction model's score, which measures how closely a county resembles counties with a severe restriction on record and never reads the county's own record. Reviewers read Nicholas County, KY and Cherokee County, KS as much less friendly than Linn County, IA, while the score put Linn in decile 8 and Nicholas in decile 1. The review found the data right and the comparison across counties wrong, and asked that a Kansas county moving from no zoning to zoning count as a severe restriction. Since then the work has gone into the score's inputs rather than into individual counties.

## What is built (merged to `main`)

| Piece | Where | What it does |
|---|---|---|
| County record score | `scripts/county_record_score.py`, `config/county_record_score.json`, `docs/county_record_score.md` | Scores every county on one rubric from its own record: instruments by severity, currency, reach and breadth; contested projects; the resemblance score as a prior where the record is empty |
| Build-out as approvals | `build_out` in the config | EIA-860M plants of 20 MW or more, online since 2020 and after the county's latest rule in force, count as uncontested approvals |
| Counties that cannot zone | `no_county_zoning` in the config | Texas counties (no general zoning power) with no record count as evidence at weight 0.6 |
| Kansas zoning transitions | `zoning_transition.counties` in the config | Seven counties: Bourbon, Brown, Cherokee, Crawford, Kiowa, Labette, Nemaha |
| Daily rescoring | `scripts/run_pipeline.py` build stages, `build-data.yml` | The score reruns on every build; the resemblance prior still refits monthly |
| Examination priority | `scripts/examination_batch.py --by-activity [--active-only]` | Orders unexamined counties by active interconnection MW |

On the data of October 21, 2026: 118 counties closed, 312 severe, 343 restrictive, 689 regulated, 412 open, and 1,270 scored on the profile prior alone (from 1,751 before build-out and the Texas rule). The four case-study counties: Cherokee 64.5 and Nicholas 57.5 (closed), Harris 12.5 (restrictive), Linn 7.35 (regulated). The score is internal: no page or report reads it until Price decides otherwise.

## In flight when this was written

The Kansas zoning pass is complete; its results are below.

It is not committed. `.packets/` is not tracked and the session scratchpad does not survive the session, so a new session may have to redo it.

1. **Status sample (run `2026-10-21-status`).** Sixty NREL-compiled instruments whose currency is `unknown`, drawn to measure how many are still in force and replace the flat 0.5 weight for unknown status (`instruments.currency.unknown`). Ten `status-checker` agents were drafting first readings; 12 drafts were back when this was written. To redraw the same sample: take NREL instruments with currency `unknown` from `data/processed/restrictions.csv`, drop those with a row in `data/review/status_resolutions.csv` or a `verification_log.csv` line dated 2026-10-07 or later, group them by technology and highest severity, sort each group by instrument id, and draw with `random.Random(20261021)` in sorted group order: solar 2: 26, solar 3: 3, solar 4: 3, wind 2: 13, wind 3: 12, wind 4: 3 (group sizes 1,144, 59, 12, 578, 503 and 62).

## Next steps

1. **Finish the status sample** with `/check-status` steps 4 to 8: a blind second reading of every draft whose result is `read`, reconcile, the record-editor writes `status_resolutions.csv` and the log, then the qc-auditor and a pull request. Keep this pull request to review files only: `review_lint.py --lane review` fails a branch that also changes code. Then set `instruments.currency.unknown` to the in-force share, weighted by group size, in a separate pull request.
2. **Second readings of the Kansas transitions.** Each of the six added on October 21 rests on one research reading. A `blind-reviewer` pass over their sources (listed in the config) would let them stand as reviewed.
3. **Turn the Kansas leads into restriction records** through `/examine-county`: Brown County's ban on commercial wind of 500 kW or more (February 2025); Crawford County's ban on future wind projects (July 10, 2026, Motion 26-320); Bourbon County's 365-day moratorium on utility-scale power generation (June 2026); Neosho County's moratoria on wind, solar and data centers, renewed June 30, 2026 (seen only in a search snippet).
4. **Sweep by activity.** `python scripts/examination_batch.py --by-activity --active-only --counties 40` gives the next sweep. Of the 1,375 counties on the prior alone before the Texas rule, 490 had active interconnection requests and 661 had neither a request nor an operating plant.
5. **County zoning status beyond Kansas.** Missouri and Kentucky also allow unzoned counties (Nicholas County, KY has no zoning). A reference file of which counties zone, built state by state from one source per state where one exists, would replace the hand list and extend the zoning rule.
6. **Lower-grade negative checks.** A check that covered only the code publisher and the county site could count at a lower evidence weight than a grade A check, so cheaper checks still move a county off the prior.
7. **Agenda feeds.** The intake reads 11 Legistar clients. Many rural counties post agendas through CivicPlus AgendaCenter, which has RSS feeds; adding them would catch moratoria as they are proposed.

## Kansas zoning pass, October 21

One research reading per county, by five agents, covering all 104 Kansas counties besides Cherokee. A shared cap of 200 web searches per turn ran out partway through, so some counties rest only on county sites and a March 2021 Kansas Senate testimony list of zoned and unzoned counties (`kslegislature.gov`, 20210322_76.pdf).

| Result | Counties |
|---|---|
| Listed as transitions | Bourbon, Brown, Crawford, Kiowa, Labette, Nemaha (and Cherokee, from October 16) |
| Discussion only, not listed | Barber (a 2024 countywide zoning survey) |
| Zoned before the window (no transition) | 51 counties, among them Linn, KS (a 2023 rewrite of existing zoning), Marion and Seward (wind or solar rules added to codes they already had); Crawford is listed above because its earlier zoning covered only a southeast area |
| Unzoned, no zoning activity found | Atchison, Chase, Cheyenne, Cloud, Elk, Ellsworth, Gove, Grant, Greeley, Jewell, Logan, Marshall, Meade, Morris, Morton, Neosho, Ness, Osborne, Phillips, Rawlins, Republic, Scott, Thomas, Wallace, Washington, Wichita |
| Not settled | Chautauqua, Clark, Comanche, Decatur, Edwards, Graham, Harper, Haskell, Hodgeman, Kearny, Lane, Lincoln, Mitchell, Norton, Rooks, Sheridan, Sherman, Smith, Stanton, Trego |

The 2021 testimony list proved unreliable: it lists Greenwood and Hamilton as unzoned, though their own documents show zoning since 2001 and 1993. Worth a second look: Trego (its website lists a county planning and zoning board, but no county zoning resolution was found); Mitchell (a planning commission since at least 2018 and a data center moratorium being drafted in October 2026); Marshall and Morris (data centers and battery storage raised in 2026 commission meetings, without a zoning step); Ellsworth (a 2022 county vision plan surveyed residents on zoning, with no step since); Graham (a 2013 conditional use permit for a wind farm, though listed as unzoned).

## What limited this session

- The web search cap (200 per turn, shared by every agent) ran out during the Kansas pass. Give research agents a search budget per item and point them at county sites and code publishers first.
- Firecrawl had no credits left.
- Municode, American Legal and eCode360 return a Cloudflare challenge to curl and to headless Chromium from this environment, so a scripted search of county codes is not possible here.
- Many county sites block automated access; scanned minutes needed OCR (`tesseract-ocr` was installed in the session).

## Decisions for Price

1. The rubric's weights are set by hand. Any that seem wrong are one line in `config/county_record_score.json`.
2. Whether a Kansas county that discussed zoning without a formal step (Barber) should count.
3. When, if ever, the record score reaches a page or a county report (the registration's rule for model scores applies to it too).
