"""Users API routes."""

from fastapi import APIRouter, Request, Depends, HTTPException, Query, Form, status
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any

from .dependencies import require_auth, require_admin
from .services import (
    get_user_by_id,
    get_users_list,
    create_user,
    update_user_role,
    disable_user as disable_user_service,
    enable_user as enable_user_service,
    delete_user as delete_user_service,
    reset_user_api_key,
    generate_api_key
)
from database import get_user_uploads, get_user_downloads

router = APIRouter(prefix="/api", tags=["users"])


# ==================== User Endpoints ====================

@router.get("/user/downloads")
async def api_user_downloads(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    _: bool = Depends(require_auth)
):
    """Get the current user's download history with pagination."""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        result = get_user_downloads(
            user_id=user_id,
            limit=per_page,
            offset=(page - 1) * per_page
        )

        downloads = []
        for dl in result["downloads"]:
            downloads.append({
                "skill_name": dl["skill_name"],
                "version": dl["version"],
                "filename": dl["filename"],
                "downloaded_at": dl["downloaded_at"].isoformat() if dl["downloaded_at"] else None,
                "ip_address": dl["ip_address"],
                "user_agent": dl["user_agent"]
            })

        return JSONResponse(content={
            "success": True,
            "data": {
                "downloads": downloads,
                "total": result["total"],
                "page": page,
                "per_page": per_page,
                "pages": (result["total"] + per_page - 1) // per_page if result["total"] > 0 else 1
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch downloads: {str(e)}"
        )


@router.get("/user/uploads")
async def api_user_uploads(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    _: bool = Depends(require_auth)
):
    """Get the current user's upload history with pagination."""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        offset = (page - 1) * per_page
        result = get_user_uploads(user_id, limit=per_page, offset=offset)
        uploads = result["uploads"]
        total = result["total"]
        total_pages = (total + per_page - 1) // per_page

        return JSONResponse(content={
            "success": True,
            "data": {
                "uploads": uploads,
                "total": total
            },
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch uploads: {str(e)}"
        )


# ==================== Admin User Management Endpoints ====================

@router.get("/admin/users")
async def api_get_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    role: Optional[str] = Query(None, pattern="^(admin|user)$"),
    status_filter: Optional[str] = Query(None, pattern="^(active|disabled)$"),
    search: Optional[str] = Query(None, max_length=50),
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Get paginated list of users with optional filters."""
    try:
        result = get_users_list(
            page=page,
            per_page=per_page,
            role=role,
            status_filter=status_filter,
            search=search
        )

        return {
            "success": True,
            "data": result
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )


@router.post("/admin/users")
async def api_create_user(
    request: Request,
    employee_id: str = Form(..., max_length=50),
    role: str = Form(..., pattern="^(admin|user)$"),
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Create a new user."""
    try:
        # Check if employee_id already exists
        existing_user = None
        from database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE employee_id = %s",
                (employee_id,)
            ).fetchone()
            if row:
                existing_user = row["id"]

        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with employee_id '{employee_id}' already exists"
            )

        # Generate API key
        api_key = generate_api_key()

        # Create user
        user_id = create_user(
            employee_id=employee_id,
            api_key=api_key,
            role=role
        )

        return {
            "success": True,
            "data": {
                "id": user_id,
                "employee_id": employee_id,
                "role": role,
                "api_key": api_key,
                "message": "User created successfully. Save the API key securely, it won't be shown again."
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@router.put("/admin/users/{user_id}")
async def api_update_user_role(
    user_id: int,
    request: Request,
    role: str = Form(..., pattern="^(admin|user)$"),
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Update a user's role."""
    try:
        # Verify user exists
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Update role
        updated = update_user_role(user_id, role)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {
            "success": True,
            "data": {
                "id": user_id,
                "role": role,
                "message": "User role updated successfully"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user role: {str(e)}"
        )


@router.patch("/admin/users/{user_id}/disable")
async def api_disable_user(
    user_id: int,
    request: Request,
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Disable a user."""
    try:
        # Get current admin user id
        current_user_id = request.session.get("user_id")

        # Prevent disabling self
        if user_id == current_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot disable yourself"
            )

        # Check if user exists
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Disable user
        disabled = disable_user_service(user_id)
        if not disabled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {
            "success": True,
            "data": {
                "id": user_id,
                "status": "disabled",
                "message": "User disabled successfully"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable user: {str(e)}"
        )


@router.delete("/admin/users/{user_id}")
async def api_delete_user(
    user_id: int,
    request: Request,
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Permanently delete a user."""
    try:
        # Get current admin user id
        current_user_id = request.session.get("user_id")

        # Prevent deleting self
        if user_id == current_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete yourself"
            )

        # Check if user exists
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Check if user has skills
        if user["skills_count"] and user["skills_count"] > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete user with existing skills. Delete or transfer skills first."
            )

        # Delete user
        deleted = delete_user_service(user_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {
            "success": True,
            "data": {
                "id": user_id,
                "message": "User deleted successfully"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )


@router.patch("/admin/users/{user_id}/enable")
async def api_enable_user(
    user_id: int,
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Re-enable a disabled user."""
    try:
        # Check if user exists
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Enable user
        enabled = enable_user_service(user_id)
        if not enabled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {
            "success": True,
            "data": {
                "id": user_id,
                "status": "active",
                "message": "User enabled successfully"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable user: {str(e)}"
        )


@router.post("/admin/users/{user_id}/reset-key")
async def api_reset_user_api_key(
    user_id: int,
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Reset a user's API key."""
    try:
        # Check if user exists
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Generate new API key
        new_api_key = generate_api_key()

        # Update API key
        updated = reset_user_api_key(user_id, new_api_key)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return {
            "success": True,
            "data": {
                "id": user_id,
                "api_key": new_api_key,
                "message": "API key reset successfully. Save the new API key securely."
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset API key: {str(e)}"
        )
