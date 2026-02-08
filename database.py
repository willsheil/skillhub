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


def migrate_add_user_id_to_downloads():
    """Migrate downloads table to add user_id column if it doesn't exist."""
    with get_connection() as conn:
        # Check if user_id column already exists
        cursor = conn.execute("PRAGMA table_info(downloads)")
        columns = [row["name"] for row in cursor.fetchall()]

        if "user_id" not in columns:
            conn.execute("ALTER TABLE downloads ADD COLUMN user_id INTEGER")
            conn.commit()
            print("Migration: Added user_id column to downloads table")
        else:
            print("Migration: user_id column already exists in downloads table")


def init_db():
    """Initialize database and create tables."""
    DB_PATH.parent.mkdir(exist_ok=True)

    # Run migrations first
    migrate_add_user_id_to_downloads()

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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT UNIQUE NOT NULL,
                api_key TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        """)

        # Index for employee_id lookups
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_employee_id
            ON users(employee_id)
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_name TEXT NOT NULL,
                version TEXT NOT NULL,
                filename TEXT NOT NULL,
                uploader_id INTEGER NOT NULL,
                status TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                reviewer_id INTEGER,
                review_comment TEXT,
                FOREIGN KEY (uploader_id) REFERENCES users(id),
                FOREIGN KEY (reviewer_id) REFERENCES users(id)
            )
        """)

        # Index for status lookups
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_skills_status
            ON skills(status)
        """)

        # Index for uploader lookups
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_skills_uploader
            ON skills(uploader_id)
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
    user_agent: Optional[str] = None,
    user_id: Optional[int] = None
) -> int:
    """Record a download event.

    Args:
        skill_name: The name of the skill being downloaded
        version: The version of the skill
        filename: The filename being downloaded
        ip_address: Optional IP address of the downloader
        user_agent: Optional user agent string
        user_id: Optional user ID if authenticated

    Returns:
        The ID of the inserted record
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO downloads (skill_name, version, filename, ip_address, user_agent, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (skill_name, version, filename, ip_address, user_agent, user_id)
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


def get_user_by_credentials(employee_id: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Query user by employee ID and API key.

    Args:
        employee_id: The employee's ID
        api_key: The API key for authentication

    Returns:
        User dictionary if found, None otherwise
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, employee_id, api_key, role, created_at, last_login
            FROM users
            WHERE employee_id = ? AND api_key = ?
            """,
            (employee_id, api_key)
        ).fetchone()

        if row:
            return {
                "id": row["id"],
                "employee_id": row["employee_id"],
                "api_key": row["api_key"],
                "role": row["role"],
                "created_at": row["created_at"],
                "last_login": row["last_login"]
            }
        return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Query user by ID.

    Args:
        user_id: The user's ID

    Returns:
        User dictionary if found, None otherwise
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, employee_id, api_key, role, created_at, last_login
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()

        if row:
            return {
                "id": row["id"],
                "employee_id": row["employee_id"],
                "api_key": row["api_key"],
                "role": row["role"],
                "created_at": row["created_at"],
                "last_login": row["last_login"]
            }
        return None


def update_last_login(user_id: int) -> None:
    """Update the last login timestamp for a user.

    Args:
        user_id: The user's ID
    """
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE users
            SET last_login = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user_id,)
        )
        conn.commit()


def create_skill_record(
    skill_name: str,
    version: str,
    filename: str,
    uploader_id: int,
    status: str
) -> int:
    """Create a skill record.

    Args:
        skill_name: The name of the skill
        version: The version of the skill
        filename: The filename of the skill
        uploader_id: The ID of the user uploading the skill
        status: The status of the skill

    Returns:
        The ID of the inserted record
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO skills (skill_name, version, filename, uploader_id, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (skill_name, version, filename, uploader_id, status)
        )
        conn.commit()
        return cursor.lastrowid


def get_pending_skills() -> List[Dict[str, Any]]:
    """Get all pending skills with uploader information.

    Returns:
        List of pending skill dictionaries with uploader info
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                s.id,
                s.skill_name,
                s.version,
                s.filename,
                s.uploader_id,
                s.status,
                s.uploaded_at,
                s.reviewed_at,
                s.reviewer_id,
                s.review_comment,
                u.employee_id as uploader_employee_id
            FROM skills s
            JOIN users u ON s.uploader_id = u.id
            WHERE s.status = 'pending'
            """
        ).fetchall()

        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "skill_name": row["skill_name"],
                "version": row["version"],
                "filename": row["filename"],
                "uploader_id": row["uploader_id"],
                "status": row["status"],
                "uploaded_at": row["uploaded_at"],
                "reviewed_at": row["reviewed_at"],
                "reviewer_id": row["reviewer_id"],
                "review_comment": row["review_comment"],
                "uploader_employee_id": row["uploader_employee_id"]
            })

        return results


