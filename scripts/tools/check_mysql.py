#!/usr/bin/env python3
"""
Check MySQL connection and create database if needed.
"""

import pymysql
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

try:
    # Connect to MySQL server (without database specified)
    conn = pymysql.connect(
        host='127.0.0.1',
        port=3306,
        user='root',
        password='root',
        charset='utf8mb4'
    )
    logger.info("Connected to MySQL server successfully!", extra={
        "host": "127.0.0.1",
        "port": 3306
    })

    # Check if skills database exists
    cursor = conn.cursor()
    cursor.execute("SHOW DATABASES LIKE 'skills'")
    result = cursor.fetchone()

    if result:
        logger.info("Database 'skills' already exists.")
    else:
        logger.info("Creating database 'skills'...")
        cursor.execute("CREATE DATABASE skills CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        logger.info("Database 'skills' created successfully!", extra={
            "database": "skills",
            "charset": "utf8mb4"
        })

    cursor.close()
    conn.close()

except Exception as e:
    logger.error(f"Error connecting to MySQL: {e}", exc_info=True, extra={
        "error": str(e),
        "host": "127.0.0.1",
        "port": 3306,
        "user": "root"
    })
    logger.info("Please make sure MySQL server is running on 127.0.0.1 with username 'root' and password 'root'")
