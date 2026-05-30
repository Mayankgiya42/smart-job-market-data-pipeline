"""
load.py
-------
Loads cleaned job data from the processed CSV into PostgreSQL.
Handles schema creation, upsert logic, and many-to-many skill relationships.
"""

from __future__ import annotations

import csv
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

import pandas as pd
import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection as PgConnection, cursor as PgCursor

from src.utils import get_logger, get_processed_filepath

logger = get_logger("load")


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

def build_dsn(config: dict) -> str:
    """
    Build a PostgreSQL DSN (Data Source Name) connection string.

    Args:
        config: Full pipeline configuration dictionary.

    Returns:
        psycopg2-compatible DSN string.
    """
    db = config["database"]
    return (
        f"host={db['host']} "
        f"port={db['port']} "
        f"dbname={db['name']} "
        f"user={db['user']} "
        f"password={db['password']}"
    )


@contextmanager
def get_connection(config: dict) -> Generator[PgConnection, None, None]:
    """
    Context manager that yields an open psycopg2 database connection.
    Commits on clean exit, rolls back on exception.

    Args:
        config: Full pipeline configuration dictionary.

    Yields:
        Open psycopg2 connection object.
    """
    conn: Optional[PgConnection] = None
    try:
        dsn = build_dsn(config)
        conn = psycopg2.connect(dsn)
        logger.debug(
            "DB connection opened → %s:%s/%s",
            config["database"]["host"],
            config["database"]["port"],
            config["database"]["name"],
        )
        yield conn
        conn.commit()
        logger.debug("Transaction committed")
    except Exception:
        if conn:
            conn.rollback()
            logger.warning("Transaction rolled back due to error")
        raise
    finally:
        if conn and not conn.closed:
            conn.close()
            logger.debug("DB connection closed")


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

_CREATE_TABLES_SQL = """
-- Jobs dimension table
CREATE TABLE IF NOT EXISTS jobs (
    job_id          TEXT        PRIMARY KEY,
    title           TEXT        NOT NULL,
    company         TEXT,
    city            TEXT,
    state_country   TEXT,
    location_raw    TEXT,
    contract_type   TEXT,
    salary_min      NUMERIC(12, 2),
    salary_max      NUMERIC(12, 2),
    salary_avg      NUMERIC(12, 2),
    posted_date     DATE,
    days_since_posted INTEGER,
    url             TEXT,
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Skills dimension table
CREATE TABLE IF NOT EXISTS skills (
    skill_id    SERIAL  PRIMARY KEY,
    skill_name  TEXT    NOT NULL UNIQUE
);

-- Many-to-many bridge table
CREATE TABLE IF NOT EXISTS job_skills (
    job_id      TEXT    NOT NULL REFERENCES jobs(job_id)    ON DELETE CASCADE,
    skill_id    INTEGER NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, skill_id)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_jobs_company        ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_city           ON jobs(city);
CREATE INDEX IF NOT EXISTS idx_jobs_posted_date    ON jobs(posted_date);
CREATE INDEX IF NOT EXISTS idx_job_skills_skill_id ON job_skills(skill_id);
"""


def initialise_schema(conn: PgConnection) -> None:
    """
    Create tables and indexes if they do not already exist.

    Args:
        conn: Open psycopg2 connection.
    """
    with conn.cursor() as cur:
        cur.execute(_CREATE_TABLES_SQL)
    logger.info("Schema initialised (tables and indexes ensured)")


# ---------------------------------------------------------------------------
# Insert helpers
# ---------------------------------------------------------------------------

def upsert_job(cur: PgCursor, row: dict) -> None:
    """
    Insert a single job record. Skips on primary-key conflict (idempotent).

    Args:
        cur: Open psycopg2 cursor.
        row: Dictionary with job column values.
    """
    sql = """
        INSERT INTO jobs (
            job_id, title, company, city, state_country, location_raw,
            contract_type, salary_min, salary_max, salary_avg,
            posted_date, days_since_posted, url, description
        )
        VALUES (
            %(job_id)s, %(title)s, %(company)s, %(city)s, %(state_country)s,
            %(location_raw)s, %(contract_type)s, %(salary_min)s, %(salary_max)s,
            %(salary_avg)s, %(posted_date)s, %(days_since_posted)s, %(url)s,
            %(description)s
        )
        ON CONFLICT (job_id) DO NOTHING;
    """
    cur.execute(sql, row)


def upsert_skill(cur: PgCursor, skill_name: str) -> int:
    """
    Insert a skill if it does not exist and return its skill_id.

    Args:
        cur: Open psycopg2 cursor.
        skill_name: Name of the skill (e.g. 'Python').

    Returns:
        skill_id of the (possibly newly created) skill record.
    """
    sql = """
        INSERT INTO skills (skill_name)
        VALUES (%s)
        ON CONFLICT (skill_name) DO NOTHING;

        SELECT skill_id FROM skills WHERE skill_name = %s;
    """
    # psycopg2 cannot execute two statements in one call — use two calls
    cur.execute(
        """
        INSERT INTO skills (skill_name) VALUES (%s)
        ON CONFLICT (skill_name) DO NOTHING
        """,
        (skill_name,),
    )
    cur.execute("SELECT skill_id FROM skills WHERE skill_name = %s", (skill_name,))
    row = cur.fetchone()
    return row[0] if row else None


def link_job_skill(cur: PgCursor, job_id: str, skill_id: int) -> None:
    """
    Create a job–skill association. Skips on conflict (idempotent).

    Args:
        cur: Open psycopg2 cursor.
        job_id: Job identifier string.
        skill_id: Skill identifier integer.
    """
    cur.execute(
        """
        INSERT INTO job_skills (job_id, skill_id)
        VALUES (%s, %s)
        ON CONFLICT (job_id, skill_id) DO NOTHING
        """,
        (job_id, skill_id),
    )


# ---------------------------------------------------------------------------
# Batch loading
# ---------------------------------------------------------------------------

def _safe_decimal(value) -> Optional[float]:
    """Convert a value to float or return None if falsy / NaN."""
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> Optional[int]:
    """Convert a value to int or return None if falsy / NaN."""
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_date(value):
    """Return a Python date or None."""
    if pd.isna(value) if hasattr(value, '__class__') else not value:
        return None
    return value if not isinstance(value, float) else None


def load_jobs(conn: PgConnection, df: pd.DataFrame) -> int:
    """
    Batch-insert all job records from the DataFrame.

    Args:
        conn: Open psycopg2 connection (not yet committed).
        df: Cleaned jobs DataFrame.

    Returns:
        Number of rows processed.
    """
    inserted = 0
    with conn.cursor() as cur:
        for _, row in df.iterrows():
            record = {
                "job_id": str(row["job_id"]),
                "title": row.get("title"),
                "company": row.get("company"),
                "city": row.get("city"),
                "state_country": row.get("state_country"),
                "location_raw": row.get("location_raw"),
                "contract_type": row.get("contract_type"),
                "salary_min": _safe_decimal(row.get("salary_min")),
                "salary_max": _safe_decimal(row.get("salary_max")),
                "salary_avg": _safe_decimal(row.get("salary_avg")),
                "posted_date": row.get("posted_date") if pd.notna(row.get("posted_date", None)) else None,
                "days_since_posted": _safe_int(row.get("days_since_posted")),
                "url": row.get("url"),
                "description": row.get("description"),
            }
            upsert_job(cur, record)
            inserted += 1

    logger.info("Upserted %d job record(s) into jobs table", inserted)
    return inserted


