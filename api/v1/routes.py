from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import FileResponse
from typing import Optional
import time

from .schemas import (
    SkillListResponse,
    SkillDetailResponse,
    SkillListQuery,
    SkillDownloadQuery,
    ErrorResponse
)
from .services import get_skills_list, get_skill_detail, get_skill_download_path
from .dependencies import verify_api_key_header, check_rate_limit

router = APIRouter(prefix="/api/v1", tags=["external-api"])

@router.get("/skills", response_model=SkillListResponse)
async def list_skills(
    query: SkillListQuery = Depends(),
    api_key_info: dict = Depends(verify_api_key_header)
):
    """获取技能列表

    支持分类过滤、分页、关键词搜索
    """
    # 检查速率限制
    if not check_rate_limit(api_key_info['api_key'], api_key_info['rate_limit']):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )

    start_time = time.time()

    # 查询数据
    result = get_skills_list(
        source_type=query.source_type.value,
        page=query.page,
        page_size=query.page_size,
        keyword=query.keyword,
        tags=query.tags
    )

    # 记录日志（异步，不阻塞响应）
    response_time = int((time.time() - start_time) * 1000)
    # TODO: 异步记录日志

    return SkillListResponse(
        code=200,
        message="success",
        data={"items": result["items"]},
        pagination=result["pagination"]
    )

@router.get("/skills/{skill_name}", response_model=SkillDetailResponse)
async def get_skill(
    skill_name: str,
    api_key_info: dict = Depends(verify_api_key_header)
):
    """获取技能详情"""
    if not check_rate_limit(api_key_info['api_key'], api_key_info['rate_limit']):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )

    detail = get_skill_detail(skill_name)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_name}' not found"
        )

    return SkillDetailResponse(
        code=200,
        message="success",
        data=detail
    )

@router.get("/skills/{skill_name}/download")
async def download_skill(
    skill_name: str,
    query: SkillDownloadQuery = Depends(),
    api_key_info: dict = Depends(verify_api_key_header)
):
    """下载技能 ZIP 压缩包"""
    if not check_rate_limit(api_key_info['api_key'], api_key_info['rate_limit']):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )

    file_path = get_skill_download_path(skill_name, query.version)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill file not found"
        )

    from pathlib import Path
    filename = Path(file_path).name

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/zip"
    )
