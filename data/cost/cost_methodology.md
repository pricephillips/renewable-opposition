# Cost ledger: methodology

Generated 2026-11-05 by `scripts/cost_ledger.py`. **Internal, not client-facing.**
The ledger prices the observed span of each contested project at published rates. It does not
estimate what opposition did to any project and makes no comparison with a project that saw
none: it is case-level observed-cost accounting, ported from the data-center-map cost ledger
(spec 025). Re-verify every anchor before any external use; the registry records when each one
is due.

## The ledger

`data/cost/cost_ledger.csv` holds one row per contested project in
`data/processed/contested_projects.csv`: 579 rows, 66 priced and
513 withheld.

| Priced by span | Rows |
|---|---|
| `accrued_to_date` | 28 |
| `request_to_decision` | 38 |

| Priced by technology | Rows |
|---|---|
| `solar` | 45 |
| `wind` | 18 |
| `battery_storage` | 3 |

| Priced by span start | Rows |
|---|---|
| `queue_request` | 66 |

| Priced by MW source | Rows |
|---|---|
| `federal_plant_inventory` | 5 |
| `queue_request` | 3 |
| `record` | 58 |

| Withheld reason | Rows |
|---|---|
| `technology_not_priced` | 46 |
| `outcome_needs_review` | 25 |
| `outcome_unverified` | 182 |
| `no_start_date` | 2 |
| `start_year_precision` | 233 |
| `start_from_possible_queue_match` | 13 |
| `queue_match_conflict` | 6 |
| `no_end_date` | 2 |
| `nonpositive_span` | 1 |
| `no_capacity_mw` | 3 |

| Review flag | Rows |
|---|---|
| `hybrid_priced_on_primary` | 25 |
| `offshore_wind` | 26 |

## Span

- `request_to_decision`: a project with a confirmed outcome (`blocked_confirmed`,
  `advanced_confirmed`, `restricted_conditional`), from the start date to its
  `resolution_date`.
- `accrued_to_date`: a pending project, from the start date to the run date. The project is
  still open, so its full span is at least this long; the row prices only the part observed so
  far.
- Start date: the first interconnection request of the project's Queued Up match
  (`data/reference/queue_matches.csv` `first_request_date`) when the match is `strong`, else a
  day- or month-precision date in the record's `event_date_text`. A start from a `possible`
  queue match, a year-only start and a missing start are withheld, and so is a strong match
  that `queue_matches.py` flags as conflicting with the published outcome
  (`queue_match_conflict`, for example a pending project whose every request was withdrawn).
- Unverified outcomes (`blocked_unverified`, `advanced_unverified`) and `needs_review` rows are
  withheld: the span's end is not settled.
- Precision. A month-precision date is stored as the first of its month, so the true date falls
  on or after it. A month-precision start shortens the span by up to (days in that month - 1);
  a month-precision end lengthens it by up to the same. The low end is floored at 1 day.
  Months are days / 30.44.

## Technology and capital basis

- Solar, wind and battery storage are priced, each on its own anchors. A record that lists more
  than one of them is priced on the first, on the stated MW, and flagged
  `hybrid_priced_on_primary`. Transmission, geothermal and hydro are withheld as
  `technology_not_priced`, and so is offshore wind (a wind record whose name or description
  says offshore, flagged `offshore_wind`), whose costs are not those of land-based wind.
- Capital basis: the per-MW anchor for the technology times a stated MW. The MW is the
  record's `capacity_mw`, else the strongly matched federal plant inventory entry's
  (`facility_capacity_mw`), else the strongly matched queue request's (`queue_capacity_mw`);
  `mw_source` says which. MW is never imputed, and never derived from acres or dollars.

## Components

Low ends use every anchor's low value (the high value of fixed O&M, which lowers net revenue)
and the shortest span; high ends use the opposite. Components 1 to 3 rise with span and with
each anchor, so those bounds are exact; component 4 is not monotone in the cost of capital, so
each of its bounds takes the extreme over both ends of that range.

A `blocked_confirmed` project is never built and never earns, so it carries capital at risk
only (component 2). Every other priced row carries components 1, 3 and 4.

**1. Construction-cost escalation (destroyed value).**
`capital_basis x construction_escalation x (span_months / 12)`.

**2. Development capital at risk on a block (destroyed value, assumption-based).**
`capital_basis x predevelopment_share`, on `blocked_confirmed` rows only.

