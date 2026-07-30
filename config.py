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

# CSV column mapping (Google Form headers -> internal keys)
# "chat_links[i]" and "drive_links[i]" are paired by position: session i's
# chat is judged against session i's image. Both lists MUST be the same
# length. Edit the header strings below once the form schema is final.

CSV_COLUMN_MAP = {
    "chat_links": [
        "Chat link 1",
        "Chat link 2",
        "Chat link 3",
        "Chat link 4",
        "Chat link 5",
    ],
    "drive_links": [
        "Image 1",
        "Image 2",
        "Image 3",
        "Image 4",
        "Image 5",
    ],
}

# Other form columns (team name, email, member names, etc.) that should be
# copied verbatim into each submission's metadata.json. Not scraped, just
# passed through.
CSV_METADATA_COLUMNS = [
    "Team Name",
    "Email Address",
    "Member Names",
]

#  HTTP
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
REQUEST_TIMEOUT = 15  # seconds