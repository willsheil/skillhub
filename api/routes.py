"""
API routes - Main router combining all route modules.

This is the entry point for the API router used in main.py.
"""

from fastapi import APIRouter

from api.v1.routes import router as v1_router

# Create main API router
router = APIRouter()

# Include v1 router
router.include_router(v1_router)

__all__ = ["router"]
