"""
Authentication module for user login and session management.
"""

from app.modules.auth.routes import router as auth_router

__all__ = ["auth_router"]
