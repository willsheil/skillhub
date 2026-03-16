"""
External API routes - Public marketplace API.

These endpoints are accessible via API key authentication
and provide access to the skill marketplace.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import json
from pathlib import Path

from db.repositories import SkillRepository, DownloadRepository
from api.v1.dependencies import verify_api_key_header
from core.constants import SourceType

router = APIRouter()


class SkillListResponse(BaseModel):
    """Skill list response."""
    code: int = 200
    message: str = "success"
    data: dict
    pagination: dict


class SkillDetailResponse(BaseModel):
    """Skill detail response."""
    code: int = 200
    message: str = "success"
    data: dict


@router.get("/skills", response_model=SkillListResponse)
async def list_skills(
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    keyword: Optional[str] = Query(None, description="Search keyword"),
    tags: Optional[str] = Query(None, description="Filter by tags"),
    api_key_info: dict = Depends(verify_api_key_header)
):
    """Get list of available skills.

    Requires API key authentication.
    """
    tag_list = tags.split(",") if tags else None

    skills, total = SkillRepository.search(
        source_type=source_type,
        keyword=keyword,
        tags=tag_list,
        page=page,
        page_size=page_size,
    )

    items = []
    for skill in skills:
        metadata = json.loads(skill.metadata) if skill.metadata else {}
        versions = SkillRepository.get_versions(skill.skill_name)

        items.append({
            "name": skill.skill_name,
            "description": skill.description or "",
            "metadata": metadata,
            "source_type": skill.source_type,
            "default_version": skill.version,
            "versions": [v["version"] for v in versions],
        })

    return SkillListResponse(
        code=200,
        message="success",
        data={"items": items},
        pagination={
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size
        }
    )


@router.get("/skills/{skill_name}", response_model=SkillDetailResponse)
async def get_skill_detail(
    skill_name: str,
    api_key_info: dict = Depends(verify_api_key_header)
):
    """Get skill details.

    Requires API key authentication.
    """
    skill = SkillRepository.get_by_name(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

    metadata = json.loads(skill.metadata) if skill.metadata else {}
    versions = SkillRepository.get_versions(skill.skill_name)

    return SkillDetailResponse(
        code=200,
        message="success",
        data={
            "name": skill.skill_name,
            "description": skill.description or "",
            "metadata": metadata,
            "source_type": skill.source_type,
            "default_version": skill.version,
            "versions": [
                {
                    "version": v["version"],
                    "is_default": v["is_default_version"],
                    "status": v["status"],
                }
                for v in versions
            ],
        }
    )


@router.get("/skills/{skill_name}/download")
async def download_skill(
    skill_name: str,
    version: Optional[str] = Query(None, description="Skill version"),
    api_key_info: dict = Depends(verify_api_key_header)
):
    """Download skill ZIP file.

    Requires API key authentication.
    """
    skill = SkillRepository.get_by_name(skill_name, version)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    # Record download
    user_id = api_key_info.get("user_id")
    if user_id:
        DownloadRepository.record(skill_name, skill.version, user_id)

    # Build file path
    from core.config import get_settings
    settings = get_settings()

    file_path = settings.PLUGINS_DIR / skill.filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Skill file not found")

    return FileResponse(
        path=str(file_path),
        filename=skill.filename,
        media_type="application/zip"
    )
