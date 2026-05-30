"""
transform.py
------------
Loads raw JSON job data, cleans and normalises it using Pandas, extracts
skills from job descriptions, and exports a cleaned CSV for loading.
"""

import json
import re
from pathlib import Path
from typing import Optional

import pandas as pd

from src.utils import (
    get_logger,
    get_raw_filepath,
    get_processed_filepath,
    log_dataframe_summary,
    safe_get,
)

logger = get_logger("transform")


# ---------------------------------------------------------------------------
# Load raw data
# ---------------------------------------------------------------------------

def load_raw_data(config: dict) -> list[dict]:
    """
    Load the raw JSON file produced by the extraction phase.

    Args:
        config: Full pipeline configuration dictionary.

    Returns:
        List of raw job dictionaries.

    Raises:
        FileNotFoundError: If the raw JSON file does not exist.
    """
    raw_path = get_raw_filepath(config)
    if not raw_path.exists():
        raise FileNotFoundError(
            f"Raw data file not found: {raw_path}. "
            "Run the extraction phase first."
        )

    with open(raw_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    jobs = payload.get("jobs", [])
    logger.info("Loaded %d raw records from %s", len(jobs), raw_path)
    return jobs


# ---------------------------------------------------------------------------
# Flatten raw records into a DataFrame
# ---------------------------------------------------------------------------

def flatten_records(jobs: list[dict]) -> pd.DataFrame:
    """
    Flatten nested Adzuna API / mock records into a flat Pandas DataFrame.

    Args:
        jobs: List of raw job dictionaries.

    Returns:
        DataFrame with one row per job and standardised column names.
    """
    rows = []
    for job in jobs:
        rows.append(
            {
                "job_id": safe_get(job, "id", default=None),
                "title": safe_get(job, "title", default=None),
                "company": safe_get(job, "company", "display_name", default=None),
                "location_raw": safe_get(job, "location", "display_name", default=None),
                "description": safe_get(job, "description", default=None),
                "salary_min": safe_get(job, "salary_min", default=None),
                "salary_max": safe_get(job, "salary_max", default=None),
                "posted_at": safe_get(job, "created", default=None),
                "url": safe_get(job, "redirect_url", default=None),
                "contract_type": safe_get(job, "contract_type", default=None),
            }
        )

    df = pd.DataFrame(rows)
    logger.debug("Flattened %d records → DataFrame shape %s", len(rows), df.shape)
    return df


# ---------------------------------------------------------------------------
# Individual cleaning steps
# ---------------------------------------------------------------------------

def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove exact duplicate rows, using job_id as the primary dedup key
    and falling back to (title, company, location_raw) if job_id is null.

    Args:
        df: Input DataFrame.

    Returns:
        DataFrame with duplicates removed.
    """
    before = len(df)

    # Primary: deduplicate on job_id (drop nulls first so they don't collapse)
    mask_with_id = df["job_id"].notna()
    df_with_id = df[mask_with_id].drop_duplicates(subset=["job_id"], keep="first")
    df_without_id = df[~mask_with_id].drop_duplicates(
        subset=["title", "company", "location_raw"], keep="first"
    )
    df = pd.concat([df_with_id, df_without_id], ignore_index=True)

    after = len(df)
    removed = before - after
    if removed:
        logger.info("Removed %d duplicate record(s) (before: %d, after: %d)", removed, before, after)
    else:
        logger.info("No duplicates found")
    return df


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Handle missing values with domain-appropriate strategies:
    - Drop rows missing job_id, title, or description (critical fields)
    - Fill textual optionals with 'Unknown'
    - Leave salary nulls as NaN (used intentionally downstream)

    Args:
        df: Input DataFrame.

    Returns:
        DataFrame with missing values handled.
    """
    before = len(df)

    # Drop rows missing critical fields
    critical = ["title", "description"]
    df = df.dropna(subset=critical)
    dropped = before - len(df)
    if dropped:
        logger.warning("Dropped %d row(s) missing critical fields (%s)", dropped, critical)

    # Fill optional text columns
    text_fill_map = {
        "company": "Unknown Company",
        "location_raw": "Unknown Location",
        "contract_type": "unspecified",
        "url": "",
    }
    for col, fill_value in text_fill_map.items():
        if col in df.columns:
            null_count = df[col].isna().sum()
            if null_count:
                df[col] = df[col].fillna(fill_value)
                logger.debug("Filled %d null(s) in '%s' with '%s'", null_count, col, fill_value)

    # Generate a job_id for records that lack one
    missing_ids = df["job_id"].isna().sum()
    if missing_ids:
        df["job_id"] = df["job_id"].fillna(
            pd.Series(
                [f"generated_{i}" for i in range(missing_ids)],
                index=df.index[df["job_id"].isna()],
            )
        )
        logger.debug("Generated IDs for %d record(s) missing job_id", missing_ids)

    logger.info("Missing-value handling complete — rows remaining: %d", len(df))
    return df


def standardise_location(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise the location_raw field into clean city and state/country columns.
    Handles common formats: 'City, State', 'City', 'Remote', etc.

    Args:
        df: Input DataFrame.

    Returns:
        DataFrame with 'city' and 'state_country' columns added.
    """
    def _parse_location(raw: str):
        """Return (city, state_country) tuple from a raw location string."""
        if not raw or raw.strip().lower() in ("", "unknown location"):
            return "Unknown", "Unknown"

        raw = raw.strip()

        # Handle 'Remote' variations
        if raw.lower() in ("remote", "work from home", "wfh", "anywhere"):
            return "Remote", "Remote"

        # Split on the first comma
        parts = [p.strip() for p in raw.split(",", 1)]
        city = parts[0] if parts[0] else "Unknown"
        state_country = parts[1] if len(parts) > 1 else "Unknown"

        return city, state_country

    parsed = df["location_raw"].apply(_parse_location)
    df["city"] = parsed.apply(lambda x: x[0])
    df["state_country"] = parsed.apply(lambda x: x[1])

    logger.info("Location standardisation complete")
    return df


def standardise_salary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Coerce salary columns to numeric, cap obvious outliers, and compute
    a salary_avg column for convenience.

    Heuristic caps: min $10k, max $1M (annual USD assumptions).

    Args:
        df: Input DataFrame.

    Returns:
        DataFrame with cleaned salary columns and salary_avg added.
    """
    for col in ("salary_min", "salary_max"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Cap outliers
    SALARY_FLOOR = 10_000
    SALARY_CEILING = 1_000_000

    for col in ("salary_min", "salary_max"):
        original_nulls = df[col].isna().sum()
        df[col] = df[col].where(
            df[col].between(SALARY_FLOOR, SALARY_CEILING, inclusive="both"),
            other=pd.NA,
        )
        new_nulls = df[col].isna().sum()
        capped = new_nulls - original_nulls
        if capped > 0:
            logger.debug("Capped %d outlier value(s) in '%s'", capped, col)

    # Average salary where both bounds are available
    df["salary_avg"] = df[["salary_min", "salary_max"]].mean(axis=1)

    salary_available = df["salary_avg"].notna().sum()
    logger.info(
        "Salary standardisation complete — %d/%d records have salary data",
        salary_available,
        len(df),
    )
    return df


def clean_text_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise free-text columns: strip whitespace, normalise internal spaces,
    and title-case company names.

    Args:
        df: Input DataFrame.

    Returns:
        DataFrame with cleaned text fields.
    """
    # Strip leading/trailing whitespace
    for col in ("title", "company", "description"):
        if col in df.columns:
            df[col] = df[col].str.strip()

    # Collapse multiple internal spaces / newlines in description
    df["description"] = df["description"].str.replace(r"\s+", " ", regex=True)

    # Normalise title to title-case
    df["title"] = df["title"].str.title()

    # Normalise contract_type to lowercase
    df["contract_type"] = df["contract_type"].str.lower().str.strip()

    logger.debug("Text field normalisation complete")
    return df


def parse_posted_at(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse the posted_at field to a proper datetime, extract the date,
    and compute days_since_posted.

    Args:
        df: Input DataFrame.

    Returns:
        DataFrame with 'posted_date' and 'days_since_posted' columns.
    """
    df["posted_at"] = pd.to_datetime(df["posted_at"], errors="coerce", utc=True)
    df["posted_date"] = df["posted_at"].dt.date

    now = pd.Timestamp.utcnow()
    df["days_since_posted"] = (now - df["posted_at"]).dt.days

    logger.debug("Date parsing complete")
    return df


# ---------------------------------------------------------------------------
# Skill extraction
# ---------------------------------------------------------------------------

def extract_skills(df: pd.DataFrame, skills_list: list[str]) -> pd.DataFrame:
    """
    Scan job descriptions for known skill keywords using case-insensitive
    whole-word matching. Adds a comma-separated 'skills' column.

    Args:
        df: Input DataFrame with a 'description' column.
        skills_list: List of skill keywords to detect.

    Returns:
        DataFrame with 'skills' column added.
    """
    # Pre-compile regex patterns for performance
    skill_patterns = {
        skill: re.compile(
            r"(?<![A-Za-z0-9])" + re.escape(skill) + r"(?![A-Za-z0-9])",
            flags=re.IGNORECASE,
        )
        for skill in skills_list
    }

    def _find_skills(text: str) -> str:
        if not isinstance(text, str) or not text.strip():
            return ""
        found = [
            skill
            for skill, pattern in skill_patterns.items()
            if pattern.search(text)
        ]
        return ", ".join(found)

    df["skills"] = df["description"].apply(_find_skills)

    # Summary stats
    skill_counts = (
        df["skills"]
        .str.split(", ")
        .explode()
        .str.strip()
        .dropna()
        .loc[lambda s: s != ""]
        .value_counts()
    )
    logger.info(
        "Skill extraction complete — top 5 skills: %s",
        skill_counts.head(5).to_dict(),
    )
    return df


# ---------------------------------------------------------------------------
# Save processed data
# ---------------------------------------------------------------------------

def save_processed_data(df: pd.DataFrame, config: dict) -> Path:
    """
    Save the cleaned DataFrame to a CSV file.

    Args:
        df: Cleaned DataFrame.
        config: Full pipeline configuration dictionary.

    Returns:
        Path to the saved CSV file.
    """
    output_path = get_processed_filepath(config)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(output_path, index=False, encoding="utf-8")
    logger.info("Processed data saved → %s (%d records)", output_path, len(df))
    return output_path


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_transformation(config: dict) -> pd.DataFrame:
    """
    Orchestrate the full transformation phase.

    Steps:
        1. Load raw JSON
        2. Flatten nested records
        3. Remove duplicates
        4. Handle missing values
        5. Standardise location
        6. Standardise salary
        7. Clean text fields
        8. Parse dates
        9. Extract skills
        10. Save cleaned CSV

    Args:
        config: Full pipeline configuration dictionary.

    Returns:
        Cleaned and enriched Pandas DataFrame.
    """
    logger.info("=== TRANSFORMATION PHASE START ===")

    # 1. Load
    raw_jobs = load_raw_data(config)
    df = flatten_records(raw_jobs)
    log_dataframe_summary(df, logger, "After flatten")

    # 2–4. Core cleaning
    df = remove_duplicates(df)
    df = handle_missing_values(df)
    df = clean_text_fields(df)

    # 5–8. Normalisation
    df = standardise_location(df)
    df = standardise_salary(df)
    df = parse_posted_at(df)

    # 9. Skill extraction
    skills_list = config["pipeline"]["skills_to_extract"]
    df = extract_skills(df, skills_list)

    log_dataframe_summary(df, logger, "Final cleaned DataFrame")

    # 10. Save
    save_processed_data(df, config)

    logger.info("=== TRANSFORMATION PHASE COMPLETE — %d records ===", len(df))
    return df
