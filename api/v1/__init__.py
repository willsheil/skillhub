"""
API V1 Routes Package (Tortoise ORM 版本）

This package contains all API v1 route modules.
使用 Tortoise ORM 进行数据库操作，支持异步访问。

支持新旧两种 API 版本共存，逐步迁移。
"""

from fastapi import APIRouter
from fastapi.templating import Jinja2Templates

# 导入旧版 API 路由（向后兼容）
try:
    from . import admin, skills, stats, users
    OLD_ROUTES_AVAILABLE = True
except ImportError:
    OLD_ROUTES_AVAILABLE = False

# 导入新版 ORM API 路由
try:
    from . import admin_orm, skills_orm, stats_orm, users_orm, notifications_orm
    ORM_ROUTES_AVAILABLE = True
except ImportError:
    ORM_ROUTES_AVAILABLE = False


def create_v1_router(templates_instance: Jinja2Templates) -> APIRouter:
    """Create and configure the v1 API router.

    Args:
        templates_instance: Jinja2Templates instance for rendering templates

    Returns:
        Configured APIRouter instance with all v1 routes
    """
    router = APIRouter(prefix="/api/v1", tags=["v1"])

    # 包含新版 ORM API 路由
    if ORM_ROUTES_AVAILABLE:
        # Admin routes
        admin_orm_router = APIRouter(prefix="/api/v1", tags=["admin"])
        from . import admin_orm
        admin_orm_router.include_router(admin_orm.router)

        # Skills routes
        skills_orm_router = APIRouter(prefix="/api/v1", tags=["skills"])
        from . import skills_orm
        skills_orm_router.include_router(skills_orm.router)

        # Stats routes
        stats_orm_router = APIRouter(prefix="/api/v1", tags=["stats"])
        from . import stats_orm
        stats_orm_router.include_router(stats_orm.router)

        # Users routes
        users_orm_router = APIRouter(prefix="/api/v1", tags=["users"])
        from . import users_orm
        users_orm_router.include_router(users_orm.router)

        # Notifications routes
        notifications_orm_router = APIRouter(prefix="/api/v1", tags=["notifications"])
        from . import notifications_orm
        notifications_orm_router.include_router(notifications_orm.router)

        # 添加所有 ORM 路由到主路由器
        router.include_router(admin_orm_router)
        router.include_router(skills_orm_router)
        router.include_router(stats_orm_router)
        router.include_router(users_orm_router)
        router.include_router(notifications_orm_router)

    # 保留旧版 API 路由（向后兼容）
    if OLD_ROUTES_AVAILABLE:
        # Admin routes (note: admin router has its own prefix)
        admin_router = admin.init_admin_router(templates_instance)
        for route in admin_router.routes:
            router.routes.append(route)

        # Skills routes
        skills_router = skills.init_skills_router(templates_instance)
        for route in skills_router.routes:
            router.routes.append(route)

        # Stats routes
        stats_router = stats.init_stats_router(templates_instance)
        for route in stats_router.routes:
            router.routes.append(route)

        # Users routes
        users_router = users.init_users_router(templates_instance)
        for route in users_router.routes:
            router.routes.append(route)

    return router
