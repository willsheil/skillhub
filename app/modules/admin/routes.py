"""
Admin module API routes.

Provides all admin-related endpoints for user and skill management.
"""

import logging
import secrets
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Request, status, Depends, Form, Query
from starlette.requests import Request as StarletteRequest
from fastapi.responses import JSONResponse

from app.modules.admin.dependencies import require_admin
from app.modules.admin.services import AdminService, ApiKeyRateLimiter
from app.modules.admin.schemas import (
    CreateUserRequest,
    UpdateUserRoleRequest,
    ReviewSkillRequest,
    UpdateSourceTypeRequest,
    BatchOperationRequest
)

# Get logger for this module
logger = logging.getLogger("skillhub.admin.routes")

# Create router
router = APIRouter(prefix="/api/admin", tags=["admin"])

# Rate limiter for API key reset operations
_api_key_rate_limiter = ApiKeyRateLimiter(rate_limit_minutes=5)


def get_admin_service(request: StarletteRequest) -> AdminService:
    """Get or create admin service instance.

    This is a dependency that can be injected into routes.

    Args:
        request: The incoming request object

    Returns:
        AdminService instance configured with database module
    """
    # Import database module lazily to avoid circular imports
    from database import (
        get_total_users_count, get_skills_count_by_status, get_today_downloads_count,
        get_top_skills_by_downloads, get_top_users_by_downloads,
        get_user_by_credentials, get_user_by_id, create_user,
        update_user_role, disable_user, enable_user, delete_user,
        reset_user_api_key, get_user_skills_count, get_connection,
        get_skill_by_id, update_skill_status, get_pending_skills,
        batch_delete_skills, delete_skill_version
    )

    # Create a simple database module wrapper
    class DBModule:
        """Wrapper for database functions."""
        def __init__(self):
            self.get_total_users_count = get_total_users_count
            self.get_skills_count_by_status = get_skills_count_by_status
            self.get_today_downloads_count = get_today_downloads_count
            self.get_top_skills_by_downloads = get_top_skills_by_downloads
            self.get_top_users_by_downloads = get_top_users_by_downloads
            self.get_user_by_credentials = get_user_by_credentials
            self.get_user_by_id = get_user_by_id
            self.create_user = create_user
            self.update_user_role = update_user_role
            self.disable_user = disable_user
            self.enable_user = enable_user
            self.delete_user = delete_user
            self.reset_user_api_key = reset_user_api_key
            self.get_user_skills_count = get_user_skills_count
            self.get_connection = get_connection
            self.get_skill_by_id = get_skill_by_id
            self.update_skill_status = update_skill_status
            self.get_pending_skills = get_pending_skills
            self.batch_delete_skills = batch_delete_skills
            self.delete_skill_version = delete_skill_version

    return AdminService(DBModule())


# ==================== Statistics Endpoints ====================

@router.get("/stats")
async def get_admin_stats(
    _: bool = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service)
) -> Dict[str, Any]:
    """Get admin statistics (admin only).

    Returns comprehensive statistics about the registry including:
    - Total users count
    - Pending skills count
    - Approved skills count
    - Today's downloads count
    - Top 10 skills by downloads
    - Top 10 users by downloads
    """
    try:
        return {
            "success": True,
            "data": admin_service.get_admin_stats()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch admin statistics: {str(e)}"
        )


# ==================== User Management Endpoints ====================

