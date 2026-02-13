"""
Skills API routes for FastAPI application.

This module contains all API endpoints for skill management.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Query, HTTPException, status as http_status, UploadFile, File, Form
from fastapi.responses import FileResponse
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.templating import Jinja2Templates

# Import from dependencies and schemas
from app.modules.skills.dependencies import require_auth, require_admin, PLUGINS_DIR
from app.modules.skills.schemas import (
    SkillListItem,
    SkillRecord,
    PendingSkillItem,
    BatchOperationRequest,
    ReviewSkillRequest,
    PaginatedSkillsResponse,
)

# Import from services
from app.modules.skills.services import (
    scan_plugins,
    validate_skill_zip,
    save_skill_zip,
    approve_skill_file,
    reject_skill_file,
    extract_metadata,
)

# Import from app.core.database
from app.core.database import (
    get_pending_skills,
    get_skill_by_id,
    update_skill_status,
    get_user_uploads,
    get_skill_active_status,
    get_my_skills,
    set_default_skill_version,
    get_skill_versions,
    get_default_skill_version,
    delete_skill_version,
    batch_unlist_skills,
    batch_delete_skills,
    get_user_by_id,
    get_download_stats,
    create_notification,
    get_connection,
)

logger = logging.getLogger("skillhub.skills.routes")

# Create router
router = APIRouter(prefix="/api/skills", tags=["skills"])

# Templates (will be injected from main app)
templates: Optional[Jinja2Templates] = None


def set_templates(tmpl: Jinja2Templates) -> None:
    """Set templates instance for HTML rendering."""
    global templates
    templates = tmpl


@router.get("")
async def api_skills(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    per_page: int = Query(1000, ge=1, le=1000, description="Items per page (max 1000)")
) -> Dict[str, Any]:
    """API endpoint for skill list (for AJAX requests) with pagination support."""
    all_plugins = scan_plugins()

    # Calculate pagination
    total = len(all_plugins)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    # Return paginated results
    paginated_plugins = all_plugins[start_idx:end_idx]

    return {
        "data": paginated_plugins,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    }


@router.get("/pending")
async def api_pending_skills(_: bool = Depends(require_admin)) -> Dict[str, Any]:
    """Get all pending skills awaiting approval (admin only)."""
    try:
        pending = get_pending_skills()
        return {
            "success": True,
            "data": pending,
            "count": len(pending)
        }
    except Exception as e:
        logger.error(f"Failed to fetch pending skills: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending skills: {str(e)}"
        )


@router.post("/review/{skill_id}")
async def api_review_skill(
    skill_id: int,
    request: Request,
    review_data: ReviewSkillRequest,
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
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Get skill record
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        if skill["status"] != "pending":
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Skill {skill_id} is not in pending status"
            )

        # Perform action
        if review_data.action == "approve":
            success = approve_skill_file(skill_id)
            if not success:
                raise HTTPException(
                    status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to approve skill {skill_id}"
                )

            # Update with reviewer info
            update_skill_status(skill_id, "approved", reviewer_id=reviewer_id, comment=review_data.comment)

            # Create Gitea push task if configured
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
            success = reject_skill_file(skill_id, review_data.comment)
            if not success:
                raise HTTPException(
                    status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to reject skill {skill_id}"
                )

            # Update with reviewer info
            update_skill_status(skill_id, "rejected", reviewer_id=reviewer_id, comment=review_data.comment)

            return {
                "success": True,
                "message": f"Skill {skill['skill_name']}@{skill['version']} rejected",
                "skill_id": skill_id
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Review failed: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Review failed: {str(e)}"
        )


@router.get("/my-skills")
async def api_my_skills(
    request: Request,
    status_filter: str = Query("all", description="Filter by status: all, active, unlisted, pending, rejected"),
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    _: bool = Depends(require_auth)
) -> Dict[str, Any]:
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
                status_code=http_status.HTTP_401_UNAUTHORIZED,
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

        return {
            "success": True,
            "data": result["skills"],
            "total": result["total"],
            "page": page,
            "per_page": per_page,
            "pages": (result["total"] + per_page - 1) // per_page if result["total"] > 0 else 1
        }

    except Exception as e:
        logger.error(f"Failed to fetch my skills: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch my skills: {str(e)}"
        )


@router.post("/my-skills/batch/unlist")
async def api_batch_unlist_skills(
    request_data: BatchOperationRequest,
    request: Request,
    _: bool = Depends(require_auth)
) -> Dict[str, Any]:
    """Unlist multiple skills at once.

    User must own all skills to unlist them.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
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

    except Exception as e:
        logger.error(f"Failed to batch unlist skills: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to batch unlist skills: {str(e)}"
        )


