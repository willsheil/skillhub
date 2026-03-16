"""User management routes."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class UserCreateRequest(BaseModel):
    """User creation request."""
    employee_id: str
    api_key: str
    role: str = "user"


class UserUpdateRequest(BaseModel):
    """User update request."""
    role: Optional[str] = None
    status: Optional[str] = None


def get_current_user_from_request(request):
    """Get current user from request."""
    # 统一使用 api/v1/dependencies.py 中的认证函数
    from api.v1.dependencies import get_current_user as api_get_current_user
    return api_get_current_user(request)
 
 
def require_admin_from_request(request):
    """Require admin access."""
    # 统一使用 api/v1/dependencies.py 中的认证函数
    from api.v1.dependencies import require_admin as api_require_admin
    return api_require_admin(request)


@router.get("/api/admin/users")
async def get_users(
    request: Request,
    role: str = None,
    status: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """Get all users (admin only)."""
    require_admin_from_request(request)

    from db.repositories import UserRepository

    offset = (page - 1) * page_size
    users = UserRepository.list_users(role=role, status=status, limit=page_size, offset=offset)
    total = UserRepository.get_total_count(role=role, status=status)

    return {
        "items": [u.to_dict() for u in users],
        "pagination": {"page": page, "page_size": page_size, "total": total}
    }


@router.post("/api/admin/users")
async def create_user(request: Request, data: UserCreateRequest):
    """Create a new user (admin only)."""
    require_admin_from_request(request)

    from db.repositories import UserRepository
    from core.security import generate_api_key

    # Use provided api_key or generate one
    api_key = data.api_key if data.api_key else generate_api_key()

    user = UserRepository.create(data.employee_id, api_key, data.role)
    return {"success": True, "user_id": user.id}


@router.put("/api/admin/users/{user_id}")
async def update_user(request: Request, user_id: int, data: UserUpdateRequest):
    """Update user (admin only)."""
    require_admin_from_request(request)

    from db.repositories import UserRepository

    if data.role:
        UserRepository.update_role(user_id, data.role)
    if data.status:
        UserRepository.update_status(user_id, data.status)

    return {"success": True}


@router.patch("/api/admin/users/{user_id}/disable")
async def disable_user(request: Request, user_id: int):
    """Disable a user (admin only)."""
    require_admin_from_request(request)

    from db.repositories import UserRepository
    UserRepository.update_status(user_id, "disabled")

    return {"success": True}


@router.delete("/api/admin/users/{user_id}")
async def delete_user(request: Request, user_id: int):
    """Delete a user (admin only)."""
    require_admin_from_request(request)

    from db.repositories import UserRepository
    UserRepository.delete(user_id)

    return {"success": True}


@router.patch("/api/admin/users/{user_id}/enable")
async def enable_user(request: Request, user_id: int):
    """Enable a user (admin only)."""
    require_admin_from_request(request)

    from db.repositories import UserRepository
    UserRepository.update_status(user_id, "active")

    return {"success": True}


@router.post("/api/admin/users/{user_id}/reset-key")
async def reset_user_key(request: Request, user_id: int):
    """Reset user's API key (admin only)."""
    require_admin_from_request(request)

    from db.repositories import UserRepository
    new_key = UserRepository.reset_api_key(user_id)

    return {"success": True, "new_api_key": new_key}
