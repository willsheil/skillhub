#!/usr/bin/env python3
"""
验证 MySQL 数据库连接和数据
"""

import pymysql
import sys

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
    print("="*60)
    print("验证 MySQL 数据库")
    print("="*60)
    print()

    try:
        # 连接到 MySQL
        print("1. 测试数据库连接...")
        conn = pymysql.connect(**DB_CONFIG)
        print("   ✓ MySQL 连接成功!")
        print(f"   主机: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print(f"   数据库: {DB_CONFIG['database']}")
        print()

        cursor = conn.cursor()

        # 检查表是否存在
        print("2. 检查表结构...")
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"   找到 {len(tables)} 个表:")
        for table in tables:
            table_name = list(table.values())[0]
            print(f"   - {table_name}")
        print()

        # 统计用户数据
        print("3. 验证用户数据...")
        cursor.execute("SELECT COUNT(*) as count FROM users")
        user_count = cursor.fetchone()['count']
        print(f"   用户总数: {user_count}")

        cursor.execute("SELECT employee_id, role FROM users ORDER BY id LIMIT 5")
        users = cursor.fetchall()
        print("   最新 5 个用户:")
        for user in users:
            print(f"   - {user['employee_id']:<15} | {user['role']:<10}")
        print()

        # 验证特定用户
        print("4. 验证测试账号 (w00545471)...")
        cursor.execute("SELECT employee_id, role FROM users WHERE employee_id = %s", ('w00545471',))
        test_user = cursor.fetchone()
        if test_user:
            print(f"   ✓ 测试账号存在")
            print(f"   - 工号: {test_user['employee_id']}")
            print(f"   - 角色: {test_user['role']}")
        else:
            print("   ✗ 测试账号不存在!")
        print()

        # 统计其他数据
        print("5. 验证其他数据...")
        cursor.execute("SELECT COUNT(*) as count FROM downloads")
        download_count = cursor.fetchone()['count']
        print(f"   下载记录: {download_count} 条")

        cursor.execute("SELECT COUNT(*) as count FROM skills")
        skill_count = cursor.fetchone()['count']
        print(f"   Skills: {skill_count} 条")
        print()

        cursor.close()
        conn.close()

        print("="*60)
        print("✓ 所有验证通过!")
        print("="*60)
        print()
        print("现在可以启动应用:")
        print("  conda activate a2a")
        print("  python main.py")
        print()
        return True

    except Exception as e:
        print(f"✗ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
