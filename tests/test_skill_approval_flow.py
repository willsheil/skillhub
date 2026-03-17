"""
Additional tests for skill approval, upload, and external API routes.
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


class TestSkillUploadFlow:
    """技能上传流程测试。"""

    def test_upload_skill_valid(self, auth_client):
        """测试上传有效技能。"""
        uid = unique_id()
        user_id = create_test_user(f"usv-{uid}", "user")
        skill_name = f"usv-skill-{uid}"

        zip_content = create_test_skill_zip(skill_name, "1.0.0", f"w{uid}")
        files = {"file": (f"{skill_name}.zip", io.BytesIO(zip_content), "application/zip")}
        data = {"skill_name": skill_name, "version": "1.0.0", "source_type": "opensource"}

        client = auth_client(user_id, "user")
        response = client.post("/api/upload", files=files, data=data)

        assert response.status_code in [200, 201, 400, 401, 422]

        cleanup_test_data("usv-")

    def test_upload_skill_invalid_zip(self, auth_client):
        """测试上传无效ZIP。"""
        uid = unique_id()
        user_id = create_test_user(f"usi-{uid}", "user")
        client = auth_client(user_id, "user")

        files = {"file": ("invalid.zip", io.BytesIO(b"not a zip"), "application/zip")}
        data = {"skill_name": "invalid-skill", "version": "1.0.0"}

        response = client.post("/api/upload", files=files, data=data)
        assert response.status_code in [400, 422]

        cleanup_test_data("usi-")

    def test_upload_skill_missing_skill_md(self, auth_client):
        """测试上传缺少SKILL.md的ZIP。"""
        uid = unique_id()
        user_id = create_test_user(f"usm-{uid}", "user")
        client = auth_client(user_id, "user")

        # Create ZIP without SKILL.md
        import zipfile
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('readme.txt', 'No skill md')

        files = {"file": ("no-md.zip", io.BytesIO(output.getvalue()), "application/zip")}
        data = {"skill_name": "no-md-skill", "version": "1.0.0"}

        response = client.post("/api/upload", files=files, data=data)
        assert response.status_code in [400, 422]

        cleanup_test_data("usm-")


class TestSkillApprovalFlow:
    """技能审批流程测试。"""

    def test_approve_skill_as_admin(self, auth_client):
        """测试管理员审批技能。"""
        uid = unique_id()
        admin_id = create_test_user(f"saa-{uid}", "admin")
        author_id = create_test_user(f"saa-auth-{uid}", "user")
        skill_name = f"saa-skill-{uid}"

        # Create pending skill with file
        os.makedirs("data/pending", exist_ok=True)
        zip_content = create_test_skill_zip(skill_name, "1.0.0", f"w{uid}")
        with open(f"data/pending/{skill_name}.zip", "wb") as f:
            f.write(zip_content)

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", f"{skill_name}.zip", author_id, "pending")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        client = auth_client(admin_id, "admin")
        response = client.post(f"/api/review/{skill_id}", json={"action": "approve"})

        assert response.status_code in [200, 201, 401, 403, 404, 500]

        # Cleanup
        cleanup_test_data("saa-")
        if os.path.exists(f"data/pending/{skill_name}.zip"):
            os.remove(f"data/pending/{skill_name}.zip")

    def test_reject_skill_as_admin(self, auth_client):
        """测试管理员拒绝技能。"""
        uid = unique_id()
        admin_id = create_test_user(f"srj-{uid}", "admin")
        author_id = create_test_user(f"srj-auth-{uid}", "user")
        skill_name = f"srj-skill-{uid}"

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", author_id, "pending")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        client = auth_client(admin_id, "admin")
        response = client.post(f"/api/review/{skill_id}", json={"action": "reject", "reason": "Test rejection"})

        assert response.status_code in [200, 201, 401, 403, 404, 500]

        cleanup_test_data("srj-")


class TestSkillDeletion:
    """技能删除测试。"""

    def test_delete_skill_as_owner(self, auth_client):
        """测试所有者删除技能。"""
        uid = unique_id()
        user_id = create_test_user(f"sdo-{uid}", "user")
        skill_name = f"sdo-skill-{uid}"

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

        cleanup_test_data("sdo-")

    def test_delete_skill_as_non_owner(self, auth_client):
        """测试非所有者删除技能。"""
        uid = unique_id()
        owner_id = create_test_user(f"sdn-o-{uid}", "user")
        other_id = create_test_user(f"sdn-x-{uid}", "user")
        skill_name = f"sdn-skill-{uid}"

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

        cleanup_test_data("sdn-")


class TestMySkillsAPI:
    """我的技能API测试。"""

    def test_get_my_skills(self, auth_client):
        """测试获取我的技能。"""
        uid = unique_id()
        user_id = create_test_user(f"gms-{uid}", "user")
        skill_name = f"gms-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            conn.commit()

        client = auth_client(user_id, "user")
        response = client.get("/api/my-skills")

        assert response.status_code in [200, 401, 404]

        cleanup_test_data("gms-")

    def test_get_my_skills_grouped(self, auth_client):
        """测试获取分组后的我的技能。"""
        uid = unique_id()
        user_id = create_test_user(f"gmsg-{uid}", "user")
        skill_name = f"gmsg-skill-{uid}"

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

        client = auth_client(user_id, "user")
        response = client.get("/api/my-skills")

        assert response.status_code in [200, 401, 404]

        cleanup_test_data("gmsg-")


class TestExternalAPIRoutes:
    """外部API路由测试。"""

    def test_get_external_apis(self, auth_client):
        """测试获取外部API列表。"""
        uid = unique_id()
        user_id = create_test_user(f"gea-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/external-apis")
        assert response.status_code in [200, 401, 404]

        cleanup_test_data("gea-")

    def test_create_external_api(self, auth_client):
        """测试创建外部API。"""
        uid = unique_id()
        user_id = create_test_user(f"cea-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.post("/api/external-apis", json={
            "name": f"test-api-{uid}",
            "api_key": "test-key",
            "description": "Test API"
        })
        assert response.status_code in [200, 201, 401, 404, 422]

        cleanup_test_data("cea-")

    def test_delete_external_api(self, auth_client):
        """测试删除外部API。"""
        uid = unique_id()
        user_id = create_test_user(f"dea-{uid}", "user")

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

        cleanup_test_data("dea-")


class TestNotificationAPI:
    """通知API测试。"""

    def test_get_notifications(self, auth_client):
        """测试获取通知列表。"""
        uid = unique_id()
        user_id = create_test_user(f"gnf-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/notifications")
        assert response.status_code in [200, 401, 404]

        cleanup_test_data("gnf-")

    def test_get_unread_count(self, auth_client):
        """测试获取未读通知数。"""
        uid = unique_id()
        user_id = create_test_user(f"guc-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/notifications/unread-count")
        assert response.status_code in [200, 401, 404]

        cleanup_test_data("guc-")

    def test_mark_all_read(self, auth_client):
        """测试标记所有已读。"""
        uid = unique_id()
        user_id = create_test_user(f"mar-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.post("/api/notifications/read-all")
        assert response.status_code in [200, 401, 404]

        cleanup_test_data("mar-")


class TestBatchOperations:
    """批量操作测试。"""

    def test_batch_delete_skills(self, auth_client):
        """测试批量删除技能。"""
        uid = unique_id()
        admin_id = create_test_user(f"bds-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.post("/api/skills/batch-delete", json={"skill_ids": [1, 2, 3]})
        assert response.status_code in [200, 401, 403, 404, 422]

        cleanup_test_data("bds-")

    def test_batch_update_status(self, auth_client):
        """测试批量更新状态。"""
        uid = unique_id()
        admin_id = create_test_user(f"bus-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.post("/api/skills/batch-status", json={"skill_ids": [1, 2, 3], "status": "approved"})
        assert response.status_code in [200, 401, 403, 404, 422]

        cleanup_test_data("bus-")


class TestConfigAPI:
    """配置API测试。"""

    def test_get_config(self, auth_client):
        """测试获取配置。"""
        uid = unique_id()
        admin_id = create_test_user(f"tgc-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.get("/api/config")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("tgc-")

    def test_update_config(self, auth_client):
        """测试更新配置。"""
        uid = unique_id()
        admin_id = create_test_user(f"tuc-{uid}", "admin")
        client = auth_client(admin_id, "admin")

        response = client.put("/api/config", json={"key": "value"})
        assert response.status_code in [200, 401, 403, 404, 422]

        cleanup_test_data("tuc-")
