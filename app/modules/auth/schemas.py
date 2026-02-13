"""
Authentication request and response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class LoginRequest(BaseModel):
    """Login request schema for API authentication."""
    employee_id: str = Field(..., description="Employee ID")
    api_key: str = Field(..., description="API key for authentication")


class LoginResponse(BaseModel):
    """Login response schema."""
    success: bool
    message: str
    user: Optional["UserResponse"] = None


class UserResponse(BaseModel):
    """User information response schema."""
    id: int
    employee_id: str
    role: str
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdminLoginRequest(BaseModel):
    """Admin login request schema."""
    username: str = Field(..., description="Admin username")
    password: str = Field(..., description="Admin password")
