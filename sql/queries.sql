-- =============================================================================
-- queries.sql
-- Smart Job Market Data Pipeline — Analytical Queries
-- =============================================================================
-- Run against job_market_db after the pipeline has loaded data.
--
-- Usage:
--   psql -U postgres -d job_market_db -f sql/queries.sql
-- =============================================================================


-- =============================================================================
-- 1. TOP SKILLS
--    Which technology skills appear most frequently across all job listings?
-- =============================================================================
\echo '=== TOP 10 IN-DEMAND SKILLS ==='

SELECT
    s.skill_name                                         AS skill,
    COUNT(js.job_id)                                     AS job_count,
    ROUND(
        COUNT(js.job_id) * 100.0 / SUM(COUNT(js.job_id)) OVER (),
        1
    )                                                    AS pct_of_listings
FROM job_skills  js
JOIN skills      s  ON js.skill_id = s.skill_id
GROUP BY s.skill_name
ORDER BY job_count DESC
LIMIT 10;


-- =============================================================================
-- 2. TOP COMPANIES
--    Which employers are posting the most Data Engineer roles?
-- =============================================================================
\echo '=== TOP 10 HIRING COMPANIES ==='

SELECT
    company,
    COUNT(*)                                             AS open_roles,
    ROUND(AVG(salary_avg), 0)                           AS avg_salary_usd
FROM jobs
WHERE company != 'Unknown Company'
GROUP BY company
ORDER BY open_roles DESC
LIMIT 10;


-- =============================================================================
-- 3. JOBS BY LOCATION
--    Which cities have the most Data Engineer openings?
-- =============================================================================
\echo '=== JOB COUNT BY CITY (TOP 10) ==='

SELECT
    city,
    state_country,
    COUNT(*)                                             AS job_count,
    ROUND(AVG(salary_avg), 0)                           AS avg_salary_usd
FROM jobs
GROUP BY city, state_country
ORDER BY job_count DESC
LIMIT 10;


-- =============================================================================
-- 4. SALARY INSIGHTS
--    What does the salary distribution look like?
-- =============================================================================
\echo '=== SALARY DISTRIBUTION ==='

SELECT
    COUNT(*)                             AS total_jobs,
    COUNT(salary_avg)                    AS jobs_with_salary,
    ROUND(MIN(salary_avg),    0)         AS min_salary,
    ROUND(MAX(salary_avg),    0)         AS max_salary,
    ROUND(AVG(salary_avg),    0)         AS mean_salary,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY salary_avg), 0)
                                         AS median_salary,
    ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY salary_avg), 0)
                                         AS p25_salary,
    ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY salary_avg), 0)
                                         AS p75_salary
FROM jobs;


-- =============================================================================
-- 5. SKILL CO-OCCURRENCE
--    Which skill pairs most often appear together in the same job listing?
-- =============================================================================
\echo '=== TOP 10 SKILL PAIRS (CO-OCCURRENCE) ==='

SELECT
    s1.skill_name                        AS skill_a,
    s2.skill_name                        AS skill_b,
    COUNT(*)                             AS co_occurrences
FROM job_skills  js1
JOIN job_skills  js2 ON js1.job_id   = js2.job_id
                     AND js1.skill_id < js2.skill_id   -- avoid self-pairs and duplicates
JOIN skills      s1  ON js1.skill_id = s1.skill_id
JOIN skills      s2  ON js2.skill_id = s2.skill_id
GROUP BY s1.skill_name, s2.skill_name
ORDER BY co_occurrences DESC
LIMIT 10;


-- =============================================================================
-- 6. REMOTE VS ON-SITE
--    What proportion of roles allow remote work?
-- =============================================================================
\echo '=== REMOTE VS ON-SITE BREAKDOWN ==='

SELECT
    CASE
        WHEN LOWER(city) = 'remote' THEN 'Remote'
        ELSE 'On-site / Hybrid'
    END                                  AS work_mode,
    COUNT(*)                             AS job_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1)
                                         AS pct
FROM jobs
GROUP BY work_mode
ORDER BY job_count DESC;


-- =============================================================================
-- 7. RECENCY
--    How fresh are the listings in the pipeline?
-- =============================================================================
\echo '=== POSTING RECENCY ==='

SELECT
    CASE
        WHEN days_since_posted <= 7   THEN '0-7 days'
        WHEN days_since_posted <= 14  THEN '8-14 days'
        WHEN days_since_posted <= 30  THEN '15-30 days'
        ELSE                               '30+ days'
    END                                  AS age_bucket,
    COUNT(*)                             AS job_count
FROM jobs
WHERE days_since_posted IS NOT NULL
GROUP BY age_bucket
ORDER BY MIN(days_since_posted);


-- =============================================================================
-- 8. CONTRACT TYPE BREAKDOWN
-- =============================================================================
\echo '=== CONTRACT TYPE BREAKDOWN ==='

SELECT
    COALESCE(NULLIF(contract_type, ''), 'unspecified') AS contract_type,
    COUNT(*)                                            AS job_count
FROM jobs
GROUP BY contract_type
ORDER BY job_count DESC;
