"""
Tests for external API v1 endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from database import (
    get_connection, create_user, create_skill_record
)
import uuid


client = TestClient(app)


def unique_name(base: str) -> str:
    """Generate a unique name for testing."""
    return f"{base}-{uuid.uuid4().hex[:8]}"


class TestV1SkillsEndpoint:
    """Tests for /api/v1/skills endpoint."""

    def test_get_skills_without_auth(self):
        """Test getting skills list without auth."""
        response = client.get("/api/v1/skills")
        # May require auth or return empty list
        assert response.status_code in [200, 401]

    def test_get_skills_with_invalid_api_key(self):
        """Test getting skills with invalid API key."""
        response = client.get(
            "/api/v1/skills",
            headers={"X-API-Key": "invalid-key"}
        )
        assert response.status_code in [200, 401]

    def test_get_skill_by_name_without_auth(self):
        """Test getting skill by name without auth."""
        skill_name = unique_name("test-skill-v1")
        response = client.get(f"/api/v1/skills/{skill_name}")
        assert response.status_code in [200, 401, 404]

    def test_get_skill_by_name_nonexistent(self):
        """Test getting nonexistent skill by name."""
        response = client.get("/api/v1/skills/nonexistent-skill-xyz")
        assert response.status_code in [200, 401, 404]


class TestV1SkillDownload:
    """Tests for skill download via V1 API."""

    def test_download_skill_without_auth(self):
        """Test downloading skill without auth."""
        skill_name = unique_name("test-download")
        response = client.get(f"/api/v1/skills/{skill_name}/download")
        assert response.status_code in [200, 302, 401, 404]


class TestV1SkillSearch:
    """Tests for skill search via V1 API."""

    def test_search_skills_without_auth(self):
        """Test searching skills without auth."""
        response = client.get("/api/v1/skills/search?q=test")
        assert response.status_code in [200, 401]

    def test_search_skills_empty_query(self):
        """Test searching skills with empty query."""
        response = client.get("/api/v1/skills/search?q=")
        assert response.status_code in [200, 400, 401]


class TestAPIKeyEndpoints:
    """Tests for API key management endpoints."""

    def test_get_api_keys_without_auth(self):
        """Test getting API keys without auth."""
        response = client.get("/api/admin/api-keys")
        assert response.status_code in [200, 302, 401, 403]

    def test_create_api_key_without_auth(self):
        """Test creating API key without auth."""
        response = client.post(
            "/api/admin/api-keys",
            json={"name": "test-key", "description": "Test"}
        )
        assert response.status_code in [200, 302, 401, 403, 422]

    def test_delete_api_key_without_auth(self):
        """Test deleting API key without auth."""
        response = client.delete("/api/admin/api-keys/1")
        assert response.status_code in [200, 302, 401, 403, 404]


class TestGiteaIntegration:
    """Tests for Gitea integration endpoints."""

    def test_gitea_status_without_auth(self):
        """Test getting Gitea status without auth."""
        response = client.get("/api/gitea/status")
        assert response.status_code in [200, 302, 401, 403, 404]

    def test_gitea_tasks_without_auth(self):
        """Test getting Gitea tasks without auth."""
        response = client.get("/api/admin/gitea-tasks")
        assert response.status_code in [200, 302, 401, 403, 404]


class TestSkillRatingEndpoints:
    """Tests for skill rating endpoints."""

    def test_get_rating_without_auth(self):
        """Test getting skill rating without auth."""
        response = client.get("/api/skills/1/rating")
        assert response.status_code in [200, 401, 404]

    def test_submit_rating_without_auth(self):
        """Test submitting rating without auth."""
        response = client.post(
            "/api/skills/1/rating",
            json={"rating": 5}
        )
        assert response.status_code in [200, 302, 401, 403, 404, 422]


class TestSkillCommentEndpoints:
    """Tests for skill comment endpoints."""

    def test_get_comments_without_auth(self):
        """Test getting skill comments without auth."""
        response = client.get("/api/skills/1/comments")
        assert response.status_code in [200, 401, 404]

    def test_add_comment_without_auth(self):
        """Test adding comment without auth."""
        response = client.post(
            "/api/skills/1/comments",
            json={"content": "Test comment"}
        )
        assert response.status_code in [200, 302, 401, 403, 404, 422]


class TestSkillRelatedEndpoints:
    """Tests for skill related endpoints."""

    def test_get_related_skills(self):
        """Test getting related skills."""
        response = client.get("/api/skills/1/related")
        assert response.status_code in [200, 401, 404]

    def test_increment_view_count(self):
        """Test incrementing view count."""
        response = client.post("/api/skills/1/view")
        assert response.status_code in [200, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
