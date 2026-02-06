"""
Database module for download statistics.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

DB_PATH = Path("./data/registry.db")


def init_db():
    """Initialize database and create tables."""
    DB_PATH.parent.mkdir(exist_ok=True)

    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_name TEXT NOT NULL,
                version TEXT NOT NULL,
                filename TEXT NOT NULL,
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT
            )
        """)

        # Index for faster queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_downloads_skill_date
            ON downloads(skill_name, downloaded_at)
        """)

        conn.commit()


@contextmanager
def get_connection():
    """Get database connection context manager."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def record_download(
    skill_name: str,
    version: str,
    filename: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> int:
    """Record a download event.

    Returns:
        The ID of the inserted record
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO downloads (skill_name, version, filename, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?)
            """,
            (skill_name, version, filename, ip_address, user_agent)
        )
        conn.commit()
        return cursor.lastrowid


def get_download_stats(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> Dict[str, Any]:
    """Get download statistics for a date range.

    Returns:
        {
            "total_downloads": int,
            "rankings": [
                {"skill_name": str, "author": str, "downloads": int},
                ...
            ]
        }
    """
    # Default to all time if no dates provided
    if start_date is None:
        start_date = date(1970, 1, 1)
    if end_date is None:
        end_date = date.today()

    with get_connection() as conn:
        # Get total downloads
        total_row = conn.execute(
            """
            SELECT COUNT(*) as total FROM downloads
            WHERE date(downloaded_at) BETWEEN ? AND ?
            """,
            (start_date.isoformat(), end_date.isoformat())
        ).fetchone()

        total_downloads = total_row["total"] if total_row else 0

        # Get rankings by skill
        rankings = []
        rows = conn.execute(
            """
            SELECT
                skill_name,
                COUNT(*) as download_count
            FROM downloads
            WHERE date(downloaded_at) BETWEEN ? AND ?
            GROUP BY skill_name
            ORDER BY download_count DESC
            """,
            (start_date.isoformat(), end_date.isoformat())
        ).fetchall()

        for row in rows:
            rankings.append({
                "skill_name": row["skill_name"],
                "downloads": row["download_count"]
            })

        return {
            "total_downloads": total_downloads,
            "rankings": rankings
        }


def get_stats_with_author(
    plugins: List[Dict],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> Dict[str, Any]:
    """Get download statistics with author information.

    Args:
        plugins: List of plugin info from scan_plugins()
        start_date: Start date for filtering
        end_date: End date for filtering

    Returns:
        Statistics with author info added
    """
    # Build skill to author mapping from plugins
    skill_author_map = {}
    for plugin in plugins:
        skill_name = plugin.get("name", "")
        metadata = plugin.get("metadata", {})
        author = metadata.get("author", {})
        author_name = author.get("name", "Unknown") if isinstance(author, dict) else "Unknown"
        skill_author_map[skill_name] = author_name

    # Get download stats
    stats = get_download_stats(start_date, end_date)

    # Add author to each ranking
    for ranking in stats["rankings"]:
        ranking["author"] = skill_author_map.get(ranking["skill_name"], "Unknown")

    return stats
