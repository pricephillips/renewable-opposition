# Cost of a siting slip: solar, wind and storage

Generated 2026-11-05 by `scripts/cost_cfo.py`. **Internal, not for client delivery.** No
decision has been made about quoting these figures outside the company (for the data center rate
card, Price made that decision on 2026-10-27); until one is, every section stays internal.

These are unit costs at published rates for a project whose schedule slips, whatever the reason.
They do not measure what opposition does to a project, and no probability of a slip or a block is
multiplied into them. Every figure is a low-high range. Apply your own slip scenario to your own
site.

## One month of slip, per MW (national rates)

Delay cost is construction escalation plus the economic cost of deferring the project's net
revenue. Capital at risk is the development spending a blocked site leaves behind before
construction starts.

| Technology | Delay cost per MW per month | of which escalation | of which deferral | Capital at risk per MW if blocked |
|---|---|---|---|---|
| Solar PV | $5K to $13K | $2K to $3K | $3K to $10K | $44K to $120K |
| Land-based wind | $2K to $17K | $0 to $3K | $2K to $14K | $44K to $131K |
| Battery storage | $11K to $28K | $0 to $5K | $11K to $23K | $28K to $99K |

Gross revenue deferred, for comparison only (revenue that arrives later, not a cost, and never added to the delay cost): solar PV $6K to $12K per MW per month; land-based wind $6K to $19K per MW per month; battery storage $22K to $31K per MW per month.

## A 100 MW project, national rates

**Solar PV**

| Slip | Escalation | Deferral | Delay cost |
|---|---|---|---|
| 3 months | $718K to $885K | $853K to $2.9M | $1.6M to $3.8M |
| 6 months | $1.4M to $1.8M | $1.7M to $5.8M | $3.1M to $7.5M |
| 12 months | $2.9M to $3.5M | $3.3M to $11.3M | $6.2M to $14.9M |
| 18 months | $4.3M to $5.3M | $4.9M to $16.6M | $9.3M to $21.9M |
| 24 months | $5.7M to $7.1M | $6.5M to $21.7M | $12.3M to $28.8M |

**Land-based wind**

| Slip | Escalation | Deferral | Delay cost |
|---|---|---|---|
| 3 months | $0 to $960K | $591K to $4.1M | $591K to $5.0M |
| 6 months | $0 to $1.9M | $1.2M to $8.1M | $1.2M to $10.0M |
| 12 months | $0 to $3.8M | $2.3M to $15.8M | $2.3M to $19.7M |
| 18 months | $0 to $5.8M | $3.4M to $23.2M | $3.4M to $29.0M |
| 24 months | $0 to $7.7M | $4.5M to $30.3M | $4.5M to $38.0M |

**Battery storage**

| Slip | Escalation | Deferral | Delay cost |
|---|---|---|---|
| 3 months | $0 to $1.5M | $3.1M to $6.9M | $3.1M to $8.4M |
| 6 months | $0 to $2.9M | $6.2M to $13.7M | $6.2M to $16.7M |
| 12 months | $0 to $5.8M | $12.3M to $26.9M | $12.3M to $32.7M |
| 18 months | $0 to $8.8M | $18.2M to $39.5M | $18.2M to $48.3M |
| 24 months | $0 to $11.7M | $24.0M to $51.6M | $24.0M to $63.3M |

Every component scales with MW; `data/cost/cost_scenarios.csv` has each technology.

## Federal tax credit deadlines

The clean electricity credits change at a date rather than by the month: a project that
misses a deadline loses the credit. The rate card's
credit column is the per-MW capital cost times the credit rate, the credit at stake at the
deadline for a project that would otherwise qualify. Whether a given project qualifies is a
tax question for the project's own counsel.

| Applies to | Rule | Date | Source |
|---|---|---|---|
| solar PV, land-based wind | Construction must begin by this date for the 2027 placed-in-service cutoff not to apply (Public Law 119-21 sections 70512 and 70513; IRS Notice 2025-42: the physical work test is the only method, and the 5% safe harbor is kept only for solar of 1.5 MW AC or less). | 2026-07-04 (passed) | https://www.irs.gov/pub/irs-drop/n-25-42.pdf |
| solar PV, land-based wind | A wind or solar facility whose construction begins after 2026-07-04 gets no 45Y or 48E credit if placed in service after this date | 2027-12-31 | https://www.govinfo.gov/content/pkg/PLAW-119publ21/pdf/PLAW-119publ21.pdf |
| solar PV, land-based wind | A facility whose construction began by 2026-07-04 keeps the continuity safe harbor if placed in service no more than four calendar years after the year construction began (end of 2030 for construction begun in 2026) | 2030-12-31 | https://www.irs.gov/pub/irs-drop/n-25-42.pdf |
| battery storage | Energy storage is exempt from the 2027 cutoff; its credit is the full credit for construction beginning by the end of 2033, 75% in 2034, 50% in 2035 and none after (applicable year 2032) | 2034-01-01 | https://www.govinfo.gov/content/pkg/PLAW-119publ21/pdf/PLAW-119publ21.pdf |

