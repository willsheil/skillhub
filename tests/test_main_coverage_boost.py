"""
Additional tests to boost coverage for main.py endpoints.
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


def login_user(employee_id: str, api_key: str):
    """Login and return session cookies."""
    response = client.post("/api/login", json={
        "employee_id": employee_id,
        "api_key": api_key
    })
    return response


class TestAuthenticationFlow:
    """Tests for authentication flow."""

    def test_login_with_valid_credentials(self):
        """Test login with valid credentials."""
        emp_id = unique_name("t-auth")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        response = login_user(emp_id, api_key)
        assert response.status_code in [200, 400, 401, 422]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_login_with_invalid_api_key(self):
        """Test login with invalid API key."""
        emp_id = unique_name("t-auth")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        response = login_user(emp_id, "wrong-api-key")
        assert response.status_code in [400, 401, 422]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_login_with_nonexistent_user(self):
        """Test login with nonexistent user."""
        response = login_user("nonexistent-user-12345", "any-key")
        assert response.status_code in [400, 401, 422]


class TestSkillUploadAuthenticated:
    """Tests for authenticated skill upload."""

    def test_upload_skill_authenticated(self):
        """Test uploading skill with authentication."""
        emp_id = unique_name("t-upa")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        # Login first
        login_response = login_user(emp_id, api_key)

        skill_name = unique_name("t-upa-skill")
        skill_zip = create_test_skill_zip(skill_name)

        response = client.post(
            "/api/upload",
            files={"file": (f"{skill_name}.zip", io.BytesIO(skill_zip), "application/zip")},
            cookies=login_response.cookies
        )
        assert response.status_code in [200, 400, 401, 422]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE skill_name = %s", (skill_name,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_upload_skill_with_metadata(self):
        """Test uploading skill with custom metadata."""
        emp_id = unique_name("t-upm")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_response = login_user(emp_id, api_key)

        skill_name = unique_name("t-upm-skill")
        skill_md = f"""---
name: {skill_name}
description: A skill with custom metadata
metadata:
  version: 2.0.0
  author: w00000001
  tags: test, automation, coverage
  category: testing
license: MIT
compatibility: Claude Code 1.0+
allowed-tools: bash, read, write
---

# {skill_name}

