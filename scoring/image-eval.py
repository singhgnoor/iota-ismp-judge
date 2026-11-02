"""
This file is to evaluate the images and return a score for the same

Compares each submitted image against its column's reference image using
CLIP embeddings (sentence-transformers) + cosine similarity.

Reference images: one per form image-column (5 total), indexed by session
position — session 0 -> REFERENCE_IMAGES[0], etc. Same index convention
ingestion already uses for chat_links[i] <-> drive_links[i].

For each data/processed/SUB-<row>/ folder:
  - finds image_<session>.<ext> files
  - scores each against the matching reference image
  - writes scores into that folder's metadata.json under "similarity_scores"
  - also collects everything into data/processed/scores.csv (summary)
"""

import csv
import json
import re
from pathlib import Path
from PIL import Image
from sentence_transformers import SentenceTransformer, util

from config import SCORES_CSV, REFERENCE_IMAGES, PROCESSED_DIR
from core.log import get_logger

logger = get_logger(__name__)

_model = None

def get_model():
    global _model
    if _model is None:
        logger.info("Loading CLIP model (clip-ViT-B-32)")
        _model = SentenceTransformer("clip-ViT-B-32")
    return _model


def embed(image_path: Path):
    return get_model().encode(Image.open(image_path), convert_to_tensor=True)


def similarity(path_a: Path, path_b: Path) -> float:
    return util.cos_sim(embed(path_a), embed(path_b)).item()


def find_session_images(row_dir: Path) -> dict[int, Path]:
    """Map session index -> image path, from files named image_<session>.<ext>."""
    images = {}
    for f in row_dir.glob("image_*"):
        m = re.match(r"image_(\d+)\.\w+$", f.name)
        if m:
            images[int(m.group(1))] = f
    return images


def score_row(row_dir: Path) -> dict[int, float]:
    scores = {}
    for session, img_path in sorted(find_session_images(row_dir).items()):
        if session >= len(REFERENCE_IMAGES):
            logger.warning(
                "%s session %d has no matching reference image, skipping",
                row_dir.name, session,
            )
            continue
        ref_path = REFERENCE_IMAGES[session]
        if not ref_path.exists():
            logger.warning(
                "Reference image missing: %s, skipping session %d",
                ref_path, session,
            )
            continue
        try:
            scores[session] = round(similarity(img_path, ref_path), 4)
        except Exception:
            logger.exception("Failed to score %s", img_path)
    return scores


def write_metadata_scores(row_dir: Path, scores: dict[int, float]) -> None:
    meta_path = row_dir / "metadata.json"
    metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    metadata["similarity_scores"] = {str(k): v for k, v in scores.items()}
    meta_path.write_text(json.dumps(metadata, indent=2))


def main():
    summary_rows = []
    for row_dir in sorted(PROCESSED_DIR.glob("SUB-*")):
        if not row_dir.is_dir():
            continue
        scores = score_row(row_dir)
        write_metadata_scores(row_dir, scores)
        for session, score in scores.items():
            summary_rows.append({"submission": row_dir.name, "session": session, "similarity": score})
        logger.info("%s: %s", row_dir.name, scores)

    with open(SCORES_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["submission", "session", "similarity"])
        writer.writeheader()
        writer.writerows(summary_rows)

    logger.info("Done. Summary written to %s", SCORES_CSV)


if __name__ == "__main__":
    main()