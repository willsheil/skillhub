"""
Users API Routes - V1

This module contains all user-related routes:
- GET /api/my-skills - Get current user's skills with pagination
- GET /my-skills - My skills page
- POST /api/my-skills/batch/unlist - Batch unlist skills
- POST /api/my-skills/batch/delete - Batch delete skills (admin only)
- POST /api/my-skills/{skill_id}/unlist - Unlist a skill
- POST /api/my-skills/{skill_id}/publish - Publish a skill
- POST /api/my-skills/{skill_id}/set-default - Set default version
- GET /api/my-skills/versions/{skill_name} - Get skill versions
- DELETE /api/my-skills/{skill_id} - Delete a skill (admin only)
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request as StarletteRequest

# Templates (will be injected from main app)
templates = None

# Logger
logger = logging.getLogger("skillhub")

# Router
router = APIRouter(prefix="/api/v1", tags=["users"])

# Dependencies from database module
from database import (
    get_skill_by_id,
    get_my_skills,
    get_skill_versions,
    update_skill_active_status,
    set_default_skill_version,
    batch_unlist_skills,
    batch_delete_skills,
)

# Import helper functions from core/dependencies
from core.dependencies import get_current_user, require_auth, require_admin


# ============================================================================
# Request Models
# ============================================================================

class BatchOperationRequest(BaseModel):
    """Request model for batch operations."""
    skill_ids: List[int]


# ============================================================================
# API Routes (User Skills Management)
# ============================================================================

@router.get("/my-skills")
async def api_my_skills(
    request: Request,
    status_filter: str = Query("all", description="Filter by status: all, active, unlisted, pending, rejected"),
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    _: bool = Depends(require_auth)
):
    """Get current user's skills with pagination and filtering.

    Query parameters:
    - status: Filter by status ('all', 'active', 'unlisted', 'pending', 'rejected')
    - page: Page number (default: 1, min: 1)
    - per_page: Items per page (default: 20, min: 1, max: 100)

    Returns paginated list of skills for the authenticated user.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Calculate offset from page number
        offset = (page - 1) * per_page

        # Get user skills from database
        result = get_my_skills(
            user_id=user_id,
            status_filter=status_filter,
            limit=per_page,
            offset=offset
        )

        # Calculate pagination metadata
        total = result["total"]
        total_pages = (total + per_page - 1) // per_page

        return {
            "success": True,
            "data": result["skills"],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch skills: {str(e)}"
        )


@router.post("/my-skills/batch/unlist")
async def api_batch_unlist_skills(
    request_data: BatchOperationRequest,
    request: Request,
    _: bool = Depends(require_auth)
):
    """Unlist multiple skills at once.

    User must own all the skills to unlist them.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        result = batch_unlist_skills(user_id, request_data.skill_ids)

        message = f"已下架 {result['success_count']} 个技能"
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
            detail=f"Failed to batch unlist skills: {str(e)}"
        )


@router.post("/my-skills/batch/delete")
async def api_batch_delete_skills(
    request_data: BatchOperationRequest,
    request: Request,
    _: bool = Depends(require_admin)
):
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


@router.post("/my-skills/{skill_id}/unlist")
async def api_unlist_skill(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_auth)
):
    """Unlist a skill (set is_active = 0).

    User must own the skill to unlist it.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Get skill record
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        # Verify ownership
        if skill["uploader_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't own this skill"
            )

        # Update active status
        update_skill_active_status(skill_id, False)

        return {
            "success": True,
            "message": f"Skill {skill['skill_name']}@{skill['version']} has been unlisted",
            "skill_id": skill_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unlist skill: {str(e)}"
        )


@router.post("/my-skills/{skill_id}/publish")
async def api_publish_skill(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_auth)
):
    """Publish a skill (set is_active = 1).

    User must own the skill to publish it.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Get skill record
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        # Verify ownership
        if skill["uploader_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't own this skill"
            )

        # Update active status
        update_skill_active_status(skill_id, True)

        return {
            "success": True,
            "message": f"Skill {skill['skill_name']}@{skill['version']} has been published",
            "skill_id": skill_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish skill: {str(e)}"
        )


@router.post("/my-skills/{skill_id}/set-default")
async def api_set_default_skill(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_auth)
):
    """Set a skill version as the default for its skill name.

    User must own the skill. All other versions of the same skill
    will have is_default_version set to 0.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Get skill record
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        # Verify ownership
        if skill["uploader_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't own this skill"
            )

        # Set as default version
        success = set_default_skill_version(
            user_id=user_id,
            skill_name=skill["skill_name"],
            skill_id=skill_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to set default version"
            )

        return {
            "success": True,
            "message": f"Skill {skill['skill_name']}@{skill['version']} is now the default version",
            "skill_id": skill_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set default version: {str(e)}"
        )


@router.get("/my-skills/versions/{skill_name}")
async def api_get_skill_versions(
    skill_name: str,
    request: Request,
    _: bool = Depends(require_auth)
):
    """Get all versions of a skill owned by the current user.

    Returns versions sorted newest first. User must own at least
    one version of the skill.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Get skill versions (function already verifies ownership by filtering on uploader_id)
        versions = get_skill_versions(user_id, skill_name)

        # Check if user owns any version of this skill
        if not versions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No versions found for skill '{skill_name}' or you don't own this skill"
            )

        return {
            "success": True,
            "data": versions,
            "skill_name": skill_name,
            "count": len(versions)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch skill versions: {str(e)}"
        )


@router.delete("/my-skills/{skill_id}")
async def api_delete_skill(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_admin)
):
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

        # Get skill record for response message
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        # Admin can delete any skill, no ownership check needed
        # Use batch_delete_skills with single item for consistency
        result = batch_delete_skills(user_id, [skill_id])

        if result["success_count"] == 0:
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


# ============================================================================
# UI Routes (User Pages)
# ============================================================================

@router.get("/my-skills-page", response_class=HTMLResponse)
async def my_skills_page(request: StarletteRequest):
    """Render my_skills.html page (requires auth)."""
    user = get_current_user(request)

    return templates.TemplateResponse("my_skills.html", {
        "request": request,
        "user": user
    })


# ============================================================================
# Initialization
# ============================================================================

def init_users_router(templates_instance: Jinja2Templates) -> APIRouter:
    """Initialize and configure the users router.

    Args:
        templates_instance: Jinja2Templates instance for rendering templates

    Returns:
        Configured APIRouter instance
    """
    global templates
    templates = templates_instance
    return router
