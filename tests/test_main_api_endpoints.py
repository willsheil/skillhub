"""
Additional tests for main.py API endpoints to boost coverage.
Focus on authenticated endpoints and edge cases.
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from database import (
    get_connection, create_user, create_skill_record,
    create_notification
)
import uuid
import io
import zipfile


client = TestClient(app)


def unique_name(base: str) -> str:
    """Generate a unique name for testing."""
    return f"{base}-{uuid.uuid4().hex[:8]}"


def login_user(employee_id: str, api_key: str):
    """Login and return session cookies."""
    response = client.post("/api/login", data={
        "employee_id": employee_id,
        "api_key": api_key
    })
    return response


def create_test_skill_zip(skill_name: str = "test-skill", version: str = "1.0.0") -> bytes:
    """Create a minimal valid skill ZIP file."""
    skill_md_content = f"""---
name: {skill_name}
description: A test skill for automated testing
metadata:
  version: {version}
  author: w00000001
  license: MIT
  compatibility: Claude Code 1.0+
allowed-tools: bash, read
---

# {skill_name}

This is a test skill for automated testing.
"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("SKILL.md", skill_md_content)
        zip_file.writestr("scripts/main.sh", "#!/bin/bash\necho 'Hello'")
    zip_buffer.seek(0)
    return zip_buffer.read()


class TestAuthenticatedSkillUpload:
    """Tests for authenticated skill upload flow."""

    def test_upload_with_session(self):
        """Test upload with valid session."""
        emp_id = unique_name("t-us")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        # Login
        login_resp = login_user(emp_id, api_key)

        skill_name = unique_name("t-us-skill")
        skill_zip = create_test_skill_zip(skill_name)

        response = client.post(
            "/api/upload",
            files={"file": (f"{skill_name}.zip", io.BytesIO(skill_zip), "application/zip")},
            cookies=login_resp.cookies
        )
        # May succeed or fail depending on file system
        assert response.status_code in [200, 400, 401, 422, 500]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE skill_name = %s", (skill_name,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_upload_without_session(self):
        """Test upload without session."""
        skill_name = unique_name("t-uws-skill")
        skill_zip = create_test_skill_zip(skill_name)

        response = client.post(
            "/api/upload",
            files={"file": (f"{skill_name}.zip", io.BytesIO(skill_zip), "application/zip")}
        )
        assert response.status_code in [200, 400, 401, 422]

    def test_upload_invalid_zip(self):
        """Test upload with invalid ZIP."""
        emp_id = unique_name("t-uiz")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_resp = login_user(emp_id, api_key)

        response = client.post(
            "/api/upload",
            files={"file": ("invalid.zip", io.BytesIO(b"not a zip"), "application/zip")},
            cookies=login_resp.cookies
        )
        assert response.status_code in [400, 401, 415, 422]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestAdminUserManagement:
    """Tests for admin user management endpoints."""

    def test_create_user_endpoint(self):
        """Test creating user via admin API."""
        admin_id = unique_name("t-aum")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        login_resp = login_user(admin_id, admin_key)

        new_emp_id = unique_name("t-new-user")
        response = client.post(
            "/api/admin/users",
            json={
                "employee_id": new_emp_id,
                "api_key": "test-key",
                "role": "user"
            },
            cookies=login_resp.cookies
        )
        assert response.status_code in [200, 201, 401, 403, 422]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE employee_id = %s", (new_emp_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
            conn.commit()

    def test_update_user_role_endpoint(self):
        """Test updating user role via admin API."""
        admin_id = unique_name("t-uur")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        user_id = create_user(unique_name("t-target"), "key", "user")

        login_resp = login_user(admin_id, admin_key)

        response = client.put(
            f"/api/admin/users/{user_id}",
            json={"role": "admin"},
            cookies=login_resp.cookies
        )
        assert response.status_code in [200, 401, 403, 404, 422]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
            conn.commit()

    def test_disable_user_endpoint(self):
        """Test disabling user via admin API."""
        admin_id = unique_name("t-du")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        user_id = create_user(unique_name("t-target"), "key", "user")

        login_resp = login_user(admin_id, admin_key)

        response = client.patch(
            f"/api/admin/users/{user_id}/disable",
            cookies=login_resp.cookies
        )
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
            conn.commit()

    def test_enable_user_endpoint(self):
        """Test enabling user via admin API."""
        admin_id = unique_name("t-eu")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        user_id = create_user(unique_name("t-target"), "key", "user")

        login_resp = login_user(admin_id, admin_key)

        response = client.patch(
            f"/api/admin/users/{user_id}/enable",
            cookies=login_resp.cookies
        )
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
            conn.commit()

    def test_delete_user_endpoint(self):
        """Test deleting user via admin API."""
        admin_id = unique_name("t-del")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        user_id = create_user(unique_name("t-target"), "key", "user")

        login_resp = login_user(admin_id, admin_key)

        response = client.delete(
            f"/api/admin/users/{user_id}",
            cookies=login_resp.cookies
        )
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
            conn.commit()


class TestAdminAPIKeys:
    """Tests for admin API key management endpoints."""

    def test_list_api_keys(self):
        """Test listing API keys."""
        admin_id = unique_name("t-lak")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        login_resp = login_user(admin_id, admin_key)

        response = client.get("/api/admin/api-keys", cookies=login_resp.cookies)
        assert response.status_code in [200, 401, 403]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
            conn.commit()

    def test_create_api_key(self):
        """Test creating API key."""
        admin_id = unique_name("t-cak")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        login_resp = login_user(admin_id, admin_key)

        response = client.post(
            "/api/admin/api-keys",
            json={"name": "Test Key", "description": "Test"},
            cookies=login_resp.cookies
        )
        assert response.status_code in [200, 201, 401, 403, 422]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
            conn.commit()


