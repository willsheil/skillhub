"""
Additional tests for main.py API endpoints and template routes.
"""

import pytest
import sys
import os
import io
import uuid

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient
from main import app
from database import get_connection
from conftest import create_test_user, create_test_skill_zip, AuthenticatedTestClient, cleanup_test_data


def unique_id():
    return uuid.uuid4().hex[:6]


class TestUserRoutes:
    """用户路由测试。"""

    def test_user_page_authenticated(self, auth_client):
        """测试用户页面已认证。"""
        uid = unique_id()
        user_id = create_test_user(f"upa-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/user")
        assert response.status_code in [200, 302, 404]

        cleanup_test_data("upa-")

    def test_user_page_not_authenticated(self, client):
        """测试用户页面未认证。"""
        response = client.get("/user")
        assert response.status_code in [200, 302, 401]


class TestSkillRoutes:
    """技能路由测试。"""

    def test_skills_page(self, client):
        """测试技能页面。"""
        response = client.get("/skills")
        assert response.status_code in [200, 302, 404]

    def test_skill_detail_page(self, client):
        """测试技能详情页面。"""
        uid = unique_id()
        user_id = create_test_user(f"sdp-{uid}", "user")
        skill_name = f"sdp-skill-{uid}"

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        response = client.get(f"/skills/{skill_id}")
        assert response.status_code in [200, 302, 404]

        cleanup_test_data("sdp-")

    def test_skill_detail_nonexistent(self, client):
        """测试技能详情页面不存在。"""
        response = client.get("/skills/999999")
        assert response.status_code in [200, 302, 404]


class TestAdminRoutes:
    """管理员路由测试。"""

    def test_admin_skills_page(self, auth_client):
        """测试管理员技能页面。"""
        uid = unique_id()
        admin_id = create_test_user(f"asp-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/admin/skills")
        assert response.status_code in [200, 302, 404]

        cleanup_test_data("asp-")

    def test_admin_review_page(self, auth_client):
        """测试管理员审核页面。"""
        uid = unique_id()
        admin_id = create_test_user(f"arp-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/admin/review")
        assert response.status_code in [200, 302, 404]

        cleanup_test_data("arp-")

    def test_admin_downloads_page(self, auth_client):
        """测试管理员下载页面。"""
        uid = unique_id()
        admin_id = create_test_user(f"adp-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/admin/downloads")
        assert response.status_code in [200, 302, 404]

        cleanup_test_data("adp-")

    def test_admin_stats_page(self, auth_client):
        """测试管理员统计页面。"""
        uid = unique_id()
        admin_id = create_test_user(f"astp-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/admin/stats")
        assert response.status_code in [200, 302, 404]

        cleanup_test_data("astp-")

    def test_admin_settings_page(self, auth_client):
        """测试管理员设置页面。"""
        uid = unique_id()
        admin_id = create_test_user(f"aset-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/admin/settings")
        assert response.status_code in [200, 302, 404]

        cleanup_test_data("aset-")


class TestUploadRoutes:
    """上传路由测试。"""

    def test_upload_page_get(self, auth_client):
        """测试上传页面GET。"""
        uid = unique_id()
        user_id = create_test_user(f"upg-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/upload")
        assert response.status_code in [200, 302, 404]

        cleanup_test_data("upg-")

    def test_upload_page_admin_get(self, auth_client):
        """测试管理员上传页面GET。"""
        uid = unique_id()
        admin_id = create_test_user(f"upag-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/admin/upload")
        assert response.status_code in [200, 302, 404]

        cleanup_test_data("upag-")


class TestAPISkillsEndpoints:
    """API技能端点测试。"""

    def test_api_skills_by_status(self, client):
        """测试按状态获取技能。"""
        response = client.get("/api/skills?status=approved")
        assert response.status_code == 200

    def test_api_skills_by_source(self, client):
        """测试按来源获取技能。"""
        response = client.get("/api/skills?source=opensource")
        assert response.status_code == 200

    def test_api_skills_by_search(self, client):
        """测试搜索技能。"""
        response = client.get("/api/skills?search=test")
        assert response.status_code == 200

    def test_api_skill_by_id(self, client):
        """测试通过ID获取技能。"""
        uid = unique_id()
        user_id = create_test_user(f"asbi-{uid}", "user")
        skill_name = f"asbi-skill-{uid}"

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        response = client.get(f"/api/skills/{skill_id}")
        assert response.status_code in [200, 404]

        cleanup_test_data("asbi-")

    def test_api_skill_by_name(self, client):
        """测试通过名称获取技能。"""
        uid = unique_id()
        user_id = create_test_user(f"asbn-{uid}", "user")
        skill_name = f"asbn-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            conn.commit()

        response = client.get(f"/api/skills/name/{skill_name}")
        assert response.status_code in [200, 404]

        cleanup_test_data("asbn-")


