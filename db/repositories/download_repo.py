"""
Download repository - Database operations for downloads.

Provides methods for recording downloads and retrieving download statistics.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from db.connection import get_connection
from db.models import Download

logger = logging.getLogger(__name__)


class DownloadRepository:
    """Repository for download database operations."""

    @staticmethod
    def record(skill_name: str, version: str, user_id: Optional[int] = None) -> Download:
        """Record a download.

        Args:
            skill_name: Skill name
            version: Skill version
            user_id: Optional user ID who downloaded

        Returns:
            Created Download object
        """
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO downloads (skill_name, version, user_id) VALUES (%s, %s, %s)",
                (skill_name, version, user_id)
            )
            conn.commit()

            cursor = conn.execute("SELECT LAST_INSERT_ID() as id")
            download_id = cursor.fetchone()['id']

            cursor = conn.execute(
                "SELECT * FROM downloads WHERE id = %s",
                (download_id,)
            )
            return Download(**cursor.fetchone())

    @staticmethod
    def get_by_user(user_id: int, limit: int = 50, offset: int = 0) -> List[Download]:
        """Get downloads by user.

        Args:
            user_id: User ID
            limit: Max results
            offset: Result offset

        Returns:
            List of Download objects
        """
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM downloads WHERE user_id = %s
                   ORDER BY downloaded_at DESC LIMIT %s OFFSET %s""",
                (user_id, limit, offset)
            )
            return [Download(**row) for row in cursor.fetchall()]

    @staticmethod
    def get_by_skill(skill_name: str, limit: int = 100) -> List[Download]:
        """Get downloads for a skill.

        Args:
            skill_name: Skill name
            limit: Max results

        Returns:
            List of Download objects
        """
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM downloads WHERE skill_name = %s
                   ORDER BY downloaded_at DESC LIMIT %s""",
                (skill_name, limit)
            )
            return [Download(**row) for row in cursor.fetchall()]

    @staticmethod
    def get_today_count() -> int:
        """Get today's download count.

        Returns:
            Number of downloads today
        """
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT COUNT(*) as count FROM downloads
                   WHERE DATE(downloaded_at) = CURDATE()"""
            )
            return cursor.fetchone()['count']

    @staticmethod
    def get_total_count() -> int:
        """Get total download count.

        Returns:
            Total number of downloads
        """
        with get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM downloads")
            return cursor.fetchone()['count']

    @staticmethod
    def get_top_skills(limit: int = 10, days: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get top skills by download count.

        Args:
            limit: Number of results
            days: Optional - only last N days

        Returns:
            List of dicts with skill_name and count
        """
        with get_connection() as conn:
            if days:
                since = datetime.now() - timedelta(days=days)
                cursor = conn.execute(
                    """SELECT skill_name, COUNT(*) as count
                       FROM downloads
                       WHERE downloaded_at >= %s
                       GROUP BY skill_name
                       ORDER BY count DESC LIMIT %s""",
                    (since, limit)
                )
            else:
                cursor = conn.execute(
                    """SELECT skill_name, COUNT(*) as count
                       FROM downloads
                       GROUP BY skill_name
                       ORDER BY count DESC LIMIT %s""",
                    (limit,)
                )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_top_users(limit: int = 10, days: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get top users by download count.

        Args:
            limit: Number of results
            days: Optional - only last N days

        Returns:
            List of dicts with user_id and count
        """
        with get_connection() as conn:
            if days:
                since = datetime.now() - timedelta(days=days)
                cursor = conn.execute(
                    """SELECT user_id, COUNT(*) as count
                       FROM downloads
                       WHERE user_id IS NOT NULL AND downloaded_at >= %s
                       GROUP BY user_id
                       ORDER BY count DESC LIMIT %s""",
                    (since, limit)
                )
            else:
                cursor = conn.execute(
                    """SELECT user_id, COUNT(*) as count
                       FROM downloads
                       WHERE user_id IS NOT NULL
                       GROUP BY user_id
                       ORDER BY count DESC LIMIT %s""",
                    (limit,)
                )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_stats_by_date(start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get download stats by date range.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of dicts with date and count
        """
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT DATE(downloaded_at) as date, COUNT(*) as count
                   FROM downloads
                   WHERE downloaded_at BETWEEN %s AND %s
                   GROUP BY DATE(downloaded_at)
                   ORDER BY date""",
                (start_date, end_date)
            )
            return [dict(row) for row in cursor.fetchall()]