def get_skill_by_id(skill_id: int) -> Optional[Dict[str, Any]]:
    """Get a skill by its ID.

    Args:
        skill_id: The skill's ID

    Returns:
        Skill dictionary if found, None otherwise
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                id,
                skill_name,
                version,
                filename,
                uploader_id,
                status,
                uploaded_at,
                reviewed_at,
                reviewer_id,
                review_comment
            FROM skills
            WHERE id = ?
            """,
            (skill_id,)
        ).fetchone()

        if row:
            return {
                "id": row["id"],
                "skill_name": row["skill_name"],
                "version": row["version"],
                "filename": row["filename"],
                "uploader_id": row["uploader_id"],
                "status": row["status"],
                "uploaded_at": row["uploaded_at"],
                "reviewed_at": row["reviewed_at"],
                "reviewer_id": row["reviewer_id"],
                "review_comment": row["review_comment"]
            }
        return None


def update_skill_status(
    skill_id: int,
    status: str,
    reviewer_id: Optional[int] = None,
    comment: Optional[str] = None
) -> None:
    """Update the status of a skill.

    Args:
        skill_id: The skill's ID
        status: The new status (e.g., 'approved', 'rejected')
        reviewer_id: The ID of the reviewer (optional)
        comment: Review comment (optional)
    """
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE skills
            SET status = ?,
                reviewed_at = CURRENT_TIMESTAMP,
                reviewer_id = ?,
                review_comment = ?
            WHERE id = ?
            """,
            (status, reviewer_id, comment, skill_id)
        )
        conn.commit()


def get_user_uploads(user_id: int) -> List[Dict[str, Any]]:
    """Get all uploads by a specific user.

    Args:
        user_id: The user's ID

    Returns:
        List of skill dictionaries uploaded by the user
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                skill_name,
                version,
                filename,
                uploader_id,
                status,
                uploaded_at,
                reviewed_at,
                reviewer_id,
                review_comment
            FROM skills
            WHERE uploader_id = ?
            """,
            (user_id,)
        ).fetchall()

        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "skill_name": row["skill_name"],
                "version": row["version"],
                "filename": row["filename"],
                "uploader_id": row["uploader_id"],
                "status": row["status"],
                "uploaded_at": row["uploaded_at"],
                "reviewed_at": row["reviewed_at"],
                "reviewer_id": row["reviewer_id"],
                "review_comment": row["review_comment"]
            })

        return results


def get_user_downloads(
    user_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 100,
    offset: int = 0
) -> Dict[str, Any]:
    """Get download history for a specific user.

    Args:
        user_id: The user's ID
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        limit: Maximum number of records to return
        offset: Number of records to skip for pagination

    Returns:
        Dictionary containing:
        - downloads: List of download records
        - total: Total count matching the filter
        - limit: The limit used
        - offset: The offset used
    """
    # Default to all time if no dates provided
    if start_date is None:
        start_date = date(1970, 1, 1)
    if end_date is None:
        end_date = date.today()

    with get_connection() as conn:
        # Get total count
        total_row = conn.execute(
            """
            SELECT COUNT(*) as total FROM downloads
            WHERE user_id = ?
              AND date(downloaded_at) BETWEEN ? AND ?
            """,
            (user_id, start_date.isoformat(), end_date.isoformat())
        ).fetchone()

        total = total_row["total"] if total_row else 0

        # Get paginated results
        rows = conn.execute(
            """
            SELECT
                id,
                skill_name,
                version,
                filename,
                downloaded_at,
                ip_address,
                user_agent
            FROM downloads
            WHERE user_id = ?
              AND date(downloaded_at) BETWEEN ? AND ?
            ORDER BY downloaded_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, start_date.isoformat(), end_date.isoformat(), limit, offset)
        ).fetchall()

        downloads = []
        for row in rows:
            downloads.append({
                "id": row["id"],
                "skill_name": row["skill_name"],
                "version": row["version"],
                "filename": row["filename"],
                "downloaded_at": row["downloaded_at"],
                "ip_address": row["ip_address"],
                "user_agent": row["user_agent"]
            })

        return {
            "downloads": downloads,
            "total": total,
            "limit": limit,
            "offset": offset
        }
