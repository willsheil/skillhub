"""
Notification services.

Business logic for managing user notifications.
"""

import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

import pymysql
from os import getenv

# Import database configuration
DB_CONFIG = {
    'host': getenv('DB_HOST', '127.0.0.1'),
    'port': int(getenv('DB_PORT', '3306')),
    'user': getenv('DB_USER', 'root'),
    'password': getenv('DB_PASSWORD', 'root'),
    'database': getenv('DB_DATABASE', 'skills'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# Get logger for this module
logger = logging.getLogger("skillhub.notifications")


class ConnectionWrapper:
    """Wrapper to provide execute() method on PyMySQL connections.

    PyMySQL doesn't support conn.execute() directly, requiring cursor.execute().
    This wrapper provides compatibility with code that expects execute() on the connection.
    """

    def __init__(self, conn):
        """Initialize wrapper with a PyMySQL connection.

        Args:
            conn: PyMySQL connection object
        """
        self._conn = conn

    def execute(self, query, params=None):
        """Execute a query using a cursor.

        Args:
            query: SQL query string
            params: Optional parameters for the query

        Returns:
            Cursor object with results
        """
        cursor = self._conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor

    def commit(self):
        """Commit the current transaction."""
        self._conn.commit()

    def __getattr__(self, name):
        """Delegate all other attributes to the underlying connection.

        Args:
            name: Attribute name

        Returns:
            Attribute from the underlying connection
        """
        return getattr(self._conn, name)


@contextmanager
def get_connection():
    """Get database connection context manager."""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield ConnectionWrapper(conn)
    finally:
        conn.close()


class NotificationService:
    """Service class for notification operations."""

    @staticmethod
    def create(
        user_id: int,
        type: str,
        title: str,
        content: Optional[str] = None,
        related_skill_id: Optional[int] = None
    ) -> int:
        """Create a notification for a user.

        Args:
            user_id: The user's ID
            type: Notification type (e.g., 'review_success', 'review_rejected')
            title: Notification title
            content: Optional notification content
            related_skill_id: Optional related skill ID

        Returns:
            The ID of the created notification
        """
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO notifications (user_id, type, title, content, related_skill_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, type, title, content, related_skill_id)
            )
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_user_notifications(
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get notifications for a user.

        Args:
            user_id: The user's ID
            unread_only: If True, only return unread notifications
            limit: Maximum number of notifications to return
            offset: Number of notifications to skip for pagination

        Returns:
            Dictionary containing:
            - notifications: List of notification records
            - total: Total count matching the filter
            - unread_count: Count of unread notifications
        """
        with get_connection() as conn:
            # Get total count
            if unread_only:
                total_row = conn.execute(
                    "SELECT COUNT(*) as total FROM notifications WHERE user_id = %s AND is_read = 0",
                    (user_id,)
                ).fetchone()
            else:
                total_row = conn.execute(
                    "SELECT COUNT(*) as total FROM notifications WHERE user_id = %s",
                    (user_id,)
                ).fetchone()

            total = total_row["total"] if total_row else 0

            # Get unread count
            unread_row = conn.execute(
                "SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0",
                (user_id,)
            ).fetchone()
            unread_count = unread_row["count"] if unread_row else 0

            # Build query
            if unread_only:
                query = """
                    SELECT id, user_id, type, title, content, related_skill_id, is_read, created_at
                    FROM notifications
                    WHERE user_id = %s AND is_read = 0
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """
                rows = conn.execute(query, (user_id, limit, offset)).fetchall()
            else:
                query = """
                    SELECT id, user_id, type, title, content, related_skill_id, is_read, created_at
                    FROM notifications
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """
                rows = conn.execute(query, (user_id, limit, offset)).fetchall()

            notifications = []
            for row in rows:
                notifications.append({
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "type": row["type"],
                    "title": row["title"],
                    "content": row["content"],
                    "related_skill_id": row["related_skill_id"],
                    "is_read": row["is_read"],
                    "created_at": row["created_at"]
                })

            return {
                "notifications": notifications,
                "total": total,
                "unread_count": unread_count
            }

    @staticmethod
    def mark_read(notification_id: int, user_id: int) -> bool:
        """Mark a notification as read.

        Args:
            notification_id: The notification's ID
            user_id: The user's ID (for ownership verification)

        Returns:
            True if marked as read, False if notification not found or not owned by user
        """
        with get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE notifications
                SET is_read = 1
                WHERE id = %s AND user_id = %s
                """,
                (notification_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def mark_all_read(user_id: int) -> int:
        """Mark all notifications as read for a user.

        Args:
            user_id: The user's ID

        Returns:
            Number of notifications marked as read
        """
        with get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE notifications
                SET is_read = 1
                WHERE user_id = %s AND is_read = 0
                """,
                (user_id,)
            )
            conn.commit()
            return cursor.rowcount

    @staticmethod
    def get_unread_count(user_id: int) -> int:
        """Get count of unread notifications for a user.

        Args:
            user_id: The user's ID

        Returns:
            Count of unread notifications
        """
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0",
                (user_id,)
            ).fetchone()
            return row["count"] if row else 0

    @staticmethod
    def cleanup_old(user_id: int, keep_count: int = 100) -> None:
        """Delete old notifications keeping only the most recent ones.

        Args:
            user_id: The user's ID
            keep_count: Number of recent notifications to keep
        """
        with get_connection() as conn:
            # Find the cutoff point
            rows = conn.execute(
                """
                SELECT id FROM notifications
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, 1, keep_count)
            ).fetchall()

            if rows:
                # Delete all notifications older than the cutoff
                cutoff_id = rows[0]["id"]
                conn.execute(
                    "DELETE FROM notifications WHERE user_id = %s AND id < %s",
                    (user_id, cutoff_id)
                )
                conn.commit()
                logger.info(f"Cleaned up old notifications for user {user_id}, keeping {keep_count}")


# Convenience functions that delegate to the service class
def create_notification(
    user_id: int,
    type: str,
    title: str,
    content: Optional[str] = None,
    related_skill_id: Optional[int] = None
) -> int:
    """Create a notification for a user.

    Args:
        user_id: The user's ID
        type: Notification type (e.g., 'review_success', 'review_rejected')
        title: Notification title
        content: Optional notification content
        related_skill_id: Optional related skill ID

    Returns:
        The ID of the created notification
    """
    return NotificationService.create(user_id, type, title, content, related_skill_id)


def get_user_notifications(
    user_id: int,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """Get notifications for a user.

    Args:
        user_id: The user's ID
        unread_only: If True, only return unread notifications
        limit: Maximum number of notifications to return
        offset: Number of notifications to skip for pagination

    Returns:
        Dictionary containing:
        - notifications: List of notification records
        - total: Total count matching the filter
        - unread_count: Count of unread notifications
    """
    return NotificationService.get_user_notifications(user_id, unread_only, limit, offset)


def mark_notification_read(notification_id: int, user_id: int) -> bool:
    """Mark a notification as read.

    Args:
        notification_id: The notification's ID
        user_id: The user's ID (for ownership verification)

    Returns:
        True if marked as read, False if notification not found or not owned by user
    """
    return NotificationService.mark_read(notification_id, user_id)


def mark_all_notifications_read(user_id: int) -> int:
    """Mark all notifications as read for a user.

    Args:
        user_id: The user's ID

    Returns:
        Number of notifications marked as read
    """
    return NotificationService.mark_all_read(user_id)


def get_unread_notifications_count(user_id: int) -> int:
    """Get count of unread notifications for a user.

    Args:
        user_id: The user's ID

    Returns:
        Count of unread notifications
    """
    return NotificationService.get_unread_count(user_id)


def cleanup_old_notifications(user_id: int, keep_count: int = 100) -> None:
    """Delete old notifications keeping only the most recent ones.

    Args:
        user_id: The user's ID
        keep_count: Number of recent notifications to keep
    """
    NotificationService.cleanup_old(user_id, keep_count)
