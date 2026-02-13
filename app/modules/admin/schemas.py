"""
Admin module request and response schemas.

Defines Pydantic models for admin API endpoints.
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator


class UserListQuery(BaseModel):
    """Query parameters for listing users."""
    page: int = Field(1, ge=1, description="Page number (starts from 1)")
    per_page: int = Field(20, ge=1, le=100, description="Users per page (max 100)")
    role: Optional[str] = Field(None, pattern="^(admin|user)$", description="Filter by role")
    status_filter: Optional[str] = Field(None, pattern="^(active|disabled)$", description="Filter by status")
    search: Optional[str] = Field(None, max_length=50, description="Search by employee_id")


class CreateUserRequest(BaseModel):
    """Request model for creating a new user."""
    employee_id: str = Field(..., max_length=50, description="Employee ID")
    role: str = Field(..., pattern="^(admin|user)$", description="User role")

    @field_validator('employee_id')
    @classmethod
    def validate_employee_id(cls, v):
        if not v or not v.strip():
            raise ValueError('employee_id cannot be empty')
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('employee_id must be alphanumeric with underscores/hyphens only')
        return v


class UpdateUserRoleRequest(BaseModel):
    """Request model for updating a user's role."""
    role: str = Field(..., pattern="^(admin|user)$", description="New role")


class UserResponse(BaseModel):
    """Response model for user data."""
    id: int
    employee_id: str
    role: str
    status: str
    skills_count: int
    created_at: Optional[str] = None
    last_login: Optional[str] = None


class UserListResponse(BaseModel):
    """Response model for paginated user list."""
    users: List[UserResponse]
    total: int
    page: int
    per_page: int
    pages: int


class AdminStatsResponse(BaseModel):
    """Response model for admin statistics."""
    total_users: int
    pending_skills: int
    approved_skills: int
    today_downloads: int
    top_skills: List[Dict[str, Any]]
    top_users: List[Dict[str, Any]]


class ReviewSkillRequest(BaseModel):
    """Request model for skill review."""
    action: str = Field(..., pattern="^(approve|reject)$", description="Action to take")
    comment: Optional[str] = Field(None, description="Optional review comment")


class UpdateSourceTypeRequest(BaseModel):
    """Request model for updating skill source type."""
    source_type: str = Field(..., pattern="^(opensource|icsl|huawei)$", description="Source type")


class SkillListQuery(BaseModel):
    """Query parameters for listing skills."""
    status: Optional[str] = Field(None, description="Filter by status")
    limit: int = Field(100, ge=1, le=500, description="Maximum skills to return")


class GiteaTaskListQuery(BaseModel):
    """Query parameters for listing Gitea tasks."""
    status: Optional[str] = Field(None, description="Filter by status")
    limit: int = Field(50, ge=1, le=200, description="Maximum tasks to return")


class BatchOperationRequest(BaseModel):
    """Request model for batch operations on skills."""
    skill_ids: List[int] = Field(..., description="List of skill IDs")
