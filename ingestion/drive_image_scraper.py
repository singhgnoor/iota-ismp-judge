"""
Scrapes images from a public drive image link.
"""

import requests
from urllib.parse import urlparse, parse_qs


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


def download_drive_image(url: str, output_path: str):
    file_id = get_file_id(url)

    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    response = requests.get(download_url)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(response.content)

if __name__ == '__main__':
    url = input("Enter the public drive image link: ")
    download_drive_image(
        url=url,
        output_path="image.jpg",
    )