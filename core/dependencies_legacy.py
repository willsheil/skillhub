"""
Dependency injection for FastAPI routes.

Provides reusable dependencies for authentication, database access,
and session management.
"""

import logging
from typing import Optional

from fastapi import HTTPException, Request, status

from database import get_user_by_id


logger = logging.getLogger("skillhub")


def get_current_user(request: Request) -> Optional[dict]:
    """Get current authenticated user from session.

    Args:
        request: FastAPI request object

    Returns:
        User dictionary if authenticated, None otherwise
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    return get_user_by_id(user_id)


def require_auth(request: Request):
    """Check if user is authenticated.

    Raises HTTP 401 if user is not logged in.

    Args:
        request: FastAPI request object

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
        request: FastAPI request object

    Returns:
        True if user is admin

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


def get_db():
    """Get database dependency for routes.

    This is a placeholder for future database dependency injection.
    Currently the database module uses a context manager pattern.

    Yields:
        Database connection wrapper
    """
    from database import get_connection
    with get_connection() as conn:
        yield conn
