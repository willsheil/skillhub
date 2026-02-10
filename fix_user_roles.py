#!/usr/bin/env python3
"""
Update user roles: w00545471 should be a regular user, admin should be the only admin.
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

def update_user_roles():
    """Update user roles correctly."""
    with get_connection() as conn:
        # Update w00545471 to regular user
        conn.execute(
            "UPDATE users SET role = 'user' WHERE employee_id = ?",
            ('w00545471',)
        )
        logger.info("Updated w00545471 to regular user", extra={"employee_id": "w00545471", "new_role": "user"})

        # Check if admin user exists
        admin_user = conn.execute(
            "SELECT * FROM users WHERE employee_id = 'admin'"
        ).fetchone()

        if admin_user:
            # Update admin user to ensure role is admin
            conn.execute(
                "UPDATE users SET role = 'admin' WHERE employee_id = 'admin'"
            )
            logger.info(f"Updated admin user", extra={"user_id": admin_user[0], "employee_id": "admin"})
        else:
            # Create admin user if doesn't exist
            conn.execute(
                "INSERT INTO users (employee_id, api_key, role) VALUES (?, ?, ?)",
                ('admin', 'admin', 'admin')
            )
            logger.info("Created new admin user", extra={"employee_id": "admin", "role": "admin"})

        conn.commit()

        # Display all users
        users = conn.execute("SELECT employee_id, role FROM users").fetchall()
        user_list = [{"employee_id": u[0], "role": u[1]} for u in users]
        logger.info("All users in database", extra={"users": user_list})

        # 记录审计日志
        audit_log(
            logger,
            action="config_change",
            user_id="system",
            change_type="user_roles_update",
            result="success"
        )

if __name__ == "__main__":
    update_user_roles()