| Technology | Credit at stake per MW |
|---|---|
| Solar PV | $507K to $531K |
| Land-based wind | $510K to $576K |

## Which assumption moves the delay cost most

A 100 MW project slipping 12 months, national rates, every anchor at its midpoint except the one moved from its low to its high value. Largest swing first.

**Solar PV**

| Anchor | Confidence | At its low | At its high | Swing |
|---|---|---|---|---|
| `ppa_price_mwh_solar` | published | $7.7M | $13.0M | $5.3M |
| `fixed_om_kw_year_solar` | published | $10.9M | $9.8M | $1.1M |
| `capacity_factor_solar` | published | $10.0M | $10.7M | $721K |
| `carrying_rate` | assumption | $9.9M | $10.6M | $648K |
| `construction_escalation_solar` | published | $10.1M | $10.6M | $519K |
| `project_life_years_solar` | published | $10.2M | $10.5M | $286K |
| `capex_per_mw_solar` | published | $10.3M | $10.4M | $148K |

**Land-based wind**

| Anchor | Confidence | At its low | At its high | Swing |
|---|---|---|---|---|
| `ppa_price_mwh_wind` | published | $4.8M | $15.9M | $11.1M |
| `construction_escalation_wind` | assumption | $8.5M | $12.1M | $3.6M |
| `capacity_factor_wind` | published | $9.5M | $11.1M | $1.6M |
| `carrying_rate` | assumption | $9.7M | $10.6M | $894K |
| `capex_per_mw_wind` | published | $10.2M | $10.4M | $220K |
| `fixed_om_kw_year_wind` | published | $10.4M | $10.3M | $90K |
| `project_life_years_wind` | published | $10.3M | $10.3M | $0 |

**Battery storage**

| Anchor | Confidence | At its low | At its high | Swing |
|---|---|---|---|---|
| `capacity_price_kw_month_battery_storage` | assumption | $18.5M | $25.6M | $7.1M |
| `construction_escalation_battery_storage` | assumption | $19.5M | $24.6M | $5.1M |
| `carrying_rate` | assumption | $19.7M | $23.6M | $3.9M |
| `project_life_years_battery_storage` | published | $20.5M | $23.3M | $2.8M |
| `fixed_om_kw_year_battery_storage` | published | $22.5M | $21.5M | $1.1M |
| `capex_per_mw_battery_storage` | published | $21.6M | $22.4M | $760K |

## How long these spans have run (observed, descriptive)

From `data/cost/cost_ledger.csv`: the recorded span from a contested project's first
interconnection request to its decision, for the priced rows with a confirmed outcome. These
are the tracked sample's own histories, not a forecast and not an effect of opposition; most
contested projects have no dated first request and are not in it.

| Technology | Projects | First quartile | Median | Third quartile |
|---|---|---|---|---|
| Solar PV | 19 | 4.3 years | 6.3 years | 7.5 years |
| Land-based wind | 17 | 4.4 years | 7.0 years | 9.7 years |
| Battery storage | 2 (few projects) | 5.0 years | 5.3 years | 5.6 years |

## Assumptions and sources

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

Hawthorn's assumptions, not published figures, each with its basis in the methodology: `capacity_price_kw_month_battery_storage`, `carrying_rate`, `construction_escalation_battery_storage`, `construction_escalation_wind`, `predevelopment_share`. Sources and what each figure includes: `data/cost/cost_methodology.md`.

No anchor was past its re-verify date on 2026-11-05. The next one due is `capex_per_mw_wind`, on 2026-12-31.

## Applying these to a site

1. Pick the technology and the site's MW. Multiply the per-MW figures by the MW.
2. Choose the slip you want to price (months) and multiply the per-month delay cost by it; for a
   long slip, read `data/cost/cost_scenarios.csv` instead: the deferral cost grows a little less
   than in proportion to the slip, so months times the monthly figure overstates it.
3. If the site could be blocked, the development capital at risk is the per-MW figure times the MW.
4. For solar and wind, check the slip against the tax credit deadlines above: a slip that crosses
   one puts the credit at stake, whatever its length.
5. Keep gross revenue deferred out of any total.
