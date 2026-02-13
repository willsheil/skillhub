"""
Admin module for user and skill management.

This module contains all admin-related functionality including:
- User management (CRUD operations)
- Skill approval workflow
- Admin statistics and reporting
- Admin-specific dependencies
"""

from app.modules.admin.routes import router as admin_router

__all__ = ["admin_router"]
