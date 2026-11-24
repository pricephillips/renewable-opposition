# Bill outcome model: what followed past state laws

Built 2026-11-24 from commit 3bf1ef2 with config/bill_outlook.json (core format 1).

For each kind of state law, this report lists the past laws of that kind with a sourced effective date (the precedents). For each one it compares the state's record in the 12 months after the law with the 12 months before it, against the same change in comparison states over the same months. Comparison states are those with no law of the same kind taking effect in that span. A score is a direction from -2 to +2 and describes resemblance to past records only. The record does not show that a law produced what followed.

Events counted: local_restriction 2471, project_advanced 121, project_blocked 234, queue_operating 1292, queue_withdrawn 9518. An event dated only by year is counted only when the whole year falls inside one window. Recent months are less complete than older ones in every state, which the comparison states partly offset.

## limits_local

A state law that limits what local governments may do to solar, wind or storage siting (preemption of local rules, caps on local moratoria, state approval in place of local approval).

| Measure | Score | Reading | Usable precedents | Leave-one-out check |
|---|---|---|---|---|
| Local restrictions adopted |  | too few dated precedents | 1 of 6 | not_testable |
| Share of decided contested projects that were blocked |  | too few dated precedents | 0 of 6 | not_testable |
| Share of interconnection requests closed by withdrawal rather than operation | +0 | precedents point different ways | 3 of 6 | not_testable |

| Precedent | Measure | Status | State before, after | Change against comparison | Direction |
|---|---|---|---|---|---|
| MI-2023-PA-233 (MI, 2024-11-29) | Local restrictions adopted | thin | 0, 1 |  |  |
| IN-2025-SEA-425 (IN, 2025-07-01) | Local restrictions adopted | ok | 0, 8 | +2.11 (log ratio) | +1 |
| MD-2025-SB-931 (MD, 2025-07-01) | Local restrictions adopted | thin | 0, 0 |  |  |
| MA-2024-c239-69T (MA, 2026-03-01) | Local restrictions adopted | too_recent |  |  |  |
| IL-PA-104-458 (IL, 2026-06-01) | Local restrictions adopted | too_recent |  |  |  |
| MS-2026-SB-2527 (MS, 2026-07-01) | Local restrictions adopted | too_recent |  |  |  |
| MI-2023-PA-233 (MI, 2024-11-29) | Share of decided contested projects that were blocked | thin | 0/0, 0/0 |  |  |
| IN-2025-SEA-425 (IN, 2025-07-01) | Share of decided contested projects that were blocked | thin | 1/2, 0/1 |  |  |
| MD-2025-SB-931 (MD, 2025-07-01) | Share of decided contested projects that were blocked | thin | 0/2, 0/1 |  |  |
| MA-2024-c239-69T (MA, 2026-03-01) | Share of decided contested projects that were blocked | too_recent |  |  |  |
| IL-PA-104-458 (IL, 2026-06-01) | Share of decided contested projects that were blocked | too_recent |  |  |  |
| MS-2026-SB-2527 (MS, 2026-07-01) | Share of decided contested projects that were blocked | too_recent |  |  |  |
| MI-2023-PA-233 (MI, 2024-11-29) | Share of interconnection requests closed by withdrawal rather than operation | ok | 3/4, 35/35 | +10 points | +1 |
| IN-2025-SEA-425 (IN, 2025-07-01) | Share of interconnection requests closed by withdrawal rather than operation | ok | 87/91, 86/87 | +0 points | +0 |
| MD-2025-SB-931 (MD, 2025-07-01) | Share of interconnection requests closed by withdrawal rather than operation | ok | 26/31, 9/11 | -6 points | +0 |
| MA-2024-c239-69T (MA, 2026-03-01) | Share of interconnection requests closed by withdrawal rather than operation | too_recent |  |  |  |
| IL-PA-104-458 (IL, 2026-06-01) | Share of interconnection requests closed by withdrawal rather than operation | too_recent |  |  |  |
| MS-2026-SB-2527 (MS, 2026-07-01) | Share of interconnection requests closed by withdrawal rather than operation | too_recent |  |  |  |

## state_standards

A state law that sets siting standards (setbacks, height, noise) that apply in place of or beside local ones.

| Measure | Score | Reading | Usable precedents | Leave-one-out check |
|---|---|---|---|---|
| Local restrictions adopted |  | too few dated precedents | 0 of 2 | not_testable |
| Share of decided contested projects that were blocked |  | too few dated precedents | 0 of 2 | not_testable |
| Share of interconnection requests closed by withdrawal rather than operation |  | too few dated precedents | 0 of 2 | not_testable |

| Precedent | Measure | Status | State before, after | Change against comparison | Direction |
|---|---|---|---|---|---|
| CT-PA-24-144 (CT, 2024-10-01) | Local restrictions adopted | thin | 0, 0 |  |  |
| LA-2025-HB-459 (LA, 2025-08-01) | Local restrictions adopted | thin | 0, 1 |  |  |
| CT-PA-24-144 (CT, 2024-10-01) | Share of decided contested projects that were blocked | thin | 0/0, 2/3 |  |  |
| LA-2025-HB-459 (LA, 2025-08-01) | Share of decided contested projects that were blocked | thin | 0/0, 2/2 |  |  |
| CT-PA-24-144 (CT, 2024-10-01) | Share of interconnection requests closed by withdrawal rather than operation | thin | 0/0, 0/0 |  |  |
| LA-2025-HB-459 (LA, 2025-08-01) | Share of interconnection requests closed by withdrawal rather than operation | thin | 83/83, 1/1 |  |  |

