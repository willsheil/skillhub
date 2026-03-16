"""
FastAPI dependencies - Authentication and authorization.
"""

import logging
from typing import Optional
from fastapi import HTTPException, Header, Request, status

from db.repositories import UserRepository, ApiKeyRepository

logger = logging.getLogger(__name__)


# Rate limiting storage (in-memory, reset every minute)
_rate_limit_storage: dict = {}


def get_current_user(request: Request) -> dict:
    """Get current authenticated user from session.

    Args:
        request: FastAPI request object

    Returns:
        User info dict

    Raises:
        HTTPException: If not authenticated
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    user = UserRepository.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return {
        "id": user.id,
        "employee_id": user.employee_id,
        "role": user.role,
    }


def require_admin(request: Request) -> dict:
    """Require admin role for access.

    Args:
        request: FastAPI request object

    Returns:
        User info dict

    Raises:
        HTTPException: If not admin
    """
    user = get_current_user(request)

    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return user


def verify_api_key_header(x_api_key: Optional[str] = Header(None)) -> dict:
    """Verify API key from header.

    Args:
        x_api_key: API key from X-API-Key header

    Returns:
        API key info dict

    Raises:
        HTTPException: If API key is invalid
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required"
        )

    api_key = ApiKeyRepository.verify(x_api_key)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    # Update last used
    ApiKeyRepository.update_last_used(api_key.id)

    # Get associated user
    user = UserRepository.get_by_id(api_key.user_id)

    return {
        "api_key_id": api_key.id,
        "user_id": api_key.user_id,
        "rate_limit": api_key.rate_limit,
        "user": user.to_dict() if user else None,
    }


def check_rate_limit(api_key: str, limit: int) -> bool:
    """Check if API key has exceeded rate limit.

    Args:
        api_key: API key string
        limit: Requests per minute limit

    Returns:
        True if within limit, False if exceeded
    """
    import time

    current_minute = int(time.time() // 60)

    if api_key not in _rate_limit_storage:
        _rate_limit_storage[api_key] = {}

    key_data = _rate_limit_storage[api_key]

    if key_data.get("minute") != current_minute:
        key_data["count"] = 0
        key_data["minute"] = current_minute

    key_data["count"] += 1

    return key_data["count"] <= limit
