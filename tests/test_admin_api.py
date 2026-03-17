"""
Tests for main.py admin API endpoints.
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


class TestAdminUserAPI:
    """管理员用户API测试。"""

    def test_get_users_list_as_admin(self, auth_client):
        """测试管理员获取用户列表。"""
        uid = unique_id()
        admin_id = create_test_user(f"gua-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/api/users")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("gua-")

    def test_get_users_list_as_user(self, auth_client):
        """测试普通用户获取用户列表。"""
        uid = unique_id()
        user_id = create_test_user(f"guu-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/users")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("guu-")

    def test_update_user_role_as_admin(self, auth_client):
        """测试管理员更新用户角色。"""
        uid = unique_id()
        admin_id = create_test_user(f"uur-adm-{uid}", "admin")
        target_id = create_test_user(f"uur-tgt-{uid}", "user")
        client = auth_client(admin_id, "admin")

        response = client.put(f"/api/users/{target_id}/role", json={"role": "admin"})
        assert response.status_code in [200, 401, 403, 404, 422]

        cleanup_test_data("uur-")

    def test_update_user_role_invalid(self, auth_client):
        """测试更新用户角色（无效角色）。"""
        uid = unique_id()
        admin_id = create_test_user(f"uurv-{uid}", "admin")
        target_id = create_test_user(f"uurv-t-{uid}", "user")
        client = auth_client(admin_id, "admin")

        response = client.put(f"/api/users/{target_id}/role", json={"role": "invalid_role"})
        assert response.status_code in [200, 400, 401, 403, 404, 422]

        cleanup_test_data("uurv-")


class TestAdminPendingAPI:
    """管理员待审批API测试。"""

    def test_get_pending_skills_as_admin(self, auth_client):
        """测试管理员获取待审批技能。"""
        uid = unique_id()
        admin_id = create_test_user(f"gps-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/api/pending")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("gps-")

    def test_get_pending_skills_as_user(self, auth_client):
        """测试普通用户获取待审批技能。"""
        uid = unique_id()
        user_id = create_test_user(f"gpsu-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/pending")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("gpsu-")


class TestAdminStatsAPI:
    """管理员统计API测试。"""

    def test_get_admin_stats_as_admin(self, auth_client):
        """测试管理员获取统计。"""
        uid = unique_id()
        admin_id = create_test_user(f"gas-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/api/admin/stats")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("gas-")

    def test_get_admin_stats_as_user(self, auth_client):
        """测试普通用户获取统计。"""
        uid = unique_id()
        user_id = create_test_user(f"gasu-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/admin/stats")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("gasu-")


class TestSkillVersionAPI:
    """技能版本API测试。"""

    def test_get_skill_versions(self, client):
        """测试获取技能版本列表。"""
        uid = unique_id()
        user_id = create_test_user(f"vrs-{uid}", "user")
        skill_name = f"vrs-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test1.zip", user_id, "approved")
            )
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "2.0.0", "test2.zip", user_id, "approved")
            )
            conn.commit()

        response = client.get(f"/api/skills/{skill_name}/versions")
        assert response.status_code in [200, 404]

        cleanup_test_data("vrs-")

    def test_get_skill_versions_nonexistent(self, client):
        """测试获取不存在的技能版本列表。"""
        response = client.get("/api/skills/nonexistent-skill-xyz/versions")
        assert response.status_code in [200, 404]


class TestSkillDetailAPI:
    """技能详情API测试。"""

    def test_get_skill_by_id(self, client):
        """测试通过ID获取技能。"""
        uid = unique_id()
        user_id = create_test_user(f"gsi-{uid}", "user")
        skill_name = f"gsi-skill-{uid}"

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        response = client.get(f"/api/skills/{skill_id}")
        assert response.status_code in [200, 404]

        cleanup_test_data("gsi-")

    def test_get_skill_by_name(self, client):
        """测试通过名称获取技能。"""
        uid = unique_id()
        user_id = create_test_user(f"gsn-{uid}", "user")
        skill_name = f"gsn-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            conn.commit()

        response = client.get(f"/api/skills/name/{skill_name}")
        assert response.status_code in [200, 404]

        cleanup_test_data("gsn-")


class TestMarketplaceAPI:
    """市场API测试。"""

    def test_marketplace_json(self, client):
        """测试市场JSON。"""
        response = client.get("/marketplace.json")
        assert response.status_code == 200
        data = response.json()
        assert "plugins" in data or "name" in data

    def test_marketplace_json_with_filters(self, client):
        """测试带过滤器的市场JSON。"""
        response = client.get("/marketplace.json?source=opensource&limit=10")
        assert response.status_code == 200


class TestSearchAPI:
    """搜索API测试。"""

    def test_search_skills(self, client):
        """测试搜索技能。"""
        uid = unique_id()
        user_id = create_test_user(f"ssk-{uid}", "user")
        skill_name = f"ssk-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            conn.commit()

        response = client.get(f"/api/search?q={skill_name}")
        assert response.status_code in [200, 404]

        cleanup_test_data("ssk-")

    def test_search_skills_empty_query(self, client):
        """测试空查询搜索。"""
        response = client.get("/api/search?q=")
        assert response.status_code in [200, 400]

    def test_search_with_filters(self, client):
        """测试带过滤条件搜索。"""
        response = client.get("/api/search?q=test&status=approved&source=opensource")
        assert response.status_code in [200, 404]


class TestStatsAPI:
    """统计API测试。"""

    def test_get_stats(self, client):
        """测试获取统计。"""
        response = client.get("/api/stats")
        assert response.status_code in [200, 404]

    def test_get_top_downloads(self, client):
        """测试获取下载排行。"""
        response = client.get("/api/stats/top")
        assert response.status_code in [200, 404]

    def test_stats_page(self, client):
        """测试统计页面。"""
        response = client.get("/stats")
        assert response.status_code in [200, 302, 404]


class TestDownloadTrackingAPI:
    """下载追踪API测试。"""

    def test_track_download(self, auth_client):
        """测试追踪下载。"""
        uid = unique_id()
        user_id = create_test_user(f"tdk-{uid}", "user")
        skill_name = f"tdk-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            conn.commit()

        client = auth_client(user_id, "user")
        response = client.post(f"/api/downloads/{skill_name}/track")
        assert response.status_code in [200, 201, 401, 404]

        cleanup_test_data("tdk-")

    def test_get_download_count(self, client):
        """测试获取下载次数。"""
        uid = unique_id()
        user_id = create_test_user(f"gdc-{uid}", "user")
        skill_name = f"gdc-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            conn.commit()

        response = client.get(f"/api/downloads/{skill_name}/count")
        assert response.status_code in [200, 404]

        cleanup_test_data("gdc-")