def load_skills(conn: PgConnection, df: pd.DataFrame) -> int:
    """
    Extract all unique skills from the DataFrame and insert them into
    the skills table, then populate the job_skills bridge table.

    Args:
        conn: Open psycopg2 connection (not yet committed).
        df: Cleaned jobs DataFrame with a 'skills' column.

    Returns:
        Total number of job–skill associations created.
    """
    associations = 0
    with conn.cursor() as cur:
        for _, row in df.iterrows():
            job_id = str(row["job_id"])
            skills_str = row.get("skills", "")
            if not skills_str or not isinstance(skills_str, str):
                continue

            for skill_name in [s.strip() for s in skills_str.split(",") if s.strip()]:
                skill_id = upsert_skill(cur, skill_name)
                if skill_id:
                    link_job_skill(cur, job_id, skill_id)
                    associations += 1

    logger.info("Created %d job–skill association(s)", associations)
    return associations


# ---------------------------------------------------------------------------
# Query insights
# ---------------------------------------------------------------------------

_INSIGHTS_QUERIES = {
    "top_skills": """
        SELECT s.skill_name, COUNT(*) AS job_count
        FROM job_skills js
        JOIN skills s ON js.skill_id = s.skill_id
        GROUP BY s.skill_name
        ORDER BY job_count DESC
        LIMIT 10;
    """,
    "top_companies": """
        SELECT company, COUNT(*) AS job_count
        FROM jobs
        WHERE company != 'Unknown Company'
        GROUP BY company
        ORDER BY job_count DESC
        LIMIT 10;
    """,
    "jobs_by_city": """
        SELECT city, COUNT(*) AS job_count
        FROM jobs
        GROUP BY city
        ORDER BY job_count DESC
        LIMIT 10;
    """,
    "avg_salary_by_city": """
        SELECT city, ROUND(AVG(salary_avg), 0) AS avg_salary, COUNT(*) AS job_count
        FROM jobs
        WHERE salary_avg IS NOT NULL
        GROUP BY city
        ORDER BY avg_salary DESC
        LIMIT 10;
    """,
}


def run_insights(conn: PgConnection) -> dict[str, pd.DataFrame]:
    """
    Execute predefined analytical SQL queries and return results as DataFrames.

    Args:
        conn: Open psycopg2 connection.

    Returns:
        Dictionary mapping query names to result DataFrames.
    """
    results = {}
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        for name, sql in _INSIGHTS_QUERIES.items():
            cur.execute(sql)
            rows = cur.fetchall()
            df_result = pd.DataFrame(rows, columns=[desc[0] for desc in cur.description])
            results[name] = df_result
            logger.info("Insight '%s':\n%s", name, df_result.to_string(index=False))

    return results


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_loading(config: dict, df: Optional[pd.DataFrame] = None) -> None:
    """
    Orchestrate the loading phase: initialise schema, insert data, log insights.

    Args:
        config: Full pipeline configuration dictionary.
        df: Optional pre-loaded DataFrame. If None, reads from the processed CSV.
    """
    logger.info("=== LOADING PHASE START ===")

    if df is None:
        csv_path = get_processed_filepath(config)
        if not csv_path.exists():
            raise FileNotFoundError(
                f"Processed CSV not found: {csv_path}. "
                "Run the transformation phase first."
            )
        df = pd.read_csv(csv_path, low_memory=False)
        logger.info("Loaded %d records from %s", len(df), csv_path)

    try:
        with get_connection(config) as conn:
            # 1. Ensure schema exists
            initialise_schema(conn)

            # 2. Load jobs
            load_jobs(conn, df)

            # 3. Load skills + associations
            load_skills(conn, df)

        # 4. Run insights (separate connection so commit is visible)
        with get_connection(config) as conn:
            run_insights(conn)

    except psycopg2.OperationalError as exc:
        logger.error(
            "Could not connect to PostgreSQL: %s\n"
            "→ Ensure the DB is running and credentials in config.yaml are correct.",
            exc,
        )
        raise

    logger.info("=== LOADING PHASE COMPLETE ===")