**3. Deferred revenue exposure (upper bound, not destroyed value).**
Solar and wind: `MW x capacity_factor x 8760 h x ppa_price_mwh x (span_months / 12)`. Storage:
`MW x 1000 kW x capacity_price_kw_month x span_months`. This is gross revenue that arrives later.
The economic cost is the time value of the deferral (component 4), not this face amount, and the
exposure is never added to the total.

**4. Economic cost of deferral.**
`net = annual gross revenue - MW x 1000 kW x fixed_om_kw_year` (floored at 0);
`value = net x (1 - (1 + r)^-L) / r`; `cost = value x (1 - (1 + r)^-(span_months / 12))`, with
`L` the project life (`project_life_years`) and `r` the cost of capital (`carrying_rate`). It is
the present value given up when the project's net revenue stream starts later.

**Total economic cost.** Components 1 and 4, or component 2 for a block; low ends added to low
ends and high ends to high ends. Gross deferred revenue is never in it. For a pending row it is
the cost of the span so far.

Not yet in the ledger: carrying cost on capital already deployed (the data center ledger fills
it from public records of land purchases and deposits), and the federal tax credit deadlines,
which are a step at a date rather than a rate (see `data/cost/cost_brief.md`).

## Anchors

| Anchor | Low | High | Unit | Confidence | As of | Re-verify by |
|---|---|---|---|---|---|---|
| `capacity_factor_solar` | 0.23 | 0.25 | fraction | published | 2026-10 | 2027-10-31 |
| `capacity_factor_wind` | 0.335 | 0.382 | fraction | published | 2024-08 | 2026-12-31 |
| `capacity_price_kw_month_battery_storage` | 22 | 31 | USD per kW-month | assumption | 2026-07 | 2027-01-31 |
| `capex_per_mw_battery_storage` | 1,080,000 | 1,460,000 | USD per MW (4-hour) | published | 2026-07 | 2027-07-31 |
| `capex_per_mw_solar` | 1,690,000 | 1,770,000 | USD per MW (AC) | published | 2026-10 | 2027-10-31 |
| `capex_per_mw_wind` | 1,700,000 | 1,920,000 | USD per MW | published | 2024-08 | 2026-12-31 |
| `carrying_rate` | 0.056 | 0.09 | fraction per year (nominal) | assumption | 2026-08 | 2027-02-28 |
| `construction_escalation_battery_storage` | 0 | 0.04 | fraction per year (real) | assumption | 2026-10 | 2027-04-30 |
| `construction_escalation_solar` | 0.017 | 0.02 | fraction per year (real) | published | 2026-10 | 2027-10-31 |
| `construction_escalation_wind` | 0 | 0.02 | fraction per year (real) | assumption | 2024-08 | 2026-12-31 |
| `credit_rate` | 0.3 | 0.3 | fraction of capital cost | published | 2025-07 | 2027-05-31 |
| `fixed_om_kw_year_battery_storage` | 15 | 31 | USD per kW per year | published | 2026-07 | 2027-07-31 |
| `fixed_om_kw_year_solar` | 11 | 24.66 | USD per kW (AC) per year | published | 2026-10 | 2027-10-31 |
| `fixed_om_kw_year_wind` | 41.9 | 43 | USD per kW per year | published | 2026-08 | 2027-08-31 |
| `ppa_price_mwh_solar` | 34 | 64.23 | USD per MWh | published | 2026-10 | 2027-01-31 |
| `ppa_price_mwh_wind` | 25 | 68.27 | USD per MWh | published | 2026-10 | 2027-01-31 |
| `predevelopment_share` | 0.026 | 0.068 | fraction of capital cost | assumption | 2025-12 | 2026-12-31 |
| `project_life_years_battery_storage` | 15 | 20 | years | published | 2026-08 | 2027-07-31 |
| `project_life_years_solar` | 30 | 35 | years | published | 2026-10 | 2027-10-31 |
| `project_life_years_wind` | 30 | 30 | years | published | 2026-08 | 2027-08-31 |

Sources:

