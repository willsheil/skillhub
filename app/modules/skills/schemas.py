"""
Pydantic schemas for skills module request/response models.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class SkillMetadata(BaseModel):
    """Skill metadata from SKILL.md file."""
    name: str
    description: str
    version: str
    author: Optional[str] = None
    license: Optional[str] = None
    compatibility: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    allowed_tools: Optional[str] = None


class PluginMetadata(BaseModel):
    """Plugin metadata for marketplace display."""
    name: str
    version: str
    description: str
    author: Dict[str, Any]
    updated_at: Optional[str] = None


class SkillListItem(BaseModel):
    """Skill item in list response."""
    name: str
    metadata: Dict[str, Any]
    latest_version: str
    source_type: str
    uploaded_at: Optional[str] = None
    download_count: int = 0
    versions: List[Dict[str, str]] = Field(default_factory=list)


class PaginatedSkillsResponse(BaseModel):
    """Paginated skills list response."""
    data: List[SkillListItem]
    total: int
    page: int
    per_page: int
    total_pages: int


class SkillRecord(BaseModel):
    """Skill record from database."""
    id: int
    skill_name: str
    version: str
    filename: str
    uploader_id: int
    status: str
    source_type: Optional[str] = "opensource"
    uploaded_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewer_id: Optional[int] = None
    review_comment: Optional[str] = None
    is_active: bool = True
    is_default_version: bool = False


class PendingSkillItem(BaseModel):
    """Pending skill item for admin review."""
    id: int
    skill_name: str
    version: str
    filename: str
    uploader_id: int
    status: str
    source_type: Optional[str] = "opensource"
    uploaded_at: Optional[datetime] = None
    uploader_employee_id: Optional[str] = None


class BatchOperationRequest(BaseModel):
    """Request model for batch operations."""
    skill_ids: List[int]


class BatchOperationResponse(BaseModel):
    """Response model for batch operations."""
    success_count: int
    failed_ids: List[int]


class ReviewSkillRequest(BaseModel):
    """Request model for skill review."""
    action: str = Field(..., pattern="^(approve|reject)$")
    comment: Optional[str] = None


class UpdateSourceTypeRequest(BaseModel):
    """Request model for updating source type."""
    source_type: str = Field(..., pattern="^(opensource|icsl|huawei)$")
