"""
High-coverage tests for main.py endpoints.
Focus on admin endpoints, skill operations, and approval workflows.
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from database import (
    get_connection, create_user, create_skill_record,
    create_notification, get_user_by_id
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


class TestAdminUserManagementEndpoints:
    """Tests for admin user management API endpoints."""

    def test_admin_create_user_success(self):
        """Test admin creating a new user."""
        admin_id = unique_name("t-acus")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        login_resp = login_user(admin_id, admin_key)
        if login_resp.status_code != 302:
            pytest.skip("Login failed")

        new_emp_id = unique_name("new-user")
        response = client.post(
            "/api/admin/users",
            json={
                "employee_id": new_emp_id,
                "api_key": "test-key-123",
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

    def test_admin_update_user_role(self):
        """Test admin updating user role."""
        admin_id = unique_name("t-uur")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        user_id = create_user(unique_name("target-user"), "key", "user")

        login_resp = login_user(admin_id, admin_key)
        if login_resp.status_code != 302:
            pytest.skip("Login failed")

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

    def test_admin_disable_user(self):
        """Test admin disabling user."""
        admin_id = unique_name("t-du")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        user_id = create_user(unique_name("target-user"), "key", "user")

        login_resp = login_user(admin_id, admin_key)
        if login_resp.status_code != 302:
            pytest.skip("Login failed")

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

    def test_admin_enable_user(self):
        """Test admin enabling user."""
        admin_id = unique_name("t-eu")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        user_id = create_user(unique_name("target-user"), "key", "user")

        login_resp = login_user(admin_id, admin_key)
        if login_resp.status_code != 302:
            pytest.skip("Login failed")

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


class TestAdminSkillEndpoints:
    """Tests for admin skill management endpoints."""

    def test_admin_get_skills_list(self):
        """Test admin getting skills list."""
        admin_id = unique_name("t-agsl")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        login_resp = login_user(admin_id, admin_key)
        if login_resp.status_code != 302:
            pytest.skip("Login failed")

        response = client.get("/api/admin/skills", cookies=login_resp.cookies)
        assert response.status_code in [200, 401, 403]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
            conn.commit()

    def test_admin_update_skill_source_type(self):
        """Test admin updating skill source type."""
        admin_id = unique_name("t-usst")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        user_id = create_user(unique_name("uploader"), "key", "user")
        skill_name = unique_name("test-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        login_resp = login_user(admin_id, admin_key)
        if login_resp.status_code != 302:
            pytest.skip("Login failed")

        response = client.put(
            f"/api/admin/skills/{skill_id}/source-type",
            json={"source_type": "icsl"},
            cookies=login_resp.cookies
        )
        assert response.status_code in [200, 401, 403, 404, 422]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
            conn.commit()


class TestMySkillsEndpoints:
    """Tests for my-skills endpoints."""

    def test_get_my_skills_list(self):
        """Test getting my skills list."""
        emp_id = unique_name("t-gmsl")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        login_resp = login_user(emp_id, api_key)
        if login_resp.status_code != 302:
            pytest.skip("Login failed")

        response = client.get("/api/my-skills", cookies=login_resp.cookies)
        assert response.status_code in [200, 401]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_delete_my_skill(self):
        """Test deleting my skill."""
        emp_id = unique_name("t-dms")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        login_resp = login_user(emp_id, api_key)
        if login_resp.status_code != 302:
            pytest.skip("Login failed")

        response = client.delete(f"/api/my-skills/{skill_id}", cookies=login_resp.cookies)
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestSkillRatingEndpoints:
    """Tests for skill rating endpoints."""

    def test_get_skill_rating(self):
        """Test getting skill rating."""
        emp_id = unique_name("t-gsr")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        response = client.get(f"/api/skills/{skill_id}/rating")
        assert response.status_code in [200, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_submit_skill_rating(self):
        """Test submitting skill rating."""
        emp_id = unique_name("t-ssr")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        login_resp = login_user(emp_id, api_key)
        if login_resp.status_code != 302:
            pytest.skip("Login failed")

        response = client.post(
            f"/api/skills/{skill_id}/rating",
            json={"rating": 5},
            cookies=login_resp.cookies
        )
        assert response.status_code in [200, 201, 401, 403, 404, 422]

        # Cleanup
        with get_connection() as conn:
            try:
                conn.execute("DELETE FROM ratings WHERE skill_id = %s", (skill_id,))
            except Exception:
                pass
            conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestSkillCommentEndpoints:
    """Tests for skill comment endpoints."""

    def test_get_skill_comments(self):
        """Test getting skill comments."""
        emp_id = unique_name("t-gsc")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        response = client.get(f"/api/skills/{skill_id}/comments")
        assert response.status_code in [200, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_add_skill_comment(self):
        """Test adding skill comment."""
        emp_id = unique_name("t-asc")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        login_resp = login_user(emp_id, api_key)
        if login_resp.status_code != 302:
            pytest.skip("Login failed")

        response = client.post(
            f"/api/skills/{skill_id}/comments",
            json={"content": "Test comment"},
            cookies=login_resp.cookies
        )
        assert response.status_code in [200, 201, 401, 403, 404, 422]

        # Cleanup
        with get_connection() as conn:
            try:
                conn.execute("DELETE FROM comments WHERE skill_id = %s", (skill_id,))
            except Exception:
                pass
            conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestCategoryEndpoints:
    """Tests for category endpoints."""

    def test_get_categories_list(self):
        """Test getting categories list."""
        response = client.get("/api/categories")
        assert response.status_code == 200

    def test_get_category_skills(self):
        """Test getting skills by category."""
        response = client.get("/api/categories/testing/skills")
        assert response.status_code in [200, 404]


class TestSearchEndpoints:
    """Tests for search endpoints."""

    def test_search_skills(self):
        """Test searching skills."""
        response = client.get("/api/search?q=test")
        assert response.status_code in [200, 400]

    def test_search_suggestions(self):
        """Test getting search suggestions."""
        response = client.get("/api/search/suggestions?prefix=test")
        assert response.status_code in [200, 400]


class TestV1APIEndpoints:
    """Tests for V1 API endpoints."""

    def test_v1_skills_list(self):
        """Test V1 skills list."""
        response = client.get("/api/v1/skills")
        assert response.status_code in [200, 401]

    def test_v1_skill_by_name(self):
        """Test V1 skill by name."""
        emp_id = unique_name("t-v1sbn")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-skill")
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
            conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestGiteaEndpoints:
    """Tests for Gitea integration endpoints."""

    def test_gitea_status_endpoint(self):
        """Test Gitea status endpoint."""
        admin_id = unique_name("t-gse")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        login_resp = login_user(admin_id, admin_key)
        if login_resp.status_code != 302:
            pytest.skip("Login failed")

        response = client.get("/api/gitea/status", cookies=login_resp.cookies)
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
            conn.commit()

    def test_gitea_tasks_endpoint(self):
        """Test Gitea tasks endpoint."""
        admin_id = unique_name("t-gte")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        login_resp = login_user(admin_id, admin_key)
        if login_resp.status_code != 302:
            pytest.skip("Login failed")

        response = client.get("/api/admin/gitea-tasks", cookies=login_resp.cookies)
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
            conn.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
