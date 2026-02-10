#!/usr/bin/env python3
"""
验证 MySQL 数据库连接和数据
"""

import pymysql
import sys
import logging
import os
from pathlib import Path

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

# MySQL configuration
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': 'root',
    'database': 'skills',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def test_connection():
    """测试 MySQL 连接"""
    logger.info("="*60)
    logger.info("验证 MySQL 数据库")
    logger.info("="*60)

    try:
        # 连接到 MySQL
        logger.info("1. 测试数据库连接...")
        conn = pymysql.connect(**DB_CONFIG)
        logger.info("MySQL 连接成功!", extra={
            "host": f"{DB_CONFIG['host']}:{DB_CONFIG['port']}",
            "database": DB_CONFIG['database']
        })

        cursor = conn.cursor()

        # 检查表是否存在
        logger.info("2. 检查表结构...")
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        table_names = [list(table.values())[0] for table in tables]
        logger.info(f"找到 {len(tables)} 个表", extra={"table_count": len(tables), "tables": table_names})

        # 统计用户数据
        logger.info("3. 验证用户数据...")
        cursor.execute("SELECT COUNT(*) as count FROM users")
        user_count = cursor.fetchone()['count']
        logger.info(f"用户总数: {user_count}", extra={"user_count": user_count})

        cursor.execute("SELECT employee_id, role FROM users ORDER BY id LIMIT 5")
        users = cursor.fetchall()
        user_list = [{"employee_id": u['employee_id'], "role": u['role']} for u in users]
        logger.info("最新 5 个用户", extra={"users": user_list})

        # 验证特定用户
        logger.info("4. 验证测试账号 (w00545471)...")
        cursor.execute("SELECT employee_id, role FROM users WHERE employee_id = %s", ('w00545471',))
        test_user = cursor.fetchone()
        if test_user:
            logger.info("测试账号存在", extra={
                "employee_id": test_user['employee_id'],
                "role": test_user['role']
            })
        else:
            logger.warning("测试账号不存在!", extra={"employee_id": "w00545471"})

        # 统计其他数据
        logger.info("5. 验证其他数据...")
        cursor.execute("SELECT COUNT(*) as count FROM downloads")
        download_count = cursor.fetchone()['count']
        logger.info(f"下载记录: {download_count} 条", extra={"download_count": download_count})

        cursor.execute("SELECT COUNT(*) as count FROM skills")
        skill_count = cursor.fetchone()['count']
        logger.info(f"Skills: {skill_count} 条", extra={"skill_count": skill_count})

        cursor.close()
        conn.close()

        logger.info("="*60)
        logger.info("所有验证通过!")
        logger.info("="*60)
        logger.info("现在可以启动应用: conda activate a2a && python main.py")

        return True

    except Exception as e:
        logger.error(f"验证失败: {e}", exc_info=True, extra={"error": str(e)})
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