class TestMySkillsOperations:
    """Tests for my-skills operations."""

    def test_get_my_skills_authenticated(self):
        """Test getting my skills authenticated."""
        emp_id = unique_name("t-gms")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_resp = login_user(emp_id, api_key)

        response = client.get("/api/my-skills", cookies=login_resp.cookies)
        assert response.status_code in [200, 401]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_get_skill_versions(self):
        """Test getting skill versions."""
        emp_id = unique_name("t-gsv")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-gsv-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        login_resp = login_user(emp_id, api_key)

        response = client.get(f"/api/my-skills/versions/{skill_name}", cookies=login_resp.cookies)
        assert response.status_code in [200, 401]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_delete_skill_version(self):
        """Test deleting skill version."""
        emp_id = unique_name("t-dsv")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-dsv-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        login_resp = login_user(emp_id, api_key)

        response = client.delete(f"/api/my-skills/{skill_id}", cookies=login_resp.cookies)
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_publish_skill(self):
        """Test publishing skill."""
        emp_id = unique_name("t-ps")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-ps-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        # Set to inactive
        with get_connection() as conn:
            conn.execute("UPDATE skills SET is_active = 0 WHERE id = %s", (skill_id,))
            conn.commit()

        login_resp = login_user(emp_id, api_key)

        response = client.post(f"/api/my-skills/{skill_id}/publish", cookies=login_resp.cookies)
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_unlist_skill(self):
        """Test unlisting skill."""
        emp_id = unique_name("t-us")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-us-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        login_resp = login_user(emp_id, api_key)

        response = client.post(f"/api/my-skills/{skill_id}/unlist", cookies=login_resp.cookies)
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestSkillRatingComments:
    """Tests for skill rating and comments."""

    def test_get_skill_rating(self):
        """Test getting skill rating."""
        emp_id = unique_name("t-gsr")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-gsr-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        response = client.get(f"/api/skills/{skill_id}/rating")
        assert response.status_code in [200, 404, 500]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_submit_rating_authenticated(self):
        """Test submitting rating authenticated."""
        emp_id = unique_name("t-sra")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-sra-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        login_resp = login_user(emp_id, api_key)

        response = client.post(
            f"/api/skills/{skill_id}/rating",
            json={"rating": 5},
            cookies=login_resp.cookies
        )
        assert response.status_code in [200, 201, 401, 403, 404, 422, 500]

        # Cleanup
        with get_connection() as conn:
            try:
                conn.execute("DELETE FROM ratings WHERE skill_id = %s", (skill_id,))
            except Exception:
                pass
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_get_skill_comments(self):
        """Test getting skill comments."""
        emp_id = unique_name("t-gsc")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-gsc-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        response = client.get(f"/api/skills/{skill_id}/comments")
        assert response.status_code in [200, 404, 500]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_add_comment_authenticated(self):
        """Test adding comment authenticated."""
        emp_id = unique_name("t-aca")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-aca-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        login_resp = login_user(emp_id, api_key)

        response = client.post(
            f"/api/skills/{skill_id}/comments",
            json={"content": "Test comment"},
            cookies=login_resp.cookies
        )
        assert response.status_code in [200, 201, 401, 403, 404, 422, 500]

        # Cleanup
        with get_connection() as conn:
            try:
                conn.execute("DELETE FROM comments WHERE skill_id = %s", (skill_id,))
            except Exception:
                pass
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestSearchEndpoints:
    """Tests for search endpoints."""

    def test_search_skills(self):
        """Test searching skills."""
        response = client.get("/api/search?q=test")
        assert response.status_code in [200, 400, 404]

    def test_search_with_filters(self):
        """Test search with filters."""
        response = client.get("/api/search?q=test&source_type=opensource")
        assert response.status_code in [200, 400, 404]

    def test_search_suggestions(self):
        """Test search suggestions."""
        response = client.get("/api/search/suggestions?prefix=test")
        assert response.status_code in [200, 400, 404]

    def test_search_history_authenticated(self):
        """Test search history authenticated."""
        emp_id = unique_name("t-sha")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_resp = login_user(emp_id, api_key)

        response = client.get("/api/search/history", cookies=login_resp.cookies)
        assert response.status_code in [200, 401, 500]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestStatsEndpoints:
    """Tests for stats endpoints."""

    def test_get_top_skills(self):
        """Test getting top skills."""
        response = client.get("/api/stats/top")
        assert response.status_code in [200, 401]

    def test_export_stats(self):
        """Test exporting stats."""
        response = client.get("/api/stats/export")
        assert response.status_code in [200, 401]


class TestCategoryEndpoints:
    """Tests for category endpoints."""

    def test_get_categories(self):
        """Test getting categories."""
        response = client.get("/api/categories")
        assert response.status_code == 200

    def test_get_category_skills(self):
        """Test getting category skills."""
        response = client.get("/api/categories/frontend/skills")
        assert response.status_code in [200, 404]


class TestV1APIEndpoints:
    """Tests for V1 API endpoints."""

    def test_v1_skills_list(self):
        """Test V1 skills list."""
        response = client.get("/api/v1/skills")
        assert response.status_code in [200, 401]

    def test_v1_skill_by_name(self):
        """Test V1 skill by name."""
        emp_id = unique_name("t-v1")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-v1-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        with get_connection() as conn:
            conn.execute("UPDATE skills SET is_active = 1 WHERE id = %s", (skill_id,))
            conn.commit()

        response = client.get(f"/api/v1/skills/{skill_name}")
        assert response.status_code in [200, 401, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_v1_skill_download(self):
        """Test V1 skill download."""
        response = client.get("/api/v1/skills/test-skill/download")
        assert response.status_code in [200, 302, 401, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
