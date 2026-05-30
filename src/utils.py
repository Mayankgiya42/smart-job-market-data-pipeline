"""
utils.py
--------
Shared utilities: logging configuration, config loading, and helper functions
used across the pipeline modules.
"""

import logging
import os
import sys
import yaml
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration loader
# ---------------------------------------------------------------------------

def load_config(config_path: str = "config.yaml") -> dict:
    """
    Load and return the YAML configuration file.

    Args:
        config_path: Path to the YAML config file.

    Returns:
        Dictionary with all configuration values.

    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the file is not valid YAML.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. "
            "Please create it from config.yaml.example."
        )

    with open(path, "r") as f:
        config = yaml.safe_load(f)

    return config


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(config: dict, logger_name: str = "pipeline") -> logging.Logger:
    """
    Configure and return a logger with both console and rotating file handlers.

    Args:
        config: Full pipeline config dictionary.
        logger_name: Name of the logger instance.

    Returns:
        Configured logging.Logger instance.
    """
    log_cfg = config.get("logging", {})
    log_dir = Path(config["paths"]["logs_dir"])
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    log_format = log_cfg.get(
        "format", "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    date_format = log_cfg.get("date_format", "%Y-%m-%d %H:%M:%S")

    # Timestamped log file for each pipeline run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"pipeline_{timestamp}.log"

    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)

    # Avoid duplicate handlers when module is re-imported
    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # File handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info("Logger initialised — log file: %s", log_file)
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Return a child logger scoped to a specific module.

    Args:
        name: Child logger name (e.g. 'pipeline.extract').

    Returns:
        logging.Logger instance.
    """
    return logging.getLogger(f"pipeline.{name}")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def ensure_directories(config: dict) -> None:
    """
    Create all required project directories if they do not exist.

    Args:
        config: Full pipeline config dictionary.
    """
    dirs = [
        config["paths"]["raw_data_dir"],
        config["paths"]["processed_data_dir"],
        config["paths"]["logs_dir"],
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)


def get_raw_filepath(config: dict) -> Path:
    """Return the full path for the raw JSON output file."""
    return Path(config["paths"]["raw_data_dir"]) / config["paths"]["raw_filename"]


def get_processed_filepath(config: dict) -> Path:
    """Return the full path for the processed CSV output file."""
    return (
        Path(config["paths"]["processed_data_dir"])
        / config["paths"]["processed_filename"]
    )


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def safe_get(d: dict, *keys, default=None):
    """
    Safely retrieve a nested value from a dictionary.

    Args:
        d: The dictionary to traverse.
        *keys: Sequence of keys forming the access path.
        default: Value to return if any key is missing.

    Returns:
        The nested value, or *default* if not found.

    Example:
        safe_get(record, "location", "display_name", default="Unknown")
    """
    current = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
        if current is default:
            return default
    return current


def format_duration(seconds: float) -> str:
    """
    Format a duration in seconds to a human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string like "2m 34s" or "45s".
    """
    if seconds >= 60:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    return f"{seconds:.2f}s"


def log_dataframe_summary(df, logger: logging.Logger, label: str = "DataFrame") -> None:
    """
    Log a concise summary of a Pandas DataFrame.

    Args:
        df: Pandas DataFrame to summarise.
        logger: Logger instance.
        label: Descriptive label for the log message.
    """
    logger.info(
        "%s — shape: %s | columns: %s",
        label,
        df.shape,
        list(df.columns),
    )
    null_counts = df.isnull().sum()
    nulls = null_counts[null_counts > 0]
    if not nulls.empty:
        logger.debug("Null value counts:\n%s", nulls.to_string())
