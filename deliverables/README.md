# Deliverables

Reports meant for a client live here so that the prose rules apply to them:
Vale (`.vale.ini`, the Hawthorn style) and the em-dash pre-commit hook cover
`deliverables/**/*.md`. The layout follows `pricephillips/data-center-map`'s
`deliverables/` folder.

- `county_reports/` holds county reports written by `scripts/site_profile.py`
  with `--out`. Re-run rather than edit: every figure comes from the
  repository's data files at run time, and each report's "Sources and method"
  section names the files it read, their hashes and the commit.
- Hand-written briefs can sit in their own subfolder.

A report is final only when Vale and the em-dash check pass. A county report
never carries a score or a prediction, and it never names the local-knowledge
file: what local contacts report prints inside the section it concerns,
labelled "reported, not verified", and is not committed anywhere.

Whether a report is committed is a decision for each engagement. Nothing here
is needed by the build or the dashboard.
