"""
Data models for SkillHub application.

These models represent the domain entities and are used throughout the application.
Note: These are simple data classes, not ORM models. Database operations are handled
by repositories.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any

from core.constants import UserRole, SkillStatus, SourceType, NotificationType, TaskStatus


@dataclass
class User:
    """User entity representing a registered user.

    Attributes:
        id: Unique user ID
        employee_id: Employee identifier
        api_key: User's API key (hashed)
        role: User role (admin/user)
        status: Account status (active/disabled)
        skills_count: Number of skills uploaded by user
        last_login: Last login timestamp
        created_at: Account creation timestamp
        updated_at: Last update timestamp
        name: User display name
        minDepartment: User's department
        team: User's team
        group: User's group
    """
    id: Optional[int] = None
    employee_id: str = ""
    api_key: str = ""
    role: str = UserRole.USER.value
    status: str = "active"
    skills_count: int = 0
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    name: Optional[str] = None
    minDepartment: Optional[str] = None
    team: Optional[str] = None
    group: Optional[str] = None

    def is_admin(self) -> bool:
        """Check if user is admin."""
        return self.role == UserRole.ADMIN.value

    def is_active(self) -> bool:
        """Check if user account is active."""
        return self.status == "active"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "role": self.role,
            "status": self.status,
            "skills_count": self.skills_count,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class Skill:
    """Skill entity representing a skill plugin.

    Attributes:
        id: Unique skill ID
        skill_name: Skill name (unique identifier)
        version: Semantic version string
        filename: ZIP filename
        description: Skill description
        metadata: JSON metadata (version, author, tags, etc.)
        uploader_id: ID of user who uploaded
        status: Skill status (pending/approved/rejected)
        source_type: Source type (opensource/icsl/huawei)
        is_active: Whether skill is visible in marketplace
        is_default_version: Whether this is the default version
        latest_push_task_id: Last Gitea push task ID
        uploaded_at: Upload timestamp
        reviewed_at: Review timestamp
        reviewer_id: ID of admin who reviewed
        review_comment: Review comment
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    id: Optional[int] = None
    skill_name: str = ""
    version: str = ""
    filename: str = ""
    description: str = ""
    metadata: Optional[str] = None
    uploader_id: int = 0
    status: str = SkillStatus.PENDING.value
    source_type: str = SourceType.OPENSOURCE.value
    is_active: bool = True
    is_default_version: bool = False
    latest_push_task_id: Optional[int] = None
    uploaded_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewer_id: Optional[int] = None
    review_comment: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Populated via joins
    uploader_employee_id: Optional[str] = None

    def is_approved(self) -> bool:
        """Check if skill is approved."""
        return self.status == SkillStatus.APPROVED.value

    def is_pending(self) -> bool:
        """Check if skill is pending review."""
        return self.status == SkillStatus.PENDING.value

    def to_dict(self, include_metadata: bool = True) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "id": self.id,
            "skill_name": self.skill_name,
            "version": self.version,
            "filename": self.filename,
            "description": self.description,
            "uploader_id": self.uploader_id,
            "status": self.status,
            "source_type": self.source_type,
            "is_active": self.is_active,
            "is_default_version": self.is_default_version,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewer_id": self.reviewer_id,
            "review_comment": self.review_comment,
        }
        if include_metadata and self.metadata:
            import json
            try:
                result["metadata"] = json.loads(self.metadata)
            except (json.JSONDecodeError, TypeError):
                result["metadata"] = {}
        return result


@dataclass
class Download:
    """Download record entity.

    Attributes:
        id: Unique download ID
        skill_name: Name of downloaded skill
        version: Version of downloaded skill
        user_id: ID of user who downloaded (nullable for anonymous)
        downloaded_at: Download timestamp
    """
    id: Optional[int] = None
    skill_name: str = ""
    version: str = ""
    user_id: Optional[int] = None
    downloaded_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "skill_name": self.skill_name,
            "version": self.version,
            "user_id": self.user_id,
            "downloaded_at": self.downloaded_at.isoformat() if self.downloaded_at else None,
        }


@dataclass
class Notification:
    """Notification entity.

    Attributes:
        id: Unique notification ID
        user_id: Target user ID
        type: Notification type (approval/rejection/upload/system)
        title: Notification title
        content: Notification content
        related_skill_id: Related skill ID (optional)
        is_read: Whether notification has been read
        created_at: Creation timestamp
    """
    id: Optional[int] = None
    user_id: int = 0
    type: str = NotificationType.SYSTEM.value
    title: str = ""
    content: Optional[str] = None
    related_skill_id: Optional[int] = None
    is_read: bool = False
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "title": self.title,
            "content": self.content,
            "related_skill_id": self.related_skill_id,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class GiteaPushTask:
    """Gitea push task entity.

    Attributes:
        id: Unique task ID
        skill_id: Associated skill ID
        status: Task status (pending/reserved/pushing/success/failed)
        retry_count: Number of retry attempts
        worker_id: ID of worker processing this task
        commit_hash: Git commit hash after successful push
        error_message: Error message if failed
        started_at: Task start timestamp
        completed_at: Task completion timestamp
        created_at: Task creation timestamp
    """
    id: Optional[int] = None
    skill_id: int = 0
    status: str = TaskStatus.PENDING.value
    retry_count: int = 0
    worker_id: Optional[str] = None
    commit_hash: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    def is_terminal(self) -> bool:
        """Check if task is in terminal state."""
        return self.status in (TaskStatus.SUCCESS.value, TaskStatus.FAILED.value)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "skill_id": self.skill_id,
            "status": self.status,
            "retry_count": self.retry_count,
            "worker_id": self.worker_id,
            "commit_hash": self.commit_hash,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class ApiKey:
    """API Key entity.

    Attributes:
        id: Unique API key ID
        key_name: Human-readable name for the key
        api_key_hash: Hashed API key value
        user_id: Owner user ID
        rate_limit: Requests per minute limit
        status: Key status (active/disabled)
        last_used_at: Last usage timestamp
        created_at: Creation timestamp
        expires_at: Expiration timestamp (optional)
    """
    id: Optional[int] = None
    key_name: str = ""
    api_key_hash: str = ""
    user_id: int = 0
    rate_limit: int = 100
    status: str = "active"
    last_used_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    def is_active(self) -> bool:
        """Check if key is active."""
        return self.status == "active"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "key_name": self.key_name,
            "user_id": self.user_id,
            "rate_limit": self.rate_limit,
            "status": self.status,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
