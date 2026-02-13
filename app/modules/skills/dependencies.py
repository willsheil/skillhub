"""
Skills-specific dependencies for FastAPI dependency injection.
"""

from pathlib import Path
from typing import Optional

from fastapi import Depends, Header
from starlette.requests import Request

# Constants
PLUGINS_DIR = Path("./plugins")
PENDING_DIR = Path("./data/pending")

# Ensure directories exist
PLUGINS_DIR.mkdir(exist_ok=True)
PENDING_DIR.mkdir(parents=True, exist_ok=True)


async def get_current_user(request: Request) -> Optional[dict]:
    """Get the current authenticated user from session.

    Args:
        request: FastAPI request object

    Returns:
        User dictionary if authenticated, None otherwise
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    # Import here to avoid circular imports
    from database import get_user_by_id
    return get_user_by_id(user_id)


async def require_auth(request: Request) -> bool:
    """Check if user is authenticated.

    Raises HTTP 401 if user is not logged in.

    Args:
        request: FastAPI request object

    Returns:
        True if authenticated

    Raises:
        HTTPException: If not authenticated
    """
    user_id = request.session.get("user_id")
    if not user_id:
        from fastapi import status
        raise Exception(
            status.HTTP_401_UNAUTHORIZED,
            "Not authenticated"
        )
    return True


async def require_admin(request: Request) -> bool:
    """Check if user is authenticated and has admin role.

    Raises HTTP 401 if user is not logged in.
    Raises HTTP 403 if user is not an admin.

    Args:
        request: FastAPI request object

    Returns:
        True if admin

    Raises:
        HTTPException: If not authenticated or not admin
    """
    user_id = request.session.get("user_id")
    if not user_id:
        from fastapi import status
        raise Exception(
            status.HTTP_401_UNAUTHORIZED,
            "Not authenticated"
        )

    role = request.session.get("role")
    if role != "admin":
        from fastapi import status
        raise Exception(
            status.HTTP_403_FORBIDDEN,
            "Admin access required"
        )
    return True
