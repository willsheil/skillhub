"""
Notifications API routes.

Defines FastAPI routes for notification management.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status, Query, Depends, Request
from starlette.requests import Request as StarletteRequest

from app.modules.notifications.services import (
    get_user_notifications,
    get_unread_notifications_count,
    mark_notification_read,
    mark_all_notifications_read,
)
from app.modules.notifications.dependencies import get_current_user_id, require_auth
from app.modules.notifications.schemas import (
    NotificationListResponse,
    UnreadCountResponse,
    MarkReadResponse,
)

# Get logger for this module
logger = logging.getLogger("skillhub.notifications")

# Create router
router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=Dict[str, Any])
async def get_notifications(
    request: StarletteRequest,
    unread_only: bool = Query(False, description="Filter to only unread notifications"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of notifications to return"),
    offset: int = Query(0, ge=0, description="Number of notifications to skip"),
    _: bool = Depends(require_auth)
):
    """Get notifications for the current user with pagination.

    Query parameters:
    - unread_only: If True, only return unread notifications (default: False)
    - limit: Maximum number of notifications to return (default: 50, max: 100)
    - offset: Number of notifications to skip for pagination (default: 0)

    Returns notifications sorted newest first.
    """
    try:
        user_id = get_current_user_id(request)
        result = get_user_notifications(user_id, unread_only, limit, offset)

        return {
            "success": True,
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch notifications: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch notifications: {str(e)}"
        )


@router.get("/unread-count", response_model=Dict[str, Any])
async def get_unread_count(
    request: StarletteRequest,
    _: bool = Depends(require_auth)
):
    """Get the count of unread notifications for the current user."""
    try:
        user_id = get_current_user_id(request)
        count = get_unread_notifications_count(user_id)

        return {
            "success": True,
            "data": {
                "unread_count": count
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch unread count: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch unread count: {str(e)}"
        )


@router.post("/{notification_id}/read", response_model=Dict[str, Any])
async def mark_read(
    notification_id: int,
    request: StarletteRequest,
    _: bool = Depends(require_auth)
):
    """Mark a specific notification as read.

    Verifies that the user owns this notification before marking it as read.
    """
    try:
        user_id = get_current_user_id(request)
        success = mark_notification_read(notification_id, user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found or does not belong to this user"
            )

        return {
            "success": True,
            "data": {
                "message": "Notification marked as read"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark notification as read: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark notification as read: {str(e)}"
        )


@router.post("/read-all", response_model=Dict[str, Any])
async def mark_all_read(
    request: StarletteRequest,
    _: bool = Depends(require_auth)
):
    """Mark all notifications as read for the current user."""
    try:
        user_id = get_current_user_id(request)
        count = mark_all_notifications_read(user_id)

        return {
            "success": True,
            "data": {
                "message": f"Marked {count} notifications as read",
                "count": count
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark all notifications as read: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark all notifications as read: {str(e)}"
        )
