"""
Notifications API Routes - V1 (Tortoise ORM 版本）

用户通知相关路由：
- GET /api/v1/notifications - 获取当前用户通知列表
- GET /api/v1/notifications/count - 获取未读通知数量
- POST /api/v1/notifications/{id}/read - 标记通知为已读
- POST /api/v1/notifications/read-all - 标记所有通知为已读
"""

import logging
from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.dependencies import get_current_user
from core.models import User, Notification
from core.repositories import NotificationRepository

logger = logging.getLogger("skillhub")

# Router
router = APIRouter(prefix="/api/v1", tags=["notifications"])


# ============================================================================
# API 路由
# ============================================================================


@router.get("/notifications")
async def api_get_notifications(
    unread_only: bool = Query(False, description="仅获取未读通知"),
    limit: int = Query(50, ge=1, le=100, description="返回数量（1-100）"),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """获取当前用户的通知列表"""
    try:
        notifications = await NotificationRepository.get_by_user(
            current_user.id,
            unread_only=unread_only,
            limit=limit
        )

        return JSONResponse({
            "notifications": [n.to_dict() for n in notifications],
            "total": len(notifications)
        })

    except Exception as e:
        logger.error(f"Error fetching notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取通知失败"
        )


@router.get("/notifications/count")
async def api_get_unread_count(
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """获取当前用户的未读通知数量"""
    try:
        count = await NotificationRepository.get_unread_count(current_user.id)

        return JSONResponse({
            "unread_count": count
        })

    except Exception as e:
        logger.error(f"Error fetching unread count: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取未读数量失败"
        )


@router.post("/notifications/{notification_id}/read")
async def api_mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """标记单个通知为已读"""
    try:
        # 验证通知存在
        notifications = await NotificationRepository.get_by_user(current_user.id, unread_only=False, limit=100)
        notification_ids = [n.id for n in notifications]

        if notification_id not in notification_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="通知不存在"
            )

        # 验证通知所有权
        if notification_id not in [n.id for n in notifications if n.id == notification_id]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此通知"
            )

        await NotificationRepository.mark_as_read(notification_id, current_user.id)

        return JSONResponse({
            "message": "通知已标记为已读",
            "notification_id": notification_id
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking notification as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="标记失败"
        )


@router.post("/notifications/read-all")
async def api_mark_all_read(
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """标记所有通知为已读"""
    try:
        count = await NotificationRepository.mark_all_as_read(current_user.id)

        return JSONResponse({
            "message": f"已标记 {count} 条通知为已读",
            "marked_count": count
        })

    except Exception as e:
        logger.error(f"Error marking all as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="标记失败"
        )
