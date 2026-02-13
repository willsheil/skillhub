"""
OpenAPI/Swagger 配置

为 FastAPI 应用添加详细的 API 文档支持
"""

from fastapi import FastAPI
from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# API 标签和描述
# ============================================================================

API_TAGS_METADATA = [
    {
        "name": "authentication",
        "description": "用户认证相关接口",
    },
    {
        "name": "users",
        "description": "用户管理相关接口",
    },
    {
        "name": "skills",
        "description": "技能管理相关接口",
    },
    {
        "name": "admin",
        "description": "管理员功能接口",
    },
    {
        "name": "stats",
        "description": "统计数据接口",
    },
    {
        "name": "notifications",
        "description": "通知相关接口",
    },
]


# ============================================================================
# 通用响应模型
# ============================================================================

class SuccessResponse(BaseModel):
    """成功响应模型"""
    success: bool = Field(True, description="操作是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[dict] = Field(None, description="响应数据")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    success: bool = Field(False, description="操作是否成功")
    error: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="详细错误描述")


class PaginationResponse(BaseModel):
    """分页响应模型"""
    page: int = Field(..., ge=1, description="当前页码")
    per_page: int = Field(..., ge=1, le=100, description="每页数量")
    total: int = Field(..., ge=0, description="总记录数")
    total_pages: int = Field(..., ge=0, description="总页数")


# ============================================================================
# API 端点描述
# ============================================================================

API_ENDPOINTS = {
    # 认证相关
    "POST /api/v1/auth/login": "用户登录，返回认证 token",
    "POST /api/v1/auth/logout": "用户登出，清除 session",

    # 技能相关
    "GET /api/v1/skills": "分页获取所有已上线技能列表，支持搜索和筛选",
    "GET /api/v1/skills/{skill_id}": "获取单个技能的详细信息",
    "POST /api/v1/skills/upload": "上传新的技能文件，进入待审核状态",
    "DELETE /api/v1/skills/{skill_id}": "删除指定技能",
    "GET /api/v1/skills/name/{skill_name}": "按名称搜索技能",
    "GET /api/v1/skills/download/{skill_id}": "下载指定技能文件",

    # 用户技能管理
    "GET /api/v1/my-skills": "获取当前用户上传的技能列表，支持分页和状态筛选",
    "POST /api/v1/my-skills/batch/unlist": "批量下架技能",
    "POST /api/v1/my-skills/batch/delete": "批量删除技能（管理员）",
    "POST /api/v1/my-skills/{skill_id}/unlist": "下架单个技能",
    "POST /api/v1/my-skills/{skill_id}/publish": "发布技能",
    "POST /api/v1/my-skills/{skill_id}/set-default": "设置技能为默认版本",
    "GET /api/v1/my-skills/versions/{skill_name}": "获取技能的所有版本",
    "DELETE /api/v1/my-skills/{skill_id}": "删除技能（管理员）",

    # 统计相关
    "GET /api/v1/stats": "获取系统总体统计（用户数、技能数、下载量）",
    "GET /api/v1/stats/downloads": "获取指定时间段内的下载统计数据",
    "GET /api/v1/stats/hot": "获取指定时间段内下载量最高的技能列表",
    "GET /api/v1/stats/top-users": "获取指定时间段内下载量最高的用户列表",
    "GET /api/v1/stats/today": "获取今日的下载统计数据",

    # 管理员相关
    "GET /api/v1/pending": "管理员获取待审核技能列表",
    "POST /api/v1/review/{skill_id}": "管理员审核技能（通过/拒绝）",
    "GET /api/v1/admin": "管理员仪表板页面",
    "GET /api/v1/admin/users": "用户管理页面",
    "POST /api/v1/admin/users/{user_id}/role": "更新用户角色",
    "POST /api/v1/admin/users/{user_id}/disable": "禁用用户",
    "POST /api/v1/admin/users/{user_id}/enable": "启用用户",
    "DELETE /api/v1/admin/users/{user_id}": "删除用户",
    "POST /api/v1/admin/users/reset-api-key": "重置用户 API 密钥",

    # 通知相关
    "GET /api/v1/notifications": "获取当前用户的通知列表，支持未读筛选",
    "GET /api/v1/notifications/count": "获取未读通知数量",
    "POST /api/v1/notifications/{id}/read": "标记单个通知为已读",
    "POST /api/v1/notifications/read-all": "标记所有通知为已读",
}


def configure_openapi(app: FastAPI) -> None:
    """配置 FastAPI 的 OpenAPI 文档

    Args:
        app: FastAPI 应用实例
    """
    # 设置应用信息
    app.title = "SkillHub API"
    app.description = """
    SkillHub 是一个内部的技能共享和管理平台。

    ## 功能特性

    - **用户管理**: 员工ID登录，API Key 认证
    - **技能管理**: 上传、下载、搜索、版本管理
    - **审核流程**: 管理员审核技能发布
    - **统计功能**: 下载统计、热门技能、活跃用户
    - **通知系统**: 实时通知用户

    ## 认证说明

    大部分 API 需要认证。使用以下方式：

    1. **员工ID + API Key**: 在请求头中添加 `Authorization: Bearer <token>`
    2. **Session Cookie**: 登录后通过 Session 维持认证状态

    ## 数据格式

    所有响应使用统一的 JSON 格式：

    ```json
    {
        "success": true,
        "message": "操作成功",
        "data": { ... }
    }
    ```

    ## 错误码说明

    - `200`: 操作成功
    - `400`: 请求参数错误
    - `401`: 未认证
    - `403`: 权限不足
    - `404`: 资源不存在
    - `500`: 服务器内部错误
    """

    app.version = "2.0.0"
    app.contact = {
        "name": "API Support",
        "email": "support@example.com"
    }

    # 配置文档标签
    app.openapi_tags = API_TAGS_METADATA

    # 添加服务器信息
    app.servers = [
        {
            "url": "/api/v1",
            "description": "API v1 - 当前版本"
        }
    ]


# ============================================================================
# 导出函数
# ============================================================================

def get_api_documentation() -> dict:
    """获取 API 文档摘要"""
    return {
        "title": "SkillHub API Documentation",
        "description": "完整的 API 端点列表和说明",
        "endpoints": API_ENDPOINTS,
        "authentication": {
            "type": "Bearer Token",
            "description": "使用 Authorization: Bearer <token> 头"
        },
        "response_format": {
            "success": "boolean",
            "message": "string",
            "data": "object"
        }
    }
