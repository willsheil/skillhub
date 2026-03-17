"""
Custom exceptions for SkillHub application.

Provides a hierarchy of exceptions for different error types,
allowing proper error handling and HTTP status code mapping.
"""

from typing import Any, Dict, Optional


class SkillHubException(Exception):
    """Base exception class for all SkillHub errors.

    All custom exceptions should inherit from this class to enable
    consistent error handling across the application.

    Attributes:
        message: Human-readable error message
        code: Error code for programmatic error handling
        details: Additional error details
    """

    def __init__(
        self,
        message: str = "An error occurred",
        code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        result = {
            "error": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


class AuthenticationError(SkillHubException):
    """Raised when authentication fails.

    This exception is raised when:
    - Invalid credentials are provided
    - Session is expired or invalid
    - API key is invalid or missing
    """

    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            details=details,
        )


class AuthorizationError(SkillHubException):
    """Raised when user lacks required permissions.

    This exception is raised when:
    - User is authenticated but not authorized to perform action
    - User role does not have required privileges
    """

    def __init__(self, message: str = "Permission denied", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            details=details,
        )


class NotFoundError(SkillHubException):
    """Raised when requested resource is not found.

    This exception is raised when:
    - Skill does not exist
    - User does not exist
    - Resource ID is invalid
    """

    def __init__(self, resource: str = "Resource", resource_id: Optional[str] = None):
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} '{resource_id}' not found"
        super().__init__(
            message=message,
            code="NOT_FOUND",
            details={"resource": resource, "resource_id": resource_id},
        )


class ValidationError(SkillHubException):
    """Raised when input validation fails.

    This exception is raised when:
    - Request data fails schema validation
    - Business logic validation fails
    - Required fields are missing
    """

    def __init__(self, message: str = "Validation failed", field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        error_details = details or {}
        if field:
            error_details["field"] = field
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=error_details,
        )


class DatabaseError(SkillHubException):
    """Raised when database operation fails.

    This exception is raised when:
    - Database connection fails
    - Query execution fails
    - Transaction fails
    """

    def __init__(self, message: str = "Database operation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            details=details,
        )


class GiteaError(SkillHubException):
    """Raised when Gitea operation fails.

    This exception is raised when:
    - Git clone fails
    - Git push fails
    - Repository is not accessible
    """

    def __init__(self, message: str = "Gitea operation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="GITEA_ERROR",
            details=details,
        )


class UploadError(SkillHubException):
    """Raised when file upload fails.

    This exception is raised when:
    - File is too large
    - Invalid file type
    - Upload process fails
    """

    def __init__(self, message: str = "Upload failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="UPLOAD_ERROR",
            details=details,
        )


class RateLimitError(SkillHubException):
    """Raised when rate limit is exceeded.

    This exception is raised when:
    - API key rate limit is exceeded
    - User rate limit is exceeded
    """

    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="RATE_LIMIT_ERROR",
            details=details,
        )


class ConflictError(SkillHubException):
    """Raised when resource conflict occurs.

    This exception is raised when:
    - Duplicate resource creation
    - Concurrent modification
    """

    def __init__(self, message: str = "Resource conflict", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="CONFLICT_ERROR",
            details=details,
        )
