#!/usr/bin/env python3
"""
Add a test user to the database.
"""

import logging
import os

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

from database import get_connection

def add_user():
    """Add test user to database."""
    with get_connection() as conn:
        # Check if user already exists
        existing = conn.execute(
            "SELECT id FROM users WHERE employee_id = ?",
            ('w00545471',)
        ).fetchone()

        if existing:
            logger.info(f"User already exists", extra={
                "employee_id": "w00545471",
                "user_id": existing[0]
            })
            return

        # Insert new user
        conn.execute(
            "INSERT INTO users (employee_id, api_key, role) VALUES (?, ?, ?)",
            ('w00545471', 'sk-123', 'admin')
        )
        conn.commit()

        logger.info("User added successfully!", extra={
            "employee_id": "w00545471",
            "role": "admin"
        })

        # 记录审计日志
        audit_log(
            logger,
            action="user_create",
            user_id="system",
            employee_id="w00545471",
            role="admin",
            result="success"
        )

if __name__ == "__main__":
    add_user()