@router.post("/my-skills/batch/delete")
async def api_batch_delete_skills(
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
                status_code=http_status.HTTP_401_UNAUTHORIZED,
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

    except Exception as e:
        logger.error(f"Failed to batch delete skills: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to batch delete skills: {str(e)}"
        )


@router.post("/my-skills/{skill_id}/unlist")
async def api_unlist_skill(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_auth)
) -> Dict[str, Any]:
    """Unlist a skill (set is_active = 0).

    User must own skill to unlist it.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Get skill record
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        # Verify ownership
        if skill["uploader_id"] != user_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="You don't own this skill"
            )

        # Update active status
        from app.core.database import update_skill_active_status
        update_skill_active_status(skill_id, False)

        return {
            "success": True,
            "message": f"Skill {skill['skill_name']}@{skill['version']} has been unlisted",
            "skill_id": skill_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unlist skill: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unlist skill: {str(e)}"
        )


@router.post("/my-skills/{skill_id}/publish")
async def api_publish_skill(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_auth)
) -> Dict[str, Any]:
    """Publish a skill (set is_active = 1).

    User must own skill to publish it.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Get skill record
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        # Verify ownership
        if skill["uploader_id"] != user_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="You don't own this skill"
            )

        # Update active status
        from app.core.database import update_skill_active_status
        update_skill_active_status(skill_id, True)

        return {
            "success": True,
            "message": f"Skill {skill['skill_name']}@{skill['version']} has been published",
            "skill_id": skill_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to publish skill: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish skill: {str(e)}"
        )


@router.post("/my-skills/{skill_id}/set-default")
async def api_set_default_skill(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_auth)
) -> Dict[str, Any]:
    """Set a skill version as the default for its skill name.

    User must own skill. All other versions of the same skill
    will have is_default_version set to 0.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Get skill record
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        # Verify ownership
        if skill["uploader_id"] != user_id:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
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
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to set default version"
            )

        return {
            "success": True,
            "message": f"Default version set to {skill['version']}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set default version: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set default version: {str(e)}"
        )


@router.get("/my-skills/versions/{skill_name}")
async def api_get_skill_versions(
    skill_name: str,
    request: Request,
    _: bool = Depends(require_auth)
) -> Dict[str, Any]:
    """Get all versions of a skill owned by current user.

    Returns versions sorted newest first. User must own at least
    one version of skill.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Get skill versions (function already verifies ownership by filtering on uploader_id)
        versions = get_skill_versions(user_id, skill_name)

        # Check if user owns any version of this skill
        if not versions:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
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
        logger.error(f"Failed to fetch skill versions: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch skill versions: {str(e)}"
        )


