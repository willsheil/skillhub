"""
Tortoise ORM 数据库配置和连接管理
"""

import os
from tortoise.contrib.fastapi import connections
from tortoise.contrib.fastapi import register_tortoise
from contextlib import asynccontextmanager


# 数据库配置
DB_CONFIG = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.mysql",
            "credentials": {
                "host": os.getenv("DB_HOST", "127.0.0.1"),
                "port": int(os.getenv("DB_PORT", "3306")),
                "user": os.getenv("DB_USER", "root"),
                "password": os.getenv("DB_PASSWORD", "root"),
                "database": os.getenv("DB_DATABASE", "skills"),
                "charset": "utf8mb4",
                "connect_timeout": 60,
                "max_connections": 100,
            }
        }
    },
    "apps": {
        "models": {
            "models": ["core.models"],
            "default_connection": "default",
        }
    },
    "use_tz": True,
    "timezone": "Asia/Shanghai",
}


async def init_db():
    """初始化数据库连接"""
    await Tortoise.init(config=DB_CONFIG)
    print("Database connected successfully")


async def close_db():
    """关闭数据库连接"""
    await Tortoise.close_connections()
    print("Database connections closed")


def get_db_config():
    """获取数据库配置（用于 FastAPI 集成）"""
    return {
        "db_url": (
            f"mysql://{os.getenv('DB_USER', 'root')}:"
            f"{os.getenv('DB_PASSWORD', 'root')}@"
            f"{os.getenv('DB_HOST', '127.0.0.1')}:"
            f"{os.getenv('DB_PORT', '3306')}/"
            f"{os.getenv('DB_DATABASE', 'skills')}"
            f"?charset=utf8mb4"
        ),
        "modules": {"models": ["core.models"]},
        "generate_schemas": False,  # 不自动创建表，使用现有表
    }


def create_life_span_handler():
    """创建 FastAPI 生命周期处理器"""
    from fastapi import FastAPI

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 启动时初始化
        await init_db()
        yield
        # 关闭时清理
        await close_db()

    return lifespan


def register_db(app):
    """
    注册 Tortoise 到 FastAPI 应用
    适用于 FastAPI 的 startup/shutdown 事件
    """
    register_tortoise(
        app,
        config=get_db_config(),
        generate_schemas=False,  # 不自动创建表
        add_exception_handlers=True,
    )
