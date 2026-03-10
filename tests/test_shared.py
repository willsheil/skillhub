"""
共享测试状态模块。

这个模块保存测试用户 ID 和角色，避免 conftest 双重加载问题。
conftest.py 和测试文件都应该从这个模块导入/设置状态。
"""

from database import get_connection

# 全局测试用户 ID - 用于认证覆盖
_test_user_id = None
_test_user_role = "user"


def get_test_user_id():
    """获取当前测试用户 ID。"""
    return _test_user_id


def get_test_user_role():
    """获取当前测试用户角色。"""
    return _test_user_role


def set_test_user_id(user_id: int, role: str = "user"):
    """设置当前测试用户 ID 和角色。"""
    global _test_user_id, _test_user_role
    _test_user_id = user_id
    _test_user_role = role


def reset_test_user():
    """重置测试用户状态。"""
    global _test_user_id, _test_user_role
    _test_user_id = None
    _test_user_role = "user"


def cleanup_test_data(prefix: str = "test-"):
    """清理测试数据。"""
    with get_connection() as conn:
        # 按外键依赖顺序删除
        conn.execute(f"DELETE FROM notifications WHERE related_skill_id IN (SELECT id FROM skills WHERE skill_name LIKE '{prefix}%')")
        conn.execute(f"DELETE FROM gitea_push_tasks WHERE skill_name LIKE '{prefix}%'")
        conn.execute(f"DELETE FROM downloads WHERE skill_name LIKE '{prefix}%'")
        conn.execute(f"DELETE FROM skills WHERE skill_name LIKE '{prefix}%'")
        conn.execute(f"DELETE FROM external_api_keys WHERE user_id IN (SELECT id FROM users WHERE employee_id LIKE '{prefix}%')")
        conn.execute(f"DELETE FROM users WHERE employee_id LIKE '{prefix}%'")
        conn.commit()
