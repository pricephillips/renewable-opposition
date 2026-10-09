-- National database: fill the tables in schema.sql from the staging tables.
--
-- scripts/build_database.py creates the staging tables first, every column
-- VARCHAR, one per input file:
--   stg_restrictions, stg_contested_projects, stg_cases, stg_siting_standards,
--   stg_state_policies, stg_sources, stg_group_registry, stg_negative_checks,
--   stg_data_center_events
-- plus the ones it computes in Python with the pipeline's own helpers:
--   stg_state (state_code, state_name, state_fips)
--   stg_county (county_fips, county_name)
--   stg_county_adjacency (county_fips, neighbor_fips)
--   stg_jurisdiction_key (state, jurisdiction_type, jurisdiction, jurisdiction_key, kind)
--   stg_project_group (project_id, group_id)

CREATE MACRO split_list(s) AS
    list_filter(list_transform(string_split(coalesce(s, ''), ';'), x -> trim(x)), x -> x <> '');

CREATE MACRO nullif_blank(s) AS nullif(trim(coalesce(s, '')), '');

-- headline_metrics.source_of
CREATE MACRO source_family(iid, edition) AS
    CASE
        WHEN iid LIKE 'sabin:%' THEN
            CASE WHEN edition = '2025-06' THEN 'Sabin 2025 (not in 2026 edition)' ELSE 'Sabin 2026' END
        WHEN iid LIKE 'nrel:%' THEN 'NREL'
        WHEN iid LIKE 'mn:%' THEN 'Moratorium Nation'
        WHEN iid LIKE 'queue:%' THEN 'review queue'
        ELSE 'other'
    END;

-- headline_metrics.VERIFICATION_RANK: an instrument is as verified as its
-- weakest row.
CREATE MACRO verification_rank(v) AS
    CASE coalesce(v, '') WHEN 'verified' THEN 0 WHEN 'located' THEN 1 ELSE 2 END;
CREATE MACRO verification_name(rank) AS
    CASE rank WHEN 0 THEN 'verified' WHEN 1 THEN 'located' ELSE 'unverified' END;

-- Geography ------------------------------------------------------------------

INSERT INTO state SELECT state_code, state_name, state_fips FROM stg_state;

INSERT INTO county
SELECT c.county_fips, s.state_code, c.county_name, s.state_code <> 'PR'
FROM stg_county c JOIN state s ON s.state_fips = substr(c.county_fips, 1, 2);

INSERT INTO county_adjacency SELECT county_fips, neighbor_fips FROM stg_county_adjacency;

INSERT INTO jurisdiction
WITH named AS (
    SELECT k.jurisdiction_key, k.kind, upper(k.state) AS state_code, k.jurisdiction AS name, r.county_fips
    FROM stg_jurisdiction_key k
    JOIN (
        SELECT state, jurisdiction_type, jurisdiction, nullif_blank(county_fips) AS county_fips FROM stg_restrictions
        UNION ALL
        SELECT state, jurisdiction_type, jurisdiction, nullif_blank(county_fips) FROM stg_siting_standards
    ) r USING (state, jurisdiction_type, jurisdiction)
)
SELECT jurisdiction_key,
       any_value(state_code),
       any_value(kind),
       mode(name),
       CASE WHEN count(DISTINCT county_fips) = 1 THEN any_value(county_fips) END
FROM named
GROUP BY jurisdiction_key;

-- Restrictions ---------------------------------------------------------------

INSERT INTO restriction_instrument
SELECT
    r.instrument_id,
    upper(any_value(r.state)),
    any_value(k.jurisdiction_key),
    any_value(nullif_blank(r.jurisdiction)),
    any_value(nullif_blank(r.jurisdiction_type)),
    any_value(r.scope),
    any_value(nullif_blank(r.status)),
    max(TRY_CAST(r.severity_score AS INTEGER)),
    coalesce(max(TRY_CAST(r.severity_score AS INTEGER)) >= 3, false),
    list_sort(list_distinct(list(r.technology))),
    list_sort(list_distinct(list(r.restriction_type))),
    any_value(r.evidence_level),
    verification_name(max(verification_rank(r.verification))),
    source_family(r.instrument_id, any_value(r.sabin_edition)),
    any_value(nullif_blank(r.sabin_edition)),
    any_value(nullif_blank(r.edition_status)),
    any_value(nullif_blank(r.date_enacted_iso)),
    TRY_CAST(any_value(nullif_blank(r.date_enacted_iso)) AS DATE),
    any_value(nullif_blank(r.date_text)),
    TRY_CAST(any_value(nullif_blank(r.current_end_date_iso)) AS DATE),
    any_value(nullif_blank(r.county_fips)),
    max(nullif_blank(r.primary_source_url)),
    max(nullif_blank(r.primary_source_access)),
    count(*)
