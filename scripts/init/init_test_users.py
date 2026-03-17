#!/usr/bin/env python3
"""
Initialize test users for the skill registry.

Run this script to create test user accounts for development and testing.
"""

import sys
from pathlib import Path
import logging
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 导入日志配置
from logging_config import setup_logging, audit_log

# 初始化日志系统
setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_dir="./logs",
    enable_json=True,
    enable_console=True
)

# 获取logger
logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database import init_db, create_user


def main():
    """Initialize database and create test users."""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized", extra={"status": "success"})

    logger.info("Creating test users...")

    created_users = []

    # Create admin user
    try:
        admin_id = create_user("admin001", "admin_key_001", role="admin")
        logger.info("Created admin user", extra={"employee_id": "admin001", "api_key": "admin_key_001"})
        created_users.append({"employee_id": "admin001", "role": "admin"})
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            logger.info("Admin user already exists", extra={"employee_id": "admin001"})
        else:
            logger.error(f"Failed to create admin user: {e}", exc_info=True)

    # Create regular users
    try:
        user1_id = create_user("test001", "test_key_001", role="user")
        logger.info("Created test user", extra={"employee_id": "test001", "api_key": "test_key_001"})
        created_users.append({"employee_id": "test001", "role": "user"})
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            logger.info("Test user already exists", extra={"employee_id": "test001"})
        else:
            logger.error(f"Failed to create test user: {e}", exc_info=True)

    try:
        user2_id = create_user("test002", "test_key_002", role="user")
        logger.info("Created test user", extra={"employee_id": "test002", "api_key": "test_key_002"})
        created_users.append({"employee_id": "test002", "role": "user"})
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            logger.info("Test user already exists", extra={"employee_id": "test002"})
        else:
            logger.error(f"Failed to create test user: {e}", exc_info=True)

    logger.info("="*60)
    logger.info("Test users initialized successfully!")
    logger.info("="*60)
    logger.info("Admin account", extra={
        "url": "http://localhost:28000/login",
        "employee_id": "admin001",
        "api_key": "admin_key_001"
    })
    logger.info("User accounts", extra={
        "users": [
            {"employee_id": "test001", "api_key": "test_key_001"},
            {"employee_id": "test002", "api_key": "test_key_002"}
        ]
    })
    logger.info("="*60)

    # 记录审计日志
    audit_log(
        logger,
        action="config_change",
        user_id="system",
        change_type="init_test_users",
        users_created=len(created_users),
        result="success"
    )


if __name__ == "__main__":
    main()
