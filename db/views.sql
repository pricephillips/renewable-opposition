-- National database: the views the dashboard and any downstream user read.
--
-- Every count here is a count of instruments (one ordinance, moratorium,
-- project or case), never of rows. scripts/build_database.py checks the
-- headline views against data/processed/headline_metrics.json on every build
-- and refuses to write a database that disagrees with it.

-- Headline numbers ----------------------------------------------------------

-- headline_metrics.restrictions.by_scope
CREATE VIEW v_headline_restrictions AS
SELECT scope,
       count(*)                                         AS instruments,
       count(*) FILTER (WHERE is_severe)                AS severe_instruments,
       count(DISTINCT state_code)                       AS states,
       count(*) FILTER (WHERE verification = 'verified')   AS verified,
       count(*) FILTER (WHERE verification = 'located')    AS located,
       count(*) FILTER (WHERE verification = 'unverified') AS unverified
FROM restriction_instrument
GROUP BY scope;

-- headline_metrics.restrictions.by_source and contested_projects.by_source
CREATE VIEW v_headline_by_source AS
SELECT 'restrictions' AS entity, source_family,
       count(*) AS instruments,
       count(*) FILTER (WHERE is_severe) AS severe_instruments,
       count(*) FILTER (WHERE verification = 'verified')   AS verified,
       count(*) FILTER (WHERE verification = 'located')    AS located,
       count(*) FILTER (WHERE verification = 'unverified') AS unverified
FROM restriction_instrument GROUP BY source_family
UNION ALL
SELECT 'contested_projects', source_family,
       count(*),
       count(*) FILTER (WHERE severity_score >= 3),
       count(*) FILTER (WHERE verification = 'verified'),
       count(*) FILTER (WHERE verification = 'located'),
       count(*) FILTER (WHERE verification = 'unverified')
FROM contested_project GROUP BY source_family;

-- headline_metrics.county_coverage
CREATE VIEW v_county_coverage_totals AS
WITH u AS (SELECT county_fips FROM county WHERE in_coverage_universe),
rec AS (
    SELECT DISTINCT county_fips, entity FROM record_county
)
SELECT
    (SELECT count(*) FROM u) AS counties,
    (SELECT count(DISTINCT county_fips) FROM rec WHERE county_fips IN (SELECT * FROM u)) AS with_any_record,
    (SELECT count(DISTINCT county_fips) FROM rec WHERE entity = 'restriction'
        AND county_fips IN (SELECT * FROM u)) AS with_restriction,
    (SELECT count(DISTINCT county_fips) FROM rec WHERE entity = 'contested_project'
        AND county_fips IN (SELECT * FROM u)) AS with_contested_project,
    (SELECT count(DISTINCT county_fips) FROM rec WHERE entity = 'siting_standard'
        AND county_fips IN (SELECT * FROM u)) AS with_siting_standard,
    (SELECT count(DISTINCT county_fips) FROM negative_check
        WHERE county_fips IN (SELECT * FROM u)) AS with_negative_check,
    (SELECT count(*) FROM u WHERE county_fips NOT IN (SELECT county_fips FROM rec)
        AND county_fips NOT IN (SELECT county_fips FROM negative_check)) AS with_neither;

-- One row per county: the map's and the county page's spine ----------------

-- coverage_status keeps three states apart, because the map must never paint
-- an unexamined county as if it had nothing:
--   has_records   at least one published record placed in the county
--   checked_none  a documented negative check and no record
--   not_examined  neither; nothing is known either way
CREATE VIEW v_county_summary AS
WITH r AS (
    SELECT rc.county_fips,
           count(DISTINCT ri.instrument_id) FILTER (WHERE ri.scope = 'renewables_only') AS restrictions,
           count(DISTINCT ri.instrument_id) FILTER (WHERE ri.scope = 'renewables_only' AND ri.is_severe)
               AS severe_restrictions,
           count(DISTINCT ri.instrument_id) FILTER (WHERE ri.scope = 'renewables_only'
               AND ri.verification = 'verified') AS verified_restrictions,
           count(DISTINCT ri.instrument_id) FILTER (WHERE ri.scope = 'multi_sector_data_centers')
               AS multi_sector_restrictions,
           count(DISTINCT ri.instrument_id) FILTER (WHERE ri.scope = 'renewables_only'
               AND 'moratorium' = ANY (ri.restriction_types) AND ri.status IN ('active', 'extended'))
               AS active_moratoria,
           max(ri.severity_score) AS max_severity
    FROM record_county rc
    JOIN restriction_instrument ri ON rc.entity = 'restriction' AND rc.record_id = ri.instrument_id
    GROUP BY rc.county_fips
), p AS (
    SELECT rc.county_fips,
           count(*) AS contested_projects,
           count(*) FILTER (WHERE cp.outcome_class = 'blocked') AS blocked_projects,
           count(*) FILTER (WHERE cp.outcome_confirmed) AS confirmed_outcomes,
           count(*) FILTER (WHERE cp.verification = 'verified') AS verified_projects
    FROM record_county rc
    JOIN contested_project cp ON rc.entity = 'contested_project' AND rc.record_id = cp.instrument_id
    GROUP BY rc.county_fips
), s AS (
    SELECT county_fips, count(*) AS siting_standard_rows
    FROM record_county WHERE entity = 'siting_standard' GROUP BY county_fips
), n AS (
    SELECT county_fips, max(checked_on) AS last_negative_check FROM negative_check GROUP BY county_fips
), d AS (
    SELECT county_fips, count(*) AS data_center_events FROM data_center_event GROUP BY county_fips
)
SELECT c.county_fips, c.state_code, c.county_name, c.in_coverage_universe,
       coalesce(r.restrictions, 0)              AS restrictions,
       coalesce(r.severe_restrictions, 0)       AS severe_restrictions,
       coalesce(r.verified_restrictions, 0)     AS verified_restrictions,
       coalesce(r.multi_sector_restrictions, 0) AS multi_sector_restrictions,
       coalesce(r.active_moratoria, 0)          AS active_moratoria,
       r.max_severity,
       coalesce(p.contested_projects, 0)        AS contested_projects,
       coalesce(p.blocked_projects, 0)          AS blocked_projects,
       coalesce(p.confirmed_outcomes, 0)        AS confirmed_outcomes,
       coalesce(p.verified_projects, 0)         AS verified_projects,
       coalesce(s.siting_standard_rows, 0)      AS siting_standard_rows,
       coalesce(d.data_center_events, 0)        AS data_center_events,
       coalesce(q.candidates, 0)                AS pending_review,
       n.last_negative_check,
       CASE
           WHEN r.county_fips IS NOT NULL OR p.county_fips IS NOT NULL OR s.county_fips IS NOT NULL
               THEN 'has_records'
           WHEN n.county_fips IS NOT NULL THEN 'checked_none'
           ELSE 'not_examined'
       END AS coverage_status
FROM county c
LEFT JOIN r USING (county_fips)
LEFT JOIN p USING (county_fips)
LEFT JOIN s USING (county_fips)
LEFT JOIN n USING (county_fips)
LEFT JOIN d USING (county_fips)
LEFT JOIN county_pending_review q USING (county_fips);

-- One row per state ----------------------------------------------------------

CREATE VIEW v_state_summary AS
WITH r AS (
    SELECT state_code,
           count(*) FILTER (WHERE scope = 'renewables_only') AS restrictions,
           count(*) FILTER (WHERE scope = 'renewables_only' AND is_severe) AS severe_restrictions,
           count(*) FILTER (WHERE scope = 'renewables_only' AND verification = 'verified')
               AS verified_restrictions,
           count(*) FILTER (WHERE scope = 'multi_sector_data_centers') AS multi_sector_restrictions
    FROM restriction_instrument GROUP BY state_code
), p AS (
    SELECT state_code, count(*) AS contested_projects,
           count(*) FILTER (WHERE outcome_class = 'blocked') AS blocked_projects,
           count(*) FILTER (WHERE outcome_confirmed) AS confirmed_outcomes
    FROM contested_project GROUP BY state_code
), k AS (
    SELECT state_code, count(*) AS cases FROM legal_case GROUP BY state_code
), sp AS (
    SELECT state_code, count(*) AS state_policies FROM state_policy GROUP BY state_code
), cov AS (
    SELECT state_code, count(*) AS counties,
           count(*) FILTER (WHERE coverage_status = 'has_records') AS counties_with_records,
           count(*) FILTER (WHERE coverage_status = 'checked_none') AS counties_checked_none,
           count(*) FILTER (WHERE coverage_status = 'not_examined') AS counties_not_examined
    FROM v_county_summary GROUP BY state_code
)
SELECT s.state_code, s.state_name,
       coalesce(r.restrictions, 0) AS restrictions,
       coalesce(r.severe_restrictions, 0) AS severe_restrictions,
       coalesce(r.verified_restrictions, 0) AS verified_restrictions,
       coalesce(r.multi_sector_restrictions, 0) AS multi_sector_restrictions,
       coalesce(p.contested_projects, 0) AS contested_projects,
       coalesce(p.blocked_projects, 0) AS blocked_projects,
       coalesce(p.confirmed_outcomes, 0) AS confirmed_outcomes,
       coalesce(k.cases, 0) AS cases,
       coalesce(sp.state_policies, 0) AS state_policies,
       coalesce(cov.counties, 0) AS counties,
       coalesce(cov.counties_with_records, 0) AS counties_with_records,
       coalesce(cov.counties_checked_none, 0) AS counties_checked_none,
       coalesce(cov.counties_not_examined, 0) AS counties_not_examined
FROM state s
LEFT JOIN r USING (state_code)
LEFT JOIN p USING (state_code)
LEFT JOIN k USING (state_code)
LEFT JOIN sp USING (state_code)
LEFT JOIN cov USING (state_code);

-- Timeline: restrictions by the month they were enacted. Most instruments
-- carry no enactment date (NREL rows never do), so the view also reports how
-- many it could not place in time.
CREATE VIEW v_restrictions_by_month AS
SELECT CAST(date_trunc('month', date_enacted) AS DATE) AS month, scope,
       count(*) AS instruments,
       count(*) FILTER (WHERE is_severe) AS severe_instruments
FROM restriction_instrument
WHERE date_enacted IS NOT NULL
GROUP BY ALL
UNION ALL
SELECT NULL, scope, count(*), count(*) FILTER (WHERE is_severe)
FROM restriction_instrument
WHERE date_enacted IS NULL
GROUP BY scope;
