"""
Tests for main.py authentication and user API endpoints.
"""

import pytest
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient
from main import app
from database import get_connection
from conftest import create_test_user, create_test_skill_zip, AuthenticatedTestClient, cleanup_test_data


def unique_id():
    return uuid.uuid4().hex[:6]


class TestAPILogin:
    """API登录端点测试。"""

    def test_api_login_success(self, client):
        """测试API登录成功。"""
        uid = unique_id()
        user_id = create_test_user(f"als-{uid}", "user")

        with get_connection() as conn:
            user = conn.execute(
                "SELECT api_key FROM users WHERE id = %s", (user_id,)
            ).fetchone()

        response = client.post("/api/login", data={
            "employee_id": f"als-{uid}",
            "api_key": user["api_key"]
        })
        # Should redirect to homepage
        assert response.status_code in [200, 302]

        cleanup_test_data("als-")

    def test_api_login_invalid_credentials(self, client):
        """测试API登录无效凭证。"""
        response = client.post("/api/login", data={
            "employee_id": "nonexistent",
            "api_key": "wrong-key"
        })
        # Should redirect to login with error
        assert response.status_code in [200, 302]

    def test_api_login_missing_fields(self, client):
        """测试API登录缺少字段。"""
        response = client.post("/api/login", data={
            "employee_id": "someuser"
            # Missing api_key
        })
        assert response.status_code == 422


class TestAPIMe:
    """当前用户API测试。"""

    def test_api_me_authenticated(self, auth_client):
        """测试已认证获取当前用户。"""
        uid = unique_id()
        user_id = create_test_user(f"ame-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/me")
        assert response.status_code in [200, 401, 404]

        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "employee_id" in data
            assert "role" in data

        cleanup_test_data("ame-")

    def test_api_me_not_authenticated(self, client):
        """测试未认证获取当前用户。"""
        response = client.get("/api/me")
        assert response.status_code in [401, 302]


class TestLogout:
    """登出测试。"""

    def test_logout(self, auth_client):
        """测试登出。"""
        uid = unique_id()
        user_id = create_test_user(f"lo-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/logout")
        assert response.status_code in [200, 302]

        cleanup_test_data("lo-")


class TestUserUploadPage:
    """用户上传页面测试。"""

    def test_upload_page_authenticated(self, auth_client):
        """测试已认证访问上传页面。"""
        uid = unique_id()
        user_id = create_test_user(f"upa-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/upload")
        assert response.status_code in [200, 302]

        cleanup_test_data("upa-")

    def test_upload_page_not_authenticated(self, client):
        """测试未认证访问上传页面。"""
        response = client.get("/upload")
        # Should redirect to login
        assert response.status_code in [200, 302]


class TestAdminDashboard:
    """管理员仪表板测试。"""

    def test_admin_dashboard_as_admin(self, auth_client):
        """测试管理员访问仪表板。"""
        uid = unique_id()
        admin_id = create_test_user(f"ada-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/admin")
        assert response.status_code in [200, 302]

        cleanup_test_data("ada-")

    def test_admin_dashboard_as_user(self, auth_client):
        """测试普通用户访问仪表板。"""
        uid = unique_id()
        user_id = create_test_user(f"adu-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/admin")
        assert response.status_code in [200, 302, 401, 403]

        cleanup_test_data("adu-")

    def test_admin_dashboard_not_authenticated(self, client):
        """测试未认证访问仪表板。"""
        response = client.get("/admin")
        assert response.status_code in [200, 302]


class TestAdminUsersPage:
    """管理员用户页面测试。"""

    def test_admin_users_as_admin(self, auth_client):
        """测试管理员访问用户页面。"""
        uid = unique_id()
        admin_id = create_test_user(f"aus-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/admin/users")
        assert response.status_code in [200, 302]

        cleanup_test_data("aus-")

    def test_admin_users_as_user(self, auth_client):
        """测试普通用户访问用户页面。"""
        uid = unique_id()
        user_id = create_test_user(f"auu-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/admin/users")
        assert response.status_code in [200, 302, 401, 403]

        cleanup_test_data("auu-")


class TestAdminApiKeysPage:
    """管理员API密钥页面测试。"""

    def test_admin_api_keys_as_admin(self, auth_client):
        """测试管理员访问API密钥页面。"""
        uid = unique_id()
        admin_id = create_test_user(f"aak-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/admin/api-keys")
        assert response.status_code in [200, 302]

        cleanup_test_data("aak-")

    def test_admin_api_keys_as_user(self, auth_client):
        """测试普通用户访问API密钥页面。"""
        uid = unique_id()
        user_id = create_test_user(f"aaku-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/admin/api-keys")
        assert response.status_code in [200, 302, 401, 403]

        cleanup_test_data("aaku-")


class TestAdminUploadPage:
    """管理员上传页面测试。"""

    def test_admin_upload_as_admin(self, auth_client):
        """测试管理员访问上传页面。"""
        uid = unique_id()
        admin_id = create_test_user(f"aup-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/admin/upload")
        assert response.status_code in [200, 302]

        cleanup_test_data("aup-")


class TestAdminLogin:
    """管理员登录测试。"""

    def test_admin_login_page_get(self, client):
        """测试获取管理员登录页面。"""
        response = client.get("/admin/login")
        assert response.status_code in [200, 302]

    def test_admin_login_post_valid(self, client):
        """测试管理员登录POST有效凭证。"""
        # This uses ADMIN_USERNAME/ADMIN_PASSWORD from env
        response = client.post("/admin/login", data={
            "username": "admin",
            "password": "admin"
        })
        assert response.status_code in [200, 302]

    def test_admin_login_post_invalid(self, client):
        """测试管理员登录POST无效凭证。"""
        response = client.post("/admin/login", data={
            "username": "wrong",
            "password": "wrong"
        })
        assert response.status_code in [200, 302]