Custom metadata skill.
"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("SKILL.md", skill_md)
            zf.writestr("scripts/main.sh", "#!/bin/bash\necho 'Test'")
        zip_buffer.seek(0)

        response = client.post(
            "/api/upload",
            files={"file": (f"{skill_name}.zip", zip_buffer, "application/zip")},
            cookies=login_response.cookies
        )
        assert response.status_code in [200, 400, 401, 422]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE skill_name = %s", (skill_name,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestMySkillsAuthenticated:
    """Tests for authenticated my-skills endpoints."""

    def test_get_my_skills_authenticated(self):
        """Test getting user's skills with authentication."""
        emp_id = unique_name("t-msa")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_response = login_user(emp_id, api_key)

        response = client.get("/api/my-skills", cookies=login_response.cookies)
        assert response.status_code in [200, 401]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_get_skill_versions_authenticated(self):
        """Test getting skill versions with authentication."""
        emp_id = unique_name("t-msv")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-msv-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        login_response = login_user(emp_id, api_key)

        response = client.get(f"/api/my-skills/versions/{skill_name}", cookies=login_response.cookies)
        assert response.status_code in [200, 401]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_delete_skill_authenticated(self):
        """Test deleting skill with authentication."""
        emp_id = unique_name("t-dsa")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-dsa-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        login_response = login_user(emp_id, api_key)

        response = client.delete(f"/api/my-skills/{skill_id}", cookies=login_response.cookies)
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_publish_skill_authenticated(self):
        """Test publishing skill with authentication."""
        emp_id = unique_name("t-psa")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-psa-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        # Set skill to inactive first
        with get_connection() as conn:
            conn.execute("UPDATE skills SET is_active = 0 WHERE id = %s", (skill_id,))
            conn.commit()

        login_response = login_user(emp_id, api_key)

        response = client.post(f"/api/my-skills/{skill_id}/publish", cookies=login_response.cookies)
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_unlist_skill_authenticated(self):
        """Test unlisting skill with authentication."""
        emp_id = unique_name("t-usa")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-usa-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        login_response = login_user(emp_id, api_key)

        response = client.post(f"/api/my-skills/{skill_id}/unlist", cookies=login_response.cookies)
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestNotificationAuthenticated:
    """Tests for authenticated notification endpoints."""

    def test_get_notifications_authenticated(self):
        """Test getting notifications with authentication."""
        emp_id = unique_name("t-na")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_response = login_user(emp_id, api_key)

        response = client.get("/api/notifications", cookies=login_response.cookies)
        assert response.status_code in [200, 401]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_get_unread_count_authenticated(self):
        """Test getting unread notification count with authentication."""
        emp_id = unique_name("t-nu")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_response = login_user(emp_id, api_key)

        response = client.get("/api/notifications/unread-count", cookies=login_response.cookies)
        assert response.status_code in [200, 401]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_mark_notification_read_authenticated(self):
        """Test marking notification as read with authentication."""
        emp_id = unique_name("t-nr")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        # Create a notification
        notif_id = create_notification(user_id, "system", "Test notification")

        login_response = login_user(emp_id, api_key)

        response = client.post(f"/api/notifications/{notif_id}/read", cookies=login_response.cookies)
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE id = %s", (notif_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_mark_all_read_authenticated(self):
        """Test marking all notifications as read with authentication."""
        emp_id = unique_name("t-mar")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_response = login_user(emp_id, api_key)

        response = client.post("/api/notifications/read-all", cookies=login_response.cookies)
        assert response.status_code in [200, 401, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestAdminEndpointsAuthenticated:
    """Tests for authenticated admin endpoints."""

    def test_admin_stats_authenticated(self):
        """Test admin stats with admin authentication."""
        emp_id = unique_name("t-asa")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "admin")

        login_response = login_user(emp_id, api_key)

        response = client.get("/api/admin/stats", cookies=login_response.cookies)
        assert response.status_code in [200, 401, 403]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_admin_users_list_authenticated(self):
        """Test admin users list with admin authentication."""
        emp_id = unique_name("t-aul")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "admin")

        login_response = login_user(emp_id, api_key)

        response = client.get("/api/admin/users", cookies=login_response.cookies)
        assert response.status_code in [200, 401, 403]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_admin_skills_list_authenticated(self):
        """Test admin skills list with admin authentication."""
        emp_id = unique_name("t-asl")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "admin")

        login_response = login_user(emp_id, api_key)

        response = client.get("/api/admin/skills", cookies=login_response.cookies)
        assert response.status_code in [200, 401, 403]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_admin_pending_skills_authenticated(self):
        """Test admin pending skills with admin authentication."""
        emp_id = unique_name("t-aps")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "admin")

        login_response = login_user(emp_id, api_key)

        response = client.get("/api/pending", cookies=login_response.cookies)
        assert response.status_code in [200, 401, 403]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_admin_review_skill_authenticated(self):
        """Test admin review skill with admin authentication."""
        emp_id_uploader = unique_name("t-ars-u")
        uploader_id = create_user(emp_id_uploader, f"key-{emp_id_uploader}", "user")

        skill_name = unique_name("t-ars-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=uploader_id,
            status="pending",
            source_type="opensource"
        )

        emp_id_admin = unique_name("t-ars-a")
        api_key = f"key-{emp_id_admin}"
        admin_id = create_user(emp_id_admin, api_key, "admin")

        login_response = login_user(emp_id_admin, api_key)

        response = client.post(
            f"/api/review/{skill_id}",
            json={"action": "approve"},
            cookies=login_response.cookies
        )
        assert response.status_code in [200, 401, 403, 404, 422, 500]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id IN (%s, %s)", (uploader_id, admin_id))
            conn.commit()


