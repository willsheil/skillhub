#!/usr/bin/env python3
"""
Initialize test users in the database.

This script creates test users for development and testing purposes.
"""

import sys
from pathlib import Path
import logging
import os

# Add parent directory to sys.path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

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

from database import init_db, get_connection


def init_users():
    """Initialize test users in the database."""
    # Ensure database tables exist
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized", extra={"status": "success"})

    # Define test users
    test_users = [
        {
            "employee_id": "w00000001",
            "api_key": "sk-test-admin-key-1",
            "role": "admin"
        },
        {
            "employee_id": "w00000002",
            "api_key": "sk-test-user-key-1",
            "role": "user"
        },
        {
            "employee_id": "w00000003",
            "api_key": "sk-test-user-key-2",
            "role": "user"
        }
    ]

    logger.info("Creating test users...")
    created_count = 0
    skipped_count = 0
    created_users = []

    with get_connection() as conn:
        for user_data in test_users:
            employee_id = user_data["employee_id"]

            # Check if user already exists
            cursor = conn.execute(
                "SELECT id FROM users WHERE employee_id = ?",
                (employee_id,)
            )
            existing = cursor.fetchone()

            if existing:
                logger.debug(f"User already exists, skipping", extra={"employee_id": employee_id})
                skipped_count += 1
            else:
                # Insert the user
                conn.execute(
                    """
                    INSERT INTO users (employee_id, api_key, role)
                    VALUES (?, ?, ?)
                    """,
                    (user_data["employee_id"], user_data["api_key"], user_data["role"])
                )
                conn.commit()
                logger.info(f"Created test user", extra={
                    "employee_id": employee_id,
                    "role": user_data["role"]
                })
                created_count += 1
                created_users.append({
                    "employee_id": employee_id,
                    "api_key": user_data["api_key"],
                    "role": user_data["role"]
                })

    logger.info(f"Test users initialization summary", extra={
        "created": created_count,
        "skipped": skipped_count,
        "total": len(test_users)
    })

    # 记录审计日志
    audit_log(
        logger,
        action="config_change",
        user_id="system",
        change_type="init_test_users",
        users_created=created_count,
        result="success"
    )

    # Log test credentials
    logger.info("="*60)
    logger.info("TEST CREDENTIALS")
    logger.info("="*60)
    logger.info("Admin User", extra={
        "employee_id": "w00000001",
        "api_key": "sk-test-admin-key-1",
        "role": "admin"
    })
    logger.info("Regular Users", extra={
        "users": [
            {"employee_id": "w00000002", "api_key": "sk-test-user-key-1", "role": "user"},
            {"employee_id": "w00000003", "api_key": "sk-test-user-key-2", "role": "user"}
        ]
    })
    logger.info("="*60)


if __name__ == "__main__":
    init_users()
