"""
CORS middleware configuration.

This module provides CORS (Cross-Origin Resource Sharing) configuration
for the FastAPI application.
"""

import os
from typing import List, Optional


# Default CORS settings
DEFAULT_ALLOW_ORIGINS: List[str] = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:3000",
]

DEFAULT_ALLOW_METHODS: List[str] = [
    "GET",
    "POST",
    "PUT",
    "DELETE",
    "OPTIONS",
]

DEFAULT_ALLOW_HEADERS: List[str] = [
    "Content-Type",
    "Authorization",
    "X-Requested-With",
]

DEFAULT_ALLOW_CREDENTIALS: bool = True


def get_cors_config(
    allow_origins: Optional[List[str]] = None,
    allow_methods: Optional[List[str]] = None,
    allow_headers: Optional[List[str]] = None,
    allow_credentials: Optional[bool] = None,
) -> dict:
    """Get CORS configuration dictionary.

    Args:
        allow_origins: List of allowed origins
        allow_methods: List of allowed HTTP methods
        allow_headers: List of allowed headers
        allow_credentials: Whether to allow credentials

    Returns:
        Dictionary with CORS configuration
    """
    # Allow overriding via environment variable
    env_origins = os.getenv("CORS_ORIGINS")
    if env_origins:
        allow_origins = env_origins.split(",")

    return {
        "allow_origins": allow_origins or DEFAULT_ALLOW_ORIGINS,
        "allow_methods": allow_methods or DEFAULT_ALLOW_METHODS,
        "allow_headers": allow_headers or DEFAULT_ALLOW_HEADERS,
        "allow_credentials": allow_credentials if allow_credentials is not None else DEFAULT_ALLOW_CREDENTIALS,
    }


__all__ = ["get_cors_config", "DEFAULT_ALLOW_ORIGINS", "DEFAULT_ALLOW_METHODS", "DEFAULT_ALLOW_HEADERS"]
