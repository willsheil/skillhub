"""
Admin routes - User management, skill review, system administration.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List

from db.repositories import UserRepository, SkillRepository, ApiKeyRepository
from api.v1.dependencies import get_current_user, require_admin

router = APIRouter()


class UserCreateRequest(BaseModel):
    """User creation request."""
    employee_id: str
    api_key: str
    role: str = "user"


class UserUpdateRequest(BaseModel):
    """User update request."""
    role: Optional[str] = None
    status: Optional[str] = None


class SkillReviewRequest(BaseModel):
    """Skill review request."""
    action: str  # "approve" or "reject"
    comment: Optional[str] = None


# ============ Skill Review ============

@router.get("/pending-skills")
async def list_pending_skills(
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(require_admin)
):
    """List pending skills (admin only)."""
    offset = (page - 1) * page_size
    skills = SkillRepository.get_pending(limit=page_size, offset=offset)

    return {
        "items": [s.to_dict() for s in skills],
        "pagination": {"page": page, "page_size": page_size}
    }


@router.post("/skills/{skill_id}/review")
async def review_skill(
    skill_id: int,
    data: SkillReviewRequest,
    current_user: dict = Depends(require_admin)
):
    """Review a skill (admin only)."""
    skill = SkillRepository.get_by_id(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    if data.action == "approve":
        status = "approved"
    elif data.action == "reject":
        status = "rejected"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    SkillRepository.update_status(
        skill_id,
        status,
        reviewer_id=current_user["id"],
        review_comment=data.comment
    )

    # TODO: Create notification for uploader

    return {"success": True, "message": f"Skill {data.action}d"}


@router.put("/skills/{skill_id}/source-type")
async def update_skill_source(
    skill_id: int,
    source_type: str,
    current_user: dict = Depends(require_admin)
):
    """Update skill source type (admin only)."""
    SkillRepository.update_source_type(skill_id, source_type)
    return {"success": True}


# ============ API Key Management ============

@router.get("/api-keys")
async def list_api_keys(
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(require_admin)
):
    """List API keys (admin only)."""
    offset = (page - 1) * page_size
    keys = ApiKeyRepository.list_all(limit=page_size, offset=offset)

    return {
        "items": [k.to_dict() for k in keys],
        "pagination": {"page": page, "page_size": page_size}
    }


@router.post("/api-keys")
async def create_api_key(
    key_name: str,
    user_id: int,
    rate_limit: int = 100,
    current_user: dict = Depends(require_admin)
):
    """Create API key (admin only)."""
    api_key, plain_key = ApiKeyRepository.create(key_name, user_id, rate_limit)
    return {"success": True, "api_key": plain_key}


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: int,
    current_user: dict = Depends(require_admin)
):
    """Delete API key (admin only)."""
    ApiKeyRepository.delete(key_id)
    return {"success": True}


@router.put("/api-keys/{key_id}/toggle")
async def toggle_api_key(
    key_id: int,
    current_user: dict = Depends(require_admin)
):
    """Toggle API key status (admin only)."""
    is_active = ApiKeyRepository.toggle_status(key_id)
    return {"success": True, "is_active": is_active}