@router.get("/users")
async def get_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    role: str = Query(None, pattern="^(admin|user)$"),
    status_filter: str = Query(None, pattern="^(active|disabled)$"),
    search: str = Query(None, max_length=50),
    _: bool = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service)
) -> Dict[str, Any]:
    """Get paginated list of users with optional filters.

    Query params:
        page: Page number (default: 1)
        per_page: Users per page (default: 20, max: 100)
        role: Filter by role ('admin' or 'user')
        status_filter: Filter by status ('active' or 'disabled')
        search: Search by employee_id (partial match)

    Returns:
        Paginated user list with total count
    """
    try:
        result = admin_service.get_users_list(
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


@router.post("/users")
async def create_user_endpoint(
    request: Request,
    employee_id: str = Form(..., max_length=50),
    role: str = Form(..., pattern="^(admin|user)$"),
    _: bool = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service)
) -> Dict[str, Any]:
    """Create a new user.

    Form data:
        employee_id: Employee ID (alphanumeric, max 50 chars)
        role: User role ('admin' or 'user')

    Returns:
        Created user data with API key (shown only once)
    """
    try:
        import re

        # Validate employee_id format
        if not employee_id or not re.match(r'^[a-zA-Z0-9_-]+$', employee_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid employee_id format. Must be alphanumeric with underscores/hyphens only."
            )

        # Create user
        user_data = admin_service.create_user(employee_id=employee_id, role=role)

        return {
            "success": True,
            "data": user_data,
            "message": "User created successfully. Save the API key now as it won't be shown again."
        }

    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@router.put("/users/{user_id}")
async def update_user_role_endpoint(
    user_id: int,
    request: Request,
    role: str = Form(..., pattern="^(admin|user)$"),
    _: bool = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service)
) -> Dict[str, Any]:
    """Update a user's role.

    Form data:
        role: New role ('admin' or 'user')

    Prevents editing own role.
    """
    try:
        # Prevent editing own role
        current_user_id = request.session.get("user_id")
        if current_user_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify your own role"
            )

        # Import database module
        from database import get_user_by_id

        # Check if user exists
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Update role
        success = admin_service.update_user_role(user_id, role)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to update user role"
            )

        return {
            "success": True,
            "data": {
                "id": user_id,
                "employee_id": user["employee_id"],
                "role": role
            },
            "message": "User role updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user role: {str(e)}"
        )


@router.patch("/users/{user_id}/disable")
async def disable_user_endpoint(
    user_id: int,
    request: Request,
    _: bool = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service)
) -> Dict[str, Any]:
    """Disable a user.

    Prevents login but keeps the user in the system.
    Prevents disabling self.
    """
    try:
        # Prevent disabling self
        current_user_id = request.session.get("user_id")
        if current_user_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot disable your own account"
            )

        # Import database module
        from database import get_user_by_id

        # Check if user exists
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Disable user
        success = admin_service.disable_user(user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to disable user"
            )

        return {
            "success": True,
            "data": {
                "id": user_id,
                "employee_id": user["employee_id"],
                "status": "disabled"
            },
            "message": "User disabled successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable user: {str(e)}"
        )


@router.delete("/users/{user_id}")
async def delete_user_endpoint(
    user_id: int,
    request: Request,
    _: bool = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service)
) -> Dict[str, Any]:
    """Permanently delete a user.

    Only allowed if user has no skills (skills_count == 0).
    Prevents deleting self.
    """
    try:
        # Prevent deleting self
        current_user_id = request.session.get("user_id")
        if current_user_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete your own account"
            )

        # Import database module
        from database import get_user_by_id

        # Check if user exists
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Check if user has active skills
        skills_count = admin_service.db.get_user_skills_count(user_id)
        if skills_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete user with {skills_count} skill(s). Please remove skills first."
            )

        # Delete user
        success = admin_service.delete_user(user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to delete user"
            )

        return {
            "success": True,
            "data": {
                "id": user_id,
                "employee_id": user["employee_id"]
            },
            "message": "User deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )


@router.patch("/users/{user_id}/enable")
async def enable_user_endpoint(
    user_id: int,
    _: bool = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service)
) -> Dict[str, Any]:
    """Re-enable a disabled user.

    Allows the user to login again.
    """
    try:
        # Import database module
        from database import get_user_by_id

        # Check if user exists
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Enable user
        success = admin_service.enable_user(user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to enable user"
            )

        return {
            "success": True,
            "data": {
                "id": user_id,
                "employee_id": user["employee_id"],
                "status": "active"
            },
            "message": "User enabled successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable user: {str(e)}"
        )


