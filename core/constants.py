"""
Constants and enumerations for SkillHub application.

Provides type-safe constants for user roles, skill status, source types,
and notification types that can be used throughout the application.
"""

from enum import Enum


class UserRole(str, Enum):
    """User role enumeration.

    Attributes:
        ADMIN: Full system access including user management
        USER: Standard user access to upload and manage own skills
    """
    ADMIN = "admin"
    USER = "user"

    @classmethod
    def choices(cls) -> list:
        """Get list of valid role choices for forms."""
        return [e.value for e in cls]

    def is_admin(self) -> bool:
        """Check if role is admin."""
        return self == self.ADMIN


class SkillStatus(str, Enum):
    """Skill status enumeration.

    Attributes:
        PENDING: Awaiting admin review
        APPROVED: Approved and available in marketplace
        REJECTED: Rejected by admin
    """
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

    @classmethod
    def choices(cls) -> list:
        """Get list of valid status choices."""
        return [e.value for e in cls]


class SourceType(str, Enum):
    """Skill source type enumeration.

    Attributes:
        OPENSOURCE: Open source skills
        ICSL: Internal company skills
        HUAWEI: Huawei partner skills
    """
    OPENSOURCE = "opensource"
    ICSL = "icsl"
    HUAWEI = "huawei"

    @classmethod
    def choices(cls) -> list:
        """Get list of valid source type choices."""
        return [e.value for e in cls]

    @classmethod
    def default(cls) -> str:
        """Get default source type."""
        return cls.OPENSOURCE.value


class NotificationType(str, Enum):
    """Notification type enumeration.

    Attributes:
        APPROVAL: Skill approval notification
        REJECTION: Skill rejection notification
        UPLOAD: New skill upload notification
        SYSTEM: System notification
    """
    APPROVAL = "approval"
    REJECTION = "rejection"
    UPLOAD = "upload"
    SYSTEM = "system"

    @classmethod
    def choices(cls) -> list:
        """Get list of valid notification type choices."""
        return [e.value for e in cls]


class TaskStatus(str, Enum):
    """Gitea push task status enumeration.

    Attributes:
        PENDING: Task waiting to be processed
        RESERVED: Task reserved by worker
        PUSHING: Currently pushing to Gitea
        SUCCESS: Push completed successfully
        FAILED: Push failed
        RETRY_PENDING: Waiting for retry
    """
    PENDING = "pending"
    RESERVED = "reserved"
    PUSHING = "pushing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY_PENDING = "retry_pending"

    @classmethod
    def choices(cls) -> list:
        """Get list of valid task status choices."""
        return [e.value for e in cls]

    def is_terminal(self) -> bool:
        """Check if this is a terminal state."""
        return self in (self.SUCCESS, self.FAILED)


# API Key related constants
API_KEY_LENGTH = 32
API_KEY_RESET_COOLDOWN_SECONDS = 60

# Pagination defaults
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# File upload limits
MAX_UPLOAD_SIZE_MB = 50
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# Skill file constraints
SKILL_NAME_MIN_LENGTH = 3
SKILL_NAME_MAX_LENGTH = 64
SKILL_NAME_PATTERN = r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$"

# Version constraints
VERSION_PATTERN = r"^\d+\.\d+\.\d+$"

# Rate limiting
DEFAULT_RATE_LIMIT_PER_MINUTE = 100
ADMIN_RATE_LIMIT_PER_MINUTE = 1000

# Cache settings
CACHE_TTL_SECONDS = 300  # 5 minutes

# Gitea settings
GITEA_MAX_RETRY = 3
GITEA_RETRY_DELAY_SECONDS = 5
GITEA_CLONE_TIMEOUT_SECONDS = 60
GITEA_PUSH_TIMEOUT_SECONDS = 120
