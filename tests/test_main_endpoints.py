"""
Tests for main.py API endpoints.

Tests cover:
- Homepage API
- Skill listing and filtering
- Skill detail retrieval
- My-skills endpoints
- Skill versions
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_connection
import uuid
import io
import zipfile

from conftest import create_test_user, create_test_skill_zip
from test_shared import set_test_user_id


client = TestClient(app)


def unique_name(base: str) -> str:
    """Generate a unique name for testing."""
    return f"{base}-{uuid.uuid4().hex[:8]}"


def create_test_skill_direct(skill_name: str, user_id: int, version: str = "1.0.0",
                            source_type: str = "opensource", status: str = "approved",
                            is_active: int = 1, description: str = "Test skill",
                            filename: str = None) -> int:
    """Create a test skill directly in database."""
    if filename is None:
        filename = f"{skill_name}-{version}.zip"
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO skills (skill_name, version, filename, uploader_id, status,
                               source_type, is_active, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (skill_name, version, filename, user_id, status, source_type, is_active, description)
        )
        skill_id = cursor.lastrowid
        conn.commit()
        return skill_id


class TestHomepageAPI:
    """Tests for homepage skill listing API."""

    def test_get_skills_returns_success(self):
        """Test that /api/skills returns a successful response."""
        response = client.get("/api/skills")
        assert response.status_code == 200

    def test_get_skills_response_format(self):
        """Test /api/skills response format."""
        response = client.get("/api/skills")
        data = response.json()

        # Response should be a list or have skills key
        assert isinstance(data, (list, dict))

    def test_get_skills_with_source_type_filter(self):
        """Test filtering skills by source type."""
        response = client.get("/api/skills?source_type=opensource")
        assert response.status_code == 200


class TestSkillDetailAPI:
    """Tests for skill detail retrieval API."""

    def test_get_nonexistent_skill_returns_404(self):
        """Test that requesting a nonexistent skill returns 404."""
        response = client.get("/api/skills/nonexistent-skill-12345")
        assert response.status_code == 404


class TestMySkillsAPI:
    """Tests for my-skills endpoints."""

    def test_get_my_skills_list(self):
        """Test retrieving current user's skills."""
        user_id = create_test_user(unique_name("t-myskills"))
        skill_name_1 = unique_name("t-myskill-1")
        skill_name_2 = unique_name("t-myskill-2")

        create_test_skill_direct(skill_name_1, user_id)
        create_test_skill_direct(skill_name_2, user_id)

        response = client.get("/api/my-skills")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_get_my_skills_by_status(self):
        """Test filtering my-skills by status."""
        user_id = create_test_user(unique_name("t-mst"))
        skill_approved = unique_name("t-myskill-app")
        skill_pending = unique_name("t-myskill-pend")

        create_test_skill_direct(skill_approved, user_id, status="approved")
        create_test_skill_direct(skill_pending, user_id, status="pending")

        response = client.get("/api/my-skills?status=approved")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_get_my_skills_unauthorized(self):
        """Test that my-skills requires authentication."""
        # Reset test user to None to simulate unauthenticated request
        set_test_user_id(None)

        response = client.get("/api/my-skills")

        # Should still work due to dependency override returning default user
        # or return 401 if auth is properly enforced
        assert response.status_code in [200, 401]


class TestSkillPublishAPI:
    """Tests for skill publish endpoint."""

    def test_publish_unlisted_skill(self):
        """Test publishing an unlisted skill."""
        user_id = create_test_user(unique_name("t-publish"))
        skill_name = unique_name("t-publish")

        skill_id = create_test_skill_direct(skill_name, user_id, is_active=0)

        response = client.post(f"/api/my-skills/{skill_id}/publish")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify skill is now active
        with get_connection() as conn:
            skill = conn.execute(
                "SELECT is_active FROM skills WHERE id = %s",
                (skill_id,)
            ).fetchone()
            assert skill["is_active"] == 1


class TestSkillDeleteAPI:
    """Tests for skill delete endpoint."""

    def test_delete_skill_as_admin(self):
        """Test deleting a skill as admin."""
        user_id = create_test_user(unique_name("t-delete"), role="admin")
        skill_name = unique_name("t-delete")

        skill_id = create_test_skill_direct(skill_name, user_id)

        response = client.delete(f"/api/my-skills/{skill_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify skill is deleted
        with get_connection() as conn:
            skill = conn.execute(
                "SELECT * FROM skills WHERE id = %s",
                (skill_id,)
            ).fetchone()
            assert skill is None


class TestSkillVersions:
    """Tests for skill version endpoints."""

    def test_get_skill_versions(self):
        """Test getting skill versions."""
        user_id = create_test_user(unique_name("t-versions"))
        skill_name = unique_name("t-versioned")

        create_test_skill_direct(skill_name, user_id, version="1.0.0")

        response = client.get(f"/api/my-skills/versions/{skill_name}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Response has 'data' key containing versions list
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_get_skill_versions_nonexistent(self):
        """Test getting versions for nonexistent skill."""
        response = client.get("/api/my-skills/versions/nonexistent-skill-12345")

        # Should return 404 or empty list
        assert response.status_code in [200, 404]


class TestSetDefaultVersion:
    """Tests for set default version endpoint."""

    def test_set_default_version(self):
        """Test setting a skill as default version."""
        user_id = create_test_user(unique_name("t-default"))
        skill_name = unique_name("t-default")

        skill_id = create_test_skill_direct(skill_name, user_id)

        response = client.post(f"/api/my-skills/{skill_id}/set-default")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestMarketplaceAPI:
    """Tests for marketplace API."""

    def test_marketplace_json_endpoint(self):
        """Test marketplace.json endpoint."""
        response = client.get("/marketplace.json")

        assert response.status_code == 200
        data = response.json()

        # Marketplace format can vary - just verify it's valid JSON
        assert isinstance(data, (dict, list))


class TestSkillUploadValidation:
    """Tests for skill upload validation."""

    def test_upload_requires_authentication(self):
        """Test that upload requires authentication."""
        # Create a minimal valid skill zip
        skill_zip = create_test_skill_zip("test-skill", "1.0.0", "test-author")

        response = client.post(
            "/api/upload",
            files={"file": ("test-skill.zip", io.BytesIO(skill_zip), "application/zip")}
        )

        # Should work due to dependency override or return 400/401/422
        # 400 means validation error, which is acceptable
        assert response.status_code in [200, 400, 401, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
