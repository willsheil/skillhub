"""
Notifications-specific dependencies.

Provides dependency injection for notifications routes.
"""

from fastapi import Request, Depends, HTTPException, status
from starlette.requests import Request as StarletteRequest


def require_auth(request: StarletteRequest) -> bool:
    """Check if user is authenticated.

    Raises HTTP 401 if user is not logged in.

    Args:
        request: The incoming request object

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


def get_current_user_id(request: StarletteRequest) -> int:
    """Get the current user's ID from session.

    Args:
        request: The incoming request object

    Returns:
        The user's ID

    Raises:
        HTTPException: If user is not authenticated
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user_id
