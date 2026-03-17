"""
Database module - Database connection, models, and repositories.

This module provides the data access layer for the application, including:
- Database connection management
- Data models and entities
- Repository classes for each domain entity

All database operations should go through this module.
"""

from .connection import get_connection, ConnectionWrapper, init_db
from .models import (
    User,
    Skill,
    Download,
    Notification,
    GiteaPushTask,
    ApiKey,
)
from .repositories import (
    UserRepository,
    SkillRepository,
    DownloadRepository,
    NotificationRepository,
    GiteaTaskRepository,
    ApiKeyRepository,
)

__all__ = [
    # Connection
    "get_connection",
    "ConnectionWrapper",
    "init_db",
    # Models
    "User",
    "Skill",
    "Download",
    "Notification",
    "GiteaPushTask",
    "ApiKey",
    # Repositories
    "UserRepository",
    "SkillRepository",
    "DownloadRepository",
    "NotificationRepository",
    "GiteaTaskRepository",
    "ApiKeyRepository",
]
