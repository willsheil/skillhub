"""
Admin-specific dependencies for FastAPI routes.

Provides authentication and authorization dependencies for admin endpoints.
"""

import logging
from typing import Optional

from fastapi import HTTPException, Request, status
from starlette.requests import Request as StarletteRequest

# Get logger for this module
logger = logging.getLogger("skillhub.admin.dependencies")


def require_admin(request: StarletteRequest) -> bool:
    """Check if user is authenticated and has admin role.

    Args:
        request: The incoming request object

    Returns:
        True if user is an admin

    Raises:
        HTTPException: 401 if not authenticated, 403 if not admin
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    role = request.session.get("role")
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return True


def get_current_admin_user(request: StarletteRequest) -> dict:
    """Get the current authenticated admin user from session.

    Args:
        request: The incoming request object

    Returns:
        Dictionary containing user information

    Raises:
        HTTPException: 401 if not authenticated or not an admin
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    role = request.session.get("role")
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return {
        "id": user_id,
        "employee_id": request.session.get("employee_id"),
        "role": role
    }
