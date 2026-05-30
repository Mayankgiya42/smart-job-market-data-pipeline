-- =============================================================================
-- schema.sql
-- Smart Job Market Data Pipeline — PostgreSQL Schema
-- =============================================================================
-- Run this manually to initialise the database, or let load.py handle it
-- automatically via the initialise_schema() function.
--
-- Usage:
--   psql -U postgres -d job_market_db -f sql/schema.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Database creation (run as superuser if the DB does not yet exist)
-- -----------------------------------------------------------------------------
-- CREATE DATABASE job_market_db;
-- \connect job_market_db

-- -----------------------------------------------------------------------------
-- Clean slate (useful during development — comment out in production)
-- -----------------------------------------------------------------------------
-- DROP TABLE IF EXISTS job_skills CASCADE;
-- DROP TABLE IF EXISTS skills    CASCADE;
-- DROP TABLE IF EXISTS jobs      CASCADE;

-- =============================================================================
-- 1. jobs
--    Core fact table — one row per unique job listing.
-- =============================================================================
CREATE TABLE IF NOT EXISTS jobs (
    job_id            TEXT           PRIMARY KEY,
    title             TEXT           NOT NULL,
    company           TEXT,
    city              TEXT,
    state_country     TEXT,
    location_raw      TEXT,
    contract_type     TEXT,
    salary_min        NUMERIC(12, 2),
    salary_max        NUMERIC(12, 2),
    salary_avg        NUMERIC(12, 2),
    posted_date       DATE,
    days_since_posted INTEGER,
    url               TEXT,
    description       TEXT,
    created_at        TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_salary_range CHECK (
        salary_min IS NULL
        OR salary_max IS NULL
        OR salary_min <= salary_max
    )
);

COMMENT ON TABLE  jobs                    IS 'One row per unique job listing ingested by the pipeline.';
COMMENT ON COLUMN jobs.job_id             IS 'Unique job identifier from source API or generated internally.';
COMMENT ON COLUMN jobs.salary_avg         IS 'Computed average of salary_min and salary_max.';
COMMENT ON COLUMN jobs.days_since_posted  IS 'Days between posted_date and pipeline extraction date.';
COMMENT ON COLUMN jobs.created_at         IS 'Timestamp when this record was inserted into the database.';

-- =============================================================================
-- 2. skills
--    Dimension table — canonical list of technology skills.
-- =============================================================================
CREATE TABLE IF NOT EXISTS skills (
    skill_id    SERIAL  PRIMARY KEY,
    skill_name  TEXT    NOT NULL UNIQUE
);

COMMENT ON TABLE  skills            IS 'Canonical technology skill vocabulary used for extraction.';
COMMENT ON COLUMN skills.skill_name IS 'Normalised skill name, e.g. "Python", "AWS", "Spark".';

-- =============================================================================
-- 3. job_skills  (many-to-many bridge)
--    Relates jobs to the skills mentioned in their descriptions.
-- =============================================================================
CREATE TABLE IF NOT EXISTS job_skills (
    job_id    TEXT    NOT NULL,
    skill_id  INTEGER NOT NULL,

    PRIMARY KEY (job_id, skill_id),

    CONSTRAINT fk_job_skills_job
        FOREIGN KEY (job_id)
        REFERENCES jobs(job_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_job_skills_skill
        FOREIGN KEY (skill_id)
        REFERENCES skills(skill_id)
        ON DELETE CASCADE
);

COMMENT ON TABLE job_skills IS 'Many-to-many bridge between jobs and skills extracted from descriptions.';

-- =============================================================================
-- Indexes
-- =============================================================================

-- Fast company filtering / aggregation
CREATE INDEX IF NOT EXISTS idx_jobs_company
    ON jobs (company);

-- Fast location-based aggregation
CREATE INDEX IF NOT EXISTS idx_jobs_city
    ON jobs (city);

-- Temporal queries
CREATE INDEX IF NOT EXISTS idx_jobs_posted_date
    ON jobs (posted_date DESC);

-- Bridge table — skill-side lookups
CREATE INDEX IF NOT EXISTS idx_job_skills_skill_id
    ON job_skills (skill_id);

-- Salary range queries
CREATE INDEX IF NOT EXISTS idx_jobs_salary_avg
    ON jobs (salary_avg)
    WHERE salary_avg IS NOT NULL;
