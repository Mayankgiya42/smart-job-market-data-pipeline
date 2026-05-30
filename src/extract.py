"""
extract.py
----------
Extracts job listings from the Adzuna API (or mock data) and saves the
raw JSON response to the data/raw/ directory for downstream processing.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from src.utils import get_logger, get_raw_filepath, safe_get

logger = get_logger("extract")


# ---------------------------------------------------------------------------
# Mock data — used when use_mock_data: true or API key is not configured
# ---------------------------------------------------------------------------

MOCK_RESPONSE = {
    "results": [
        {
            "id": "ind_001",
            "title": "Data Engineer",
            "company": {"display_name": "TCS"},
            "location": {"display_name": "Bangalore, India"},
            "description": "Python, SQL, AWS, Airflow, ETL pipelines",
            "salary_min": 800000,
            "salary_max": 1500000,
            "created": "2024-03-15T09:00:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_002",
            "title": "Senior Data Engineer",
            "company": {"display_name": "Infosys"},
            "location": {"display_name": "Hyderabad, India"},
            "description": "Python, SQL, Spark, AWS",
            "salary_min": 1200000,
            "salary_max": 2200000,
            "created": "2024-03-14T10:30:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_003",
            "title": "Data Engineer",
            "company": {"display_name": "Wipro"},
            "location": {"display_name": "Pune, India"},
            "description": "Python, SQL, ETL, Airflow",
            "salary_min": 700000,
            "salary_max": 1400000,
            "created": "2024-03-13T14:00:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_004",
            "title": "Data Engineer",
            "company": {"display_name": "Accenture"},
            "location": {"display_name": "Mumbai, India"},
            "description": "Python, SQL, Azure, Power BI",
            "salary_min": 900000,
            "salary_max": 1600000,
            "created": "2024-03-12T08:00:00Z",
            "redirect_url": "#",
            "contract_type": "contract",
        },
        {
            "id": "ind_005",
            "title": "Junior Data Engineer",
            "company": {"display_name": "Capgemini"},
            "location": {"display_name": "Chennai, India"},
            "description": "Python, SQL, MySQL, ETL",
            "salary_min": 500000,
            "salary_max": 900000,
            "created": "2024-03-11T11:00:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_006",
            "title": "Data Engineer",
            "company": {"display_name": "Flipkart"},
            "location": {"display_name": "Bangalore, India"},
            "description": "Python, SQL, Kafka, Spark, AWS",
            "salary_min": 1500000,
            "salary_max": 2800000,
            "created": "2024-03-10T09:30:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_007",
            "title": "Data Engineer",
            "company": {"display_name": "Zomato"},
            "location": {"display_name": "Delhi, India"},
            "description": "Python, SQL, ETL, AWS",
            "salary_min": 1100000,
            "salary_max": 2000000,
            "created": "2024-03-09T15:00:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_008",
            "title": "Data Engineer",
            "company": {"display_name": "Swiggy"},
            "location": {"display_name": "Bangalore, India"},
            "description": "Python, SQL, Airflow, Docker",
            "salary_min": 1300000,
            "salary_max": 2400000,
            "created": "2024-03-08T12:00:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_009",
            "title": "Data Engineer",
            "company": {"display_name": "HCLTech"},
            "location": {"display_name": "Noida, India"},
            "description": "Python, SQL, ETL, AWS",
            "salary_min": 800000,
            "salary_max": 1500000,
            "created": "2024-03-07T10:00:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_010",
            "title": "Data Engineer",
            "company": {"display_name": "Tech Mahindra"},
            "location": {"display_name": "Pune, India"},
            "description": "Python, SQL, Spark, Hadoop",
            "salary_min": 900000,
            "salary_max": 1600000,
            "created": "2024-03-06T09:00:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_011",
            "title": "Senior Data Engineer",
            "company": {"display_name": "Amazon India"},
            "location": {"display_name": "Hyderabad, India"},
            "description": "Python, SQL, AWS, Redshift",
            "salary_min": 2000000,
            "salary_max": 3500000,
            "created": "2024-03-05T08:00:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_012",
            "title": "Data Engineer",
            "company": {"display_name": "Paytm"},
            "location": {"display_name": "Noida, India"},
            "description": "Python, SQL, Kafka, AWS",
            "salary_min": 1400000,
            "salary_max": 2600000,
            "created": "2024-03-04T07:30:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_013",
            "title": "Data Engineer",
            "company": {"display_name": "Ola"},
            "location": {"display_name": "Bangalore, India"},
            "description": "Python, SQL, Spark, ETL",
            "salary_min": 1500000,
            "salary_max": 2700000,
            "created": "2024-03-03T06:30:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_014",
            "title": "Data Engineer",
            "company": {"display_name": "Reliance Jio"},
            "location": {"display_name": "Mumbai, India"},
            "description": "Python, SQL, Hadoop, ETL",
            "salary_min": 1000000,
            "salary_max": 1800000,
            "created": "2024-03-02T05:30:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_015",
            "title": "Junior Data Engineer",
            "company": {"display_name": "Cognizant"},
            "location": {"display_name": "Chennai, India"},
            "description": "Python, SQL, ETL",
            "salary_min": 600000,
            "salary_max": 1000000,
            "created": "2024-03-01T04:30:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_016",
            "title": "Data Engineer",
            "company": {"display_name": "Byju's"},
            "location": {"display_name": "Bangalore, India"},
            "description": "Python, SQL, AWS, Airflow",
            "salary_min": 1300000,
            "salary_max": 2200000,
            "created": "2024-02-28T03:30:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_017",
            "title": "Data Engineer",
            "company": {"display_name": "Freshworks"},
            "location": {"display_name": "Chennai, India"},
            "description": "Python, SQL, ETL, APIs",
            "salary_min": 1200000,
            "salary_max": 2000000,
            "created": "2024-02-27T02:30:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_018",
            "title": "Data Engineer",
            "company": {"display_name": "Zoho"},
            "location": {"display_name": "Chennai, India"},
            "description": "Python, SQL, ETL, cloud",
            "salary_min": 1100000,
            "salary_max": 1900000,
            "created": "2024-02-26T01:30:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_019",
            "title": "Data Engineer",
            "company": {"display_name": "Meesho"},
            "location": {"display_name": "Bangalore, India"},
            "description": "Python, SQL, Spark, AWS",
            "salary_min": 1400000,
            "salary_max": 2600000,
            "created": "2024-02-25T00:30:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        },
        {
            "id": "ind_020",
            "title": "Data Engineer",
            "company": {"display_name": "PhonePe"},
            "location": {"display_name": "Bangalore, India"},
            "description": "Python, SQL, Kafka, ETL",
            "salary_min": 1500000,
            "salary_max": 2800000,
            "created": "2024-02-24T00:00:00Z",
            "redirect_url": "#",
            "contract_type": "permanent",
        }
    ]
}
MOCK_JOBS = MOCK_RESPONSE["results"]

# ---------------------------------------------------------------------------
# Adzuna API client
# ---------------------------------------------------------------------------

def _build_adzuna_url(config: dict, page: int) -> str:
    """Construct the Adzuna API endpoint URL for a specific page."""
    api_cfg = config["api"]
    country = api_cfg["country"]
    base_url = api_cfg["base_url"]
    return f"{base_url}/{country}/search/{page}"


def _build_adzuna_params(config: dict) -> dict:
    """Build the query parameters dict for the Adzuna API request."""
    api_cfg = config["api"]
    return {
        "app_id": api_cfg["app_id"],
        "app_key": api_cfg["app_key"],
        "results_per_page": api_cfg["results_per_page"],
        "what": api_cfg["search_term"],
        "content-type": "application/json",
    }


def fetch_from_adzuna(config: dict) -> list[dict]:
    """
    Fetch job listings from the Adzuna API across multiple pages.

    Args:
        config: Full pipeline configuration dictionary.

    Returns:
        List of raw job listing dictionaries.

    Raises:
        requests.HTTPError: On non-2xx API responses.
        requests.ConnectionError: On network failures.
    """
    api_cfg = config["api"]
    max_pages = api_cfg["max_pages"]
    params = _build_adzuna_params(config)
    all_jobs: list[dict] = []

    logger.info(
        "Fetching '%s' jobs from Adzuna API — up to %d pages x %d results",
        api_cfg["search_term"],
        max_pages,
        api_cfg["results_per_page"],
    )

    for page in range(1, max_pages + 1):
        url = _build_adzuna_url(config, page)
        logger.debug("Requesting page %d: %s", page, url)

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.HTTPError as exc:
            logger.error("HTTP error on page %d: %s", page, exc)
            raise
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error on page %d: %s", page, exc)
            raise
        except requests.exceptions.Timeout:
            logger.warning("Request timed out on page %d — skipping", page)
            continue

        results = data.get("results", [])
        if not results:
            logger.info("No results returned on page %d — stopping early", page)
            break

        all_jobs.extend(results)
        logger.info("Page %d: fetched %d jobs (total so far: %d)", page, len(results), len(all_jobs))

        # Respect API rate limits
        time.sleep(0.5)

    logger.info("Adzuna fetch complete — total jobs retrieved: %d", len(all_jobs))
    return all_jobs


# ---------------------------------------------------------------------------
# Mock data provider
# ---------------------------------------------------------------------------

def fetch_mock_data() -> list[dict]:
    """
    Return a pre-built list of mock job listings.
    Used when use_mock_data is true in config or when running tests.

    Returns:
        List of mock job listing dictionaries.
    """
    logger.info("Using mock data — %d records loaded (includes 1 intentional duplicate)", len(MOCK_JOBS))
    return MOCK_JOBS


# ---------------------------------------------------------------------------
# Save raw data
# ---------------------------------------------------------------------------

def save_raw_data(jobs: list[dict], config: dict) -> Path:
    """
    Persist raw job data as a JSON file in the raw data directory.

    Args:
        jobs: List of raw job dictionaries.
        config: Full pipeline configuration dictionary.

    Returns:
        Path to the saved JSON file.
    """
    output_path = get_raw_filepath(config)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "extracted_at": datetime.utcnow().isoformat() + "Z",
        "total_records": len(jobs),
        "source": config["api"]["provider"],
        "search_term": config["api"]["search_term"],
        "jobs": jobs,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    logger.info("Raw data saved → %s (%d records)", output_path, len(jobs))
    return output_path


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_extraction(config: dict) -> Path:
    """
    Orchestrate the extraction phase: fetch jobs and save raw JSON.

    Args:
        config: Full pipeline configuration dictionary.

    Returns:
        Path to the saved raw JSON file.
    """
    logger.info("=== EXTRACTION PHASE START ===")

    use_mock = config["api"].get("use_mock_data", False)
    app_id = config["api"].get("app_id", "YOUR_ADZUNA_APP_ID")
    placeholder = "YOUR_ADZUNA_APP_ID"

    if use_mock or app_id == placeholder:
        if not use_mock:
            logger.warning(
                "API credentials not configured — falling back to mock data. "
                "Set app_id / app_key in config.yaml to use the real API."
            )
        jobs = fetch_mock_data()
    else:
        jobs = fetch_from_adzuna(config)

    if not jobs:
        logger.warning("No jobs retrieved — pipeline will continue with empty dataset")

    output_path = save_raw_data(jobs, config)
    logger.info("=== EXTRACTION PHASE COMPLETE ===")
    return output_path
