"""Users request/response schemas."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """Schema for creating a new user."""
    employee_id: str = Field(..., max_length=50, description="Employee ID")
    role: str = Field(..., pattern="^(admin|user)$", description="User role (admin or user)")


class UserUpdateRole(BaseModel):
    """Schema for updating a user's role."""
    role: str = Field(..., regex="^(admin|user)$", description="New role (admin or user)")


class UserResponse(BaseModel):
    """Schema for user response."""
    id: int
    employee_id: str
    role: str
    status: str
    skills_count: int
    created_at: str
    last_login: Optional[str] = None


class UserListResponse(BaseModel):
    """Schema for paginated user list response."""
    users: List[UserResponse]
    total: int
    page: int
    per_page: int
    pages: int


class APIKeyResponse(BaseModel):
    """Schema for API key reset response."""
    api_key: str


class ErrorResponse(BaseModel):
    """Schema for error responses."""
    detail: str