## expands_local

A state law that gives local governments new power to bar or restrict projects (opt-out or restricted-area laws).

| Measure | Score | Reading | Usable precedents | Leave-one-out check |
|---|---|---|---|---|
| Local restrictions adopted |  | too few dated precedents | 0 of 1 | not_testable |
| Share of decided contested projects that were blocked |  | too few dated precedents | 0 of 1 | not_testable |
| Share of interconnection requests closed by withdrawal rather than operation |  | too few dated precedents | 1 of 1 | not_testable |

| Precedent | Measure | Status | State before, after | Change against comparison | Direction |
|---|---|---|---|---|---|
| OH-2021-SB-52 (OH, 2021-10-11) | Local restrictions adopted | thin | 0, 0 |  |  |
| OH-2021-SB-52 (OH, 2021-10-11) | Share of decided contested projects that were blocked | thin | 0/0, 1/1 |  |  |
| OH-2021-SB-52 (OH, 2021-10-11) | Share of interconnection requests closed by withdrawal rather than operation | ok | 22/26, 23/23 | +19 points | +1 |

## state_ban

A state law that itself bars a technology in some places.

| Measure | Score | Reading | Usable precedents | Leave-one-out check |
|---|---|---|---|---|
| Local restrictions adopted |  | too few dated precedents | 0 of 2 | not_testable |
| Share of decided contested projects that were blocked |  | too few dated precedents | 0 of 2 | not_testable |
| Share of interconnection requests closed by withdrawal rather than operation |  | too few dated precedents | 2 of 2 | not_testable |

| Precedent | Measure | Status | State before, after | Change against comparison | Direction |
|---|---|---|---|---|---|
| ME-PL-2021-c407 (ME, 2021-07-06) | Local restrictions adopted | thin | 0, 0 |  |  |
| FL-2024-HB-1645 (FL, 2024-07-01) | Local restrictions adopted | thin | 0, 0 |  |  |
| ME-PL-2021-c407 (ME, 2021-07-06) | Share of decided contested projects that were blocked | thin | 0/0, 0/1 |  |  |
| FL-2024-HB-1645 (FL, 2024-07-01) | Share of decided contested projects that were blocked | thin | 0/0, 0/0 |  |  |
| ME-PL-2021-c407 (ME, 2021-07-06) | Share of interconnection requests closed by withdrawal rather than operation | ok | 16/16, 5/5 | +3 points | +0 |
| FL-2024-HB-1645 (FL, 2024-07-01) | Share of interconnection requests closed by withdrawal rather than operation | ok | 2/29, 0/26 | -15 points | -1 |

## Tracked bills

No bill is listed in config/bill_outlook.json yet. Add one entry per bill (id, state, group, source_url) and rebuild. Its passes branch is the pooled score of its group above, and its fails branch is the state's recent record below.

## Recent record by state (the fails branch)

The last window against the window before it, compared with the same change in all other states.

| State | Local restrictions adopted | Share of decided contested projects that were blocked | Share of interconnection requests closed by withdrawal rather than operation |
|---|---|---|---|
| AK | thin | thin | thin |
| AL | thin | thin | thin |
| AR | thin | thin | thin |
| AZ | thin | thin | thin |
| CA | -1 -0.93 (log ratio) | thin | thin |
| CO | -1 -0.94 (log ratio) | thin | thin |
| CT | thin | thin | thin |
| DE | thin | thin | thin |
| FL | thin | thin | thin |
| GA | thin | thin | thin |
| HI | thin | thin | thin |
| IA | +0 -0.27 (log ratio) | thin | thin |
| ID | thin | thin | thin |
| IL | +0 +0.33 (log ratio) | thin | +1 +13 points |
| IN | +0 +0.20 (log ratio) | thin | +1 +16 points |
| KS | +1 +2.97 (log ratio) | thin | thin |
| KY | -1 -0.93 (log ratio) | thin | +1 +14 points |
| LA | thin | thin | thin |
| MA | thin | thin | thin |
| MD | thin | thin | thin |
| ME | -1 -1.44 (log ratio) | thin | thin |
| MI | +1 +2.91 (log ratio) | thin | thin |
| MN | thin | thin | thin |
| MO | +1 +2.28 (log ratio) | thin | +1 +12 points |
| MS | thin | thin | thin |
| MT | thin | thin | thin |
| NC | thin | thin | -1 -62 points |
| ND | thin | thin | -1 -19 points |
| NE | +0 +0.20 (log ratio) | thin | thin |
| NH | thin | thin | thin |
| NJ | thin | thin | thin |
| NM | thin | thin | thin |
| NV | thin | thin | thin |
| NY | -1 -0.78 (log ratio) | thin | thin |
| OH | +1 +1.51 (log ratio) | thin | thin |
| OK | thin | thin | thin |
| OR | thin | thin | thin |
| PA | +1 +1.31 (log ratio) | thin | +1 +19 points |
| PR | thin | thin | thin |
| RI | thin | thin | thin |
| SC | +1 +1.05 (log ratio) | thin | thin |
| SD | thin | thin | thin |
| TN | thin | thin | thin |
| TX | thin | thin | +0 -1 points |
| UT | thin | thin | thin |
| VA | thin | thin | -1 -37 points |
| VT | thin | thin | thin |
| WA | +0 -0.15 (log ratio) | thin | thin |
| WI | thin | thin | thin |
| WV | thin | thin | thin |
| WY | thin | thin | thin |
