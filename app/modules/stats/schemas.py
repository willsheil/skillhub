"""
Stats module request and response schemas.
"""

from datetime import date
from typing import List, Optional, Any
from pydantic import BaseModel, Field


class DownloadRanking(BaseModel):
    """Download ranking for a single skill."""
    skill_name: str = Field(..., description="Name of the skill")
    author: str = Field(default="Unknown", description="Author of the skill")
    downloads: int = Field(..., description="Number of downloads", ge=0)


class StatsResponse(BaseModel):
    """Statistics response with period info and rankings."""
    period: "PeriodInfo" = Field(..., description="Time period for the statistics")
    total_downloads: int = Field(..., description="Total downloads in the period", ge=0)
    rankings: List[DownloadRanking] = Field(..., description="Download rankings by skill")


class PeriodInfo(BaseModel):
    """Time period information for statistics."""
    start_date: str = Field(..., description="Start date (YYYY-MM-DD or 'all-time')")
    end_date: str = Field(..., description="End date (YYYY-MM-DD or 'all-time')")


class TopSkill(BaseModel):
    """Top skill by downloads."""
    skill_name: str = Field(..., description="Name of the skill")
    downloads: int = Field(..., description="Number of downloads", ge=0)


class TopUser(BaseModel):
    """Top user by downloads."""
    employee_id: str = Field(..., description="Employee ID")
    role: str = Field(..., description="User role")
    downloads: int = Field(..., description="Number of downloads", ge=0)


class AdminStatsResponse(BaseModel):
    """Admin statistics response."""
    success: bool = Field(True, description="Success flag")
    data: "AdminStatsData" = Field(..., description="Statistics data")


class AdminStatsData(BaseModel):
    """Admin statistics data."""
    total_users: int = Field(..., description="Total number of users", ge=0)
    pending_skills: int = Field(..., description="Number of pending skills", ge=0)
    approved_skills: int = Field(..., description="Number of approved skills", ge=0)
    today_downloads: int = Field(..., description="Number of downloads today", ge=0)
    top_skills: List[TopSkill] = Field(..., description="Top skills by downloads")
    top_users: List[TopUser] = Field(..., description="Top users by downloads")


# Update forward references
StatsResponse.model_rebuild()
AdminStatsResponse.model_rebuild()
