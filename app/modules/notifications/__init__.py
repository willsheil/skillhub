"""
Notifications module for managing user notifications.

This module provides functionality for:
- Creating notifications for users
- Fetching user notifications with pagination
- Marking notifications as read
- Getting unread notification counts
"""

from app.modules.notifications.routes import router
from app.modules.notifications.services import (
    NotificationService,
    create_notification,
    get_user_notifications,
    get_unread_notifications_count,
    mark_notification_read,
    mark_all_notifications_read,
    cleanup_old_notifications,
)
from app.modules.notifications.schemas import (
    NotificationResponse,
    NotificationListResponse,
    UnreadCountResponse,
    MarkReadResponse,
)

__all__ = [
    "router",
    "NotificationService",
    "create_notification",
    "get_user_notifications",
    "get_unread_notifications_count",
    "mark_notification_read",
    "mark_all_notifications_read",
    "cleanup_old_notifications",
    "NotificationResponse",
    "NotificationListResponse",
    "UnreadCountResponse",
    "MarkReadResponse",
]
