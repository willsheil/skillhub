"""
Statistics routes - Download stats, user stats, system stats.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from datetime import datetime, timedelta, date

from db.repositories import SkillRepository, DownloadRepository, UserRepository
from api.v1.dependencies import get_current_user

router = APIRouter()


@router.get("/top")
async def api_stats_top(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """Get download statistics with rankings (public endpoint)."""
    try:
        # Parse dates
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None

        # Import here to avoid circular imports
        from main import scan_plugins
        from database import get_stats_with_author

        # Get plugins for author mapping
        plugins = scan_plugins()

        # Get stats with author info
        stats = get_stats_with_author(plugins, start, end)

        return {
            "period": {
                "start_date": start_date or "all-time",
                "end_date": end_date or "all-time"
            },
            "total_downloads": stats["total_downloads"],
            "rankings": stats["rankings"]
        }

    except ValueError as e:
        raise HTTPException(400, f"Invalid date format: {e}")
    except Exception as e:
        raise HTTPException(500, f"Failed to get stats: {e}")


@router.get("/downloads")
async def get_download_stats(
    days: Optional[int] = 30,
    current_user: dict = Depends(get_current_user)
):
    """Get download statistics."""
    top_skills = DownloadRepository.get_top_skills(limit=10, days=days)
    top_users = DownloadRepository.get_top_users(limit=10, days=days)
    today_count = DownloadRepository.get_today_count()
    total_count = DownloadRepository.get_total_count()

    return {
        "period_days": days,
        "today_count": today_count,
        "total_count": total_count,
        "top_skills": top_skills,
        "top_users": top_users,
    }


@router.get("/skills")
async def get_skill_stats(current_user: dict = Depends(get_current_user)):
    """Get skill statistics."""
    stats = SkillRepository.get_stats()
    return stats


@router.get("/users")
async def get_user_stats(current_user: dict = Depends(get_current_user)):
    """Get user statistics."""
    total = UserRepository.get_total_count()
    admins = UserRepository.get_total_count(role="admin")
    users = UserRepository.get_total_count(role="user")

    return {
        "total": total,
        "admins": admins,
        "users": users,
    }


@router.get("/overview")
async def get_overview_stats(current_user: dict = Depends(get_current_user)):
    """Get overall system overview."""
    skill_stats = SkillRepository.get_stats()
    download_stats = {
        "today": DownloadRepository.get_today_count(),
        "total": DownloadRepository.get_total_count(),
    }
    user_stats = {
        "total": UserRepository.get_total_count(),
    }

    return {
        "skills": skill_stats,
        "downloads": download_stats,
        "users": user_stats,
    }
