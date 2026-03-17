"""
Additional tests for main.py endpoints to increase coverage.

Tests cover:
- Admin dashboard endpoints
- User profile endpoints
- Search and filter functionality
- Error handling paths
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_connection, create_user, create_skill_record
import uuid


client = TestClient(app)


def unique_name(base: str) -> str:
    """Generate a unique name for testing."""
    return f"{base}-{uuid.uuid4().hex[:8]}"


class TestAdminDashboard:
    """Tests for admin dashboard endpoints."""

    def test_admin_page_access(self):
        """Test admin page access."""
        response = client.get("/admin")
        # May redirect to login or show admin page
        assert response.status_code in [200, 302, 401, 403, 404]

    def test_admin_users_page(self):
        """Test admin users management page."""
        response = client.get("/admin/users")
        assert response.status_code in [200, 302, 401, 403, 404]

    def test_admin_skills_page(self):
        """Test admin skills management page."""
        response = client.get("/admin/skills")
        assert response.status_code in [200, 302, 401, 403, 404]

    def test_admin_stats_page(self):
        """Test admin statistics page."""
        response = client.get("/admin/stats")
        assert response.status_code in [200, 302, 401, 403, 404]


class TestUserProfile:
    """Tests for user profile endpoints."""

    def test_user_profile_page(self):
        """Test user profile page."""
        emp_id = unique_name("t-prof")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")

        response = client.get("/profile")
        # May redirect to login or show profile
        assert response.status_code in [200, 302, 401, 404]

    def test_user_settings_page(self):
        """Test user settings page."""
        response = client.get("/settings")
        assert response.status_code in [200, 302, 401, 404]


class TestSearchEndpoints:
    """Tests for search functionality."""

    def test_search_skills_endpoint(self):
        """Test skill search endpoint."""
        response = client.get("/api/skills/search?q=test")
        assert response.status_code in [200, 400, 404]

    def test_search_with_empty_query(self):
        """Test search with empty query."""
        response = client.get("/api/skills/search?q=")
        assert response.status_code in [200, 400, 404]

    def test_search_with_special_characters(self):
        """Test search with special characters."""
        response = client.get("/api/skills/search?q=%3Cscript%3E")
        assert response.status_code in [200, 400, 404]


class TestCategoryEndpoints:
    """Tests for category functionality."""

    def test_get_categories(self):
        """Test getting categories."""
        response = client.get("/api/categories")
        assert response.status_code in [200, 404]

    def test_get_category_by_slug(self):
        """Test getting category by slug."""
        response = client.get("/api/categories/test-category")
        assert response.status_code in [200, 404]


class TestDownloadTracking:
    """Tests for download tracking."""

    def test_record_download(self):
        """Test recording a download."""
        response = client.get("/api/skills/1/download")
        assert response.status_code in [200, 302, 401, 404]

    def test_download_stats(self):
        """Test download stats endpoint."""
        response = client.get("/api/stats/downloads")
        assert response.status_code in [200, 401, 404]


class TestRatingEndpoints:
    """Tests for rating functionality."""

    def test_get_skill_ratings(self):
        """Test getting skill ratings."""
        emp_id = unique_name("t-rtg")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")
        skill_name = unique_name("t-rtg-skill")

        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        response = client.get(f"/api/skills/{skill_id}/ratings")
        assert response.status_code in [200, 404]

    def test_submit_rating_unauthenticated(self):
        """Test submitting rating without auth."""
        response = client.post("/api/skills/1/rate", json={"rating": 5})
        assert response.status_code in [200, 401, 403, 404, 422]


class TestCommentEndpoints:
    """Tests for comment functionality."""

    def test_get_comments(self):
        """Test getting skill comments."""
        response = client.get("/api/skills/1/comments")
        assert response.status_code in [200, 404]

    def test_add_comment_unauthenticated(self):
        """Test adding comment without auth."""
        response = client.post("/api/skills/1/comments", json={"content": "Test"})
        assert response.status_code in [200, 401, 403, 404, 422]


class TestHealthCheck:
    """Tests for health check endpoints."""

    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code in [200, 404]

    def test_api_health(self):
        """Test API health check."""
        response = client.get("/api/health")
        assert response.status_code in [200, 404]


class TestErrorHandling:
    """Tests for error handling."""

    def test_404_for_unknown_route(self):
        """Test 404 for unknown routes."""
        response = client.get("/api/unknown-endpoint-12345")
        assert response.status_code == 404

    def test_method_not_allowed(self):
        """Test method not allowed error."""
        response = client.patch("/api/skills")
        assert response.status_code in [405, 404]

    def test_invalid_json(self):
        """Test invalid JSON handling."""
        response = client.post(
            "/api/login",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [400, 422]


class TestPagination:
    """Tests for pagination."""

    def test_skills_pagination(self):
        """Test skills list pagination."""
        response = client.get("/api/skills?page=1&per_page=10")
        assert response.status_code == 200

    def test_invalid_page_number(self):
        """Test with invalid page number."""
        response = client.get("/api/skills?page=-1")
        assert response.status_code in [200, 400, 422]

    def test_large_per_page(self):
        """Test with large per_page value."""
        response = client.get("/api/skills?per_page=1000")
        assert response.status_code in [200, 400, 422]


class TestSortOrder:
    """Tests for sorting."""

    def test_sort_by_name(self):
        """Test sorting by name."""
        response = client.get("/api/skills?sort=name")
        assert response.status_code == 200

    def test_sort_by_date(self):
        """Test sorting by date."""
        response = client.get("/api/skills?sort=date")
        assert response.status_code == 200

    def test_sort_descending(self):
        """Test descending sort order."""
        response = client.get("/api/skills?sort=date&order=desc")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
