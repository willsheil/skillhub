"""
API module - API services, schemas, and dependencies.

This module provides the API layer:
- services/: Business logic
- schemas/: Pydantic request/response models
- dependencies/: FastAPI dependency injection
Routes have been moved to apps/ directory.
"""

from .v1.services import SkillService, AuthService, UploadService
from .v1.dependencies import get_current_user, require_admin

__all__ = [
    "SkillService",
    "AuthService",
    "UploadService",
    "get_current_user",
    "require_admin",
]
