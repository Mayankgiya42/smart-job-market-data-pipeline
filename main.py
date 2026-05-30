"""
main.py
-------
Pipeline orchestrator for the Smart Job Market Data Pipeline.

Runs the three phases in sequence:
    1. Extract  — fetch job listings from API → data/raw/
    2. Transform — clean & enrich with Pandas → data/processed/
    3. Load     — insert into PostgreSQL → job_market_db

Usage:
    python main.py                     # Run full pipeline
    python main.py --phase extract     # Run only extraction
    python main.py --phase transform   # Run only transformation
    python main.py --phase load        # Run only loading
    python main.py --config my.yaml    # Use a custom config file
"""

import argparse
import sys
import time
from pathlib import Path

# Ensure the project root is on the Python path when run directly
sys.path.insert(0, str(Path(__file__).parent))

from src.extract import run_extraction
from src.transform import run_transformation
from src.load import run_loading
from src.utils import (
    ensure_directories,
    format_duration,
    load_config,
    setup_logging,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Smart Job Market Data Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the YAML configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--phase",
        choices=["extract", "transform", "load", "all"],
        default="all",
        help="Pipeline phase to run (default: all)",
    )
    return parser.parse_args()


def run_pipeline(config: dict, phase: str, logger) -> None:
    """
    Execute one or all pipeline phases.

    Args:
        config: Loaded configuration dictionary.
        phase:  One of 'extract', 'transform', 'load', 'all'.
        logger: Configured root logger instance.
    """
    pipeline_start = time.perf_counter()
    logger.info("╔══════════════════════════════════════════════════╗")
    logger.info("║     Smart Job Market Data Pipeline               ║")
    logger.info("╚══════════════════════════════════════════════════╝")
    logger.info("Phase selected: %s", phase.upper())

    df = None  # DataFrame passed between transform and load phases

    # ------------------------------------------------------------------
    # Phase 1 — Extract
    # ------------------------------------------------------------------
    if phase in ("extract", "all"):
        t0 = time.perf_counter()
        try:
            run_extraction(config)
            logger.info("✔ Extraction completed in %s", format_duration(time.perf_counter() - t0))
        except Exception as exc:
            logger.error("✘ Extraction failed: %s", exc, exc_info=True)
            raise SystemExit(1) from exc

    # ------------------------------------------------------------------
    # Phase 2 — Transform
    # ------------------------------------------------------------------
    if phase in ("transform", "all"):
        t0 = time.perf_counter()
        try:
            df = run_transformation(config)
            logger.info("✔ Transformation completed in %s", format_duration(time.perf_counter() - t0))
        except Exception as exc:
            logger.error("✘ Transformation failed: %s", exc, exc_info=True)
            raise SystemExit(1) from exc

    # ------------------------------------------------------------------
    # Phase 3 — Load
    # ------------------------------------------------------------------
    if phase in ("load", "all"):
        t0 = time.perf_counter()
        try:
            run_loading(config, df=df)
            logger.info("✔ Loading completed in %s", format_duration(time.perf_counter() - t0))
        except Exception as exc:
            logger.error(
                "✘ Loading failed: %s\n"
                "  → If PostgreSQL is not available, run with --phase extract or --phase transform\n"
                "    to exercise the pipeline without a database.",
                exc,
                exc_info=True,
            )
            raise SystemExit(1) from exc

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    total = format_duration(time.perf_counter() - pipeline_start)
    logger.info("══════════════════════════════════════════════════")
    logger.info("Pipeline finished successfully in %s", total)
    logger.info("══════════════════════════════════════════════════")


def main() -> None:
    """Entry point: parse arguments, load config, and run the pipeline."""
    args = parse_args()

    # Load config first so we can set up logging with its settings
    try:
        config = load_config(args.config)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    # Ensure output directories exist
    ensure_directories(config)

    # Set up the root 'pipeline' logger (all child loggers inherit it)
    logger = setup_logging(config, logger_name="pipeline")

    run_pipeline(config, args.phase, logger)


if __name__ == "__main__":
    main()
