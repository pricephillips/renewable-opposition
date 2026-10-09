# Column coverage

Each published CSV against the previous commit. A column with at least 20 values fails when its fill rate drops by more than 20 percent.

Every declared floor holds (7 checked).

Declared drops (config/coverage_exceptions.json):

- restrictions.csv `date_enacted_iso`: 264 -> 264. 2026-10-09: the column keeps 264 values (264 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- restrictions.csv `long_description`: 335 -> 553. 2026-10-09: the column keeps 553 values (335 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- restrictions.csv `moratorium_id`: 286 -> 286. 2026-10-09: the column keeps 286 values (286 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- restrictions.csv `source_record_id`: 323 -> 934. 2026-10-09: the column keeps 934 values (323 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- restrictions.csv `current_end_date_iso`: 49 -> 49. 2026-10-09: the column keeps 49 values (49 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- restrictions.csv `latitude`: 286 -> 286. 2026-10-09: the column keeps 286 values (286 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- restrictions.csv `longitude`: 286 -> 286. 2026-10-09: the column keeps 286 values (286 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- restrictions.csv `needs_verification`: 87 -> 87. 2026-10-09: the column keeps 87 values (87 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- restrictions.csv `sectors`: 286 -> 286. 2026-10-09: the column keeps 286 values (286 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- restrictions.csv `legal_basis`: 275 -> 275. 2026-10-09: the column keeps 275 values (275 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- restrictions.csv `primary_source_verdict`: 65 -> 92. 2026-10-09: the column keeps 92 values (65 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- restrictions.csv `primary_source_access`: 65 -> 92. 2026-10-09: the column keeps 92 values (65 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- restrictions.csv `primary_source_url`: 65 -> 92. 2026-10-09: the column keeps 92 values (65 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- restrictions.csv `primary_source_checked_on`: 57 -> 84. 2026-10-09: the column keeps 84 values (57 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- contested_projects.csv `opposition_type`: 160 -> 304. 2026-10-09: the column keeps 304 values (160 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- contested_projects.csv `opposition_groups`: 30 -> 28. 2026-10-09: the column keeps 28 values (28 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- contested_projects.csv `group_sources`: 30 -> 28. 2026-10-09: the column keeps 28 values (28 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- contested_projects.csv `resolution_url`: 116 -> 116. 2026-10-09: the column keeps 116 values (116 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- contested_projects.csv `resolution_access`: 116 -> 116. 2026-10-09: the column keeps 116 values (116 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.
- contested_projects.csv `resolution_date`: 114 -> 114. 2026-10-09: the column keeps 114 values (114 before) while the file gained rows: the Sabin September 2026 edition and 2,393 NREL restrictions, which do not carry this field. Not a loss of values.

No column collapsed (4 files compared).
