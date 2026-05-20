"""
conftest.py — root-level pytest configuration.

Loads the .env file before any test module is imported, so environment
variables are available to every test and to the modules under python/.

Provides shared utility functions for checking test environment availability:
  - narr_grid_available(): Checks if narr_latlon.h5 test fixture exists
  - aws_fully_configured(): Checks if AWS credentials and NARR_BUCKET are configured
  - narr_s3_available(): Alias for aws_fully_configured() for backward compat
"""
import os
from pathlib import Path
from dotenv import load_dotenv

def pytest_configure(config):
    """Load .env once at the very start of the test session."""
    
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)
    else:
        raise RuntimeError("Environment file not found")


# ---------------------------------------------------------------------------
# Shared environment checking utilities
# ---------------------------------------------------------------------------

def narr_grid_available() -> bool:
    """Return True if the test narr_latlon.h5 fixture is available."""
    test_data_dir = Path(__file__).parent / "tests" / "data"
    test_grid_file = test_data_dir / "narr_latlon.h5"
    return test_grid_file.exists()


def aws_fully_configured() -> bool:
    """Return True only when AWS credentials and NARR_BUCKET are configured.
    
    Tries to load AWS config from environment (.env already loaded by pytest_configure).
    Returns True only if both credentials are valid AND NARR_BUCKET is set.
    """
    try:
        from mioffset.aws import get_aws_config
        get_aws_config()  # raises ValueError when credentials are missing
    except (ValueError, Exception):
        return False
    return bool(os.getenv("NARR_BUCKET"))


def narr_s3_available() -> bool:
    """Alias for aws_fully_configured() for backward compatibility.
    
    Returns True if AWS credentials and both NARR_BUCKET and NARR_GRID_LATLON_S3
    environment variables are configured.
    """
    if not aws_fully_configured():
        return False
    key = os.getenv("NARR_GRID_LATLON_S3", "")
    return bool(key)
