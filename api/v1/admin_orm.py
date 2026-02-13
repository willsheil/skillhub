"""
Admin API Routes - V1 (Tortoise ORM 版本）

管理员相关路由：
- GET /api/v1/admin - 管理员仪表板页面
- GET /api/v1/pending - 获取待审核技能列表
- POST /api/v1/review/{skill_id} - 审核技能（通过/拒绝）
- POST /api/v1/admin/users/{user_id}/role - 更新用户角色
- POST /api/v1/admin/users/{user_id}/disable - 禁用用户
- POST /api/v1/admin/users/{user_id}/enable - 启用用户
- DELETE /api/v1/admin/users/{user_id} - 删除用户
- POST /api/v1/admin/users/reset-api-key - 重置用户API密钥
"""

import logging
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, Field

from core.dependencies import get_current_user, get_current_admin, get_pagination
from core.models import User, Skill, SkillStatus, Notification, NotificationType
from core.repositories import SkillRepository, UserRepository, NotificationRepository

logger = logging.getLogger("skillhub")

# 目录配置
PLUGINS_DIR = Path("./plugins")
PENDING_DIR = Path("./data/pending")

# Router
router = APIRouter(prefix="/api/v1", tags=["admin"])


# ============================================================================
# 请求模型
# ============================================================================

class ReviewRequest(BaseModel):
    """审核请求模型"""
    action: str = Field(..., description="操作: approve 或 reject")
    comment: Optional[str] = Field(None, description="审核意见")


class UpdateRoleRequest(BaseModel):
    """更新角色请求模型"""
    role: str = Field(..., description="新角色: admin, user, reviewer")


class ResetAPIKeyRequest(BaseModel):
    """重置API密钥请求模型"""
    user_id: int = Field(..., description="用户ID")


# ============================================================================
# 管理员页面路由（HTML）
# ============================================================================


@router.get("/admin")
async def admin_dashboard(
    request,
    current_admin: User = Depends(get_current_admin),
) -> HTMLResponse:
    """管理员仪表板页面"""
    from fastapi.templating import Jinja2Templates

    # 注入 templates
    if not router.dependencies:
        from main import get_templates
        router.dependencies["templates"] = get_templates()

    templates = router.dependencies.get("templates")
    if not templates:
        templates = Jinja2Templates(directory="templates")

    stats = {
        "total_users": await User.filter(status="active").count(),
        "total_skills": await Skill.all().count(),
        "pending_skills": await Skill.filter(status=SkillStatus.PENDING).count(),
    }

    return templates.TemplateResponse(
        "admin_dashboard.html",
        {"request": request, "admin": current_admin, "stats": stats}
    )


@router.get("/admin/upload")
async def admin_upload_page(
    request,
    current_admin: User = Depends(get_current_admin),
) -> HTMLResponse:
    """上传管理页面"""
    from fastapi.templating import Jinja2Templates

    if not router.dependencies:
        from main import get_templates
        router.dependencies["templates"] = get_templates()

    templates = router.dependencies.get("templates")
    if not templates:
        templates = Jinja2Templates(directory="templates")

    return templates.TemplateResponse(
        "admin_upload.html",
        {"request": request, "admin": current_admin}
    )


@router.get("/admin/users")
async def admin_users_page(
    request,
    current_admin: User = Depends(get_current_admin),
) -> HTMLResponse:
    """用户管理页面"""
    from fastapi.templating import Jinja2Templates

    if not router.dependencies:
        from main import get_templates
        router.dependencies["templates"] = get_templates()

    templates = router.dependencies.get("templates")
    if not templates:
        templates = Jinja2Templates(directory="templates")

    users = await User.all().limit(100).order_by("-created_at")

    return templates.TemplateResponse(
        "admin_users.html",
        {"request": request, "admin": current_admin, "users": users}
    )


# ============================================================================
# API 路由
# ============================================================================


@router.get("/pending")
async def api_get_pending_skills(
    pagination: Depends(get_pagination),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """获取待审核技能列表

    Query 参数:
    - page: 页码（默认1）
    - per_page: 每页数量（默认20，最大100）

    Returns: 分页的待审核技能列表
    """
    try:
        if current_user.role not in ["admin", "reviewer"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限查看待审核技能"
            )

        # 获取待审核技能
        skills = await Skill.filter(status=SkillStatus.PENDING).prefetch_related(["uploader"]).all()

        # 分页
        total = len(skills)
        start = pagination.offset
        end = start + pagination.limit
        paginated_skills = skills[start:end]

        # 预加载关联数据
        for skill in paginated_skills:
            await skill.fetch_related("uploader")

        return JSONResponse({
            "skills": [skill.to_dict() for skill in paginated_skills],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.page_size,
                "total": total
            }
        })

    except Exception as e:
        logger.error(f"Error fetching pending skills: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取待审核技能失败"
        )