- `capacity_factor_solar`: LBNL Utility-Scale Solar 2026 Edition: slide 39, fleet 'cumulative net capacity factor ... is 23% but ranges from 6% to 40%'; slide 8, first-year capacity factor of 2024 plants rose 'from an average of 24% to 25%'. https://eta-publications.lbl.gov/sites/default/files/2026-10/utility_scale_solar_2026_edition_slides.pdf
- `capacity_factor_wind`: LBNL Land-Based Wind Market Report 2024 Edition, p. 7: 'The average capacity factor in 2023 was 33.5% on a fleet-wide basis and 38.2% among wind plants built in 2022.' https://eta-publications.lbl.gov/sites/default/files/land-based_wind_market_report_2024_edition_executive_summary.pdf
- `capacity_price_kw_month_battery_storage`: Assumption. No published tolling or capacity price was found. Revenue is set equal to Lazard LCOE+ (July 2026) unsubsidized levelized cost of 4-hour storage, $266-369 per kW-year (about $22-31 per kW-month): the revenue at which the project recovers its costs. https://www.lazard.com/media/kcfconhf/lazards-lcoeplus_vf.pdf
- `capex_per_mw_battery_storage`: Lazard LCOE+ (July 2026, LCOS v11.0), 4-hour utility-scale storage: 'Total Capital Cost $/kWh $270 - $365' (including inverter), times 4 hours. NLR 2025 ATB gives $1,449/kW for 2024, inside the range. https://www.lazard.com/media/kcfconhf/lazards-lcoeplus_vf.pdf
- `capex_per_mw_solar`: LBNL Utility-Scale Solar 2026 Edition, slide 31: 'Capacity-weighted means ... increased from $1.65/WAC in 2024 to $1.69/WAC in 2025. Medians ... increased from $1.74/WAC in 2024 to $1.77/WAC in 2025.' Low is the capacity-weighted mean, high the median. PV only; 2025 figures are preliminary. By size, slide 33 runs from $1.53/WAC (over 250 MW) to $2.10/WAC (under 20 MW). https://eta-publications.lbl.gov/sites/default/files/2026-10/utility_scale_solar_2026_edition_slides.pdf
- `capex_per_mw_wind`: Low: LBNL Land-Based Wind Market Report 2024 Edition, executive summary p. 8: installed costs 'since 2018, have largely held steady at ~$1,700/MW [per kW] on a capacity-weighted average basis' (2023 dollars; regional averages as low as $1,320/kW in SPP). High: NLR (formerly NREL) 2025 Electricity ATB workbook, land-based wind CAPEX $1,920/kW for 2024 (2023 dollars, Moderate scenario), https://data.openei.org/files/8759/2025_v1_Workbook_08-27-2026.xlsx. The LBNL 2025 and 2026 wind editions could not be opened on 2026-11-05; read the 2026 edition before relying on this range. https://eta-publications.lbl.gov/sites/default/files/land-based_wind_market_report_2024_edition_executive_summary.pdf
- `carrying_rate`: Assumption. Low: NLR 2025 ATB nominal WACC without tax credits, 5.63% for utility PV and 5.74% for land-based wind (Moderate, WACC Calc sheet). High: Hawthorn's allowance for merchant and storage risk; Lazard's storage case assumes 20% debt at 8% and 80% equity at 12%, about 11%. https://data.openei.org/files/8759/2025_v1_Workbook_08-27-2026.xlsx
- `construction_escalation_battery_storage`: Assumption. No source gives a year-over-year change in standalone storage capex. The high end is LBNL Utility-Scale Solar 2026 Edition, slide 12: 'Costs of PV+battery projects increased 4% to $2.7/WAC-PV in 2025.' https://eta-publications.lbl.gov/sites/default/files/2026-10/utility_scale_solar_2026_edition_slides.pdf
- `construction_escalation_solar`: LBNL Utility-Scale Solar 2026 Edition, slide 7: installed costs of new PV were '$1.7/WAC ... 2% higher than in 2024'; the median rose from $1.74 to $1.77/WAC (1.7%, slide 31). A change in real dollars: nominal escalation is higher by the rate of inflation. https://eta-publications.lbl.gov/sites/default/files/2026-10/utility_scale_solar_2026_edition_slides.pdf
- `construction_escalation_wind`: Assumption. LBNL Land-Based Wind Market Report 2024 Edition, p. 8, says installed cost has 'largely held steady' since 2018 (low end 0); the high end is the solar figure, since no wind source gives one. https://eta-publications.lbl.gov/sites/default/files/land-based_wind_market_report_2024_edition_executive_summary.pdf
- `credit_rate`: 26 U.S.C. 48E(a)(2): the applicable percentage is 6 percent, or 30 percent when the prevailing wage and apprenticeship requirements are met. Applied to the full per-MW capital cost, so it is an upper bound where qualified investment is smaller than installed cost; the energy community and domestic content adders are not included. https://www.law.cornell.edu/uscode/text/26/48E
- `fixed_om_kw_year_battery_storage`: Lazard LCOE+ (July 2026), 4-hour storage O&M $3.75-7.75 per kWh-year, times 4 hours. Lazard's figures, to match the revenue assumption taken from its levelized cost. NLR 2025 ATB puts fixed O&M at about $50/kW-year, including battery augmentation. https://www.lazard.com/media/kcfconhf/lazards-lcoeplus_vf.pdf
- `fixed_om_kw_year_solar`: Low: LBNL Utility-Scale Solar 2026 Edition, slide 36, O&M costs 'about $11/kWAC-year' (FERC Form 1 scope, without property tax, insurance or land). High: NLR 2025 ATB utility-scale PV page, '$24.66/kW AC-yr for 2024', https://atb.nlr.gov/electricity/2025/utility-scale_pv. https://eta-publications.lbl.gov/sites/default/files/2026-10/utility_scale_solar_2026_edition_slides.pdf
- `fixed_om_kw_year_wind`: NLR 2025 Electricity ATB workbook, land-based wind fixed O&M: $43.0/kW-year (2023 base year) and $41.9/kW-year (2024), 2023 dollars, Moderate scenario. https://data.openei.org/files/8759/2025_v1_Workbook_08-27-2026.xlsx
- `ppa_price_mwh_solar`: Low: LBNL Utility-Scale Solar 2026 Edition, slide 10, average levelized PPA price of 2025-COD projects, $34/MWh (25th to 75th percentile $27-47; contracts signed 1.5 to 4 years before operation). High: LevelTen North American PPA Price Index Q3 2026: 'Core-Markets P25 Solar Price ... rests at $64.23/MWh' (offers, not signed contracts), https://www.leveltenenergy.com/post/levelten-north-american-ppa-price-index-q3-2026. https://eta-publications.lbl.gov/sites/default/files/2026-10/utility_scale_solar_2026_edition_slides.pdf
- `ppa_price_mwh_wind`: Low: LBNL Land-Based Wind Market Report 2024 Edition, p. 8, recent levelized PPA prices '~$25/MWh' in the Central and West regions (2021-22 contracts; '~$45/MWh' in the East). High: LevelTen North American PPA Price Index Q3 2026: 'Core-Markets P25 Wind Price for Q3 came in at $68.27/MWh' (offers), https://www.leveltenenergy.com/post/levelten-north-american-ppa-price-index-q3-2026. https://www.leveltenenergy.com/post/levelten-north-american-ppa-price-index-q3-2026
- `predevelopment_share`: Assumption, taken from NREL/NLR Q1 2024 Solar Cost Benchmarks (PVSCM 2024, file 'UPV 2024Q1.txt'): 'Officework' (engineering, permits, interconnection, land outreach) of $32-69 per kWdc against a total of $1,021-1,212 per kWdc for a 100 MWdc single-axis project, 2.6% to 6.8%. Applied to wind and storage as well; network upgrade deposits are not in it. https://www.osti.gov/biblio/3007269
- `project_life_years_battery_storage`: NLR 2025 ATB utility-scale battery storage: '15-year lifetime' (low), https://atb.nlr.gov/electricity/2025/utility-scale_battery_storage. Lazard LCOE+ (July 2026): 'Project Life ... 20' years (high). https://www.lazard.com/media/kcfconhf/lazards-lcoeplus_vf.pdf
- `project_life_years_solar`: NLR 2025 ATB, financial cases and methods: cost recovery period '30 years for all technologies' (low). LBNL Utility-Scale Solar 2026 Edition, slide 45: 'Project design life increases from 21.5 years in 2007 to 35 years in 2021 and thereafter' (high). https://eta-publications.lbl.gov/sites/default/files/2026-10/utility_scale_solar_2026_edition_slides.pdf
- `project_life_years_wind`: NLR 2025 ATB, land-based wind and financial cases and methods: technical life and cost recovery period of 30 years. https://atb.nlr.gov/electricity/2025/financial_cases_&_methods

No anchor was past its re-verify-by date on 2026-11-05.
