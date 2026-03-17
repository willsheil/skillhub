"""Notification routes."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/api/notifications")
async def get_notifications(request: Request, page: int = 1, page_size: int = 20):
    """Get user notifications."""
    from main import get_current_user
    from db.repositories import NotificationRepository

    user = get_current_user(request)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user.get("id") if isinstance(user, dict) else None
    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid session")

    offset = (page - 1) * page_size
    notifications = NotificationRepository.get_by_user(user_id, limit=page_size, offset=offset)
    total = NotificationRepository.get_unread_count(user_id)

    return {
        "items": [n.to_dict() for n in notifications],
        "pagination": {"page": page, "page_size": page_size, "total": total}
    }


@router.get("/api/notifications/unread-count")
async def get_unread_count(request: Request):
    """Get unread notification count."""
    from main import get_current_user
    from db.repositories import NotificationRepository

    user = get_current_user(request)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user.get("id") if isinstance(user, dict) else None
    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid session")

    count = NotificationRepository.get_unread_count(user_id)
    return {"count": count}


@router.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int, request: Request):
    """Mark a notification as read."""
    from main import get_current_user
    from db.repositories import NotificationRepository

    user = get_current_user(request)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user.get("id") if isinstance(user, dict) else None
    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid session")

    NotificationRepository.mark_as_read(notification_id, user_id)
    return {"success": True}


@router.post("/api/notifications/read-all")
async def mark_all_notifications_read(request: Request):
    """Mark all notifications as read."""
    from main import get_current_user
    from db.repositories import NotificationRepository

    user = get_current_user(request)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user.get("id") if isinstance(user, dict) else None
    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid session")

    NotificationRepository.mark_all_as_read(user_id)
    return {"success": True}
