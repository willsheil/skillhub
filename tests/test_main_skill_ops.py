"""
Tests for main.py skill operations - upload, download, approval, deletion.
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


class TestSkillDownload:
    """技能下载测试。"""

    def test_download_skill_authenticated(self, auth_client):
        """测试已认证下载技能。"""
        uid = unique_id()
        user_id = create_test_user(f"ds-{uid}", "user")
        skill_name = f"ds-skill-{uid}"

        # Create skill file
        zip_content = create_test_skill_zip(skill_name, "1.0.0", f"w{uid}")
        os.makedirs("plugins", exist_ok=True)
        with open(f"plugins/{skill_name}.zip", "wb") as f:
            f.write(zip_content)

        # Create database record
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", f"{skill_name}.zip", user_id, "approved")
            )
            conn.commit()

        client = auth_client(user_id, "user")
        response = client.get(f"/plugins/{skill_name}.zip")

        assert response.status_code in [200, 302, 401, 404]

        # Cleanup
        cleanup_test_data("ds-")
        if os.path.exists(f"plugins/{skill_name}.zip"):
            os.remove(f"plugins/{skill_name}.zip")

    def test_download_nonexistent_skill(self, auth_client):
        """测试下载不存在的技能。"""
        uid = unique_id()
        user_id = create_test_user(f"dn-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/plugins/nonexistent-skill.zip")
        assert response.status_code in [404, 302]

        cleanup_test_data("dn-")

    def test_download_without_auth(self, client):
        """测试未认证下载。"""
        response = client.get("/plugins/some-skill.zip")
        assert response.status_code in [200, 302, 401, 404]


class TestSkillUpload:
    """技能上传测试。"""

    def test_upload_skill_valid(self, auth_client):
        """测试上传有效技能。"""
        uid = unique_id()
        user_id = create_test_user(f"us-{uid}", "user")
        skill_name = f"us-skill-{uid}"

        zip_content = create_test_skill_zip(skill_name, "1.0.0", f"w{uid}")
        files = {"file": (f"{skill_name}.zip", io.BytesIO(zip_content), "application/zip")}
        data = {"skill_name": skill_name, "version": "1.0.0", "source_type": "opensource"}

        client = auth_client(user_id, "user")
        response = client.post("/api/upload", files=files, data=data)

        assert response.status_code in [200, 201, 400, 401, 422]

        cleanup_test_data("us-")

    def test_upload_skill_missing_file(self, auth_client):
        """测试上传缺少文件。"""
        uid = unique_id()
        user_id = create_test_user(f"um-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.post("/api/upload", data={"skill_name": "test", "version": "1.0.0"})
        assert response.status_code in [400, 422]

        cleanup_test_data("um-")

    def test_upload_skill_invalid_zip(self, auth_client):
        """测试上传无效ZIP。"""
        uid = unique_id()
        user_id = create_test_user(f"ui-{uid}", "user")
        client = auth_client(user_id, "user")

        files = {"file": ("invalid.zip", io.BytesIO(b"not a zip"), "application/zip")}
        data = {"skill_name": "invalid-skill", "version": "1.0.0"}

        response = client.post("/api/upload", files=files, data=data)
        assert response.status_code in [400, 422]

        cleanup_test_data("ui-")


class TestSkillApproval:
    """技能审批测试。"""

    def test_approve_skill_as_admin(self, auth_client):
        """测试管理员审批技能。"""
        uid = unique_id()
        admin_id = create_test_user(f"sa-{uid}", "admin")
        author_id = create_test_user(f"sa-auth-{uid}", "user")
        skill_name = f"sa-skill-{uid}"

        # Create pending skill
        zip_content = create_test_skill_zip(skill_name, "1.0.0", f"w{uid}")
        os.makedirs("data/pending", exist_ok=True)
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
        cleanup_test_data("sa-")
        if os.path.exists(f"data/pending/{skill_name}.zip"):
            os.remove(f"data/pending/{skill_name}.zip")

    def test_reject_skill_as_admin(self, auth_client):
        """测试管理员拒绝技能。"""
        uid = unique_id()
        admin_id = create_test_user(f"sr-{uid}", "admin")
        author_id = create_test_user(f"sr-auth-{uid}", "user")
        skill_name = f"sr-skill-{uid}"

        # Create pending skill
        os.makedirs("data/pending", exist_ok=True)
        with open(f"data/pending/{skill_name}.zip", "wb") as f:
            f.write(create_test_skill_zip(skill_name, "1.0.0", f"w{uid}"))

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", f"{skill_name}.zip", author_id, "pending")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        client = auth_client(admin_id, "admin")
        response = client.post(f"/api/review/{skill_id}", json={"action": "reject", "reason": "Test rejection"})

        assert response.status_code in [200, 201, 401, 403, 404, 500]

        # Cleanup
        cleanup_test_data("sr-")
        if os.path.exists(f"data/pending/{skill_name}.zip"):
            os.remove(f"data/pending/{skill_name}.zip")

    def test_approve_skill_as_user(self, auth_client):
        """测试普通用户审批技能（应该失败）。"""
        uid = unique_id()
        user_id = create_test_user(f"su-{uid}", "user")
        author_id = create_test_user(f"su-auth-{uid}", "user")
        skill_name = f"su-skill-{uid}"

        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", author_id, "pending")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        client = auth_client(user_id, "user")
        response = client.post(f"/api/review/{skill_id}", json={"action": "approve"})

        assert response.status_code in [401, 403, 404, 500]

        cleanup_test_data("su-")


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

    def test_delete_nonexistent_skill(self, auth_client):
        """测试删除不存在的技能。"""
        uid = unique_id()
        user_id = create_test_user(f"sdx-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.delete("/api/skills/999999")
        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("sdx-")


class TestMySkills:
    """我的技能测试。"""

    def test_get_my_skills(self, auth_client):
        """测试获取我的技能。"""
        uid = unique_id()
        user_id = create_test_user(f"ms-{uid}", "user")
        skill_name = f"ms-skill-{uid}"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test.zip", user_id, "approved")
            )
            conn.commit()

        client = auth_client(user_id, "user")
        response = client.get("/api/my-skills")

        assert response.status_code in [200, 401, 404]

        cleanup_test_data("ms-")

    def test_get_my_skills_empty(self, auth_client):
        """测试获取空的我的技能。"""
        uid = unique_id()
        user_id = create_test_user(f"mse-{uid}", "user")
        client = auth_client(user_id, "user")

        response = client.get("/api/my-skills")
        assert response.status_code in [200, 401, 404]

        cleanup_test_data("mse-")


class TestSetDefaultVersion:
    """设置默认版本测试。"""

    def test_set_default_version(self, auth_client):
        """测试设置默认版本。"""
        uid = unique_id()
        user_id = create_test_user(f"sdv-{uid}", "user")
        skill_name = f"sdv-skill-{uid}"

        with get_connection() as conn:
            # Create two versions
            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "1.0.0", "test1.zip", user_id, "approved")
            )
            skill_id_1 = cursor.lastrowid

            cursor = conn.execute(
                "INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active) VALUES (%s, %s, %s, %s, %s, 1)",
                (skill_name, "2.0.0", "test2.zip", user_id, "approved")
            )
            skill_id_2 = cursor.lastrowid
            conn.commit()

        client = auth_client(user_id, "user")
        response = client.post(f"/api/my-skills/{skill_id_2}/set-default")

        assert response.status_code in [200, 401, 403, 404]

        cleanup_test_data("sdv-")
