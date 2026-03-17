"""
Database repositories for SkillHub.

Provides data access classes for each domain entity.
Each repository encapsulates all database operations for a specific entity.
"""

from .user_repo import UserRepository
from .skill_repo import SkillRepository
from .download_repo import DownloadRepository
from .notification_repo import NotificationRepository
from .gitea_task_repo import GiteaTaskRepository
from .api_key_repo import ApiKeyRepository

__all__ = [
    "UserRepository",
    "SkillRepository",
    "DownloadRepository",
    "NotificationRepository",
    "GiteaTaskRepository",
    "ApiKeyRepository",
]
