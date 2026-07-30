"""
Ingestion orchestrator for the ISMP judge pipeline.

Reads data/raw/form_responses.csv row by row. Each row is one submission
containing N parallel (chat_link, image_link) session pairs, matched by
position via CSV_COLUMN_MAP["chat_links"][i] <-> CSV_COLUMN_MAP["drive_links"][i].
For every session the orchestrator:

  - scrapes the chat conversation via gpt_scraper.scrape_chatgpt_share
  - downloads the paired image via drive_image_scraper.download_drive_image
  - saves the image as data/processed/SUB-<row>/image_<session>.<ext>

All scraped data plus the passthrough form columns (CSV_METADATA_COLUMNS)
are written to data/processed/SUB-<row>/metadata.json.

Failures are isolated per field, never per row: if a chat or an image fails
to scrape, that single entry is left null in metadata.json and a WARNING is
logged with the row, session index, and URL so it can be filled in
manually. Every other session in the row is still processed.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from config import (
    CSV_COLUMN_MAP,
    CSV_METADATA_COLUMNS,
    PROCESSED_DIR,
    RAW_CSV_PATH,
)
from core.log import get_logger
from ingestion.drive_image_scraper import download_drive_image
from ingestion.gpt_scraper import scrape_chatgpt_share

logger = get_logger(__name__)


def _submission_dir(row_number: int) -> Path:
    sub_dir = PROCESSED_DIR / f"SUB-{row_number:03d}"
    sub_dir.mkdir(parents=True, exist_ok=True)
    return sub_dir


def _scrape_chat(
    url: str, row_number: int, session_index: int
) -> tuple[list[dict[str, str]] | None, str | None]:
    """Returns (chat_turns_as_dicts, error_message). Either may be None."""
    if not url:
        return None, None  # blank in the form, not a scrape failure

    try:
        turns = scrape_chatgpt_share(url)
        if not turns:
            raise ValueError("Scraper returned zero turns")
        return [asdict(turn) for turn in turns], None
    except Exception as exc:
        logger.warning(
            f"[SUB-{row_number:03d}][session {session_index}] "
            f"Could not scrape chat link, needs MANUAL retrieval: {url} ({exc!r})"
        )
        return None, str(exc)


def _download_image(
    url: str, sub_dir: Path, row_number: int, session_index: int
) -> tuple[str | None, str | None]:
    """Returns (saved_filename, error_message). Either may be None."""
    if not url:
        return None, None  # blank in the form, not a scrape failure

    target_stem = sub_dir / f"image_{session_index}"
    try:
        final_path = download_drive_image(url, target_stem)
        return final_path.name, None
    except Exception as exc:
        logger.warning(
            f"[SUB-{row_number:03d}][session {session_index}] "
            f"Could not download image, needs MANUAL retrieval: {url} ({exc!r})"
        )
        return None, str(exc)


def _process_row(row_number: int, row: dict[str, str]) -> None:
    sub_dir = _submission_dir(row_number)

    form_metadata = {col: row.get(col, "") for col in CSV_METADATA_COLUMNS}

    chat_cols = CSV_COLUMN_MAP["chat_links"]
    image_cols = CSV_COLUMN_MAP["drive_links"]

    if len(chat_cols) != len(image_cols):
        raise ValueError(
            "CSV_COLUMN_MAP['chat_links'] and ['drive_links'] must be the "
            f"same length (got {len(chat_cols)} vs {len(image_cols)})"
        )

    sessions: list[dict[str, Any]] = []

    for session_index, (chat_col, image_col) in enumerate(
        zip(chat_cols, image_cols), start=1
    ):
        chat_url = (row.get(chat_col) or "").strip()
        image_url = (row.get(image_col) or "").strip()

        chat_turns, chat_error = _scrape_chat(chat_url, row_number, session_index)
        image_filename, image_error = _download_image(
            image_url, sub_dir, row_number, session_index
        )

        sessions.append(
            {
                "index": session_index,
                "chat_link": chat_url or None,
                "chat_turns": chat_turns,
                "chat_scrape_error": chat_error,
                "image_link": image_url or None,
                "image_filename": image_filename,
                "image_scrape_error": image_error,
            }
        )

    metadata = {
        "submission_id": sub_dir.name,
        "row_number": row_number,
        "form_metadata": form_metadata,
        "sessions": sessions,
    }

    metadata_path = sub_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    logger.info(f"Wrote {metadata_path}")


def run(csv_path: Path = RAW_CSV_PATH) -> None:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row_number, row in enumerate(reader, start=1):
            logger.info(f"Processing row {row_number}...")
            logger.debug(f"Processing row {row_number} : {row}")
            try:
                _process_row(row_number, row)
            except Exception:
                # Only truly unexpected failures (bad CSV row, disk error,
                # misconfigured CSV_COLUMN_MAP) skip the whole row. Individual
                # chat/image scrape failures are handled per-field above and
                # never abort a row.
                logger.exception(f"Row {row_number} failed entirely, skipping.")


if __name__ == "__main__":
    run()