"""
Skills API Routes - V1 (Tortoise ORM 版本）

技能管理相关路由：
- GET /api/v1/skills - 获取所有技能列表（分页）
- GET /api/v1/skills/{skill_id} - 获取技能详情
- POST /api/v1/skills/upload - 上传新技能
- PUT /api/v1/skills/{skill_id} - 更新技能信息
- DELETE /api/v1/skills/{skill_id} - 删除技能
- GET /api/v1/skills/name/{skill_name} - 按名称搜索技能
"""

import logging
import os
import secrets
import shutil
import zipfile
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field

from core.dependencies import get_current_user, get_current_reviewer, get_pagination
from core.models import User, Skill, SkillStatus, SkillSourceType, Download
from core.repositories import SkillRepository, DownloadRepository

logger = logging.getLogger("skillhub")

# 目录配置
PLUGINS_DIR = Path(os.getenv("PLUGINS_DIR", "./plugins"))
PENDING_DIR = Path("./data/pending")
PLUGINS_DIR.mkdir(exist_ok=True)
PENDING_DIR.mkdir(parents=True, exist_ok=True)

# Router
router = APIRouter(prefix="/api/v1", tags=["skills"])


# ============================================================================
# 请求模型
# ============================================================================

class SkillUploadRequest(BaseModel):
    """技能上传请求模型"""
    skill_name: str = Field(..., description="技能名称")
    version: str = Field(..., description="版本号")
    source_type: str = Field("opensource", description="来源类型: opensource, icsl, huawei")


class SkillUpdateRequest(BaseModel):
    """技能更新请求模型"""
    version: Optional[str] = Field(None, description="版本号")
    description: Optional[str] = Field(None, description="描述")


# ============================================================================
# API 路由
# ============================================================================


@router.get("/skills")
async def api_list_skills(
    search: Optional[str] = Query(None, description="搜索关键词"),
    source_type: Optional[str] = Query(None, description="来源类型筛选"),
    pagination: Depends(get_pagination),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """获取所有技能列表（支持搜索和筛选）"""
    try:
        # 构建查询
        query = Skill.filter(is_active=True)

        if search:
            query = query.filter(skill_name__icontains=search)
        if source_type:
            query = query.filter(source_type=source_type)

        skills = await query.offset(pagination.offset).limit(pagination.limit).prefetch_related(["uploader"]).all()

        # 获取每个技能的下载量
        for skill in skills:
            download_count = await Download.filter(skill_name=skill.skill_name).count()
            skill.download_count = download_count

        return JSONResponse({
            "skills": [skill.to_dict() for skill in skills],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.page_size,
                "total": len(skills)
            }
        })

    except Exception as e:
        logger.error(f"Error listing skills: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取技能列表失败"
        )


@router.get("/skills/{skill_id}")
async def api_get_skill_detail(
    skill_id: int,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """获取技能详情"""
    try:
        skill = await SkillRepository.get_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="技能不存在"
            )

        await skill.fetch_related(["uploader"])

        # 获取下载量
        download_count = await Download.filter(skill_name=skill.skill_name).count()

        # 构建响应
        response = skill.to_dict()
        response["download_count"] = download_count

        return JSONResponse(response)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching skill detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取技能详情失败"
        )


@router.post("/skills/upload")
async def api_upload_skill(
    request,
    file: UploadFile = File(..., description="技能文件（.zip）"),
    skill_name: str = Form(..., description="技能名称"),
    version: str = Form(..., description="版本号"),
    source_type: str = Form("opensource", description="来源类型"),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """上传新技能文件"""
    try:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请选择文件"
            )

        # 验证文件类型
        if not file.filename.lower().endswith('.zip'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只支持 .zip 格式的技能文件"
            )

        # 生成唯一文件名
        unique_filename = f"{skill_name}_{version}_{secrets.token_hex(8)}.zip"
        pending_path = PENDING_DIR / unique_filename

        # 保存文件到 pending 目录
        with open(pending_path, 'wb') as f:
            content = await file.read()
            f.write(content)

        # 创建技能记录
        skill = await SkillRepository.create(
            skill_name=skill_name,
            version=version,
            filename=unique_filename,
            uploader_id=current_user.id,
            source_type=source_type
        )

        logger.info(f"User {current_user.employee_id} uploaded skill: {skill_name} v{version}")

        return JSONResponse({
            "message": "技能上传成功，等待审核",
            "skill_id": skill.id,
            "filename": unique_filename
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading skill: {e}")
        # 清理已上传的文件
        if pending_path.exists():
            pending_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="上传失败"
        )


@router.put("/skills/{skill_id}")
async def api_update_skill(
    skill_id: int,
    request: SkillUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """更新技能信息"""
    try:
        skill = await SkillRepository.get_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="技能不存在"
            )

        if skill.uploader_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限修改此技能"
            )

        # 更新字段
        if request.version:
            skill.version = request.version
        if request.description:
            skill.review_comment = request.description

        await skill.save()

        logger.info(f"User {current_user.employee_id} updated skill {skill_id}")

        return JSONResponse({
            "message": "技能已更新",
            "skill_id": skill_id
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating skill: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新失败"
        )


@router.delete("/skills/{skill_id}")
async def api_delete_skill(
    skill_id: int,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """删除技能"""
    try:
        skill = await SkillRepository.get_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="技能不存在"
            )

        if skill.uploader_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限删除此技能"
            )

        # 删除技能文件
        plugin_path = PLUGINS_DIR / skill.filename
        if plugin_path.exists():
            # 如果是目录，删除整个目录
            if plugin_path.is_dir():
                shutil.rmtree(plugin_path)
            else:
                plugin_path.unlink()

        # 删除数据库记录
        await Skill.filter(id=skill_id).delete()

        logger.info(f"User {current_user.employee_id} deleted skill {skill_id}")

        return JSONResponse({
            "message": "技能已删除",
            "skill_id": skill_id
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting skill: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除失败"
        )


@router.get("/skills/name/{skill_name}")
async def api_search_skills_by_name(
    skill_name: str,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """按名称搜索技能"""
    try:
        skills = await Skill.filter(
            skill_name__icontains=skill_name,
            is_active=True,
            status=SkillStatus.APPROVED
        ).prefetch_related(["uploader"]).limit(20).all()

        if not skills:
            return JSONResponse({
                "skills": [],
                "message": "未找到匹配的技能"
            })

        # 获取下载量
        for skill in skills:
            download_count = await Download.filter(skill_name=skill.skill_name).count()
            skill.download_count = download_count

        return JSONResponse({
            "skills": [skill.to_dict() for skill in skills],
            "total": len(skills)
        })

    except Exception as e:
        logger.error(f"Error searching skills: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="搜索失败"
        )


@router.get("/skills/download/{skill_id}")
async def api_download_skill(
    skill_id: int,
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """下载技能文件"""
    try:
        skill = await SkillRepository.get_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="技能不存在"
            )

        if not skill.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="技能未上线或已下架"
            )

        # 查找文件
        plugin_path = PLUGINS_DIR / skill.skill_name
        if not plugin_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="技能文件不存在"
            )

        # 记录下载
        await DownloadRepository.create(
            skill_name=skill.skill_name,
            version=skill.version,
            filename=skill.filename,
            user_id=current_user.id if current_user else None
        )

        logger.info(f"User {current_user.employee_id if current_user else 'anonymous'} downloaded {skill.skill_name}")

        return FileResponse(
            path=str(plugin_path),
            filename=skill.filename,
            media_type="application/zip"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading skill: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="下载失败"
        )
