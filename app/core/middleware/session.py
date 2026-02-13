"""
Session middleware for FastAPI.

This module provides session management using Starlette's SessionMiddleware.
"""

import os
from typing import Callable

from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import Response


def get_session_middleware(
    secret_key: str,
    session_cookie: str = "session",
    max_age: int = 14 * 24 * 60 * 60,  # 14 days
    same_site: str = "lax",
) -> SessionMiddleware:
    """Get a SessionMiddleware instance with the specified configuration.

    Args:
        secret_key: Secret key for signing session cookies
        session_cookie: Name of the session cookie
        max_age: Max age of session in seconds
        same_site: SameSite cookie attribute

    Returns:
        Configured SessionMiddleware instance
    """
    return SessionMiddleware(
        secret_key=secret_key,
        session_cookie=session_cookie,
        max_age=max_age,
        same_site=same_site,
    )


# Re-export SessionMiddleware for convenience
SessionMiddleware = SessionMiddleware


__all__ = ["SessionMiddleware", "get_session_middleware"]