@router.post("/review/{skill_id}")
async def api_review_skill(
    skill_id: int,
    review: ReviewRequest,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """审核技能（通过或拒绝）

    Body 参数:
    - action: 操作类型（approve=通过, reject=拒绝）
    - comment: 审核意见（可选）
    """
    try:
        if current_user.role not in ["admin", "reviewer"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限审核技能"
            )

        skill = await SkillRepository.get_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="技能不存在"
            )

        if skill.status != SkillStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能审核待审核状态的技能"
            )

        # 确定新状态
        if review.action == "approve":
            new_status = SkillStatus.APPROVED
            title = f"技能 {skill.skill_name} 审核通过"
            # 移动文件到 plugins 目录
            success = _approve_skill_file(skill)
        elif review.action == "reject":
            new_status = SkillStatus.REJECTED
            title = f"技能 {skill.skill_name} 审核未通过"
            success = True  # 拒绝不需要移动文件
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的审核操作: {review.action}"
            )

        # 更新技能状态
        await SkillRepository.update_status(
            skill_id,
            new_status,
            reviewer_id=current_user.id,
            review_comment=review.comment
        )

        # 创建通知
        await NotificationRepository.create(
            user_id=skill.uploader_id,
            type=NotificationType.SKILL_APPROVED if review.action == "approve" else NotificationType.SKILL_REJECTED,
            title=title,
            content=review.comment
        )

        logger.info(f"Skill {skill_id} reviewed by {current_user.employee_id}: {review.action}")

        return JSONResponse({
            "message": "审核完成",
            "skill_id": skill_id,
            "status": new_status
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reviewing skill {skill_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="审核失败"
        )


@router.post("/admin/users/{user_id}/role")
async def api_update_user_role(
    user_id: int,
    request: UpdateRoleRequest,
    current_admin: User = Depends(get_current_admin),
) -> JSONResponse:
    """更新用户角色"""
    try:
        user = await UserRepository.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        await UserRepository.update_role(user_id, request.role)

        logger.info(f"Admin {current_admin.employee_id} updated user {user_id} role to {request.role}")

        return JSONResponse({
            "message": "角色已更新",
            "user_id": user_id,
            "new_role": request.role
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新失败"
        )


@router.post("/admin/users/{user_id}/disable")
async def api_disable_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
) -> JSONResponse:
    """禁用用户"""
    try:
        user = await UserRepository.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        if user.id == current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能禁用自己"
            )

        await UserRepository.disable(user_id)

        logger.info(f"Admin {current_admin.employee_id} disabled user {user_id}")

        return JSONResponse({
            "message": "用户已禁用",
            "user_id": user_id
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="禁用失败"
        )


@router.post("/admin/users/{user_id}/enable")
async def api_enable_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
) -> JSONResponse:
    """启用用户"""
    try:
        user = await UserRepository.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        await UserRepository.enable(user_id)

        logger.info(f"Admin {current_admin.employee_id} enabled user {user_id}")

        return JSONResponse({
            "message": "用户已启用",
            "user_id": user_id
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="启用失败"
        )


@router.delete("/admin/users/{user_id}")
async def api_delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
) -> JSONResponse:
    """删除用户"""
    try:
        user = await UserRepository.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        if user.id == current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能删除自己"
            )

        await UserRepository.delete(user_id)

        logger.info(f"Admin {current_admin.employee_id} deleted user {user_id}")

        return JSONResponse({
            "message": "用户已删除",
            "user_id": user_id
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除失败"
        )


@router.post("/admin/users/reset-api-key")
async def api_reset_user_api_key(
    request: ResetAPIKeyRequest,
    current_admin: User = Depends(get_current_admin),
) -> JSONResponse:
    """重置用户API密钥"""
    try:
        import secrets

        user = await UserRepository.get_by_id(request.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        # 生成新密钥
        new_key = secrets.token_hex(16)

        await UserRepository.reset_api_key(request.user_id, new_key)

        logger.info(f"Admin {current_admin.employee_id} reset API key for user {request.user_id}")

        return JSONResponse({
            "message": "API密钥已重置",
            "user_id": request.user_id,
            "new_api_key": new_key
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="重置失败"
        )


# ============================================================================
# 辅助函数
# ============================================================================

def _approve_skill_file(skill: Skill) -> bool:
    """审核通过技能时移动文件

    从 pending 目录移动到 plugins 目录
    """
    pending_path = PENDING_DIR / skill.filename
    plugins_path = PLUGINS_DIR / skill.filename

    try:
        if not pending_path.exists():
            logger.error(f"Pending file not found: {pending_path}")
            return False

        # 移除已存在的文件
        if plugins_path.exists():
            logger.info(f"Removing existing file: {plugins_path}")
            plugins_path.unlink()

        # 移动文件
        shutil.move(str(pending_path), str(plugins_path))

        return True

    except Exception as e:
        logger.error(f"Error moving skill file: {e}")
        return False
