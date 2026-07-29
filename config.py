"""
Project-wide Central Configuration.
Resolves the project directories.

Single source of truth for tunable constants used across the pipeline.
"""

from pathlib import Path

# DEBUG -
VERBOSE = False

## Dirs
BASE_DIR = Path(__file__).resolve().parent
RAW_CSV_PATH = BASE_DIR / "data" / "raw" / "form_responses.csv"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# Logging
LOG_LEVEL = "DEBUG" if VERBOSE else "INFO"

# CSV column mapping (your actual Google Form headers → internal keys)
CSV_COLUMN_MAP = {
    "drive_link": "Upload your images (Google Drive folder link)",
    "chat_link": "Chat link (ChatGPT/Gemini)",
}

#  HTTP
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
REQUEST_TIMEOUT = 15  # seconds