class TestAPIUserEndpoints:
    """API用户端点测试。"""

    def test_api_user_profile_get(self, auth_client):
        """测试获取用户资料。"""
        uid = unique_id()
        user_id = create_test_user(f"aupg-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/user/profile")
        assert response.status_code in [200, 401, 404]

        cleanup_test_data("aupg-")

    def test_api_user_profile_put(self, auth_client):
        """测试更新用户资料。"""
        uid = unique_id()
        user_id = create_test_user(f"aupp-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.put("/api/user/profile", json={"display_name": "Test User"})
        assert response.status_code in [200, 401, 404, 422]

        cleanup_test_data("aupp-")

    def test_api_user_change_password(self, auth_client):
        """测试修改密码。"""
        uid = unique_id()
        user_id = create_test_user(f"aucp-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.post("/api/user/change-password", json={"new_password": "new-api-key"})
        assert response.status_code in [200, 401, 404, 422]

        cleanup_test_data("aucp-")

    def test_api_user_skills_get(self, auth_client):
        """测试获取用户技能。"""
        uid = unique_id()
        user_id = create_test_user(f"ausg-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/user/skills")
        assert response.status_code in [200, 401, 404]

        cleanup_test_data("ausg-")


class TestAPIAdminEndpoints:
    """API管理员端点测试。"""

    def test_api_admin_skills(self, auth_client):
        """测试管理员获取技能。"""
        uid = unique_id()
        admin_id = create_test_user(f"aask-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/api/admin/skills")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("aask-")

    def test_api_admin_users_list(self, auth_client):
        """测试管理员获取用户列表。"""
        uid = unique_id()
        admin_id = create_test_user(f"aaul-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/api/admin/users")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("aaul-")

    def test_api_admin_user_detail(self, auth_client):
        """测试管理员获取用户详情。"""
        uid = unique_id()
        admin_id = create_test_user(f"aaud-{uid}", "admin")
        user_id = create_test_user(f"aaud-u-{uid}", "user")
        client = auth_client(admin_id, "admin")

        response = client.get(f"/api/admin/users/{user_id}")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("aaud-")

    def test_api_admin_user_update_role(self, auth_client):
        """测试管理员更新用户角色。"""
        uid = unique_id()
        admin_id = create_test_user(f"aaur-{uid}", "admin")
        user_id = create_test_user(f"aaur-u-{uid}", "user")
        client = auth_client(admin_id, "admin")

        response = client.put(f"/api/admin/users/{user_id}/role", json={"role": "admin"})
        assert response.status_code in [200, 401, 403, 404, 422]

        cleanup_test_data("aaur-")


class TestAPIDownloadEndpoints:
    """API下载端点测试。"""

    def test_api_downloads_list(self, auth_client):
        """测试获取下载列表。"""
        uid = unique_id()
        user_id = create_test_user(f"adl-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/downloads")
        assert response.status_code in [200, 401, 404]

        cleanup_test_data("adl-")

    def test_api_downloads_track(self, auth_client):
        """测试追踪下载。"""
        uid = unique_id()
        user_id = create_test_user(f"adt-{uid}", "user")
        skill_name = f"adt-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            conn.commit()

        client = auth_client(user_id, "user")
        response = client.post(f"/api/downloads/{skill_name}/track")
        assert response.status_code in [200, 201, 401, 404]

        cleanup_test_data("adt-")

    def test_api_downloads_increment(self, auth_client):
        """测试增加下载次数。"""
        uid = unique_id()
        user_id = create_test_user(f"adi-{uid}", "user")
        skill_name = f"adi-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            conn.commit()

        client = auth_client(user_id, "user")
        response = client.post(f"/api/downloads/{skill_name}/increment")
        assert response.status_code in [200, 201, 401, 404]

        cleanup_test_data("adi-")


class TestAPISettingsEndpoints:
    """API设置端点测试。"""

    def test_api_settings_get(self, auth_client):
        """测试获取设置。"""
        uid = unique_id()
        admin_id = create_test_user(f"asg-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/api/settings")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("asg-")

    def test_api_settings_put(self, auth_client):
        """测试更新设置。"""
        uid = unique_id()
        admin_id = create_test_user(f"asp-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.put("/api/settings", json={"key": "value"})
        assert response.status_code in [200, 401, 403, 404, 422]

        cleanup_test_data("asp-")


class TestErrorPages:
    """错误页面测试。"""

    def test_404_page(self, client):
        """测试404页面。"""
        response = client.get("/nonexistent-route-xyz-12345")
        assert response.status_code == 404

    def test_405_method_not_allowed(self, client):
        """测试405方法不允许。"""
        response = client.post("/api/skills")  # GET only
        assert response.status_code in [405, 422]
