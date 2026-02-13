"""
Skills module for managing Claude Code skills.

This module handles skill CRUD operations, validation, metadata extraction,
and API routes for skill management.
"""

from app.modules.skills.routes import router as skills_router

__all__ = ["skills_router"]
