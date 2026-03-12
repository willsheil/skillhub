"""
Tests for database.py additional functions.
"""

import pytest
import sys
import os
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from database import (
    get_connection,
    search_skills,
    get_skills_count_by_status,
    create_skill_record,
    get_pending_skills
)
from conftest import create_test_user, create_test_skill_zip, cleanup_test_data


def unique_id():
    return uuid.uuid4().hex[:6]


class TestSkillQueries:
    """技能查询测试。"""

    def test_get_pending_skills(self):
        """测试获取待审批技能。"""
        skills = get_pending_skills()
        assert skills is not None
        assert isinstance(skills, list)

    def test_search_skills(self):
        """测试搜索技能。"""
        uid = unique_id()
        user_id = create_test_user(f"tss-{uid}", "user")
        skill_name = f"tss-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            conn.commit()

        skills = search_skills(skill_name)
        assert skills is not None
        assert isinstance(skills, list)

        cleanup_test_data("tss-")

    def test_search_skills_empty(self):
        """测试空搜索。"""
        skills = search_skills("")
        assert skills is not None

    def test_get_skills_count_by_status(self):
        """测试按状态获取技能数量。"""
        count = get_skills_count_by_status("approved")
        assert count is not None
        assert isinstance(count, int)
        assert count >= 0


class TestSkillRecordOperations:
    """技能记录操作测试。"""

    def test_create_skill_record(self):
        """测试创建技能记录。"""
        uid = unique_id()
        user_id = create_test_user(f"tcsr-{uid}", "user")
        skill_name = f"tcsr-skill-{uid}"

        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename="test.zip",
            uploader_id=user_id,
            status="pending",
            source_type="opensource"
        )

        assert skill_id is not None
        assert skill_id > 0

        cleanup_test_data("tcsr-")


class TestDatabaseConnection:
    """数据库连接测试。"""

    def test_get_connection_works(self):
        """测试获取连接工作。"""
        with get_connection() as conn:
            result = conn.execute("SELECT 1 as test").fetchone()
            assert result is not None
            assert result["test"] == 1

    def test_connection_context_manager(self):
        """测试连接上下文管理器。"""
        with get_connection() as conn:
            # Connection should be active
            assert conn is not None
            result = conn.execute("SELECT 1 as test").fetchone()
            assert result["test"] == 1

    def test_connection_query(self):
        """测试连接查询。"""
        with get_connection() as conn:
            result = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
            assert result is not None
            assert "cnt" in result


class TestUserOperations:
    """用户操作测试。"""

    def test_create_and_get_user(self):
        """测试创建和获取用户。"""
        uid = unique_id()
        emp_id = f"tcgu-{uid}"
        user_id = create_test_user(emp_id, "user")

        with get_connection() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE id = %s", (user_id,)
            ).fetchone()

        assert user is not None
        assert user["employee_id"] == emp_id

        cleanup_test_data("tcgu-")

    def test_update_user_last_login(self):
        """测试更新用户最后登录时间。"""
        uid = unique_id()
        user_id = create_test_user(f"tuull-{uid}", "user")

        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET last_login = %s WHERE id = %s",
                (datetime.now(), user_id)
            )
            conn.commit()

        with get_connection() as conn:
            user = conn.execute(
                "SELECT last_login FROM users WHERE id = %s", (user_id,)
            ).fetchone()

        assert user["last_login"] is not None

        cleanup_test_data("tuull-")


class TestSkillOperations:
    """技能操作测试。"""

    def test_insert_and_query_skill(self):
        """测试插入和查询技能。"""
        uid = unique_id()
        user_id = create_test_user(f"tiaqs-{uid}", "user")
        skill_name = f"tiaqs-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            conn.commit()

        with get_connection() as conn:
            skill = conn.execute(
                "SELECT * FROM skills WHERE skill_name = %s", (skill_name,)
            ).fetchone()

        assert skill is not None
        assert skill["skill_name"] == skill_name

        cleanup_test_data("tiaqs-")

    def test_update_skill_status(self):
        """测试更新技能状态。"""
        uid = unique_id()
        user_id = create_test_user(f"tuss-{uid}", "user")
        skill_name = f"tuss-skill-{uid}"

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "pending")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        with get_connection() as conn:
            conn.execute(
                "UPDATE skills SET status = %s WHERE id = %s", ("approved", skill_id)
            )
            conn.commit()

        with get_connection() as conn:
            skill = conn.execute(
                "SELECT status FROM skills WHERE id = %s", (skill_id,)
            ).fetchone()

        assert skill["status"] == "approved"

        cleanup_test_data("tuss-")

    def test_delete_skill(self):
        """测试删除技能。"""
        uid = unique_id()
        user_id = create_test_user(f"tds-{uid}", "user")
        skill_name = f"tds-skill-{uid}"

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.commit()

        with get_connection() as conn:
            skill = conn.execute(
                "SELECT * FROM skills WHERE id = %s", (skill_id,)
            ).fetchone()

        assert skill is None

        cleanup_test_data("tds-")


class TestDownloadOperations:
    """下载操作测试。"""

    def test_record_download(self):
        """测试记录下载。"""
        uid = unique_id()
        user_id = create_test_user(f"trd-{uid}", "user")
        skill_name = f"trd-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            conn.commit()

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO downloads (skill_name, version, filename, ip_address, user_agent, user_id) VALUES (%s, %s, %s, %s, %s, %s)",
                (skill_name, "1.0.0", "test.zip", "127.0.0.1", "test-agent", user_id)
            )
            conn.commit()

        with get_connection() as conn:
            download = conn.execute(
                "SELECT * FROM downloads WHERE skill_name = %s", (skill_name,)
            ).fetchone()

        assert download is not None

        cleanup_test_data("trd-")


class TestNotificationOperations:
    """通知操作测试。"""

    def test_create_notification(self):
        """测试创建通知。"""
        uid = unique_id()
        user_id = create_test_user(f"tcno-{uid}", "user")

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO notifications (user_id, type, title, content, is_read) VALUES (%s, %s, %s, %s, 0)",
                (user_id, "system", "Test", "Test content")
            )
            conn.commit()

        with get_connection() as conn:
            notif = conn.execute(
                "SELECT * FROM notifications WHERE user_id = %s", (user_id,)
            ).fetchone()

        assert notif is not None

        cleanup_test_data("tcno-")

    def test_mark_notification_read(self):
        """测试标记通知已读。"""
        uid = unique_id()
        user_id = create_test_user(f"tmnr-{uid}", "user")

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO notifications (user_id, type, title, content, is_read) VALUES (%s, %s, %s, %s, 0)",
                (user_id, "system", "Test", "Test content")
            )
            notif_id = cursor.lastrowid
            conn.commit()

        with get_connection() as conn:
            conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = %s", (notif_id,)
            )
            conn.commit()

        with get_connection() as conn:
            notif = conn.execute(
                "SELECT is_read FROM notifications WHERE id = %s", (notif_id,)
            ).fetchone()

        assert notif["is_read"] == 1

        cleanup_test_data("tmnr-")
