"""
API Package

This package contains all API route modules organized by version.
"""

from fastapi import APIRouter
from fastapi.templating import Jinja2Templates


def create_api_router(templates_instance: Jinja2Templates) -> APIRouter:
    """Create and configure the main API router.

    Args:
        templates_instance: Jinja2Templates instance for rendering templates

    Returns:
        Configured APIRouter instance with all API routes
    """
    from .v1 import create_v1_router

    router = APIRouter()

    # Include v1 routes
    v1_router = create_v1_router(templates_instance)
    router.include_router(v1_router)

    return router
