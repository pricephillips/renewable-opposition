# Column coverage

Each published CSV against the previous commit. A column with at least 20 values fails when its fill rate drops by more than 20 percent.

Every declared floor holds (7 checked).

Declared drops (config/coverage_exceptions.json):

- contested_projects.csv `facility_conflict`: 24 -> 18. 2026-11-05: the verification runs of 2026-10-31 to 2026-11-03 read sources moving six projects from pending to advanced_confirmed (S26P-3921 Torrington Solar CT, S26P-3958 Goose Creek Wind IL, S26P-4120 Platteview Solar NE, S26P-4203 Border Basin Solar OH, S26P-4214 Great Bend Solar OH, S26P-4226 Yellow Wood Solar OH). Each plant is operating or under construction, so the published outcome now agrees with the plant's status and the conflict clears. No row was lost and no new conflict appeared.

No column collapsed (4 files compared).
