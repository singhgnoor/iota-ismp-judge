"""
Scrapes images from a public drive image link.
"""

import mimetypes
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import requests
from config import REQUEST_HEADERS, REQUEST_TIMEOUT
from core.log import get_logger

logger = get_logger(__name__)

# Google sometimes can't scan large files for viruses (or the file isn't
# actually public) and serves an HTML confirmation page instead of the raw
# bytes when hit via uc?export=download. Treat that as a scrape failure
# rather than silently saving an HTML page as an "image".
_HTML_CONTENT_TYPES = {"text/html"}


def get_file_id(url: str) -> str:
    parsed = urlparse(url)

    # Handles:
    # https://drive.google.com/open?id=...
    if "id" in parse_qs(parsed.query):
        return parse_qs(parsed.query)["id"][0]

    # Handles:
    # https://drive.google.com/file/d/<ID>/view
    parts = parsed.path.split("/")
    if "d" in parts:
        return parts[parts.index("d") + 1]

    raise ValueError("Could not extract file ID")


def download_drive_image(url: str, output_path_no_ext: Path) -> Path:
    """
    Downloads a public Drive image and writes it to disk, with the
    extension inferred from the response's Content-Type.

    Parameters
    ----------
    url : str
        Public Drive share link.
    output_path_no_ext : Path
        Destination path WITHOUT an extension, e.g. .../SUB-001/image_1
        The correct extension (.jpg, .png, ...) is appended automatically.

    Returns
    -------
    Path
        The final path the file was written to, including its extension.

    Raises
    ------
    ValueError
        If the file ID can't be parsed from the URL, Drive serves back an
        HTML page instead of image bytes, or the Content-Type can't be
        mapped to an extension.
    requests.HTTPError
        If the download request itself fails (404, 403, etc.).
    """
    file_id = get_file_id(url)

    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    logger.info(f"Downloading drive image id {file_id} : url {download_url}")

    response = requests.get(
        download_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT
)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").split(";")[0].strip()

    if content_type in _HTML_CONTENT_TYPES:
        raise ValueError(
            "Drive returned an HTML page instead of image bytes (likely "
            "the 'can't scan for viruses' interstitial for large files, "
            "or the file isn't actually publicly shared)"
        )

    ext = mimetypes.guess_extension(content_type) or ""
    if not ext:
        raise ValueError(
            f"Could not determine an image extension from Content-Type '{content_type}'"
        )
    if ext == ".jpe":
        ext = ".jpg"

    final_path = output_path_no_ext.with_suffix(ext)
    final_path.write_bytes(response.content)

    logger.debug(f"Saved {len(response.content)} bytes to {final_path}")

    return final_path


if __name__ == "__main__":
    url = input("Enter the public drive image link: ").strip()
    saved_path = download_drive_image(
        url=url,
        output_path_no_ext=Path("image"),
    )
    print(f"Saved to {saved_path}")