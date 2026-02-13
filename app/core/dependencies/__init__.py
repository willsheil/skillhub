"""Dependency injection module."""
from app.core.dependencies.auth import (
    get_current_user,
    get_current_user_from_session,
    require_admin,
    require_admin_or_author,
)

__all__ = [
    "get_current_user",
    "get_current_user_from_session",
    "require_admin",
    "require_admin_or_author",
]
