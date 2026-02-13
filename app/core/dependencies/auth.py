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


def require_admin_or_author(request: Request, skill_id: int):
    """Check if user is admin or the author of the skill.

    Args:
        request: FastAPI Request object
        skill_id: ID of the skill to check

    Returns:
        True if admin or author

    Raises:
        HTTPException: If user is not authenticated and not the author
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    role = request.session.get("role")
    if role == "admin":
        return True

    from app.core.database.models import get_skill_by_id
    skill = get_skill_by_id(skill_id)
    if skill and skill["uploader_id"] == user_id:
        return True

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access or authorship required"
    )


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


def get_current_user_from_session(request: Request):
    """Dependency to get current user or raise HTTP 401.

    Args:
        request: FastAPI Request object

    Returns:
        User dictionary

    Raises:
        HTTPException: If user is not authenticated
    """
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user
