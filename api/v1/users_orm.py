"""
Users API Routes - V1 (Tortoise ORM 版本）

用户管理相关路由：
- GET /api/v1/my-skills - 获取当前用户的技能（分页）
- POST /api/v1/my-skills/batch/unlist - 批量下架技能
- POST /api/v1/my-skills/batch/delete - 批量删除技能（仅管理员）
- POST /api/v1/my-skills/{skill_id}/unlist - 下架单个技能
- POST /api/v1/my-skills/{skill_id}/publish - 发布技能
- POST /api/v1/my-skills/{skill_id}/set-default - 设置默认版本
- GET /api/v1/my-skills/versions/{skill_name} - 获取技能所有版本
- DELETE /api/v1/my-skills/{skill_id} - 删除技能（仅管理员）
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.dependencies import get_current_user, get_current_admin, get_pagination
from core.models import User, SkillStatus, Skill
from core.repositories import SkillRepository

logger = logging.getLogger("skillhub")

# Router
router = APIRouter(prefix="/api/v1", tags=["users"])


# ============================================================================
# 请求模型
# ============================================================================

class BatchOperationRequest(BaseModel):
    """批量操作请求模型"""
    skill_ids: List[int] = Field(..., description="技能ID列表")


class UnlistSkillRequest(BaseModel):
    """下架技能请求模型"""
    reason: Optional[str] = Field(None, description="下架原因")


class PublishSkillRequest(BaseModel):
    """发布技能请求模型"""
    changelog: Optional[str] = Field(None, description="更新日志")


# ============================================================================
# API 路由
# ============================================================================


@router.get("/my-skills")
async def api_my_skills(
    status_filter: str = Query("all", description="状态筛选: all, active, unlisted, pending, rejected"),
    pagination = Depends(get_pagination),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """获取当前用户的技能列表（支持分页和筛选）

    Query 参数:
    - status: 状态筛选 ('all', 'active', 'unlisted', 'pending', 'rejected')
    - page: 页码（从1开始，默认1）
    - per_page: 每页数量（默认20，最大100）

    Returns: 分页的技能列表
    """
    try:
        # 构建查询条件
        if status_filter == "all":
            skills = await Skill.filter(
                uploader_id=current_user.id
            ).offset(pagination.offset).limit(pagination.limit).all()
        elif status_filter == "active":
            skills = await Skill.filter(
                uploader_id=current_user.id,
                is_active=True,
                status=SkillStatus.APPROVED
            ).offset(pagination.offset).limit(pagination.limit).all()
        elif status_filter == "unlisted":
            skills = await Skill.filter(
                uploader_id=current_user.id,
                status=SkillStatus.UNLISTED
            ).offset(pagination.offset).limit(pagination.limit).all()
        elif status_filter == "pending":
            skills = await Skill.filter(
                uploader_id=current_user.id,
                status=SkillStatus.PENDING
            ).offset(pagination.offset).limit(pagination.limit).all()
        elif status_filter == "rejected":
            skills = await Skill.filter(
                uploader_id=current_user.id,
                status=SkillStatus.REJECTED
            ).offset(pagination.offset).limit(pagination.limit).all()
        else:
            skills = await Skill.filter(
                uploader_id=current_user.id
            ).offset(pagination.offset).limit(pagination.limit).all()

        # 预加载关联数据
        for skill in skills:
            await skill.fetch_related("uploader")

        return JSONResponse({
            "skills": [skill.to_dict() for skill in skills],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.page_size,
                "total": len(skills)
            }
        })

    except Exception as e:
        logger.error(f"Error fetching user skills: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取技能列表失败"
        )


@router.post("/my-skills/batch/unlist")
async def api_batch_unlist(
    request: BatchOperationRequest,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """批量下架技能

    将多个技能状态设置为 unlisted
    """
    try:
        await SkillRepository.batch_unlist(request.skill_ids)

        logger.info(f"User {current_user.employee_id} unlisted skills: {request.skill_ids}")

        return JSONResponse({
            "message": f"成功下架 {len(request.skill_ids)} 个技能",
            "unlisted_count": len(request.skill_ids)
        })

    except Exception as e:
        logger.error(f"Error batch unlisting skills: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="批量下架失败"
        )


@router.post("/my-skills/batch/delete")
async def api_batch_delete(
    request: BatchOperationRequest,
    current_admin: User = Depends(get_current_admin),
) -> JSONResponse:
    """批量删除技能（仅管理员）

    永久删除多个技能记录
    """
    try:
        await SkillRepository.batch_delete(request.skill_ids)

        logger.info(f"Admin {current_admin.employee_id} deleted skills: {request.skill_ids}")

        return JSONResponse({
            "message": f"成功删除 {len(request.skill_ids)} 个技能",
            "deleted_count": len(request.skill_ids)
        })

    except Exception as e:
        logger.error(f"Error batch deleting skills: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="批量删除失败"
        )


@router.post("/my-skills/{skill_id}/unlist")
async def api_unlist_skill(
    skill_id: int,
    request: UnlistSkillRequest,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """下架单个技能

    将指定技能状态设置为 unlisted
    """
    try:
        # 验证技能所有权
        skill = await SkillRepository.get_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="技能不存在"
            )

        if skill.uploader_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此技能"
            )

        await SkillRepository.update_status(
            skill_id,
            SkillStatus.UNLISTED
        )

        logger.info(f"User {current_user.employee_id} unlisted skill {skill_id}")

        return JSONResponse({
            "message": "技能已下架",
            "skill_id": skill_id
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unlisting skill {skill_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="下架失败"
        )


@router.post("/my-skills/{skill_id}/publish")
async def api_publish_skill(
    skill_id: int,
    request: PublishSkillRequest,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """发布技能

    将 unlisted 状态的技能重新发布为 active
    """
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
                detail="无权限操作此技能"
            )

        if skill.status != SkillStatus.UNLISTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只有下架状态的技能可以重新发布"
            )

        await SkillRepository.update_status(
            skill_id,
            SkillStatus.APPROVED
        )

        logger.info(f"User {current_user.employee_id} published skill {skill_id}")

        return JSONResponse({
            "message": "技能已发布",
            "skill_id": skill_id
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing skill {skill_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="发布失败"
        )


@router.post("/my-skills/{skill_id}/set-default")
async def api_set_default_version(
    skill_id: int,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """设置技能为默认版本

    将指定版本的技能设置为该名称的默认版本
    """
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
                detail="无权限操作此技能"
            )

        await SkillRepository.set_default_version(skill_id)

        logger.info(f"User {current_user.employee_id} set skill {skill_id} as default")

        return JSONResponse({
            "message": "已设置为默认版本",
            "skill_id": skill_id,
            "skill_name": skill.skill_name
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting default version {skill_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="设置失败"
        )


@router.get("/my-skills/versions/{skill_name}")
async def api_skill_versions(
    skill_name: str,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """获取技能的所有版本

    返回指定技能名称的所有版本
    """
    try:
        skills = await SkillRepository.get_versions(skill_name)

        # 检查所有权
        user_skill_ids = []
        for skill in skills:
            if skill.uploader_id == current_user.id:
                user_skill_ids.append(skill.id)

        if not user_skill_ids:
            return JSONResponse({
                "skill_name": skill_name,
                "versions": [],
                "message": "您没有上传此技能"
            })

        # 预加载关联数据
        for skill in skills:
            await skill.fetch_related("uploader")

        return JSONResponse({
            "skill_name": skill_name,
            "versions": [
                {
                    "id": skill.id,
                    "version": skill.version,
                    "filename": skill.filename,
                    "status": skill.status,
                    "is_active": skill.is_active,
                    "default": skill.default_version,
                    "uploaded_at": skill.uploaded_at.isoformat() if skill.uploaded_at else None,
                    "owned": skill.uploader_id == current_user.id
                }
                for skill in skills
            ]
        })

    except Exception as e:
        logger.error(f"Error fetching skill versions for {skill_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取版本信息失败"
        )


@router.delete("/my-skills/{skill_id}")
async def api_delete_skill(
    skill_id: int,
    current_admin: User = Depends(get_current_admin),
) -> JSONResponse:
    """删除技能（仅管理员）

    永久删除指定技能记录
    """
    try:
        skill = await SkillRepository.get_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="技能不存在"
            )

        skill_name = skill.skill_name
        await Skill.delete.filter(id=skill_id)

        logger.info(f"Admin deleted skill {skill_id}: {skill_name}")

        return JSONResponse({
            "message": "技能已删除",
            "skill_id": skill_id
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting skill {skill_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除失败"
        )
