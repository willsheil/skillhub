"""
API V1 Routes Package

This package contains all API v1 route modules.
"""

from fastapi import APIRouter
from fastapi.templating import Jinja2Templates

from . import admin, skills, stats, users


def create_v1_router(templates_instance: Jinja2Templates) -> APIRouter:
    """Create and configure the v1 API router.

    Args:
        templates_instance: Jinja2Templates instance for rendering templates

    Returns:
        Configured APIRouter instance with all v1 routes
    """
    router = APIRouter(prefix="/api/v1", tags=["v1"])

    # Include admin routes (note: admin router has its own prefix)
    admin_router = admin.init_admin_router(templates_instance)

    # For now, we include the admin router without its prefix
    # because the admin routes are defined with their full paths
    for route in admin_router.routes:
        router.routes.append(route)

    # Include skills routes
    skills_router = skills.init_skills_router(templates_instance)

    # Include skills router without prefix (routes have their full paths)
    for route in skills_router.routes:
        router.routes.append(route)

    # Include stats routes
    stats_router = stats.init_stats_router(templates_instance)

    for route in stats_router.routes:
        router.routes.append(route)

    # Include users routes
    users_router = users.init_users_router(templates_instance)

    for route in users_router.routes:
        router.routes.append(route)

    return router