@router.post("/users/{user_id}/reset-key")
async def reset_user_api_key_endpoint(
    user_id: int,
    _: bool = Depends(require_admin),
    admin_service: AdminService = Depends(get_admin_service)
) -> Dict[str, Any]:
    """Reset a user's API key.

    Generates a new 32-character API key.
    Old key is immediately invalidated.
    Rate limited to once per 5 minutes per user.
    """
    try:
        # Check rate limit
        rate_limit_error = _api_key_rate_limiter.check_rate_limit(user_id)
        if rate_limit_error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=rate_limit_error
            )

        # Import database module
        from database import get_user_by_id

        # Check if user exists
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Generate new API key
        new_api_key = secrets.token_hex(16)

        # Reset API key
        success = admin_service.reset_user_api_key(user_id, new_api_key)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to reset API key"
            )

        # Store reset time after successful reset
        _api_key_rate_limiter.record_operation(user_id)

        return {
            "success": True,
            "data": {
                "id": user_id,
                "employee_id": user["employee_id"],
                "api_key": new_api_key
            },
            "message": "API key reset successfully. Save the new key now as it won't be shown again."
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset API key: {str(e)}"
        )


# ==================== Skill Management Endpoints ====================

@router.get("/skills")
async def get_all_skills(
    status: str = Query(None),
    limit: int = Query(100, ge=1, le=500),
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Get all skills with optional status filter (admin only).

    Args:
        status: Filter by status (pending/approved/rejected)
        limit: Maximum number of skills to return

    Returns:
        List of skills with full details
    """
    try:
        from database import get_connection

        with get_connection() as conn:
            if status:
                rows = conn.execute("""
                    SELECT s.id, s.skill_name, s.version, s.filename, s.status,
                           s.source_type, s.uploaded_at, u.employee_id as uploader_name
                    FROM skills s
                    LEFT JOIN users u ON s.uploader_id = u.id
                    WHERE s.status = %s
                    ORDER BY s.uploaded_at DESC
                    LIMIT %s
                """, (status, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT s.id, s.skill_name, s.version, s.filename, s.status,
                           s.source_type, s.uploaded_at, u.employee_id as uploader_name
                    FROM skills s
                    LEFT JOIN users u ON s.uploader_id = u.id
                    ORDER BY s.uploaded_at DESC
                    LIMIT %s
                """, (limit,)).fetchall()

            return {
                "success": True,
                "data": rows,
                "count": len(rows)
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch skills: {str(e)}"
        )


@router.put("/skills/{skill_id}/source-type")
async def update_skill_source_type(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Update the source_type of a skill (admin only).

    Expects JSON body with:
    {
        "source_type": "opensource" | "icsl" | "huawei"
    }
    """
    try:
        # Get current user
        reviewer_id = request.session.get("user_id")
        if not reviewer_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Parse request body
        data = await request.json()
        source_type = data.get("source_type")

        # Validate source_type
        valid_types = ["opensource", "icsl", "huawei"]
        if source_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source_type. Must be one of: {', '.join(valid_types)}"
            )

        # Import database module
        from database import get_skill_by_id, get_connection

        # Get skill record
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        # Update source_type in database
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE skills
                SET source_type = %s
                WHERE id = %s
                """,
                (source_type, skill_id)
            )
            conn.commit()

        return {
            "success": True,
            "message": f"Updated source_type for {skill['skill_name']} to {source_type}",
            "skill_id": skill_id,
            "source_type": source_type
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update source_type: {str(e)}"
        )


@router.get("/gitea-tasks")
async def get_gitea_tasks(
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Get Gitea push tasks with optional status filter.

    Args:
        status: Filter by status (pending/pushing/success/failed)
        limit: Maximum number of tasks to return

    Returns:
        List of push tasks with skill info
    """
    try:
        from database import get_connection

        with get_connection() as conn:
            if status:
                rows = conn.execute("""
                    SELECT t.*, s.skill_name, s.uploader_id, u.employee_id as uploader_name
                    FROM gitea_push_tasks t
                    JOIN skills s ON t.skill_id = s.id
                    LEFT JOIN users u ON s.uploader_id = u.id
                    WHERE t.status = %s
                    ORDER BY t.created_at DESC
                    LIMIT %s
                """, (status, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT t.*, s.skill_name, s.uploader_id, u.employee_id as uploader_name
                    FROM gitea_push_tasks t
                    JOIN skills s ON t.skill_id = s.id
                    LEFT JOIN users u ON s.uploader_id = u.id
                    ORDER BY t.created_at DESC
                    LIMIT %s
                """, (limit,)).fetchall()

            return {
                "success": True,
                "data": rows,
                "count": len(rows)
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tasks: {str(e)}"
        )


