from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class SourceTypeEnum(str, Enum):
    """技能来源类型枚举"""
    opensource = "opensource"
    icsl = "icsl"
    huawei = "huawei"
    all = "all"

# ========== 嵌套模型 ==========

class SkillMetadata(BaseModel):
    """技能元数据"""
    version: str
    author: str
    tags: List[str] = []
    category: Optional[str] = None
    license: Optional[str] = None
    compatibility: Optional[str] = None

class SkillVersionInfo(BaseModel):
    """技能版本信息"""
    version: str
    filename: str
    is_default: bool
    download_url: str

class PaginationInfo(BaseModel):
    """分页信息"""
    page: int
    page_size: int
    total: int
    total_pages: int

# ========== 技能相关模型 ==========

class SkillItem(BaseModel):
    """技能列表项"""
    name: str
    description: str
    metadata: SkillMetadata
    source_type: str
    default_version: str
    versions: List[str]
    download_url: str

class SkillDetail(BaseModel):
    """技能详情"""
    name: str
    description: str
    metadata: SkillMetadata
    source_type: str
    versions: List[SkillVersionInfo]

# ========== 请求参数模型 ==========

class SkillListQuery(BaseModel):
    """技能列表查询参数"""
    source_type: SourceTypeEnum = SourceTypeEnum.all
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
    keyword: Optional[str] = Field(None, description="搜索关键词")
    tags: Optional[str] = Field(None, description="标签过滤，逗号分隔")

    class Config:
        extra = "forbid"

class SkillDownloadQuery(BaseModel):
    """技能下载查询参数"""
    version: Optional[str] = Field(None, description="指定版本，不指定则下载默认版本")

# ========== 响应模型 ==========

class ApiResponse(BaseModel):
    """统一 API 响应基类"""
    code: int
    message: str
    data: Any

class SkillListResponse(BaseModel):
    """技能列表响应"""
    code: int
    message: str
    data: Dict[str, List[SkillItem]]
    pagination: PaginationInfo

class SkillDetailResponse(BaseModel):
    """技能详情响应"""
    code: int
    message: str
    data: SkillDetail

class ErrorResponse(BaseModel):
    """错误响应"""
    code: int
    message: str
    data: None = None
