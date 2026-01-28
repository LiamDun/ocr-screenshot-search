from pathlib import Path
from typing import Callable, Optional

import config
import database
import ocr_engine

# Supported image extensions
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}


def get_all_images(folder: Path) -> list[Path]:
    """
    Recursively find all image files in a folder.

    Args:
        folder: Root folder to scan

    Returns:
        List of Path objects for all image files
    """
    images = []

    for ext in IMAGE_EXTENSIONS:
        # Case-insensitive glob on Windows
        images.extend(folder.rglob(f"*{ext}"))
        images.extend(folder.rglob(f"*{ext.upper()}"))

    # Remove duplicates (in case of case-insensitive filesystem)
    unique_images = list(set(images))

    return sorted(unique_images, key=lambda p: p.stat().st_mtime, reverse=True)


def scan_and_index(
    folder: Optional[Path] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> dict:
    """
    Scan a folder for images and index them using OCR.

    Args:
        folder: Folder to scan (defaults to configured screenshots folder)
        progress_callback: Optional callback function(current, total, filename)

    Returns:
        Dict with 'indexed', 'skipped', and 'failed' counts
    """
    if folder is None:
        folder = Path(config.get_screenshots_folder())

    # Ensure database is initialized
    database.init_db()

    # Get all images
    images = get_all_images(folder)
    total = len(images)

    stats = {'indexed': 0, 'skipped': 0, 'failed': 0}

    for i, image_path in enumerate(images):
        file_path_str = str(image_path)

        # Report progress
        if progress_callback:
            progress_callback(i + 1, total, image_path.name)

        # Skip if already indexed
        if database.is_indexed(file_path_str):
            stats['skipped'] += 1
            continue

        # Extract text
        text = ocr_engine.extract_text(file_path_str)

        if text:
            database.add_screenshot(file_path_str, text)
            stats['indexed'] += 1
        else:
            # Still add to database with empty text so we don't retry
            database.add_screenshot(file_path_str, "")
            stats['failed'] += 1

    return stats
