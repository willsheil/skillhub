"""
Stats module dependencies.

Provides dependency injection functions for stats routes.
"""

from typing import Optional
from datetime import date
from fastapi import Query, HTTPException, status, Request


def parse_date_range(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
) -> tuple[Optional[date], Optional[date]]:
    """Parse and validate date range query parameters.

    Args:
        start_date: Start date string in YYYY-MM-DD format
        end_date: End date string in YYYY-MM-DD format

    Returns:
        Tuple of (start_date, end_date) as date objects or None

    Raises:
        HTTPException: If date format is invalid
    """
    try:
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None
        return start, end
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {e}"
        )


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
