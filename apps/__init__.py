"""
Apps module - Route handlers for FastAPI.

Provides all API route handlers organized by domain (Django-style apps).
This module imports and combines routes from submodules.
"""

from fastapi import APIRouter

# Import all route modules
from . import auth, skills, admin, stats, gitea, external, pages, downloads, notifications, users, keys

# Create main API router
router = APIRouter()

# Include all sub-routers
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(skills.router, prefix="/api/skills", tags=["Skills"])
router.include_router(admin.router, prefix="/admin", tags=["Admin"])
router.include_router(stats.router, prefix="/api/stats", tags=["Statistics"])
router.include_router(gitea.router, prefix="/gitea", tags=["Gitea"])
router.include_router(external.router, tags=["External API"])
router.include_router(pages.router, tags=["Pages"])
router.include_router(downloads.router, tags=["Downloads"])
router.include_router(notifications.router, tags=["Notifications"])
router.include_router(users.router, tags=["Users"])
router.include_router(keys.router, tags=["API Keys"])

# Re-export for convenience
__all__ = ["router", "pages", "downloads", "notifications", "users", "keys"]
