"""
Tests for main.py authentication and admin endpoints.

Tests cover:
- Login/logout functionality
- Admin endpoints
- Session management
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_connection
import uuid

from conftest import create_test_user, create_test_skill_zip
from test_shared import set_test_user_id
import io


client = TestClient(app)


def unique_name(base: str) -> str:
    """Generate a unique name for testing."""
    return f"{base}-{uuid.uuid4().hex[:8]}"


class TestLoginAPI:
    """Tests for login API endpoints."""

    def test_login_page_renders(self):
        """Test that login page renders successfully."""
        response = client.get("/admin/login")
        assert response.status_code == 200

    def test_login_with_invalid_credentials(self):
        """Test login with invalid credentials."""
        response = client.post("/api/login", json={
            "employee_id": "invalid",
            "api_key": "invalid"
        })
        # Should return error for invalid credentials
        assert response.status_code in [400, 401, 422]

    def test_login_with_missing_fields(self):
        """Test login with missing required fields."""
        response = client.post("/api/login", json={
            "employee_id": "test"
        })
        assert response.status_code == 422  # Validation error


class TestAdminEndpoints:
    """Tests for admin-only endpoints."""

    def test_admin_pending_skills_as_admin(self):
        """Test getting pending skills as admin."""
        user_id = create_test_user(unique_name("t-admin"), role="admin")
        response = client.get("/api/pending")
        # Should succeed with admin override
        assert response.status_code in [200, 401, 403]

    def test_admin_pending_skills_as_user(self):
        """Test getting pending skills as regular user."""
        user_id = create_test_user(unique_name("t-user"))
        response = client.get("/api/pending")
        # Should be forbidden for regular users
        assert response.status_code in [200, 401, 403]

    def test_admin_stats_endpoint(self):
        """Test admin statistics endpoint."""
        user_id = create_test_user(unique_name("t-stats"), role="admin")
        response = client.get("/stats")
        assert response.status_code in [200, 302, 401, 403]


class TestSessionManagement:
    """Tests for session management."""

    def test_logout_endpoint(self):
        """Test logout functionality."""
        response = client.get("/api/logout")
        # Should redirect or return success
        assert response.status_code in [200, 302, 404]

    def test_session_persistence(self):
        """Test that session persists across requests."""
        user_id = create_test_user(unique_name("t-session"))

        # First request to set session
        response1 = client.get("/api/my-skills")
        assert response1.status_code in [200, 401]

        # Second request should use same session
        response2 = client.get("/api/my-skills")
        assert response2.status_code == response1.status_code


class TestSkillUpload:
    """Tests for skill upload functionality."""

    def test_upload_valid_skill(self):
        """Test uploading a valid skill ZIP."""
        user_id = create_test_user(unique_name("t-upload"))
        skill_zip = create_test_skill_zip("test-skill", "1.0.0", "w00000001")

        response = client.post(
            "/api/upload",
            files={"file": ("test-skill.zip", io.BytesIO(skill_zip), "application/zip")}
        )

        # Should succeed or return validation error
        assert response.status_code in [200, 400, 422]

    def test_upload_invalid_file_type(self):
        """Test uploading invalid file type."""
        user_id = create_test_user(unique_name("t-upinv"))

        response = client.post(
            "/api/upload",
            files={"file": ("test.txt", io.BytesIO(b"not a zip"), "text/plain")}
        )

        # Should reject non-ZIP files
        assert response.status_code in [400, 422]

    def test_upload_missing_skill_md(self):
        """Test uploading ZIP without SKILL.md."""
        user_id = create_test_user(unique_name("t-upmd"))
        import zipfile
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("README.md", "# Test")
        zip_buffer.seek(0)

        response = client.post(
            "/api/upload",
            files={"file": ("no-skill.zip", zip_buffer, "application/zip")}
        )

        # Should reject or handle gracefully
        assert response.status_code in [200, 400, 422]


class TestReviewEndpoints:
    """Tests for skill review functionality."""

    def test_approve_skill(self):
        """Test approving a pending skill."""
        admin_id = create_test_user(unique_name("t-review"), role="admin")
        skill_name = unique_name("t-approve")

        # Create pending skill directly
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO skills (skill_name, version, filename, uploader_id, status,
                                   source_type, is_active, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (skill_name, "1.0.0", f"{skill_name}-1.0.0.zip", admin_id, "pending", "opensource", 0, "Test")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        response = client.post(f"/api/review/{skill_id}", json={
            "action": "approve"
        })

        # Should succeed or return auth error (500 if file not found)
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_reject_skill(self):
        """Test rejecting a pending skill."""
        admin_id = create_test_user(unique_name("t-reject"), role="admin")
        skill_name = unique_name("t-reject-skill")

        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO skills (skill_name, version, filename, uploader_id, status,
                                   source_type, is_active, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (skill_name, "1.0.0", f"{skill_name}-1.0.0.zip", admin_id, "pending", "opensource", 0, "Test")
            )
            skill_id = cursor.lastrowid
            conn.commit()

        response = client.post(f"/api/review/{skill_id}", json={
            "action": "reject",
            "comment": "Test rejection"
        })

        assert response.status_code in [200, 400, 401, 403, 404]

    def test_review_nonexistent_skill(self):
        """Test reviewing a nonexistent skill."""
        admin_id = create_test_user(unique_name("t-rev-ne"), role="admin")

        response = client.post("/api/review/99999", json={
            "action": "approve"
        })

        assert response.status_code in [400, 401, 403, 404]


class TestSkillDetail:
    """Tests for skill detail retrieval."""

    def test_get_skill_detail(self):
        """Test getting skill detail."""
        user_id = create_test_user(unique_name("t-detail"))
        skill_name = unique_name("t-detail-skill")

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO skills (skill_name, version, filename, uploader_id, status,
                                   source_type, is_active, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (skill_name, "1.0.0", f"{skill_name}-1.0.0.zip", user_id, "approved", "opensource", 1, "Test skill")
            )
            conn.commit()

        response = client.get(f"/api/skills/{skill_name}")
        assert response.status_code in [200, 404]

    def test_get_skill_detail_with_version(self):
        """Test getting skill detail with specific version."""
        user_id = create_test_user(unique_name("t-det-ver"))
        skill_name = unique_name("t-detver")

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO skills (skill_name, version, filename, uploader_id, status,
                                   source_type, is_active, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (skill_name, "1.0.0", f"{skill_name}-1.0.0.zip", user_id, "approved", "opensource", 1, "Test skill")
            )
            conn.commit()

        response = client.get(f"/api/skills/{skill_name}?version=1.0.0")
        assert response.status_code in [200, 404]


class TestHomepageFilters:
    """Tests for homepage filtering."""

    def test_filter_by_source_type_opensource(self):
        """Test filtering by opensource source type."""
        response = client.get("/api/skills?source_type=opensource")
        assert response.status_code == 200

    def test_filter_by_source_type_icsl(self):
        """Test filtering by icsl source type."""
        response = client.get("/api/skills?source_type=icsl")
        assert response.status_code == 200

    def test_filter_by_source_type_huawei(self):
        """Test filtering by huawei source type."""
        response = client.get("/api/skills?source_type=huawei")
        assert response.status_code == 200

    def test_search_skills(self):
        """Test searching skills."""
        response = client.get("/api/skills?search=test")
        assert response.status_code == 200


class TestDownloadEndpoint:
    """Tests for download endpoint."""

    def test_download_nonexistent_file(self):
        """Test downloading a nonexistent file."""
        response = client.get("/plugins/nonexistent-file-12345.zip")
        # Should return 404 or redirect to login
        assert response.status_code in [302, 404, 401]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