FROM stg_restrictions r
LEFT JOIN stg_jurisdiction_key k USING (state, jurisdiction_type, jurisdiction)
GROUP BY r.instrument_id;

INSERT INTO restriction
SELECT id, instrument_id, technology, restriction_type,
       TRY_CAST(severity_score AS INTEGER), nullif_blank(severity_basis), nullif_blank(mechanisms),
       nullif_blank(description), nullif_blank(long_description), nullif_blank(legal_basis),
       nullif_blank(sectors), TRY_CAST(latitude AS DOUBLE), TRY_CAST(longitude AS DOUBLE),
       nullif_blank(nrel_id), nullif_blank(ordinance_url), nullif_blank(conflicts_with),
       nullif_blank(needs_verification), source, nullif_blank(source_url), nullif_blank(source_id),
       nullif_blank(source_record_id)
FROM stg_restrictions;

-- Contested projects and cases -----------------------------------------------

INSERT INTO contested_project
SELECT
    instrument_id, id, nullif_blank(source_record_id), upper(state), nullif_blank(project_name),
    split_list(technology),
    outcome,
    CASE
        WHEN outcome LIKE 'blocked_%' THEN 'blocked'
        WHEN outcome LIKE 'advanced_%' THEN 'advanced'
        WHEN outcome = 'restricted_conditional' THEN 'restricted'
        WHEN outcome = 'pending' THEN 'pending'
        ELSE 'needs_review'
    END,
    outcome LIKE '%_confirmed',
    nullif_blank(finality_evidence), nullif_blank(status), TRY_CAST(severity_score AS INTEGER),
    CASE lower(has_litigation) WHEN 'true' THEN true WHEN 'yes' THEN true WHEN 'false' THEN false
                               WHEN 'no' THEN false END,
    nullif_blank(opposition_type), nullif_blank(county_fips), nullif_blank(municipality),
    nullif_blank(event_date_text),
    nullif_blank(capacity_mw), TRY_CAST(nullif(regexp_extract(capacity_mw, '[0-9]+(\.[0-9]+)?'), '') AS DOUBLE),
    nullif_blank(area_acres),
    nullif_blank(description), nullif_blank(long_description),
    source_family(instrument_id, sabin_edition), nullif_blank(sabin_edition), nullif_blank(edition_status),
    evidence_level, verification, source, nullif_blank(source_url), nullif_blank(source_id)
FROM stg_contested_projects;

INSERT INTO legal_case
SELECT
    instrument_id,
    upper(any_value(nullif_blank(state))),
    any_value(nullif_blank(case_name)),
    any_value(nullif_blank(court)),
    any_value(nullif_blank(court_level)),
    any_value(nullif_blank(docket_number)),
    coalesce(any_value(case_status), ''),
    list_sort(list_distinct(flatten(list(split_list(technology))))),
    max(nullif_blank(case_source_url)),
    any_value(evidence_level),
    verification_name(max(verification_rank(verification))),
    count(*)
FROM stg_cases
GROUP BY instrument_id;

INSERT INTO case_project
SELECT c.instrument_id, p.instrument_id, c.id, nullif_blank(c.source_record_id)
FROM stg_cases c
LEFT JOIN stg_contested_projects p
       ON nullif_blank(c.source_record_id) = nullif_blank(p.source_record_id);

-- Siting standards and state policy ------------------------------------------

INSERT INTO siting_standard
SELECT s.id, upper(s.state), k.jurisdiction_key, nullif_blank(s.jurisdiction),
       nullif_blank(s.jurisdiction_type), nullif_blank(s.county_fips), s.technology, s.feature,
       nullif_blank(s.value), nullif_blank(s.units), nullif_blank(s.setback_adder),
       TRY_CAST(s.min_setback_ft AS DOUBLE), TRY_CAST(s.max_setback_ft AS DOUBLE),
       nullif_blank(s.section), TRY_CAST(s.ordinance_year AS INTEGER), nullif_blank(s.ordinance_url),
       coalesce(s.restricting = 'yes', false), nullif_blank(s.restriction_instrument_id),
       nullif_blank(s.evidence_level), coalesce(nullif_blank(s.verification), 'unverified'),
       nullif_blank(s.verified_by)
FROM stg_siting_standards s
LEFT JOIN stg_jurisdiction_key k USING (state, jurisdiction_type, jurisdiction);

