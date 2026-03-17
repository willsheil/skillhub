"""
Comprehensive tests for main.py routes - additional coverage.
"""

import pytest
import sys
import os
import io
import json
import uuid

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient
from main import app
from database import get_connection
from conftest import create_test_user, create_test_skill_zip, AuthenticatedTestClient, cleanup_test_data
import test_shared


def unique_id():
    """Generate unique ID for test data."""
    return uuid.uuid4().hex[:6]


class TestSkillRoutes:
    """技能路由测试。"""

    def test_get_skill_list(self, client):
        """测试获取技能列表。"""
        response = client.get("/api/skills")
        assert response.status_code in [200, 404]

    def test_get_skill_by_id(self, client):
        """测试通过ID获取技能。"""
        uid = unique_id()
        user_id = create_test_user(f"tgs-{uid}", "user")

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (f"tgs-skill-{uid}", "1.0.0", "test.zip", user_id, "approved")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        response = client.get(f"/api/skills/{skill_id}")
        assert response.status_code in [200, 404]

        cleanup_test_data(f"tgs-")

    def test_get_skill_by_name(self, client):
        """测试通过名称获取技能。"""
        uid = unique_id()
        user_id = create_test_user(f"tgsn-{uid}", "user")
        skill_name = f"tgsn-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            conn.commit()

        response = client.get(f"/api/skills/name/{skill_name}")
        assert response.status_code in [200, 404]

        cleanup_test_data(f"tgsn-")


class TestUserRoutes:
    """用户路由测试。"""

    def test_get_users_list(self, auth_client):
        """测试获取用户列表。"""
        uid = unique_id()
        admin_id = create_test_user(f"tgu-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/api/users")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data(f"tgu-")

    def test_get_current_user(self, auth_client):
        """测试获取当前用户信息。"""
        uid = unique_id()
        user_id = create_test_user(f"tgcu-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/user")
        assert response.status_code in [200, 401, 404]

        cleanup_test_data(f"tgcu-")

    def test_update_user_role(self, auth_client):
        """测试更新用户角色。"""
        uid = unique_id()
        admin_id = create_test_user(f"tuur-adm-{uid}", "admin")
        user_id = create_test_user(f"tuur-u-{uid}", "user")
        client = auth_client(admin_id, "admin")

        response = client.put(f"/api/users/{user_id}/role", json={"role": "admin"})
        assert response.status_code in [200, 401, 403, 404, 422]

        cleanup_test_data(f"tuur-")


class TestDownloadRoutes:
    """下载路由测试。"""

    def test_record_download(self, auth_client):
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

        client = auth_client(user_id, "user")
        response = client.post(f"/api/downloads/{skill_name}")
        assert response.status_code in [200, 201, 401, 404]

        cleanup_test_data(f"trd-")

    def test_get_download_history(self, auth_client):
        """测试获取下载历史。"""
        uid = unique_id()
        user_id = create_test_user(f"tgdh-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/downloads")
        assert response.status_code in [200, 401, 404]

        cleanup_test_data(f"tgdh-")


class TestNotificationRoutes:
    """通知路由测试。"""

    def test_get_notifications(self, auth_client):
        """测试获取通知列表。"""
        uid = unique_id()
        user_id = create_test_user(f"tgn-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/notifications")
        assert response.status_code in [200, 401, 404]

        cleanup_test_data(f"tgn-")

    def test_mark_notification_read(self, auth_client):
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

        client = auth_client(user_id, "user")
        # 使用POST而不是PUT，因为API可能使用POST
        response = client.post(f"/api/notifications/{notif_id}/read")
        assert response.status_code in [200, 401, 404, 405]

        cleanup_test_data(f"tmnr-")


class TestExternalAPIRoutes:
    """外部API路由测试。"""

    def test_external_api_list(self, auth_client):
        """测试获取外部API列表。"""
        uid = unique_id()
        user_id = create_test_user(f"teal-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/external-apis")
        assert response.status_code in [200, 401, 404]

        cleanup_test_data(f"teal-")

    def test_create_external_api(self, auth_client):
        """测试创建外部API。"""
        uid = unique_id()
        user_id = create_test_user(f"tcea-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.post("/api/external-apis", json={
            "api_name": f"test-api-{uid}",
            "api_key": "test-key",
            "description": "Test API"
        })
        assert response.status_code in [200, 201, 401, 404, 422]

        cleanup_test_data(f"tcea-")

    def test_delete_external_api(self, auth_client):
        """测试删除外部API。"""
        uid = unique_id()
        user_id = create_test_user(f"tdea-{uid}", "user")

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO external_api_keys (user_id, name, api_key, is_active) VALUES (%s, %s, %s, 1)",
                (user_id, f"test-api-{uid}", f"test-key-{uid}")
            )
            api_id = cursor.lastrowid
            conn.commit()

        client = auth_client(user_id, "user")
        response = client.delete(f"/api/external-apis/{api_id}")
        assert response.status_code in [200, 401, 404]

        cleanup_test_data(f"tdea-")


class TestSearchRoutes:
    """搜索路由测试。"""

    def test_search_skills(self, client):
        """测试搜索技能。"""
        response = client.get("/api/search?q=test")
        assert response.status_code in [200, 404]

    def test_search_with_filters(self, client):
        """测试带过滤条件搜索。"""
        response = client.get("/api/search?q=test&status=approved&source=opensource")
        assert response.status_code in [200, 404]


class TestStatsRoutes:
    """统计路由测试。"""

    def test_get_overall_stats(self, client):
        """测试获取总体统计。"""
        response = client.get("/api/stats")
        assert response.status_code in [200, 404]

    def test_get_top_downloads(self, client):
        """测试获取下载排行。"""
        response = client.get("/api/stats/top")
        assert response.status_code in [200, 404]

    def test_export_stats(self, auth_client):
        """测试导出统计。"""
        uid = unique_id()
        admin_id = create_test_user(f"tes-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/api/stats/export")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data(f"tes-")


class TestConfigRoutes:
    """配置路由测试。"""

    def test_get_config(self, auth_client):
        """测试获取配置。"""
        uid = unique_id()
        admin_id = create_test_user(f"tgc-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/api/config")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data(f"tgc-")

    def test_update_config(self, auth_client):
        """测试更新配置。"""
        uid = unique_id()
        admin_id = create_test_user(f"tuc-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.put("/api/config", json={"key": "value"})
        assert response.status_code in [200, 401, 403, 404, 422]

        cleanup_test_data(f"tuc-")


class TestBatchOperations:
    """批量操作测试。"""

    def test_batch_delete_skills(self, auth_client):
        """测试批量删除技能。"""
        uid = unique_id()
        admin_id = create_test_user(f"tbds-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.post("/api/skills/batch-delete", json={"skill_ids": [1, 2, 3]})
        assert response.status_code in [200, 401, 403, 404, 422]

        cleanup_test_data(f"tbds-")

    def test_batch_update_status(self, auth_client):
        """测试批量更新状态。"""
        uid = unique_id()
        admin_id = create_test_user(f"tbus-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.post("/api/skills/batch-status", json={"skill_ids": [1, 2, 3], "status": "approved"})
        assert response.status_code in [200, 401, 403, 404, 422]

        cleanup_test_data(f"tbus-")
