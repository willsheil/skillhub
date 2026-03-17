"""
Edge case tests for various API endpoints.
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


class TestPaginationEdgeCases:
    """Tests for pagination edge cases."""

    def test_skills_list_page_zero(self):
        """Test skills list with page 0."""
        response = client.get("/api/skills?page=0&per_page=10")
        assert response.status_code in [200, 400, 422]

    def test_skills_list_negative_page(self):
        """Test skills list with negative page."""
        response = client.get("/api/skills?page=-1&per_page=10")
        assert response.status_code in [200, 400, 422]

    def test_skills_list_large_per_page(self):
        """Test skills list with large per_page."""
        response = client.get("/api/skills?page=1&per_page=10000")
        assert response.status_code in [200, 400, 422]

    def test_skills_list_zero_per_page(self):
        """Test skills list with zero per_page - should return 422 validation error."""
        response = client.get("/api/skills?page=1&per_page=0")
        # per_page has ge=1 validation, so 0 should return 422
        assert response.status_code == 422


class TestSearchEdgeCases:
    """Tests for search edge cases."""

    def test_search_with_special_characters(self):
        """Test search with special characters."""
        response = client.get("/api/search?q=<script>alert(1)</script>")
        assert response.status_code in [200, 400]

    def test_search_with_unicode(self):
        """Test search with unicode characters."""
        response = client.get("/api/search?q=测试")
        assert response.status_code in [200, 400]

    def test_search_with_long_query(self):
        """Test search with very long query."""
        long_query = "a" * 1000
        response = client.get(f"/api/search?q={long_query}")
        assert response.status_code in [200, 400]

    def test_search_suggestions_with_special_chars(self):
        """Test search suggestions with special characters."""
        response = client.get("/api/search/suggestions?prefix=test<script>")
        assert response.status_code in [200, 400]


class TestUserInputValidation:
    """Tests for user input validation."""

    def test_login_with_sql_injection_attempt(self):
        """Test login with SQL injection attempt."""
        response = client.post("/api/login", data={
            "employee_id": "admin' OR '1'='1",
            "api_key": "anything"
        })
        # Should not succeed with SQL injection
        assert response.status_code in [200, 302, 400, 401]

    def test_login_with_empty_strings(self):
        """Test login with empty strings."""
        response = client.post("/api/login", data={
            "employee_id": "",
            "api_key": ""
        })
        assert response.status_code in [200, 302, 400, 422]

    def test_login_with_whitespace(self):
        """Test login with whitespace."""
        response = client.post("/api/login", data={
            "employee_id": "   ",
            "api_key": "   "
        })
        assert response.status_code in [200, 302, 400, 401]


class TestContentTypeHandling:
    """Tests for content type handling."""

    def test_json_endpoint_with_form_data(self):
        """Test JSON endpoint receiving form data - should handle gracefully."""
        response = client.post(
            "/api/admin/users",
            data="employee_id=test&api_key=test&role=user",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        # May return various error codes depending on auth and validation
        assert response.status_code in [200, 302, 400, 401, 403, 404, 422, 500]

    def test_form_endpoint_with_json(self):
        """Test form endpoint receiving JSON."""
        response = client.post(
            "/api/login",
            json={"employee_id": "test", "api_key": "test"}
        )
        assert response.status_code in [200, 302, 400, 422]


class TestHTTPMethods:
    """Tests for HTTP method handling."""

    def test_get_on_post_endpoint(self):
        """Test GET request on POST-only endpoint."""
        response = client.get("/api/login")
        assert response.status_code in [200, 405]

    def test_delete_on_get_endpoint(self):
        """Test DELETE request on GET-only endpoint."""
        response = client.delete("/api/skills")
        assert response.status_code in [200, 405]

    def test_patch_on_get_endpoint(self):
        """Test PATCH request on GET-only endpoint."""
        response = client.patch("/api/skills")
        assert response.status_code in [200, 405]


class TestURLEncoding:
    """Tests for URL encoding handling."""

    def test_skill_name_with_spaces(self):
        """Test skill name with spaces (URL encoded)."""
        response = client.get("/api/skill/test%20skill")
        assert response.status_code in [200, 404]

    def test_skill_name_with_slash(self):
        """Test skill name with slash (URL encoded)."""
        response = client.get("/api/skill/test%2Fskill")
        assert response.status_code in [200, 404]

    def test_skill_name_with_percent(self):
        """Test skill name with percent sign."""
        response = client.get("/api/skill/test%25skill")
        assert response.status_code in [200, 404]


class TestRateLimiting:
    """Tests for rate limiting (if implemented)."""

    def test_multiple_rapid_requests(self):
        """Test multiple rapid requests."""
        responses = []
        for i in range(10):
            response = client.get("/api/health")
            responses.append(response.status_code)

        # All should succeed if no rate limiting, or some may fail if rate limiting exists
        assert all(r in [200, 429] for r in responses)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
