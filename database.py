import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import config

DB_PATH = Path(__file__).parent / "screenshots.db"


def get_connection():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with FTS5 virtual table."""
    conn = get_connection()
    cursor = conn.cursor()

    # Create FTS5 virtual table for full-text search
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS screenshots USING fts5(
            file_path,
            extracted_text,
            indexed_date
        )
    """)

    conn.commit()
    conn.close()


def add_screenshot(file_path: str, extracted_text: str):
    """Add a screenshot to the database."""
    conn = get_connection()
    cursor = conn.cursor()

    indexed_date = datetime.now().isoformat()

    cursor.execute(
        "INSERT INTO screenshots (file_path, extracted_text, indexed_date) VALUES (?, ?, ?)",
        (file_path, extracted_text, indexed_date)
    )

    conn.commit()
    conn.close()


def is_indexed(file_path: str) -> bool:
    """Check if a file is already indexed."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT file_path FROM screenshots WHERE file_path = ?",
        (file_path,)
    )

    result = cursor.fetchone() is not None
    conn.close()
    return result


def search(
    query: str,
    limit: int = 100,
    date_filter: Optional[str] = None,
    folder_filter: Optional[str] = None
) -> list:
    """
    Search for screenshots containing the query text.

    Args:
        query: Search text
        limit: Maximum results to return
        date_filter: One of 'today', 'week', 'month', 'year', or None for all
        folder_filter: Folder path to filter by, or None for all

    Returns list of dicts with file_path, extracted_text, and snippet.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Use FTS5 MATCH for full-text search with snippet
    cursor.execute("""
        SELECT
            file_path,
            extracted_text,
            snippet(screenshots, 1, '>>>', '<<<', '...', 30) as snippet,
            indexed_date
        FROM screenshots
        WHERE screenshots MATCH ?
        ORDER BY rank
        LIMIT ?
    """, (query, limit * 10))  # Fetch more to filter in Python

    results = []

    # Calculate date threshold if filtering
    date_threshold = None
    if date_filter:
        now = datetime.now()
        if date_filter == 'today':
            date_threshold = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_filter == 'week':
            date_threshold = now - timedelta(days=7)
        elif date_filter == 'month':
            date_threshold = now - timedelta(days=30)
        elif date_filter == 'year':
            date_threshold = now - timedelta(days=365)

    for row in cursor.fetchall():
        file_path = row['file_path']

        # Apply folder filter
        if folder_filter and folder_filter != "All Folders":
            if folder_filter not in file_path:
                continue

        # Apply date filter
        if date_threshold:
            try:
                indexed_date = datetime.fromisoformat(row['indexed_date'])
                if indexed_date < date_threshold:
                    continue
            except (ValueError, TypeError):
                pass

        results.append({
            'file_path': file_path,
            'extracted_text': row['extracted_text'],
            'snippet': row['snippet']
        })

        if len(results) >= limit:
            break

    conn.close()
    return results


def get_stats() -> dict:
    """Get database statistics."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM screenshots")
    count = cursor.fetchone()['count']

    conn.close()
    return {'total_indexed': count}


def delete_missing_files():
    """Remove entries for files that no longer exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT rowid, file_path FROM screenshots")
    rows = cursor.fetchall()

    deleted = 0
    for row in rows:
        if not Path(row['file_path']).exists():
            cursor.execute("DELETE FROM screenshots WHERE rowid = ?", (row['rowid'],))
            deleted += 1

    conn.commit()
    conn.close()
    return deleted


def get_folders() -> list[str]:
    """Get list of subfolders in the screenshots directory."""
    folders = ["All Folders"]

    screenshots_root = Path(config.get_screenshots_folder())
    if screenshots_root.exists():
        for item in sorted(screenshots_root.iterdir(), reverse=True):
            if item.is_dir():
                # Add year folder
                folders.append(item.name)
                # Add month subfolders
                for subitem in sorted(item.iterdir(), reverse=True):
                    if subitem.is_dir():
                        folders.append(f"{item.name}/{subitem.name}")

    return folders


def get_screenshot_text(file_path: str) -> str:
    """Get the extracted text for a specific screenshot."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT extracted_text FROM screenshots WHERE file_path = ?",
        (file_path,)
    )

    row = cursor.fetchone()
    conn.close()

    return row['extracted_text'] if row else ""
