"""
Middleware for SkillHub application.

Provides session and CORS middleware for the FastAPI application.
"""

import logging
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware as StarletteCORSMiddleware
from starlette.middleware.sessions import SessionMiddleware


logger = logging.getLogger("skillhub")


# Re-export Starlette's session middleware
SessionMiddleware = SessionMiddleware


class CORSMiddleware:
    """CORS middleware wrapper for FastAPI.

    Configures Cross-Origin Resource Sharing headers
    for API access from different origins.
    """

    def __init__(
        self,
        app,
        allow_origins: list = None,
        allow_credentials: bool = True,
        allow_methods: list = None,
        allow_headers: list = None,
    ):
        """Initialize CORS middleware.

        Args:
            app: FastAPI application
            allow_origins: List of allowed origins
            allow_credentials: Allow credentials in requests
            allow_methods: List of allowed HTTP methods
            allow_headers: List of allowed headers
        """
        if allow_origins is None:
            allow_origins = ["*"]
        if allow_methods is None:
            allow_methods = ["*"]
        if allow_headers is None:
            allow_headers = ["*"]

        self.middleware = StarletteCORSMiddleware(
            app,
            allow_origins=allow_origins,
            allow_credentials=allow_credentials,
            allow_methods=allow_methods,
            allow_headers=allow_headers,
        )

    async def __call__(self, scope, receive, send):
        """Call the underlying CORS middleware."""
        return await self.middleware(scope, receive, send)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all incoming requests.

    Logs request method, path, client IP, and response status.
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and log details.

        Args:
            request: Incoming request
            call_next: Next middleware/route handler

        Returns:
            Response from downstream
        """
        logger.debug(
            f"{request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None,
            }
        )

        response = await call_next(request)

        logger.debug(
            f"{request.method} {request.url.path} -> {response.status_code}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
            }
        )

        return response