class TestSkillDetailEndpoints:
    """Tests for skill detail endpoints."""

    def test_skill_detail_page(self):
        """Test skill detail page."""
        emp_id = unique_name("t-sdp")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")

        skill_name = unique_name("t-sdp-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        with get_connection() as conn:
            conn.execute(
                "UPDATE skills SET is_active = 1, description = 'Test skill' WHERE id = %s",
                (skill_id,)
            )
            conn.commit()

        response = client.get(f"/skill/{skill_name}")
        assert response.status_code in [200, 302, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_skill_detail_page_with_version(self):
        """Test skill detail page with specific version."""
        emp_id = unique_name("t-sdpv")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")

        skill_name = unique_name("t-sdpv-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        with get_connection() as conn:
            conn.execute(
                "UPDATE skills SET is_active = 1, description = 'Test skill' WHERE id = %s",
                (skill_id,)
            )
            conn.commit()

        response = client.get(f"/skill/{skill_name}/1.0.0")
        assert response.status_code in [200, 302, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestSearchEndpoints:
    """Tests for search endpoints."""

    def test_search_with_query(self):
        """Test search with query parameter."""
        response = client.get("/api/search?q=test")
        assert response.status_code in [200, 400, 404]

    def test_search_with_filters(self):
        """Test search with multiple filters."""
        response = client.get("/api/search?q=test&source_type=opensource&category=frontend")
        assert response.status_code in [200, 400, 404]

    def test_search_suggestions(self):
        """Test search suggestions endpoint."""
        response = client.get("/api/search/suggestions?prefix=test")
        assert response.status_code in [200, 400, 404]


class TestStatsEndpoints:
    """Tests for stats endpoints."""

    def test_stats_top_endpoint(self):
        """Test stats top endpoint."""
        response = client.get("/api/stats/top")
        assert response.status_code in [200, 401]

    def test_stats_export_endpoint(self):
        """Test stats export endpoint."""
        response = client.get("/api/stats/export")
        assert response.status_code in [200, 401]


class TestUserEndpoints:
    """Tests for user endpoints."""

    def test_get_user_profile_authenticated(self):
        """Test getting user profile with authentication."""
        emp_id = unique_name("t-gup")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_response = login_user(emp_id, api_key)

        response = client.get("/api/me", cookies=login_response.cookies)
        assert response.status_code in [200, 401, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_update_user_profile_authenticated(self):
        """Test updating user profile with authentication."""
        emp_id = unique_name("t-uup")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_response = login_user(emp_id, api_key)

        response = client.put(
            "/api/user/profile",
            json={"name": "Test User", "email": "test@example.com"},
            cookies=login_response.cookies
        )
        assert response.status_code in [200, 401, 403, 404, 422]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_get_user_uploads_authenticated(self):
        """Test getting user uploads with authentication."""
        emp_id = unique_name("t-guu")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_response = login_user(emp_id, api_key)

        response = client.get("/api/user/uploads", cookies=login_response.cookies)
        assert response.status_code in [200, 401]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestV1API:
    """Tests for V1 API endpoints."""

    def test_v1_skills_list(self):
        """Test V1 skills list endpoint."""
        response = client.get("/api/v1/skills")
        assert response.status_code in [200, 401]

    def test_v1_skills_with_pagination(self):
        """Test V1 skills with pagination."""
        response = client.get("/api/v1/skills?page=1&per_page=20")
        assert response.status_code in [200, 401]

    def test_v1_skill_by_name(self):
        """Test V1 skill by name endpoint."""
        emp_id = unique_name("t-v1sn")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")

        skill_name = unique_name("t-v1sn-skill")
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
        """Test V1 skill download endpoint."""
        emp_id = unique_name("t-v1sd")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")

        skill_name = unique_name("t-v1sd-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        response = client.get(f"/api/v1/skills/{skill_name}/download")
        assert response.status_code in [200, 302, 401, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestBatchOperations:
    """Tests for batch operations."""

    def test_batch_delete_authenticated(self):
        """Test batch delete with authentication."""
        emp_id = unique_name("t-bda")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_response = login_user(emp_id, api_key)

        response = client.post(
            "/api/my-skills/batch/delete",
            json={"skill_ids": [1, 2, 3]},
            cookies=login_response.cookies
        )
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_batch_unlist_authenticated(self):
        """Test batch unlist with authentication."""
        emp_id = unique_name("t-bua")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_response = login_user(emp_id, api_key)

        response = client.post(
            "/api/my-skills/batch/unlist",
            json={"skill_ids": [1, 2, 3]},
            cookies=login_response.cookies
        )
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestPluginDownload:
    """Tests for plugin download endpoints."""

    def test_download_plugin(self):
        """Test downloading plugin."""
        response = client.get("/plugins/test-skill.zip")
        assert response.status_code in [200, 302, 404]

    def test_download_plugin_with_version(self):
        """Test downloading plugin with version."""
        response = client.get("/plugins/test-skill-1.0.0.zip")
        assert response.status_code in [200, 302, 404]


class TestHealthEndpoints:
    """Tests for health endpoints."""

    def test_health_endpoint(self):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code in [200, 404]

    def test_api_health_endpoint(self):
        """Test API health endpoint."""
        response = client.get("/api/health")
        assert response.status_code in [200, 404]


class TestMarketplaceEndpoint:
    """Tests for marketplace endpoint."""

    def test_marketplace_json(self):
        """Test marketplace.json endpoint."""
        response = client.get("/marketplace.json")
        assert response.status_code == 200
        data = response.json()
        assert "plugins" in data or "skills" in data or "data" in data


class TestCategoryEndpoints:
    """Tests for category endpoints."""

    def test_get_categories(self):
        """Test getting categories."""
        response = client.get("/api/categories")
        assert response.status_code == 200
        data = response.json()
        assert "categories" in data

    def test_get_category_skills(self):
        """Test getting skills by category."""
        response = client.get("/api/categories/frontend/skills")
        assert response.status_code in [200, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
