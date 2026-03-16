"""
Core module - Configuration, constants, exceptions, and security utilities.

This module provides the foundational building blocks used across the entire
application. All other modules depend on this module.
"""

from .config import Settings, get_settings
from .exceptions import (
    SkillHubException,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    DatabaseError,
    GiteaError,
)
from .constants import (
    UserRole,
    SkillStatus,
    SourceType,
    NotificationType,
)
from .security import (
    hash_api_key,
    verify_api_key,
    generate_token,
    mask_sensitive_data,
)

__all__ = [
    # Config
    "Settings",
    "get_settings",
    # Exceptions
    "SkillHubException",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ValidationError",
    "DatabaseError",
    "GiteaError",
    # Constants
    "UserRole",
    "SkillStatus",
    "SourceType",
    "NotificationType",
    # Security
    "hash_api_key",
    "verify_api_key",
    "generate_token",
    "mask_sensitive_data",
]
