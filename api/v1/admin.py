"""
Admin API Routes - V1

This module contains all admin-related routes migrated from main.py:
- GET /admin - Admin dashboard page
- GET /admin/upload - Upload page
- GET /admin/users - User management page
- GET /api/pending - Get pending skills for review
- POST /api/review/{id} - Approve or reject a skill
"""

import logging
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request as StarletteRequest

# Configuration (will be imported from config module in future)
PLUGINS_DIR = Path("./plugins")
PENDING_DIR = Path("./data/pending")

# Templates (will be injected from main app)
templates = None

# Logger
logger = logging.getLogger("skillhub")

# Router
router = APIRouter(prefix="/api/v1", tags=["admin"])

# Dependencies from database module (will be properly imported in future)
from database import (
    get_skill_by_id,
    get_pending_skills,
    update_skill_status,
    update_skill_active_status,
    create_notification,
)

# Import helper functions from core/dependencies
from core.dependencies import get_current_user, require_admin


# ============================================================================
# Helper Functions (to be moved to core/admin module)
# ============================================================================

def approve_skill_file(skill_id: int) -> bool:
    """Approve a skill by moving it from pending to plugins directory.

    Args:
        skill_id: The ID of the skill to approve

    Returns:
        True if successful, False otherwise
    """
    # Get skill record
    skill = get_skill_by_id(skill_id)
    if not skill:
        return False

    if skill["status"] != "pending":
        return False

    # File paths
    pending_path = PENDING_DIR / skill["filename"]
    plugins_path = PLUGINS_DIR / skill["filename"]

    try:
        # Check if file is in pending directory
        if pending_path.exists():
            # Move file from pending to plugins
            # Remove existing file if it exists (prevents FileExistsError on re-approval)
            if plugins_path.exists():
                logger.info(f"Removing existing file: {plugins_path}")
                plugins_path.unlink()

            shutil.move(str(pending_path), str(plugins_path))
        elif not plugins_path.exists():
            # File not in pending and not in plugins - error
            logger.error(f"Skill file not found: {skill['filename']} (checked both pending and plugins directories)")
            return False
        else:
            # File already in plugins directory (possibly from old batch upload)
            logger.info(f"File already in plugins directory: {plugins_path}")

        # Update database status
        update_skill_status(skill_id, "approved")

        # Set is_active=1 on approval
        update_skill_active_status(skill_id, True)

        # Create notification for uploader
        uploader_id = skill.get("uploader_id")
        if uploader_id:
            content = f"您的技能 {skill['skill_name']} (版本 {skill['version']}) 已通过审核并上线。"
            create_notification(
                user_id=uploader_id,
                type="review_success",
                title="您的技能已通过审核",
                content=content,
                related_skill_id=skill_id
            )

        return True
    except Exception as e:
        logger.error(f"Failed to approve skill {skill_id}: {e}")
        return False


def reject_skill_file(skill_id: int, comment: Optional[str] = None) -> bool:
    """Reject a skill by deleting the pending file.

    Args:
        skill_id: The ID of the skill to reject
        comment: Optional rejection comment

    Returns:
        True if successful, False otherwise
    """
    # Get skill record
    skill = get_skill_by_id(skill_id)
    if not skill:
        return False

    if skill["status"] != "pending":
        return False

    # Delete pending file
    pending_path = PENDING_DIR / skill["filename"]

    try:
        if pending_path.exists():
            pending_path.unlink()

        # Update database status
        update_skill_status(skill_id, "rejected", comment=comment)

        # Create notification for uploader
        uploader_id = skill.get("uploader_id")
        if uploader_id:
            content = f"您的技能 {skill['skill_name']} (版本 {skill['version']}) 未通过审核。"
            if comment:
                content += f" 原因: {comment}"
            create_notification(
                user_id=uploader_id,
                type="review_rejected",
                title="您的技能未通过审核",
                content=content,
                related_skill_id=skill_id
            )

        return True
    except Exception as e:
        logger.error(f"Failed to reject skill {skill_id}: {e}")
        return False


# ============================================================================
# UI Routes (Admin Pages)
# ============================================================================

@router.get("/admin/upload", response_class=HTMLResponse)
async def upload_page(request: StarletteRequest, _: bool = Depends(require_admin)):
    """Display admin upload page (requires auth)."""
    user = get_current_user(request)

    return templates.TemplateResponse("admin_upload.html", {
        "request": request,
        "user": user,
        "success": None,
        "error": None
    })


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: StarletteRequest):
    """Display admin dashboard (requires admin)."""
    # Get current user
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Check admin role
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user
    })


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: StarletteRequest):
    """Display user management page (requires admin)."""
    # Get current user
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Check admin role
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "user": user
    })


# ============================================================================
# API Routes (Admin Actions)
# ============================================================================

@router.get("/pending")
async def api_pending_skills(
    _: bool = Depends(require_admin)
):
    """Get all pending skills awaiting approval (admin only)."""
    try:
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
async def api_review_skill(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_admin)
):
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
            success = approve_skill_file(skill_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to approve skill {skill_id}"
                )

            # Update with reviewer info
            update_skill_status(skill_id, "approved", reviewer_id=reviewer_id, comment=comment)

            # NEW: Create Gitea push task
            task_id = None
            try:
                from gitea_integration import create_push_task
                task_id = create_push_task(skill_id)
                logger.info(f"Created Gitea push task {task_id} for skill {skill_id}")
            except Exception as e:
                # Log error but don't block approval
                logger.error(f"Failed to create Gitea push task: {e}")

            return {
                "success": True,
                "message": f"Skill {skill['skill_name']}@{skill['version']} approved",
                "skill_id": skill_id,
                "push_task_id": task_id
            }

        else:  # reject
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


# ============================================================================
# Initialization
# ============================================================================

def init_admin_router(templates_instance: Jinja2Templates) -> APIRouter:
    """Initialize and configure the admin router.

    Args:
        templates_instance: Jinja2Templates instance for rendering templates

    Returns:
        Configured APIRouter instance
    """
    global templates
    templates = templates_instance
    return router
