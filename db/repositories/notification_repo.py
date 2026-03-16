"""
Notification repository - Database operations for notifications.

Provides methods for creating, reading, and managing user notifications.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from db.connection import get_connection
from db.models import Notification
from core.constants import NotificationType

logger = logging.getLogger(__name__)


class NotificationRepository:
    """Repository for notification database operations."""

    @staticmethod
    def create(
        user_id: int,
        notification_type: str,
        title: str,
        content: Optional[str] = None,
        related_skill_id: Optional[int] = None,
    ) -> Notification:
        """Create a new notification.

        Args:
            user_id: Target user ID
            notification_type: Type of notification
            title: Notification title
            content: Optional notification content
            related_skill_id: Optional related skill ID

        Returns:
            Created Notification object
        """
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO notifications
                   (user_id, type, title, content, related_skill_id)
                   VALUES (%s, %s, %s, %s, %s)""",
                (user_id, notification_type, title, content, related_skill_id)
            )
            conn.commit()

            cursor = conn.execute("SELECT LAST_INSERT_ID() as id")
            notif_id = cursor.fetchone()['id']

            cursor = conn.execute(
                "SELECT * FROM notifications WHERE id = %s",
                (notif_id,)
            )
            return Notification(**cursor.fetchone())

    @staticmethod
    def get_by_id(notification_id: int) -> Optional[Notification]:
        """Get notification by ID.

        Args:
            notification_id: Notification ID

        Returns:
            Notification object if found, None otherwise
        """
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM notifications WHERE id = %s",
                (notification_id,)
            )
            row = cursor.fetchone()
            if row:
                return Notification(**row)
            return None

    @staticmethod
    def get_by_user(
        user_id: int,
        is_read: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        """Get notifications for a user.

        Args:
            user_id: User ID
            is_read: Optional filter by read status
            limit: Max results
            offset: Result offset

        Returns:
            List of Notification objects
        """
        with get_connection() as conn:
            if is_read is not None:
                cursor = conn.execute(
                    """SELECT * FROM notifications
                       WHERE user_id = %s AND is_read = %s
                       ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                    (user_id, int(is_read), limit, offset)
                )
            else:
                cursor = conn.execute(
                    """SELECT * FROM notifications
                       WHERE user_id = %s
                       ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                    (user_id, limit, offset)
                )
            return [Notification(**row) for row in cursor.fetchall()]

    @staticmethod
    def get_unread_count(user_id: int) -> int:
        """Get count of unread notifications.

        Args:
            user_id: User ID

        Returns:
            Number of unread notifications
        """
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0",
                (user_id,)
            )
            return cursor.fetchone()['count']

    @staticmethod
    def mark_as_read(notification_id: int) -> bool:
        """Mark notification as read.

        Args:
            notification_id: Notification ID

        Returns:
            True if updated
        """
        with get_connection() as conn:
            conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = %s",
                (notification_id,)
            )
            conn.commit()
            return True

    @staticmethod
    def mark_all_as_read(user_id: int) -> int:
        """Mark all notifications as read for a user.

        Args:
            user_id: User ID

        Returns:
            Number of notifications marked as read
        """
        with get_connection() as conn:
            conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE user_id = %s AND is_read = 0",
                (user_id,)
            )
            conn.commit()
            return conn.execute("SELECT ROW_COUNT()").fetchone()['ROW_COUNT()']

    @staticmethod
    def delete_old_notifications(days: int = 30) -> int:
        """Delete old read notifications.

        Args:
            days: Delete notifications older than this many days

        Returns:
            Number of deleted notifications
        """
        cutoff = datetime.now() - timedelta(days=days)
        with get_connection() as conn:
            conn.execute(
                """DELETE FROM notifications
                   WHERE is_read = 1 AND created_at < %s""",
                (cutoff,)
            )
            conn.commit()
            return conn.execute("SELECT ROW_COUNT()").fetchone()['ROW_COUNT()']

    @staticmethod
    def delete(notification_id: int) -> bool:
        """Delete a notification.

        Args:
            notification_id: Notification ID

        Returns:
            True if deleted
        """
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE id = %s", (notification_id,))
            conn.commit()
            return True
