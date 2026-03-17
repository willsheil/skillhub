#!/usr/bin/env python3
"""
Ensure only 'admin' is the admin user, all others are regular users.
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

def fix_admin_role():
    """Fix user roles so only 'admin' is admin."""
    with get_connection() as conn:
        # Set all users to 'user' role except 'admin'
        conn.execute(
            "UPDATE users SET role = 'user' WHERE employee_id != ?",
            ('admin',)
        )
        logger.info("Set all non-admin users to 'user' role")

        # Ensure admin user exists and has admin role
        admin_user = conn.execute(
            "SELECT * FROM users WHERE employee_id = 'admin'"
        ).fetchone()

        if not admin_user:
            # Create admin user if doesn't exist
            conn.execute(
                "INSERT INTO users (employee_id, api_key, role) VALUES (?, ?, ?)",
                ('admin', 'admin', 'admin')
            )
            logger.info("Created new admin user", extra={"employee_id": "admin", "role": "admin"})

        conn.commit()

        # Display all users
        users = conn.execute("SELECT employee_id, api_key, role FROM users ORDER BY employee_id").fetchall()
        user_list = [{"employee_id": u[0], "role": u[2]} for u in users]
        logger.info("All users in database", extra={"users": user_list})

        # 记录审计日志
        audit_log(
            logger,
            action="config_change",
            user_id="system",
            change_type="fix_admin_role",
            result="success"
        )

if __name__ == "__main__":
    fix_admin_role()
