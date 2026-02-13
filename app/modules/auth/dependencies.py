"""
Authentication dependencies for route protection.
"""

import os
from typing import Optional

from fastapi import HTTPException, Request, status
from starlette.requests import Request as StarletteRequest

from app.core.database.models import get_user_by_id


def require_auth(request: Request):
    """Check if user is authenticated.

    Raises HTTP 401 if user is not logged in.

    Args:
        request: FastAPI Request object

    Returns:
        True if authenticated

    Raises:
        HTTPException: If user is not authenticated
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return True


def require_admin(request: Request):
    """Check if user is authenticated and has admin role.

    Raises HTTP 401 if user is not logged in.
    Raises HTTP 403 if user is not an admin.

    Args:
        request: FastAPI Request object

    Returns:
        True if authenticated and admin

    Raises:
        HTTPException: If user is not authenticated or not an admin
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


def get_current_user(request: StarletteRequest) -> Optional[dict]:
    """Get the current authenticated user from session.

    Args:
        request: Starlette Request object

    Returns:
        User dictionary if authenticated, None otherwise
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    return get_user_by_id(user_id)


def verify_admin_credentials(username: str, password: str) -> bool:
    """Verify admin credentials.

    Args:
        username: Admin username
        password: Admin password

    Returns:
        True if credentials are valid
    """
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    return username == admin_username and password == admin_password
