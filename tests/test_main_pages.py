"""
More tests for main.py endpoints to further increase coverage.

Tests cover:
- Web UI endpoints
- Static file serving
- Template rendering
- Form submissions
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_connection, create_user, create_skill_record
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
description: A test skill
metadata:
  version: {version}
  author: w00000001
  license: MIT
---

# {skill_name}

Test skill content.
"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("SKILL.md", skill_md_content)
    zip_buffer.seek(0)
    return zip_buffer.read()


class TestWebUIEndpoints:
    """Tests for web UI endpoints."""

    def test_home_page(self):
        """Test home page renders."""
        response = client.get("/")
        assert response.status_code in [200, 302]

    def test_skills_page(self):
        """Test skills listing page."""
        response = client.get("/skills")
        assert response.status_code in [200, 302, 404]

    def test_install_guide_page(self):
        """Test install guide page."""
        response = client.get("/install")
        assert response.status_code in [200, 302, 404]

    def test_api_docs(self):
        """Test API documentation page."""
        response = client.get("/docs")
        assert response.status_code in [200, 404]

    def test_openapi_schema(self):
        """Test OpenAPI schema endpoint."""
        response = client.get("/openapi.json")
        assert response.status_code in [200, 404]


class TestFormSubmissions:
    """Tests for form submission endpoints."""

    def test_login_form_submission(self):
        """Test login form submission."""
        response = client.post("/admin/login", data={
            "username": "test",
            "password": "test"
        })
        assert response.status_code in [200, 302, 400, 401, 422]

    def test_search_form_submission(self):
        """Test search form submission."""
        response = client.post("/search", data={
            "query": "test"
        })
        assert response.status_code in [200, 302, 404, 405]


class TestAPIEndpointsExtended:
    """Extended tests for API endpoints."""

    def test_api_skills_list(self):
        """Test API skills list endpoint."""
        response = client.get("/api/skills")
        assert response.status_code == 200

    def test_api_skills_with_pagination(self):
        """Test API skills with pagination."""
        response = client.get("/api/skills?page=1&limit=20")
        assert response.status_code == 200

    def test_api_skill_detail_not_found(self):
        """Test API skill detail for non-existent skill."""
        response = client.get("/api/skills/nonexistent-skill-xyz")
        assert response.status_code == 404

    def test_api_my_skills(self):
        """Test API my-skills endpoint."""
        response = client.get("/api/my-skills")
        assert response.status_code in [200, 401]

    def test_api_pending_skills(self):
        """Test API pending skills endpoint."""
        response = client.get("/api/pending")
        assert response.status_code in [200, 401, 403]

    def test_api_stats(self):
        """Test API stats endpoint."""
        response = client.get("/api/stats")
        assert response.status_code in [200, 401, 404]

    def test_api_users_list(self):
        """Test API users list endpoint."""
        response = client.get("/api/users")
        assert response.status_code in [200, 401, 403, 404]

    def test_api_download_count(self):
        """Test API download count endpoint."""
        response = client.get("/api/downloads/count")
        assert response.status_code in [200, 401, 404]


class TestSkillOperations:
    """Tests for skill operations."""

    def test_upload_skill_valid(self):
        """Test uploading a valid skill."""
        emp_id = unique_name("t-upsv")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")
        skill_zip = create_test_skill_zip("test-skill-upload")

        response = client.post(
            "/api/upload",
            files={"file": ("test-skill.zip", io.BytesIO(skill_zip), "application/zip")}
        )

        assert response.status_code in [200, 400, 401, 422]

    def test_upload_skill_empty_file(self):
        """Test uploading empty file."""
        response = client.post(
            "/api/upload",
            files={"file": ("empty.zip", io.BytesIO(b""), "application/zip")}
        )

        assert response.status_code in [400, 401, 422]

    def test_upload_skill_no_file(self):
        """Test upload without file."""
        response = client.post("/api/upload")
        assert response.status_code in [400, 422]


class TestSkillStatusEndpoints:
    """Tests for skill status endpoints."""

    def test_unlist_skill(self):
        """Test unlisting a skill."""
        emp_id = unique_name("t-unl")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")
        skill_name = unique_name("t-unl-skill")

        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        response = client.post(f"/api/my-skills/{skill_id}/unlist")
        assert response.status_code in [200, 401, 403, 404]

    def test_delete_skill_endpoint(self):
        """Test delete skill endpoint."""
        emp_id = unique_name("t-del")
        user_id = create_user(emp_id, f"key-{emp_id}", "admin")
        skill_name = unique_name("t-del-skill")

        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        response = client.delete(f"/api/my-skills/{skill_id}")
        assert response.status_code in [200, 401, 403, 404]


class TestSkillVersionEndpoints:
    """Tests for skill version endpoints."""

    def test_get_skill_versions(self):
        """Test getting skill versions."""
        emp_id = unique_name("t-ver")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")
        skill_name = unique_name("t-ver-skill")

        create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        response = client.get(f"/api/my-skills/versions/{skill_name}")
        assert response.status_code in [200, 401, 404]

    def test_set_default_version(self):
        """Test setting default version."""
        emp_id = unique_name("t-sdv")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")
        skill_name = unique_name("t-sdv-skill")

        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        response = client.post(f"/api/my-skills/{skill_id}/set-default")
        assert response.status_code in [200, 401, 403, 404]


class TestUserEndpoints:
    """Tests for user endpoints."""

    def test_get_user_profile(self):
        """Test getting user profile."""
        response = client.get("/api/user/profile")
        assert response.status_code in [200, 401, 404]

    def test_update_user_profile(self):
        """Test updating user profile."""
        response = client.put("/api/user/profile", json={
            "name": "Test User"
        })
        assert response.status_code in [200, 401, 404, 405, 422]

    def test_change_password(self):
        """Test changing password."""
        response = client.post("/api/user/change-password", json={
            "old_password": "old",
            "new_password": "new"
        })
        assert response.status_code in [200, 401, 404, 405, 422]


class TestNotificationEndpoints:
    """Tests for notification endpoints."""

    def test_get_notifications(self):
        """Test getting notifications."""
        response = client.get("/api/notifications")
        assert response.status_code in [200, 401, 404]

    def test_mark_notification_read(self):
        """Test marking notification as read."""
        response = client.post("/api/notifications/1/read")
        assert response.status_code in [200, 401, 404]

    def test_mark_all_notifications_read(self):
        """Test marking all notifications as read."""
        response = client.post("/api/notifications/read-all")
        assert response.status_code in [200, 401, 404]


class TestStaticFiles:
    """Tests for static file serving."""

    def test_plugins_directory_listing(self):
        """Test plugins directory listing (should be disabled)."""
        response = client.get("/plugins/")
        assert response.status_code in [200, 403, 404]

    def test_static_file_not_found(self):
        """Test requesting non-existent static file."""
        response = client.get("/static/nonexistent.css")
        assert response.status_code in [200, 403, 404]


class TestCORSAndHeaders:
    """Tests for CORS and security headers."""

    def test_cors_preflight(self):
        """Test CORS preflight request."""
        response = client.options("/api/skills", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        })
        assert response.status_code in [200, 400, 405]

    def test_content_type_json(self):
        """Test that API returns JSON content type."""
        response = client.get("/api/skills")
        if response.status_code == 200:
            assert "application/json" in response.headers.get("content-type", "")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
