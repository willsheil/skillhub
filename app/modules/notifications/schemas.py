"""
Notification request and response schemas.

Defines Pydantic models for notifications API.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    """Single notification response."""

    id: int
    user_id: int
    type: str = Field(..., description="Notification type (e.g., 'review_success', 'review_rejected')")
    title: str
    content: Optional[str] = None
    related_skill_id: Optional[int] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Paginated list of notifications."""

    notifications: List[NotificationResponse]
    total: int = Field(..., description="Total count matching the filter")
    unread_count: int = Field(..., description="Count of unread notifications")


class UnreadCountResponse(BaseModel):
    """Unread notification count response."""

    unread_count: int


class MarkReadResponse(BaseModel):
    """Response after marking notification(s) as read."""

    message: str
    count: Optional[int] = None
