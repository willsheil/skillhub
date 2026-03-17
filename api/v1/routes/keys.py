"""API Key management routes."""

from fastapi import APIRouter, Depends, Query, HTTPException, Request

router = APIRouter()


def get_current_user_from_request(request):
    """Get current user from request."""
    from main import get_current_user as main_get_current_user
    return main_get_current_user(request)


def require_admin_from_request(request):
    """Require admin access."""
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/api/admin/api-keys")
async def get_api_keys(request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    """Get all API keys (admin only)."""
    require_admin_from_request(request)

    from db.repositories import ApiKeyRepository

    offset = (page - 1) * page_size
    keys = ApiKeyRepository.list_all(limit=page_size, offset=offset)

    return {
        "items": [k.to_dict() for k in keys],
        "pagination": {"page": page, "page_size": page_size}
    }


@router.post("/api/admin/api-keys")
async def create_api_key(request, key_name: str = None, user_id: int = None, rate_limit: int = 100):
    """Create API key (admin only)."""
    require_admin_from_request(request)

    if not key_name or not user_id:
        raise HTTPException(status_code=400, detail="key_name and user_id are required")

    from db.repositories import ApiKeyRepository
    api_key, plain_key = ApiKeyRepository.create(key_name, user_id, rate_limit)

    return {"success": True, "api_key": plain_key}


@router.delete("/api/admin/api-keys/{key_id}")
async def delete_api_key(request, key_id: int):
    """Delete API key (admin only)."""
    require_admin_from_request(request)

    from db.repositories import ApiKeyRepository
    ApiKeyRepository.delete(key_id)

    return {"success": True}


@router.put("/api/admin/api-keys/{key_id}/toggle")
async def toggle_api_key(request, key_id: int):
    """Toggle API key status (admin only)."""
    require_admin_from_request(request)

    from db.repositories import ApiKeyRepository
    is_active = ApiKeyRepository.toggle_status(key_id)

    return {"success": True, "is_active": is_active}


@router.get("/api/admin/api-keys/{key_id}/stats")
async def get_api_key_stats(request, key_id: int):
    """Get API key statistics (admin only)."""
    require_admin_from_request(request)

    from db.repositories import ApiKeyRepository

    stats = ApiKeyRepository.get_stats(key_id)

    return {
        "total_requests": stats.get("total_requests", 0),
        "last_used": stats.get("last_used"),
        "created_at": stats.get("created_at")
    }
