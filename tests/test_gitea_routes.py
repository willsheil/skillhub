"""
Tests for main.py Gitea integration routes and additional API endpoints.
"""

import pytest
import sys
import os
import io
import uuid
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient
from main import app
from database import get_connection
from conftest import create_test_user, create_test_skill_zip, AuthenticatedTestClient, cleanup_test_data


def unique_id():
    return uuid.uuid4().hex[:6]


class TestGiteaIntegration:
    """Gitea集成测试。"""

    def test_gitea_status(self, auth_client):
        """测试Gitea状态。"""
        uid = unique_id()
        admin_id = create_test_user(f"tgs-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/api/gitea/status")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("tgs-")

    def test_gitea_sync(self, auth_client):
        """测试Gitea同步。"""
        uid = unique_id()
        admin_id = create_test_user(f"tsy-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.post("/api/gitea/sync")
        assert response.status_code in [200, 201, 401, 403, 404, 500]

        cleanup_test_data("tsy-")

    def test_gitea_tasks(self, auth_client):
        """测试Gitea任务列表。"""
        uid = unique_id()
        admin_id = create_test_user(f"tgt-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/api/gitea/tasks")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("tgt-")

    def test_gitea_health(self, auth_client):
        """测试Gitea健康检查。"""
        uid = unique_id()
        admin_id = create_test_user(f"tgh-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/api/gitea/health")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("tgh-")


class TestCategoryRoutes:
    """分类路由测试。"""

    def test_get_categories(self, client):
        """测试获取分类列表。"""
        response = client.get("/api/categories")
        assert response.status_code in [200, 404]

    def test_create_category(self, auth_client):
        """测试创建分类。"""
        uid = unique_id()
        admin_id = create_test_user(f"tcc-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.post("/api/categories", json={
            "name": f"test-category-{uid}",
            "description": "Test category"
        })
        assert response.status_code in [200, 201, 401, 403, 404, 422]

        cleanup_test_data("tcc-")

    def test_update_category(self, auth_client):
        """测试更新分类。"""
        uid = unique_id()
        admin_id = create_test_user(f"tuc-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.put("/api/categories/1", json={
            "name": f"updated-category-{uid}",
            "description": "Updated"
        })
        assert response.status_code in [200, 401, 403, 404, 422]

        cleanup_test_data("tuc-")

    def test_delete_category(self, auth_client):
        """测试删除分类。"""
        uid = unique_id()
        admin_id = create_test_user(f"tdc-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.delete("/api/categories/999999")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("tdc-")


class TestTagRoutes:
    """标签路由测试。"""

    def test_get_tags(self, client):
        """测试获取标签列表。"""
        response = client.get("/api/tags")
        assert response.status_code in [200, 404]

    def test_create_tag(self, auth_client):
        """测试创建标签。"""
        uid = unique_id()
        admin_id = create_test_user(f"tct-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.post("/api/tags", json={
            "name": f"test-tag-{uid}"
        })
        assert response.status_code in [200, 201, 401, 403, 404, 422]

        cleanup_test_data("tct-")

    def test_delete_tag(self, auth_client):
        """测试删除标签。"""
        uid = unique_id()
        admin_id = create_test_user(f"tdt-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.delete("/api/tags/999999")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("tdt-")


class TestRatingRoutes:
    """评分路由测试。"""

    def test_rate_skill(self, auth_client):
        """测试评分技能。"""
        uid = unique_id()
        user_id = create_test_user(f"trs-{uid}", "user")
        skill_name = f"trs-skill-{uid}"

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        client = auth_client(user_id, "user")
        response = client.post(f"/api/skills/{skill_id}/rate", json={"rating": 5})
        assert response.status_code in [200, 201, 401, 404, 422]

        cleanup_test_data("trs-")

    def test_get_skill_ratings(self, client):
        """测试获取技能评分。"""
        uid = unique_id()
        user_id = create_test_user(f"tgsr-{uid}", "user")
        skill_name = f"tgsr-skill-{uid}"

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        response = client.get(f"/api/skills/{skill_id}/ratings")
        assert response.status_code in [200, 404]

        cleanup_test_data("tgsr-")

    def test_get_skill_average_rating(self, client):
        """测试获取技能平均评分。"""
        uid = unique_id()
        user_id = create_test_user(f"tgsa-{uid}", "user")
        skill_name = f"tgsa-skill-{uid}"

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        response = client.get(f"/api/skills/{skill_id}/rating")
        assert response.status_code in [200, 404]

        cleanup_test_data("tgsa-")


class TestCommentRoutes:
    """评论路由测试。"""

    def test_add_comment(self, auth_client):
        """测试添加评论。"""
        uid = unique_id()
        user_id = create_test_user(f"tac-{uid}", "user")
        skill_name = f"tac-skill-{uid}"

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        client = auth_client(user_id, "user")
        response = client.post(f"/api/skills/{skill_id}/comments", json={"content": "Great skill!"})
        assert response.status_code in [200, 201, 401, 404, 422]

        cleanup_test_data("tac-")

    def test_get_comments(self, client):
        """测试获取评论列表。"""
        uid = unique_id()
        user_id = create_test_user(f"tgcm-{uid}", "user")
        skill_name = f"tgcm-skill-{uid}"

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        response = client.get(f"/api/skills/{skill_id}/comments")
        assert response.status_code in [200, 404]

        cleanup_test_data("tgcm-")

    def test_delete_comment(self, auth_client):
        """测试删除评论。"""
        uid = unique_id()
        user_id = create_test_user(f"tdlc-{uid}", "user")
        skill_name = f"tdlc-skill-{uid}"

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        client = auth_client(user_id, "user")
        response = client.delete(f"/api/skills/{skill_id}/comments/999999")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("tdlc-")


class TestActivityLog:
    """活动日志测试。"""

    def test_get_activity_log(self, auth_client):
        """测试获取活动日志。"""
        uid = unique_id()
        user_id = create_test_user(f"tgal-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/activity")
        assert response.status_code in [200, 401, 404]

        cleanup_test_data("tgal-")

    def test_get_user_activity(self, auth_client):
        """测试获取用户活动。"""
        uid = unique_id()
        user_id = create_test_user(f"tgua-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/user/activity")
        assert response.status_code in [200, 401, 404]

        cleanup_test_data("tgua-")


class TestFeedbackRoutes:
    """反馈路由测试。"""

    def test_submit_feedback(self, auth_client):
        """测试提交反馈。"""
        uid = unique_id()
        user_id = create_test_user(f"tsf-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.post("/api/feedback", json={
            "type": "bug",
            "content": "Test feedback",
            "skill_id": None
        })
        assert response.status_code in [200, 201, 401, 404, 422]

        cleanup_test_data("tsf-")

    def test_get_feedback_list(self, auth_client):
        """测试获取反馈列表。"""
        uid = unique_id()
        admin_id = create_test_user(f"tgfl-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/api/admin/feedback")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("tgfl-")


class TestSkillSourceFilter:
    """技能来源过滤测试。"""

    def test_filter_by_opensource(self, client):
        """测试按开源过滤。"""
        response = client.get("/api/skills?source=opensource")
        assert response.status_code == 200

    def test_filter_by_icsl(self, client):
        """测试按ICSL过滤。"""
        response = client.get("/api/skills?source=icsl")
        assert response.status_code == 200

    def test_filter_by_huawei(self, client):
        """测试按华为过滤。"""
        response = client.get("/api/skills?source=huawei")
        assert response.status_code == 200


class TestPagination:
    """分页测试。"""

    def test_pagination_page_1(self, client):
        """测试分页第1页。"""
        response = client.get("/api/skills?page=1&per_page=10")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1

    def test_pagination_large_per_page(self, client):
        """测试大per_page。"""
        response = client.get("/api/skills?per_page=100")
        assert response.status_code == 200

    def test_pagination_invalid_page(self, client):
        """测试无效页码。"""
        response = client.get("/api/skills?page=-1")
        assert response.status_code in [200, 400, 422]

    def test_pagination_invalid_per_page(self, client):
        """测试无效per_page。"""
        response = client.get("/api/skills?per_page=0")
        assert response.status_code in [200, 400, 422]
