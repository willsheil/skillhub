"""
Authentication routes - Login, logout, session management.
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from db.repositories import UserRepository
from core.constants import UserRole

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request model."""
    employee_id: str
    api_key: str


class LoginResponse(BaseModel):
    """Login response model."""
    success: bool
    message: str
    user_id: int
    role: str


@router.post("/login", response_model=LoginResponse)
async def login(request: Request, credentials: LoginRequest):
    """User login endpoint.

    Args:
        request: FastAPI request object
        credentials: Login credentials

    Returns:
        LoginResponse with success status
    """
    # Authenticate user
    user = UserRepository.get_by_credentials(
        credentials.employee_id,
        credentials.api_key
    )

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.status != "active":
        raise HTTPException(status_code=403, detail="Account is disabled")

    # Update last login
    UserRepository.update_last_login(user.id)

    # Set session
    request.session["user_id"] = user.id
    request.session["employee_id"] = user.employee_id
    request.session["role"] = user.role

    return LoginResponse(
        success=True,
        message="Login successful",
        user_id=user.id,
        role=user.role
    )


@router.post("/logout")
async def logout(request: Request):
    """User logout endpoint."""
    request.session.clear()
    return {"success": True, "message": "Logged out"}


@router.get("/me")
async def get_current_user(request: Request):
    """Get current logged in user.

    Requires authentication.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = UserRepository.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user.id,
        "employee_id": user.employee_id,
        "role": user.role,
        "skills_count": user.skills_count,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }
