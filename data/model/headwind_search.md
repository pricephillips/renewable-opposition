# Renewable Headwind Model: wide search over variables and combinations

Written by `scripts/headwind_search.py`. Do not edit by hand. Internal, staff only. Read `docs/headwind_model.md` first.

**What it tests.** Whether some combination of the county variables, searched widely, predicts which interconnection requests withdrew better than the request alone (year, size, technology, grid region), on later years the search never saw. Two searches: a sparse (lasso) logistic regression over the variables, their squares, every pair multiplied and each times each technology, and gradient-boosted trees over the variables. Each picks its settings and variables on earlier years only.

**The bar.** A search holds up only if it adds at least 0.01 AUC over the request-only model on average, adds something on every later period, and beats the same search run on shuffled county data in nearly all of 99 shuffles (p of 0.0125 or less: 0.05 divided by the 4 searches run). AUC is the chance that a withdrawn request, picked at random, scores above one that did not; 0.5 is a coin toss.

| Label | Search | Candidates | Gain by later period | Mean gain | Best shuffled gain (95th percentile) | p | Holds up |
|---|---|---:|---|---:|---:|---:|---|
| `withdrawn` | sparse logistic | 396 | 2015 to 2016: 0.041; 2017 to 2019: 0.080 | 0.061 | 0.017 | 0.01 | yes |
| `withdrawn` | boosted trees | 24 | 2015 to 2016: -0.020; 2017 to 2019: -0.103 | -0.061 | -0.048 | 0.36 | no |
| `withdrawn_3y` | sparse logistic | 396 | 2017 to 2018: -0.009; 2019 to 2022: 0.030 | 0.010 | 0.021 | 0.16 | no |
| `withdrawn_3y` | boosted trees | 24 | 2017 to 2018: -0.025; 2019 to 2022: 0.036 | 0.006 | -0.014 | 0.01 | no |

## Variables and combinations chosen in every later period, with the same sign

**`withdrawn`, sparse logistic** (holds up):

- the state's earlier requests: share withdrawn (smoothed) (more often withdrew)
- the county's earlier requests: share withdrawn (smoothed) times the state's earlier requests: share withdrawn (smoothed) (more often withdrew)

**`withdrawn`, boosted trees** (does not hold up):

- median household income (log)
- neighbouring counties' earlier requests: share withdrawn (smoothed)
- a local rule on the technology with no year
- the state's earlier requests: share withdrawn (smoothed)
- presidential margin before the request (Democratic minus Republican)
- log of per capita personal income in the county, the year before the request (BEA)
- share with a bachelor's degree
- population density (log)
- solar and wind MW already operating (log)
- county house price change over five years, as of the year before the request (FHFA)
- share of county establishments in agriculture support, the year before the request (County Business Patterns)
- the county's earlier requests: share withdrawn (smoothed)

**`withdrawn_3y`, sparse logistic** (does not hold up):

- county poverty rate, the year before the request (SAIPE) times storage (less often withdrew)
- county house price change over five years, as of the year before the request (FHFA) (squared) (more often withdrew)

**`withdrawn_3y`, boosted trees** (does not hold up):

- neighbouring counties' earlier requests: share withdrawn (smoothed)
- log of per capita personal income in the county, the year before the request (BEA)
- population density (log)
- log of county employment, the year before the request (County Business Patterns)
- share of county establishments in construction, the year before the request (County Business Patterns)
- log of county median household income, the year before the request (SAIPE)
- the county's earlier requests: how many (log)
- the county's earlier requests: share withdrawn (smoothed)

## Limits

- Withdrawal is the outcome, and most withdrawals have market or grid reasons. A variable that holds up describes requests that withdrew, not opposition.
- Only two later periods per label are scored, so a gain that holds up rests on few periods.
- With 99 shuffles the smallest p possible is 0.01, so a pass means the real search beat every shuffle or all but one.
