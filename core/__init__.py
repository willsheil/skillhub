"""
Core module for SkillHub application.

Provides FastAPI app factory, dependency injection, and middleware.
"""

from core.app import create_app
from core.dependencies import get_db, get_current_user, require_auth, require_admin
from core.middleware import SessionMiddleware, CORSMiddleware

__all__ = [
    "create_app",
    "get_db",
    "get_current_user",
    "require_auth",
    "require_admin",
    "SessionMiddleware",
    "CORSMiddleware",
]
