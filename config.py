"""
Project-wide Central Configuration.
Resolves the project directories.

Single source of truth for tunable constants used across the pipeline.
"""

from pathlib import Path

load_dotenv()

# DEBUG -
VERBOSE = False


## Dirs
BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# Logging
LOG_LEVEL = "DEBUG" if VERBOSE else "INFO"