@router.delete("/my-skills/{skill_id}")
async def api_delete_skill(
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
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Get skill record for response message
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        # Admin can delete any skill, no ownership check needed
        # Delete skill (pass is_admin=True to skip ownership check)
        success = delete_skill_version(user_id, skill_id, is_admin=True)

        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
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
        logger.error(f"Failed to delete skill: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete skill: {str(e)}"
        )


@router.get("/{skill_name}", include_in_schema=False)
async def skill_detail_page(request: Request, skill_name: str):
    """Display skill detail page with Skill.md content."""
    # Check if user is authenticated
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    # First, try to get default version from database
    default_version = get_default_skill_version(skill_name)

    skill_zip = None

    if default_version:
        # Use default version's filename
        skill_zip = PLUGINS_DIR / default_version["filename"]
        if not skill_zip.exists():
            # Default version file not found, fall back to searching
            skill_zip = None

    if not skill_zip:
        # No default version or file not found, try exact match
        skill_zip = PLUGINS_DIR / f"{skill_name}.zip"
        if not skill_zip.exists():
            # Try to find a ZIP that starts with skill_name-
            matching_zips = list(PLUGINS_DIR.glob(f"{skill_name}-*.zip"))
            if matching_zips:
                skill_zip = matching_zips[0]  # Use first match
            else:
                raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")

    # Extract metadata from skill
    metadata = extract_metadata(skill_zip.name)

    # Get real skill name from metadata
    real_skill_name = metadata.get("name", skill_name) if metadata else skill_name

    # Get download count from database
    stats = get_download_stats()
    download_count = 0
    for ranking in stats["rankings"]:
        if ranking["skill_name"] == real_skill_name:
            download_count = ranking["downloads"]
            break

    # Get author from metadata
    author = "Unknown"
    if metadata and "metadata" in metadata:
        author_meta = metadata["metadata"].get("author", "Unknown")
        if isinstance(author_meta, dict):
            author = author_meta.get("name", "Unknown")
        else:
            author = str(author_meta) if author_meta else "Unknown"

    # Get version
    version = metadata.get("version", "1.0.0") if metadata else "1.0.0"

    # Get updated_at from file modification time
    updated_at = datetime.fromtimestamp(skill_zip.stat().st_mtime).strftime("%Y-%m-%d")

    # Get current user
    from app.core.database import get_user_by_id
    user = get_user_by_id(user_id) if user_id else None

    return templates.TemplateResponse("skill_detail.html", {
        "request": request,
        "skill_name": real_skill_name,
        "author": author,
        "download_count": download_count,
        "version": version,
        "updated_at": updated_at,
        "download_url": f"/plugins/{skill_zip.name}",
        "user": user
    })


@router.get("/{skill_name}/content", include_in_schema=False)
async def get_skill_content_api(skill_name: str) -> Dict[str, Any]:
    """Get Skill.md content for a skill.

    Returns complete SKILL.md file content (including YAML frontmatter).
    """
    logger.debug(f"API called with skill_name: '{skill_name}'", extra={"skill_name": skill_name})

    # Find skill ZIP file
    # First try exact match, then try with version pattern
    skill_zip = PLUGINS_DIR / f"{skill_name}.zip"
    logger.debug(f"Trying exact match: {skill_zip}, exists: {skill_zip.exists()}", extra={"skill_name": skill_name, "zip_path": str(skill_zip)})

    if not skill_zip.exists():
        # Try to find a ZIP that starts with skill_name-
        matching_zips = list(PLUGINS_DIR.glob(f"{skill_name}-*.zip"))
        logger.debug(f"Pattern match found: {len(matching_zips)} files", extra={"skill_name": skill_name, "match_count": len(matching_zips)})
        if matching_zips:
            skill_zip = matching_zips[0]  # Use first match
            logger.debug(f"Using: {skill_zip}", extra={"skill_name": skill_name, "zip_path": str(skill_zip)})
        else:
            raise HTTPException(status_code=404, detail=f"Skill ZIP file not found for: {skill_name}")

    try:
        # Extract SKILL.md content
        import zipfile
        with zipfile.ZipFile(skill_zip, 'r') as zf:
            # Find SKILL.md (may be in root or subdirectory)
            skill_md_paths = [name for name in zf.namelist()
                           if name.endswith('SKILL.md') or name == 'SKILL.md']

            if not skill_md_paths:
                raise HTTPException(status_code=404, detail="SKILL.md not found in skill ZIP")

            skill_md_path = skill_md_paths[0]
            content = zf.read(skill_md_path).decode('utf-8')

            return {
                "content": content
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read skill content: {e}", extra={"skill_name": skill_name})
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read skill content: {str(e)}"
        )


@router.put("/admin/skills/{skill_id}/source-type")
async def api_update_skill_source_type(
    skill_id: int,
    request: Request,
    source_type: str = Query(..., description="Source type: opensource, icsl, huawei"),
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Update source_type of a skill (admin only).

    Valid source types: "opensource" | "icsl" | "huawei"
    """
    try:
        # Get current user
        reviewer_id = request.session.get("user_id")
        if not reviewer_id:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Validate source_type
        valid_types = ["opensource", "icsl", "huawei"]
        if source_type not in valid_types:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source_type. Must be one of: {', '.join(valid_types)}"
            )

        # Get skill record
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
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
        logger.error(f"Failed to update source_type: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update source_type: {str(e)}"
        )


@router.get("/admin/skills")
async def api_get_all_skills(
    status_filter: Optional[str] = Query(None, description="Filter by status: pending/approved/rejected"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of skills to return"),
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
        with get_connection() as conn:
            if status_filter:
                rows = conn.execute("""
                    SELECT s.id, s.skill_name, s.version, s.filename, s.status,
                           s.source_type, s.uploaded_at, u.employee_id as uploader_name
                    FROM skills s
                    LEFT JOIN users u ON s.uploader_id = u.id
                    WHERE s.status = %s
                    ORDER BY s.uploaded_at DESC
                    LIMIT %s
                """, (status_filter, limit)).fetchall()
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
        logger.error(f"Failed to fetch skills: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch skills: {str(e)}"
        )
