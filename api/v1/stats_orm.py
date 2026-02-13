"""
Stats API Routes - V1 (Tortoise ORM 版本）

统计数据相关路由：
- GET /api/v1/stats - 获取总体统计
- GET /api/v1/stats/downloads - 获取下载统计
- GET /api/v1/stats/hot - 获取热门技能
- GET /api/v1/stats/top-users - 获取活跃用户
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.dependencies import get_current_user
from core.models import User, Skill, Download, SkillStatus
from core.repositories import StatsRepository, DownloadRepository, SkillRepository

logger = logging.getLogger("skillhub")

# Router
router = APIRouter(prefix="/api/v1", tags=["stats"])


# ============================================================================
# 请求/响应模型
# ============================================================================

class OverallStats(BaseModel):
    """总体统计响应模型"""
    total_users: int
    total_downloads: int
    pending_skills: int
    approved_skills: int


class DownloadStats(BaseModel):
    """下载统计响应模型"""
    date: str
    count: int


class HotSkill(BaseModel):
    """热门技能响应模型"""
    skill_name: str
    downloads: int
    author: Optional[str] = None


# ============================================================================
# API 路由
# ============================================================================


@router.get("/stats")
async def api_overall_stats(
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """获取总体统计数据"""
    try:
        stats = await StatsRepository.get_overall()

        return JSONResponse({
            "total_users": stats["total_users"],
            "total_downloads": stats["total_downloads"],
            "pending_skills": stats["pending_skills"],
            "approved_skills": stats["approved_skills"],
            "total_skills": stats["total_skills"],
        })

    except Exception as e:
        logger.error(f"Error fetching overall stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取统计失败"
        )


@router.get("/stats/downloads")
async def api_download_stats(
    days: int = Query(30, ge=1, le=90, description="统计天数（1-90天）"),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """获取下载统计数据

    Query 参数:
    - days: 统计天数（默认30天，最大90天）
    """
    try:
        stats = await DownloadRepository.get_stats(days=days)

        # 格式化响应
        response = []
        for stat in stats:
            response.append({
                "skill_name": stat["skill_name"],
                "version": stat["version"],
                "count": stat["count"]
            })

        return JSONResponse({
            "period_days": days,
            "stats": response
        })

    except Exception as e:
        logger.error(f"Error fetching download stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取下载统计失败"
        )


@router.get("/stats/hot")
async def api_hot_skills(
    days: int = Query(30, ge=1, le=90, description="统计天数（1-90天）"),
    limit: int = Query(10, ge=1, le=50, description="返回数量（1-50）"),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """获取热门技能统计

    Query 参数:
    - days: 统计天数（默认30天，最大90天）
    - limit: 返回数量（默认10，最大50）
    """
    try:
        top_skills = await DownloadRepository.get_top_skills(limit=limit, days=days)

        # 获取技能名称对应的作者信息
        skill_names = [s["skill_name"] for s in top_skills]

        # 查询作者信息
        skills = await Skill.filter(
            skill_name__in=skill_names,
            status=SkillStatus.APPROVED,
            is_active=True
        ).prefetch_related(["uploader"]).all()

        # 构建作者映射
        skill_author_map = {}
        for skill in skills:
            if skill.uploader:
                skill_author_map[skill.skill_name] = skill.uploader.employee_id

        # 组合响应
        response = []
        for item in top_skills:
            response.append({
                "skill_name": item["skill_name"],
                "downloads": item["downloads"],
                "author": skill_author_map.get(item["skill_name"], "Unknown")
            })

        return JSONResponse({
            "period_days": days,
            "hot_skills": response
        })

    except Exception as e:
        logger.error(f"Error fetching hot skills: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取热门技能失败"
        )


@router.get("/stats/top-users")
async def api_top_users(
    days: int = Query(30, ge=1, le=90, description="统计天数（1-90天）"),
    limit: int = Query(10, ge=1, le=50, description="返回数量（1-50）"),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """获取活跃用户统计

    Query 参数:
    - days: 统计天数（默认30天，最大90天）
    - limit: 返回数量（默认10，最大50）
    """
    try:
        top_users = await DownloadRepository.get_top_users(limit=limit, days=days)

        return JSONResponse({
            "period_days": days,
            "top_users": top_users
        })

    except Exception as e:
        logger.error(f"Error fetching top users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取活跃用户失败"
        )


@router.get("/stats/today")
async def api_today_stats(
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """获取今日统计数据"""
    try:
        today_count = await DownloadRepository.count_today()
        total_count = await DownloadRepository.count_total()

        return JSONResponse({
            "today_downloads": today_count,
            "total_downloads": total_count
        })

    except Exception as e:
        logger.error(f"Error fetching today stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取今日统计失败"
        )
