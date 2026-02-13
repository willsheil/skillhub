"""
FastAPI 依赖注入和数据库会话管理
支持新旧两种数据库访问方式
"""

import logging
from typing import Optional, Generator

from fastapi import HTTPException, Request, status, Depends

# 导入新的 ORM 模块
from core.models import User
from core.repositories import UserRepository

# 导入旧的数据库模块（用于向后兼容）
try:
    from database import get_user_by_id
    OLD_DB_AVAILABLE = True
except ImportError:
    OLD_DB_AVAILABLE = False

logger = logging.getLogger("skillhub")


# ============================================================================
# 新版依赖（使用 Tortoise ORM）
# ============================================================================

async def get_current_user_optional(request: Request) -> Optional[User]:
    """
    获取当前登录用户（可选）
    用于需要用户信息但不强制登录的场景
    """
    # 从 session 获取用户ID
    user_id = request.session.get("user_id")
    if user_id:
        return await UserRepository.get_by_id(user_id)
    return None


async def get_current_user(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    """
    获取当前登录用户（必需）
    用于需要强制登录的接口
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录已过期"
        )
    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    获取当前管理员用户
    用于需要管理员权限的接口
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


async def get_current_reviewer(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    获取当前审核员用户
    用于需要审核员权限的接口
    """
    if current_user.role not in ["admin", "reviewer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要审核员权限"
        )
    return current_user


class PaginationParams:
    """分页参数"""
    def __init__(
        self,
        page: int = 1,
        page_size: int = 20
    ):
        self.page = max(1, page)
        self.page_size = min(100, max(1, page_size))
        self.offset = (self.page - 1) * self.page_size
        self.limit = self.page_size


async def get_pagination(
    page: int = 1,
    page_size: int = 20
) -> PaginationParams:
    """获取分页参数"""
    return PaginationParams(page, page_size)


# ============================================================================
# 旧版依赖（向后兼容，逐步废弃）
# ============================================================================

def get_current_user_legacy(request: Request) -> Optional[dict]:
    """获取当前用户（旧版，使用原生SQL）"""
    if not OLD_DB_AVAILABLE:
        raise RuntimeError("旧数据库模块不可用，请使用新版依赖")
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(user_id)


def require_auth_legacy(request: Request):
    """检查认证（旧版）"""
    if not OLD_DB_AVAILABLE:
        raise RuntimeError("旧数据库模块不可用，请使用新版依赖")
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return True


def require_admin_legacy(request: Request):
    """检查管理员权限（旧版）"""
    if not OLD_DB_AVAILABLE:
        raise RuntimeError("旧数据库模块不可用，请使用新版依赖")
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    role = request.session.get("role")
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return True


def get_db_legacy() -> Generator:
    """获取数据库连接（旧版）"""
    if not OLD_DB_AVAILABLE:
        raise RuntimeError("旧数据库模块不可用，请使用新版依赖")
    from database import get_connection
    with get_connection() as conn:
        yield conn
