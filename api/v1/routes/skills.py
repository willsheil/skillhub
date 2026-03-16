"""
Skill management routes - Upload, list, download, manage skills.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List

from db.repositories import SkillRepository, DownloadRepository
from api.v1.dependencies import get_current_user
from core.constants import SkillStatus, SourceType
from core.config import get_settings

router = APIRouter()

# Import scan_plugins from main.py (will be refactored later)
from main import scan_plugins

class SkillUploadResponse(BaseModel):
    """Skill upload response."""
    skill_id: int
    skill_name: str
    version: str
    status: str

class SkillListQuery(BaseModel):
    """Skill list query parameters."""
    source_type: Optional[str] = None
    keyword: Optional[str] = None
    page: int = 1
    page_size: int = 20

@router.get("/skills")
async def api_skills(page: int = 1, per_page: int = 1000):
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

@router.post("/upload")
async def upload_skill(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a new skill.

    Requires authentication.
    """
    settings = get_settings()

    # Read file content
    content = await file.read()

    # Check file size
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    # Validate ZIP file
    if not file.filename or not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files allowed")

    # TODO: Parse skill metadata and save to pending directory
    # This is a simplified version - full implementation would:
    # 1. Extract ZIP to temp directory
    # 2. Parse SKILL.md for metadata
    # 3. Create skill record in database
    # 4. Move to pending directory

    return {
        "success": True,
        "message": "Skill uploaded successfully",
        "filename": file.filename
    }

@router.get("/list")
async def list_skills(
    source_type: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """List skills with filters.

    Requires authentication.
    """
    skills, total = SkillRepository.search(
        source_type=source_type,
        keyword=keyword,
        page=page,
        page_size=page_size,
        status=SkillStatus.APPROVED.value,
    )

    return {
        "items": [s.to_dict() for s in skills],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size
        }
    }

@router.get("/my-skills")
async def get_my_skills(current_user: dict = Depends(get_current_user)):
    """Get skills uploaded by current user."""
    skills = SkillRepository.get_by_uploader(current_user["id"])

    # Group by skill name
    grouped = {}
    for skill in skills:
        if skill.skill_name not in grouped:
            grouped[skill.skill_name] = {
                "skill_name": skill.skill_name,
                "versions": []
            }
        grouped[skill.skill_name]["versions"].append({
            "id": skill.id,
            "version": skill.version,
            "status": skill.status,
            "is_default": skill.is_default_version,
            "is_active": skill.is_active,
        })

    return {"skills": list(grouped.values())}

@router.post("/{skill_id}/set-default")
async def set_default_version(
    skill_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Set a skill version as default."""
    skill = SkillRepository.get_by_id(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    if skill.uploader_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    SkillRepository.set_default_version(skill_id)

    return {"success": True, "message": "Default version set"}

@router.post("/{skill_id}/unlist")
async def unlist_skill(
    skill_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Unlist a skill (hide from marketplace)."""
    skill = SkillRepository.get_by_id(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    if skill.uploader_id != current_user["id"] and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    SkillRepository.update_active_status(skill_id, False)

    return {"success": True, "message": "Skill unlisted"}

@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a skill version."""
    skill = SkillRepository.get_by_id(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    if skill.uploader_id != current_user["id"] and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    SkillRepository.delete(skill_id)

    return {"success": True, "message": "Skill deleted"}
