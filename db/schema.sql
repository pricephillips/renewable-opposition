-- National database: table definitions.
--
-- Built by scripts/build_database.py from data/processed/ (and the reference
-- files named below). The database is derived: it is rebuilt from scratch on
-- every run and never edited by hand. The CSVs in data/processed/ stay the
-- source of truth; see docs/national_database_design.md.
--
-- Keys
--   instrument_id  The counting unit (classify.instrument_id): one ordinance,
--                  moratorium, project or case, however many technologies
--                  it covers. Every headline count is a count of these.
--   id             One published row: one technology of one instrument.
--   county_fips    5-digit 2024 county FIPS, the geographic spine.
--
-- Dialect: DuckDB. Arrays (VARCHAR[]) hold the semicolon lists the CSVs use.

-- ---------------------------------------------------------------------------
-- Geography
-- ---------------------------------------------------------------------------

CREATE TABLE state (
    state_code      VARCHAR PRIMARY KEY,   -- USPS code, e.g. 'IA'
    state_name      VARCHAR NOT NULL,
    state_fips      VARCHAR NOT NULL       -- 2-digit FIPS
);

CREATE TABLE county (
    county_fips     VARCHAR PRIMARY KEY,
    state_code      VARCHAR NOT NULL REFERENCES state (state_code),
    county_name     VARCHAR NOT NULL,
    -- headline_metrics.county_coverage counts the 50 states and DC only.
    in_coverage_universe BOOLEAN NOT NULL
);

CREATE TABLE county_adjacency (
    county_fips     VARCHAR NOT NULL REFERENCES county (county_fips),
    neighbor_fips   VARCHAR NOT NULL REFERENCES county (county_fips),
    PRIMARY KEY (county_fips, neighbor_fips)
);

-- Local governments named by restrictions and siting standards, matched on
-- common.jurisdiction_key ('Town of Morris' == 'Morris' within a state and
-- kind). A match key, not an authority file: two sources that spell a place
-- differently can still produce two rows.
CREATE TABLE jurisdiction (
    jurisdiction_key VARCHAR PRIMARY KEY,  -- '<ST>::<kind>::<cleaned name>'
    state_code      VARCHAR NOT NULL REFERENCES state (state_code),
    kind            VARCHAR NOT NULL,      -- state | county | municipal
    display_name    VARCHAR NOT NULL,      -- the most common spelling
    county_fips     VARCHAR                -- the county it sits in, when every row agrees
);

-- Census governments a record names, by GEOID (geoid_match.py): a place
-- (7 digits) or county subdivision (10) from data/census_governments_2024.csv,
-- a county (5) or a state (2). Only governments some record matches.
CREATE TABLE government (
    geoid           VARCHAR PRIMARY KEY,
    kind            VARCHAR NOT NULL,      -- place | county_subdivision | county | state
    state_code      VARCHAR NOT NULL REFERENCES state (state_code),
    county_fips     VARCHAR,               -- a place's county holds its internal point
    census_name     VARCHAR NOT NULL,      -- 'Binghamton city', 'Binghamton town'
    funcstat        VARCHAR                -- Census functional status: A, B or C
);

