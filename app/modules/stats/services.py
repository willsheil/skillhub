"""
Stats module business logic.

Provides services for download statistics tracking and reporting.
"""

from datetime import date, timedelta
from typing import List, Dict, Any, Optional
import logging

# Import from database module directly
# TODO: Switch to app.core.database when the core module is fully migrated
from database import get_connection

logger = logging.getLogger("skillhub.stats.services")


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
        skill_name: The name of skill being downloaded
        version: The version of skill
        filename: The filename being downloaded
        ip_address: Optional IP address of downloader
        user_agent: Optional user agent string
        user_id: Optional user ID if authenticated

    Returns:
        The ID of inserted record
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO downloads (skill_name, version, filename, ip_address, user_agent, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (skill_name, version, filename, ip_address, user_agent, user_id)
        )
        conn.commit()
        return cursor.lastrowid


def get_download_stats(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    days: Optional[int] = None
) -> Dict[str, Any]:
    """Get download statistics for a date range.

    Args:
        start_date: Start date (YYYY-MM-DD), defaults to 30 days ago
        end_date: End date (YYYY-MM-DD), defaults to today
        days: Number of days for range (default 30), max 90

    Returns:
        {
            "total_downloads": int,
            "rankings": [
                {"skill_name": str, "downloads": int},
                ...
            ]
        }
    """
    # Default to last 30 days if no dates provided
    if start_date is None and end_date is None:
        start_date = date.today() - timedelta(days=30)
        end_date = date.today()

    # Override end_date if days is specified
    if days is not None:
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

    with get_connection() as conn:
        # Get total downloads
        total_row = conn.execute(
            """
            SELECT COUNT(*) as total FROM downloads
            WHERE DATE(downloaded_at) BETWEEN %s AND %s
            """,
            (start_date.isoformat(), end_date.isoformat())
        ).fetchone()

        total_downloads = total_row["total"] if total_row else 0

        # Get rankings by skill (limited to top 6)
        rankings = []
        rows = conn.execute(
            """
            SELECT
                skill_name,
                COUNT(*) as download_count
            FROM downloads
            WHERE DATE(downloaded_at) BETWEEN %s AND %s
            GROUP BY skill_name
            ORDER BY download_count DESC
            LIMIT 6
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

        # Author can be in multiple locations:
        # 1. metadata.author (top-level in YAML frontmatter)
        # 2. metadata.metadata.author (inside metadata section in YAML frontmatter)
        author = metadata.get("author") or metadata.get("metadata", {}).get("author")

        # Handle different author formats
        if isinstance(author, dict):
            author_name = author.get("name", "Unknown")
        elif isinstance(author, str) and author:
            author_name = author
        else:
            author_name = "Unknown"

        # Map both base name and versioned names (from versions array)
        skill_author_map[skill_name] = author_name
        for version_info in plugin.get("versions", []):
            filename = version_info.get("filename", "")
            # Remove .zip extension to match skill_name in downloads table
            if filename.endswith(".zip"):
                versioned_name = filename[:-4]
                skill_author_map[versioned_name] = author_name

    # Get download stats
    stats = get_download_stats(start_date, end_date)

    # Filter rankings to only include skills that still exist (active)
    # This prevents deleted/inactive skills from appearing in hot rankings
    filtered_rankings = []
    valid_skill_names = set(skill_author_map.keys())
    for ranking in stats["rankings"]:
        # Only include skills that are still in plugins list (active)
        if ranking["skill_name"] in valid_skill_names:
            ranking["author"] = skill_author_map.get(ranking["skill_name"], "Unknown")
            filtered_rankings.append(ranking)

    stats["rankings"] = filtered_rankings
    return stats


def get_today_downloads_count() -> int:
    """Get count of downloads today.

    Returns:
        Number of downloads today
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) as count FROM downloads
            WHERE DATE(downloaded_at) = CURDATE()
            """
        ).fetchone()
        return row["count"] if row else 0


def get_top_skills_by_downloads(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top skills by download count.

    Args:
        limit: Maximum number of skills to return

    Returns:
        List of skills with download counts
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                skill_name,
                COUNT(*) as download_count
            FROM downloads
            GROUP BY skill_name
            ORDER BY download_count DESC
            LIMIT %s
            """,
            (limit,)
        ).fetchall()

        results = []
        for row in rows:
            results.append({
                "skill_name": row["skill_name"],
                "downloads": row["download_count"]
            })

        return results


def get_top_users_by_downloads(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top users by download count.

    Args:
        limit: Maximum number of users to return

    Returns:
        List of users with download counts
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                u.employee_id,
                u.role,
                COUNT(d.id) as download_count
            FROM users u
            LEFT JOIN downloads d ON u.id = d.user_id
            GROUP BY u.id
            ORDER BY download_count DESC
            LIMIT %s
            """,
            (limit,)
        ).fetchall()

        results = []
        for row in rows:
            results.append({
                "employee_id": row["employee_id"],
                "role": row["role"],
                "downloads": row["download_count"]
            })

        return results
