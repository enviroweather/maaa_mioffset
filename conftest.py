"""
conftest.py — root-level pytest configuration.

Loads the .env file before any test module is imported, so environment
variables are available to every test and to the modules under python/.
"""
from pathlib import Path
from dotenv import load_dotenv

def pytest_configure(config):
    """Load .env once at the very start of the test session."""
    
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)
    else:
        raise RuntimeError("Environment file not found")
