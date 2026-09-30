# Column coverage

Each published CSV against the previous commit. A column with at least 20 values fails when its fill rate drops by more than 20 percent.

Declared drops (config/coverage_exceptions.json):

- contested_projects.csv `municipality`: 22 -> 17. REC-0190 to REC-0194 carried the project name in municipality; build_sabin_seeds.py now moves it to project_name.

No column collapsed (4 files compared).
