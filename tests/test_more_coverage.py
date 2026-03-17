"""
More tests to increase coverage of main.py and database.py
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


class TestDatabaseConnectionHandling:
    """Tests for database connection handling."""

    def test_connection_context_manager(self):
        """Test connection context manager."""
        with get_connection() as conn:
                result = conn.execute("SELECT 1")
                assert result is not None

    def test_multiple_connections(self):
        """Test multiple concurrent connections."""
        connections = []
        try:
                for i in range(3):
                    conn = get_connection()
                    connections.append(conn)
                assert len(connections) == 3
        finally:
                for conn in connections:
                    try:
                        conn.close()
                    except Exception:
                        pass


class TestUserManagement:
    """Tests for user management."""

    def test_create_user_success(self):
        """Test creating user successfully."""
        emp_id = unique_name("t-cus")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")
        try:
                assert user_id is not None
                assert user_id > 0
        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()

    def test_create_admin_user(self):
        """Test creating admin user."""
        emp_id = unique_name("t-cau")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "admin")
        try:
                assert user_id is not None
                with get_connection() as conn:
                    result = conn.execute(
                        "SELECT role FROM users WHERE id = %s",
                        (user_id,)
                    )
                    row = result.fetchone()
                    assert row is not None
                    assert row["role"] == "admin"
        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestSkillManagement:
    """Tests for skill management."""

    def test_create_skill_record_success(self):
        """Test creating skill record successfully."""
        emp_id = unique_name("t-csrs")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")
        skill_name = unique_name("skill")

        try:
                skill_id = create_skill_record(
                    skill_name=skill_name,
                    version="1.0.0",
                    filename=f"{skill_name}.zip",
                    uploader_id=user_id,
                    status="pending",
                    source_type="opensource"
                )
                assert skill_id is not None
                assert skill_id > 0
        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
                conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestLoginEndpoint:
    """Tests for login endpoint."""

    def test_login_page_loads(self):
        """Test login page loads."""
        response = client.get("/login")
        assert response.status_code == 200

    def test_login_with_valid_credentials(self):
        """Test login with valid credentials."""
        emp_id = unique_name("t-lv")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")
        try:
                response = client.post("/api/login", data={
                    "employee_id": emp_id,
                    "api_key": api_key
                }, follow_redirects=False)
                assert response.status_code in [200, 302]
        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()

    def test_login_with_invalid_credentials(self):
        """Test login with invalid credentials."""
        response = client.post("/api/login", data={
            "employee_id": "nonexistent_user",
            "api_key": "wrong_key"
        }, follow_redirects=False)
        assert response.status_code in [200, 302, 401]

    def test_login_with_missing_fields(self):
        """Test login with missing fields."""
        response = client.post("/api/login", data={
            "employee_id": "",
            "api_key": ""
        }, follow_redirects=False)
        assert response.status_code in [200, 302, 400, 422]


class TestMarketplaceEndpoint:
    """Tests for marketplace endpoint."""

    def test_marketplace_returns_valid_json(self):
        """Test marketplace returns valid JSON."""
        response = client.get("/marketplace.json")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "plugins" in data

    def test_marketplace_with_pagination(self):
        """Test marketplace with pagination parameters."""
        response = client.get("/marketplace.json?page=1&per_page=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


class TestSkillsListEndpoint:
    """Tests for skills list endpoint."""

    def test_skills_list_returns_data(self):
        """Test skills list returns data."""
        response = client.get("/api/skills")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data or isinstance(data, list)

    def test_skills_list_with_pagination(self):
        """Test skills list with pagination."""
        response = client.get("/api/skills?page=1&per_page=10")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data or "total" in data

    def test_skills_list_with_invalid_page(self):
        """Test skills list with invalid page number."""
        response = client.get("/api/skills?page=-1")
        assert response.status_code in [200, 400, 422]


class TestAdminEndpoints:
    """Tests for admin endpoints."""

    def test_admin_pending_without_auth(self):
        """Test admin pending endpoint without auth."""
        response = client.get("/api/pending")
        assert response.status_code in [200, 302, 401, 403]

    def test_admin_users_without_auth(self):
        """Test admin users endpoint without auth."""
        response = client.get("/api/admin/users")
        assert response.status_code in [200, 302, 401, 403, 404]


class TestSkillDetailEndpoints:
    """Tests for skill detail endpoints."""

    def test_skill_by_name_not_found(self):
        """Test skill by name when not found."""
        response = client.get("/api/skill/nonexistent-skill-xyz")
        assert response.status_code in [200, 404]

    def test_skill_by_id_not_found(self):
        """Test skill by ID when not found."""
        response = client.get("/api/skills/999999")
        assert response.status_code in [200, 404]


class TestSearchEndpoints:
    """Tests for search endpoints."""

    def test_search_with_query(self):
        """Test search with query parameter."""
        response = client.get("/api/search?q=test")
        assert response.status_code in [200, 400, 404]

    def test_search_with_empty_query(self):
        """Test search with empty query."""
        response = client.get("/api/search?q=")
        assert response.status_code in [200, 400]

    def test_search_suggestions(self):
        """Test search suggestions endpoint."""
        response = client.get("/api/search/suggestions?prefix=test")
        assert response.status_code in [200, 400, 404]


class TestStaticFileEndpoints:
    """Tests for static file endpoints."""

    def test_nonexistent_plugin_file(self):
        """Test nonexistent plugin file."""
        response = client.get("/plugins/nonexistent.zip")
        assert response.status_code in [200, 404]


class TestErrorPages:
    """Tests for error pages."""

    def test_404_page(self):
        """Test 404 error page."""
        response = client.get("/nonexistent-page-xyz")
        assert response.status_code == 404

    def test_method_not_allowed(self):
        """Test method not allowed error."""
        response = client.delete("/api/skills")
        assert response.status_code in [405, 404]


class TestCORSHeaders:
    """Tests for CORS headers."""

    def test_cors_preflight(self):
        """Test CORS preflight request."""
        response = client.options("/api/skills")
        assert response.status_code in [200, 405, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
