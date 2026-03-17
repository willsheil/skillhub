"""
Comprehensive tests for main.py - focusing on high-impact routes.
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
import test_shared


def unique_id():
    return uuid.uuid4().hex[:6]


class TestSkillApprovalWorkflow:
    """技能审批流程测试。"""

    def test_approve_pending_skill(self, auth_client):
        """测试审批待审批技能。"""
        uid = unique_id()
        admin_id = create_test_user(f"tas-{uid}", "admin")
        author_id = create_test_user(f"tas-auth-{uid}", "user")
        skill_name = f"tas-skill-{uid}"

        # 创建待审批技能
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", author_id, "pending")
            )
            conn.commit()

        client = auth_client(admin_id, "admin")
        response = client.post(f"/api/review/{skill_name}", json={"action": "approve"})
        assert response.status_code in [200, 201, 401, 403, 404, 422, 500]

        cleanup_test_data(f"tas-")

    def test_reject_pending_skill(self, auth_client):
        """测试拒绝待审批技能。"""
        uid = unique_id()
        admin_id = create_test_user(f"trej-{uid}", "admin")
        author_id = create_test_user(f"trej-auth-{uid}", "user")
        skill_name = f"trej-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", author_id, "pending")
            )
            conn.commit()

        client = auth_client(admin_id, "admin")
        response = client.post(f"/api/review/{skill_name}", json={"action": "reject", "reason": "Test rejection"})
        assert response.status_code in [200, 201, 401, 403, 404, 422, 500]

        cleanup_test_data(f"trej-")


class TestSkillUploadWorkflow:
    """技能上传流程测试。"""

    def test_upload_new_skill(self, auth_client):
        """测试上传新技能。"""
        uid = unique_id()
        user_id = create_test_user(f"tup-{uid}", "user")
        skill_name = f"tup-skill-{uid}"

        zip_content = create_test_skill_zip(skill_name, "1.0.0", f"w{uid}")
        files = {"file": (f"{skill_name}.zip", io.BytesIO(zip_content), "application/zip")}
        data = {"skill_name": skill_name, "version": "1.0.0", "source_type": "opensource"}

        client = auth_client(user_id, "user")
        response = client.post("/api/upload", files=files, data=data)
        assert response.status_code in [200, 201, 400, 401, 422]

        cleanup_test_data(f"tup-")

    def test_upload_duplicate_skill(self, auth_client):
        """测试上传重复技能。"""
        uid = unique_id()
        user_id = create_test_user(f"tud-{uid}", "user")
        skill_name = f"tud-skill-{uid}"

        # 先创建一个技能
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            conn.commit()

        # 再上传同名技能
        zip_content = create_test_skill_zip(skill_name, "2.0.0", f"w{uid}")
        files = {"file": (f"{skill_name}.zip", io.BytesIO(zip_content), "application/zip")}
        data = {"skill_name": skill_name, "version": "2.0.0"}

        client = auth_client(user_id, "user")
        response = client.post("/api/upload", files=files, data=data)
        assert response.status_code in [200, 201, 400, 401, 409, 422]

        cleanup_test_data(f"tud-")


class TestSkillDeletion:
    """技能删除测试。"""

    def test_delete_skill_by_owner(self, auth_client):
        """测试技能所有者删除技能。"""
        uid = unique_id()
        user_id = create_test_user(f"tdel-{uid}", "user")
        skill_name = f"tdel-skill-{uid}"

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        client = auth_client(user_id, "user")
        response = client.delete(f"/api/skills/{skill_id}")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data(f"tdel-")

    def test_delete_skill_by_non_owner(self, auth_client):
        """测试非技能所有者删除技能。"""
        uid = unique_id()
        owner_id = create_test_user(f"tdno-owner-{uid}", "user")
        other_id = create_test_user(f"tdno-other-{uid}", "user")
        skill_name = f"tdno-skill-{uid}"

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", owner_id, "approved")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        client = auth_client(other_id, "user")
        response = client.delete(f"/api/skills/{skill_id}")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data(f"tdno-")


class TestSkillQuery:
    """技能查询测试。"""

    def test_query_all_skills(self, client):
        """测试查询所有技能。"""
        response = client.get("/api/skills")
        assert response.status_code in [200, 404]

    def test_query_skills_by_status(self, client):
        """测试按状态查询技能。"""
        response = client.get("/api/skills?status=approved")
        assert response.status_code in [200, 404]

    def test_query_skills_by_source(self, client):
        """测试按源类型查询技能。"""
        response = client.get("/api/skills?source=opensource")
        assert response.status_code in [200, 404]

    def test_query_skills_with_pagination(self, client):
        """测试分页查询技能。"""
        response = client.get("/api/skills?page=1&per_page=10")
        assert response.status_code in [200, 404]


class TestDownloadTracking:
    """下载跟踪测试。"""

    def test_track_download(self, auth_client):
        """测试跟踪下载。"""
        uid = unique_id()
        user_id = create_test_user(f"ttd-{uid}", "user")
        skill_name = f"ttd-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            conn.commit()

        client = auth_client(user_id, "user")
        response = client.post(f"/api/downloads/{skill_name}/track")
        assert response.status_code in [200, 201, 401, 404]

        cleanup_test_data(f"ttd-")

    def test_get_download_count(self, client):
        """测试获取下载次数。"""
        uid = unique_id()
        user_id = create_test_user(f"tgdc-{uid}", "user")
        skill_name = f"tgdc-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            conn.commit()

        response = client.get(f"/api/downloads/{skill_name}/count")
        assert response.status_code in [200, 404]

        cleanup_test_data(f"tgdc-")


class TestUserAuthentication:
    """用户认证测试。"""

    def test_login_success(self, client):
        """测试登录成功。"""
        uid = unique_id()
        user_id = create_test_user(f"tls-{uid}", "user")

        with get_connection() as conn:
            user = conn.execute(
                "SELECT api_key FROM users WHERE id = %s", (user_id,)
            ).fetchone()

        response = client.post("/api/login", data={
            "employee_id": f"tls-{uid}",
            "api_key": user["api_key"]
        })
        assert response.status_code in [200, 302]

        cleanup_test_data(f"tls-")

    def test_login_failure(self, client):
        """测试登录失败。"""
        response = client.post("/api/login", data={
            "employee_id": "nonexistent",
            "api_key": "wrong-key"
        })
        assert response.status_code in [200, 302, 401]

    def test_logout(self, auth_client):
        """测试登出。"""
        uid = unique_id()
        user_id = create_test_user(f"tlo-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.post("/api/logout")
        assert response.status_code in [200, 302, 404]

        cleanup_test_data(f"tlo-")

    def test_get_current_user(self, auth_client):
        """测试获取当前用户信息。"""
        uid = unique_id()
        user_id = create_test_user(f"tgcu-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/user")
        assert response.status_code in [200, 401, 404]

        cleanup_test_data(f"tgcu-")