-- Every distinct (state, jurisdiction type, name, counties) a restriction or
-- siting standard uses, with its GEOID when exactly one government fits. The
-- counties are part of the key because one name can be many governments
-- (Pennsylvania's Washington Townships). method
-- says how it matched, or why not (ambiguous, no_match, county_differs);
-- the unmatched are listed in data/review/geoid_worklist.csv.
CREATE TABLE jurisdiction_match (
    state_code      VARCHAR NOT NULL,
    jurisdiction_type VARCHAR NOT NULL,
    jurisdiction    VARCHAR NOT NULL,
    counties        VARCHAR NOT NULL,      -- the rows' county_fips_all, as published ('' when unplaced)
    geoid           VARCHAR REFERENCES government (geoid),
    method          VARCHAR NOT NULL,
    candidates      INTEGER NOT NULL,      -- governments that fit; 1 when matched
    PRIMARY KEY (state_code, jurisdiction_type, jurisdiction, counties)
);

-- ---------------------------------------------------------------------------
-- Restrictions: one instrument, many technology rows
-- ---------------------------------------------------------------------------

CREATE TABLE restriction_instrument (
    instrument_id   VARCHAR PRIMARY KEY,
    state_code      VARCHAR NOT NULL REFERENCES state (state_code),
    jurisdiction_key VARCHAR REFERENCES jurisdiction (jurisdiction_key),
    jurisdiction_name VARCHAR,
    jurisdiction_type VARCHAR,
    scope           VARCHAR NOT NULL,      -- renewables_only | multi_sector_data_centers
    status          VARCHAR,               -- active | extended | pending | unknown
    severity_score  INTEGER,               -- highest of its rows
    is_severe       BOOLEAN NOT NULL,      -- severity 3 or 4
    technologies    VARCHAR[] NOT NULL,
    restriction_types VARCHAR[] NOT NULL,
    evidence_level  VARCHAR NOT NULL,
    verification    VARCHAR NOT NULL,      -- weakest of its rows
    source_family   VARCHAR NOT NULL,      -- headline_metrics.source_of
    sabin_edition   VARCHAR,
    edition_status  VARCHAR,
    date_enacted_iso VARCHAR,              -- as published; may be a year or year-month
    date_enacted    DATE,                  -- only when date_enacted_iso is a full date
    date_text       VARCHAR,
    current_end_date DATE,
    county_fips     VARCHAR,               -- the one county the map paints
    primary_source_url VARCHAR,
    primary_source_access VARCHAR,         -- opened | archived | snippet
    n_rows          INTEGER NOT NULL,
    geoid           VARCHAR REFERENCES government (geoid)  -- the Census government, when one fits
);

CREATE TABLE restriction (
    id              VARCHAR PRIMARY KEY,
    instrument_id   VARCHAR NOT NULL REFERENCES restriction_instrument (instrument_id),
    technology      VARCHAR NOT NULL,
    restriction_type VARCHAR NOT NULL,
    severity_score  INTEGER,
    severity_basis  VARCHAR,
    mechanisms      VARCHAR,
    description     VARCHAR,
    long_description VARCHAR,
    legal_basis     VARCHAR,
    sectors         VARCHAR,
    latitude        DOUBLE,
    longitude       DOUBLE,
    nrel_id         VARCHAR,
    ordinance_url   VARCHAR,
    conflicts_with  VARCHAR,
    needs_verification VARCHAR,
    source          VARCHAR,
    source_url      VARCHAR,
    source_id       VARCHAR,
    source_record_id VARCHAR
);

-- ---------------------------------------------------------------------------
-- Contested projects and the cases about them
-- ---------------------------------------------------------------------------

CREATE TABLE contested_project (
    instrument_id   VARCHAR PRIMARY KEY,
    id              VARCHAR NOT NULL UNIQUE,
    source_record_id VARCHAR,
    state_code      VARCHAR NOT NULL REFERENCES state (state_code),
    project_name    VARCHAR,
    technologies    VARCHAR[] NOT NULL,
    outcome         VARCHAR NOT NULL,      -- the outcome ladder, README
    outcome_class   VARCHAR NOT NULL,      -- blocked | advanced | restricted | pending | needs_review
    outcome_confirmed BOOLEAN NOT NULL,
    finality_evidence VARCHAR,
    status          VARCHAR,
    severity_score  INTEGER,
    has_litigation  BOOLEAN,
    opposition_type VARCHAR,
    county_fips     VARCHAR,
    municipality    VARCHAR,
    event_date_text VARCHAR,
    capacity_mw_text VARCHAR,              -- as the source gives it ('35-40 MW')
    capacity_mw_low DOUBLE,                -- first number in capacity_mw_text
    area_acres_text VARCHAR,
    description     VARCHAR,
    long_description VARCHAR,
    source_family   VARCHAR NOT NULL,
    sabin_edition   VARCHAR,
    edition_status  VARCHAR,
    evidence_level  VARCHAR NOT NULL,
    verification    VARCHAR NOT NULL,
    source          VARCHAR,
    source_url      VARCHAR,
    source_id       VARCHAR
);

CREATE TABLE legal_case (
    instrument_id   VARCHAR PRIMARY KEY,
    state_code      VARCHAR REFERENCES state (state_code),
    case_name       VARCHAR,
    court           VARCHAR,
    court_level     VARCHAR,
    docket_number   VARCHAR,
    case_status     VARCHAR,
    technologies    VARCHAR[] NOT NULL,
    case_source_url VARCHAR,
    evidence_level  VARCHAR NOT NULL,
    verification    VARCHAR NOT NULL,
    n_rows          INTEGER NOT NULL
);

-- A case can concern more than one project (cases.csv repeats it per record).
CREATE TABLE case_project (
    case_id         VARCHAR NOT NULL REFERENCES legal_case (instrument_id),
    project_id      VARCHAR REFERENCES contested_project (instrument_id),
    case_row_id     VARCHAR NOT NULL,
    source_record_id VARCHAR,
    PRIMARY KEY (case_row_id)
);

-- ---------------------------------------------------------------------------
-- Siting standards (NREL 2025) and state siting law
-- ---------------------------------------------------------------------------

CREATE TABLE siting_standard (
    id              VARCHAR PRIMARY KEY,
    state_code      VARCHAR NOT NULL REFERENCES state (state_code),
    jurisdiction_key VARCHAR REFERENCES jurisdiction (jurisdiction_key),
    jurisdiction    VARCHAR,
    jurisdiction_type VARCHAR,
    county_fips     VARCHAR,
    technology      VARCHAR NOT NULL,
    feature         VARCHAR NOT NULL,
    value           VARCHAR,
    units           VARCHAR,
    setback_adder   VARCHAR,
    min_setback_ft  DOUBLE,
    max_setback_ft  DOUBLE,
    section         VARCHAR,
    ordinance_year  INTEGER,
    ordinance_url   VARCHAR,
    restricting     BOOLEAN NOT NULL,
    restriction_instrument_id VARCHAR,     -- the restriction it contributes to, if any
    evidence_level  VARCHAR,
    verification    VARCHAR NOT NULL,
    verified_by     VARCHAR,
    geoid           VARCHAR REFERENCES government (geoid)  -- the Census government, when one fits
);

CREATE TABLE state_policy (
    id              VARCHAR PRIMARY KEY,
    state_code      VARCHAR NOT NULL REFERENCES state (state_code),
    technology      VARCHAR,
    policy_type     VARCHAR,
    who_decides     VARCHAR,
    state_body      VARCHAR,
    threshold_mw    VARCHAR,
    summary         VARCHAR,
    statute_citation VARCHAR,
    statute_url     VARCHAR,
    evidence_level  VARCHAR,
    verification    VARCHAR,
    reviewed_on     DATE
);

-- ---------------------------------------------------------------------------
-- Placement, sources and evidence
-- ---------------------------------------------------------------------------

-- Every county a record touches (county_fips_all), one row each.
CREATE TABLE record_county (
    entity          VARCHAR NOT NULL,      -- restriction | contested_project | siting_standard
    record_id       VARCHAR NOT NULL,      -- instrument_id, or siting_standard.id
    county_fips     VARCHAR NOT NULL REFERENCES county (county_fips),
    is_primary      BOOLEAN NOT NULL,      -- equals the record's county_fips
    method          VARCHAR,               -- name | names | point | place | place_text | override | source_fips
    PRIMARY KEY (entity, record_id, county_fips)
);

CREATE TABLE source_document (
    source_id       VARCHAR PRIMARY KEY,
    url             VARCHAR NOT NULL,
    normalized_url  VARCHAR,
    title           VARCHAR,
    record_count    INTEGER,
    entities        VARCHAR[],
    archived_url    VARCHAR
);

-- Every URL that stands behind a record, with the job it does and how it was
-- seen. Only 'opened' and 'archived' access upgrades a record (README,
-- "How the evidence was seen").
CREATE TABLE evidence_link (
    entity          VARCHAR NOT NULL,      -- restriction | contested_project | legal_case
    record_id       VARCHAR NOT NULL,      -- instrument_id
    role            VARCHAR NOT NULL,      -- compiled_source | primary_source | ordinance | outcome_evidence | placement | court_record
    url             VARCHAR NOT NULL,
    access          VARCHAR,               -- opened | archived | snippet | blank for compiled sources
    archived_url    VARCHAR,
    PRIMARY KEY (entity, record_id, role, url)
);

-- ---------------------------------------------------------------------------
-- Opposition groups
-- ---------------------------------------------------------------------------

CREATE TABLE opposition_group (
    group_id        VARCHAR PRIMARY KEY,   -- group_registry canonical_id
    canonical_name  VARCHAR NOT NULL,
    variants        VARCHAR[],
    n_projects      INTEGER,
    states          VARCHAR[],
    first_seen      VARCHAR,
    last_seen       VARCHAR,
    source_urls     VARCHAR[]
);

CREATE TABLE project_group (
    project_id      VARCHAR NOT NULL REFERENCES contested_project (instrument_id),
    group_id        VARCHAR NOT NULL REFERENCES opposition_group (group_id),
    PRIMARY KEY (project_id, group_id)
);

-- ---------------------------------------------------------------------------
-- Coverage and reference
-- ---------------------------------------------------------------------------

-- "Checked, nothing found" (data/review/negative_checks.csv, as the processed
-- build copied it to data/processed/negative_checks.csv). Not a record:
-- it separates a county someone searched from one nobody has looked at.
CREATE TABLE negative_check (
    county_fips     VARCHAR NOT NULL REFERENCES county (county_fips),
    scope           VARCHAR NOT NULL,      -- restrictions | projects | both
    sources_checked VARCHAR[] NOT NULL,
    checked_on      DATE NOT NULL,
    result          VARCHAR NOT NULL,
    note            VARCHAR,
    reviewer        VARCHAR,
    governments_checked VARCHAR,           -- every government covered (docs/COUNTY_CHECK.md)
    drafted_by      VARCHAR,
    grade           VARCHAR NOT NULL,      -- A to U (scripts/negative_checks.py)
    classes         VARCHAR[] NOT NULL,    -- primary_law, proceeding, secondary
    recheck_by      DATE,                  -- stale after this day
    held            BOOLEAN NOT NULL       -- drafted, not yet reviewed: not counted
);

-- How many review-queue candidates still pending review name the county
-- (site_profile.pending_for). A count only: the candidates themselves are
-- never published.
CREATE TABLE county_pending_review (
    county_fips     VARCHAR PRIMARY KEY REFERENCES county (county_fips),
    candidates      INTEGER NOT NULL
);

-- How long each review worklist is (build_database.WORKLISTS). Sizes only:
-- the worklists themselves stay in data/review/.
CREATE TABLE worklist_size (
    worklist        VARCHAR PRIMARY KEY,
    description     VARCHAR NOT NULL,
    rows            INTEGER NOT NULL
);

-- Data center events copied from pricephillips/data-center-map. Context for
-- a county; never part of a renewable count.
CREATE TABLE data_center_event (
    county_fips     VARCHAR,
    state_code      VARCHAR,
    jurisdiction    VARCHAR,
    event_date      VARCHAR,
    event_type      VARCHAR,
    status          VARCHAR,
    summary         VARCHAR,
    source_urls     VARCHAR[],
    opposition_groups VARCHAR[],
    dc_row_ref      VARCHAR
);

-- The headline figures as each data build published them, one row per day
-- on which they changed (data/snapshots/headline_history.csv,
-- scripts/headline_history.py). A blank is a figure the metrics did not carry
-- yet that day.
CREATE TABLE headline_history (
    date            DATE PRIMARY KEY,
    restrictions    INTEGER,               -- renewables only, by instrument
    severe_restrictions INTEGER,
    verified_restrictions INTEGER,
    multi_sector_restrictions INTEGER,
    contested_projects INTEGER,
    confirmed_outcomes INTEGER,
    verified_projects INTEGER,
    cases           INTEGER,
    siting_standard_rows INTEGER,
    state_policies  INTEGER,
    counties_with_records INTEGER,
    counties_not_examined INTEGER
);

-- What this database was built from.
CREATE TABLE build_info (
    key             VARCHAR PRIMARY KEY,
    value           VARCHAR
);