# ==================== Skill Review Endpoints ====================

@router.get("/pending")
async def get_pending_skills(
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Get all pending skills awaiting approval (admin only)."""
    try:
        from database import get_pending_skills

        pending = get_pending_skills()
        return {
            "success": True,
            "data": pending,
            "count": len(pending)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending skills: {str(e)}"
        )


@router.post("/review/{skill_id}")
async def review_skill(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Approve or reject a pending skill (admin only).

    Expects JSON body with:
    {
        "action": "approve" | "reject",
        "comment": "optional comment"
    }
    """
    try:
        # Get current user (reviewer)
        reviewer_id = request.session.get("user_id")
        if not reviewer_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Parse request body
        data = await request.json()
        action = data.get("action")
        comment = data.get("comment")

        if action not in ["approve", "reject"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid action. Must be 'approve' or 'reject'"
            )

        # Import database modules
        from database import get_skill_by_id, update_skill_status, get_connection

        # Get skill record
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        if skill["status"] != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Skill {skill_id} is not in pending status"
            )

        # Perform action
        if action == "approve":
            from database import approve_skill_file
            success = approve_skill_file(skill_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to approve skill {skill_id}"
                )

            # Update with reviewer info
            update_skill_status(skill_id, "approved", reviewer_id=reviewer_id, comment=comment)

            # Create Gitea push task
            task_id = None
            try:
                from gitea_integration import create_push_task
                task_id = create_push_task(skill_id)
                logger.info(f"Created Gitea push task {task_id} for skill {skill_id}")
            except Exception as e:
                logger.error(f"Failed to create Gitea push task: {e}")

            return {
                "success": True,
                "message": f"Skill {skill['skill_name']}@{skill['version']} approved",
                "skill_id": skill_id,
                "push_task_id": task_id
            }

        else:  # reject
            from database import reject_skill_file
            success = reject_skill_file(skill_id, comment)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to reject skill {skill_id}"
                )

            # Update with reviewer info
            update_skill_status(skill_id, "rejected", reviewer_id=reviewer_id, comment=comment)

            return {
                "success": True,
                "message": f"Skill {skill['skill_name']}@{skill['version']} rejected",
                "skill_id": skill_id
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Review failed: {str(e)}"
        )


# ==================== Batch Operations Endpoints ====================

@router.post("/my-skills/batch/delete")
async def batch_delete_skills_endpoint(
    request_data: BatchOperationRequest,
    request: Request,
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Delete multiple skills at once (admin only).

    Only admin users can delete any skills. The physical ZIP files will also be removed.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        from database import batch_delete_skills

        result = batch_delete_skills(user_id, request_data.skill_ids)

        message = f"已删除 {result['success_count']} 个技能"
        if result["failed_ids"]:
            message += f"，{len(result['failed_ids'])} 个失败"

        return {
            "success": True,
            "message": message,
            "success_count": result["success_count"],
            "failed_ids": result["failed_ids"]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to batch delete skills: {str(e)}"
        )


@router.delete("/my-skills/{skill_id}")
async def delete_skill_endpoint(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Delete a skill version (admin only).

    Only admin users can delete any skill. The physical ZIP file will also be removed.
    If this is the default version and there are other versions, another version will be set as default.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Import database modules
        from database import get_skill_by_id, delete_skill_version

        # Get skill record for response message
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        # Admin can delete any skill, no ownership check needed
        success = delete_skill_version(user_id, skill_id, is_admin=True)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete skill"
            )

        return {
            "success": True,
            "message": f"Skill {skill['skill_name']}@{skill['version']} has been deleted",
            "skill_id": skill_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete skill: {str(e)}"
        )