INSERT INTO state_policy
SELECT id, upper(state), nullif_blank(technology), nullif_blank(policy_type), nullif_blank(who_decides),
       nullif_blank(state_body), nullif_blank(threshold_mw), nullif_blank(summary),
       nullif_blank(statute_citation), nullif_blank(statute_url), nullif_blank(evidence_level),
       nullif_blank(verification), TRY_CAST(nullif_blank(reviewed_on) AS DATE)
FROM stg_state_policies;

-- Placement ------------------------------------------------------------------

INSERT INTO record_county
WITH placed AS (
    SELECT 'restriction' AS entity, instrument_id AS record_id, county_fips AS primary_fips,
           county_fips_all, county_fips_method
    FROM stg_restrictions
    UNION ALL
    SELECT 'contested_project', instrument_id, county_fips, county_fips_all, county_fips_method
    FROM stg_contested_projects
    UNION ALL
    SELECT 'siting_standard', id, county_fips, county_fips_all, county_fips_method
    FROM stg_siting_standards
), exploded AS (
    SELECT entity, record_id, primary_fips, county_fips_method,
           unnest(CASE WHEN len(split_list(county_fips_all)) > 0 THEN split_list(county_fips_all)
                       ELSE split_list(primary_fips) END) AS fips
    FROM placed
)
SELECT e.entity, e.record_id, e.fips, bool_or(e.fips = coalesce(e.primary_fips, '')),
       any_value(nullif_blank(e.county_fips_method))
FROM exploded e
JOIN county c ON c.county_fips = e.fips
GROUP BY e.entity, e.record_id, e.fips;

-- Sources and evidence -------------------------------------------------------

INSERT INTO source_document
SELECT source_id, url, nullif_blank(normalized_url), nullif_blank(title),
       TRY_CAST(record_count AS INTEGER), split_list(entities), nullif_blank(archived_url)
FROM stg_sources;

INSERT INTO evidence_link
WITH links AS (
    SELECT 'restriction' AS entity, instrument_id AS record_id, 'compiled_source' AS role,
           source_url AS url, NULL AS access, NULL AS archived_url
    FROM stg_restrictions
    UNION ALL
    SELECT 'restriction', instrument_id, 'primary_source', primary_source_url, primary_source_access,
           primary_source_archived_url
    FROM stg_restrictions
    UNION ALL
    SELECT 'restriction', instrument_id, 'ordinance', ordinance_url, NULL, NULL FROM stg_restrictions
    UNION ALL
    SELECT 'restriction', instrument_id, 'placement', placement_url, placement_access, NULL
    FROM stg_restrictions
    UNION ALL
    SELECT 'contested_project', instrument_id, 'compiled_source', source_url, source_access, NULL
    FROM stg_contested_projects
    UNION ALL
    SELECT 'contested_project', instrument_id, 'outcome_evidence', resolution_url, resolution_access,
           resolution_archived_url
    FROM stg_contested_projects
    UNION ALL
    SELECT 'legal_case', instrument_id, 'court_record', case_source_url, NULL, NULL FROM stg_cases
    UNION ALL
    SELECT 'legal_case', instrument_id, 'compiled_source', source_url, NULL, NULL FROM stg_cases
)
SELECT entity, record_id, role, trim(url), max(nullif_blank(access)), max(nullif_blank(archived_url))
FROM links
WHERE nullif_blank(url) IS NOT NULL
GROUP BY entity, record_id, role, trim(url);

-- Groups ---------------------------------------------------------------------

INSERT INTO opposition_group
SELECT canonical_id, canonical_name, split_list(variants), TRY_CAST(n_projects AS INTEGER),
       split_list(states), nullif_blank(first_seen), nullif_blank(last_seen), split_list(source_urls)
FROM stg_group_registry;

INSERT INTO project_group
SELECT DISTINCT pg.project_id, pg.group_id
FROM stg_project_group pg
JOIN opposition_group g USING (group_id)
JOIN contested_project p ON p.instrument_id = pg.project_id;

-- Coverage and reference -----------------------------------------------------

INSERT INTO negative_check
SELECT lpad(trim(county_fips), 5, '0'), scope, split_list(sources_checked),
       CAST(checked_on AS DATE), result, nullif_blank(note), nullif_blank(reviewer)
FROM stg_negative_checks;

INSERT INTO data_center_event
SELECT nullif_blank(county_fips), upper(nullif_blank(state)), nullif_blank(jurisdiction),
       nullif_blank(date), nullif_blank(event_type), nullif_blank(status), nullif_blank(summary),
       split_list(source_urls), split_list(opposition_groups), nullif_blank(dc_row_ref)
FROM stg_data_center_events;
