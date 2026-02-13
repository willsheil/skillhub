#!/usr/bin/env python3
import logging
import os

# 导入日志配置
from logging_config import setup_logging

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

with get_connection() as conn:
    user = conn.execute('SELECT * FROM users WHERE employee_id = ?', ('w00545471',)).fetchone()
    if user:
        logger.info("User found", extra={
            "user_id": user[0],
            "employee_id": user[1],
            "role": user[3],
            "created_at": str(user[4]),
            "last_login": str(user[5]) if user[5] else None
        })
    else:
        logger.warning("User not found", extra={"employee_id": "w00545471"})
