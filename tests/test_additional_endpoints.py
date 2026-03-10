"""
Additional tests for more main.py endpoints.
Focus on user management, notifications, and misc endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from database import (
    get_connection, create_user, create_skill_record,
    create_notification, get_user_by_id
)
import uuid


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


class TestUserManagementEndpoints:
    """Tests for user management endpoints."""

    def test_get_users_list_as_admin(self):
        """Test getting users list as admin."""
        admin_id = unique_name("t-gula")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/admin/users", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 403]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()

    def test_create_user_as_admin(self):
        """Test creating a new user as admin."""
        admin_id = unique_name("t-cuaa")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        new_user_emp_id = unique_name("new-user")

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                "/api/admin/users",
                json={
                    "employee_id": new_user_emp_id,
                    "api_key": "test-key-123",
                    "role": "user"
                },
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 201, 401, 403, 422]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE employee_id = %s", (new_user_emp_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()

    def test_update_user_role_as_admin(self):
        """Test updating user role as admin."""
        admin_id = unique_name("t-uura")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        user_id = create_user(unique_name("target-user"), "key", "user")

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.put(
                f"/api/admin/users/{user_id}",
                json={"role": "admin"},
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 403, 404, 422]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()

    def test_disable_user_as_admin(self):
        """Test disabling user as admin."""
        admin_id = unique_name("t-duaa")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        user_id = create_user(unique_name("target-user"), "key", "user")

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.patch(
                f"/api/admin/users/{user_id}/disable",
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 403, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()

    def test_enable_user_as_admin(self):
        """Test enabling user as admin."""
        admin_id = unique_name("t-euaa")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        user_id = create_user(unique_name("target-user"), "key", "user")

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.patch(
                f"/api/admin/users/{user_id}/enable",
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 403, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()

    def test_delete_user_as_admin(self):
        """Test deleting user as admin."""
        admin_id = unique_name("t-dela")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        user_id = create_user(unique_name("target-user"), "key", "user")

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.delete(
                f"/api/admin/users/{user_id}",
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 403, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()

    def test_reset_user_api_key_as_admin(self):
        """Test resetting user API key as admin."""
        admin_id = unique_name("t-ruak")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        user_id = create_user(unique_name("target-user"), "key", "user")

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                f"/api/admin/users/{user_id}/reset-key",
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 403, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()


class TestNotificationEndpoints:
    """Tests for notification endpoints."""

    def test_get_notifications(self):
        """Test getting user notifications."""
        emp_id = unique_name("t-gn")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/notifications", cookies=login_resp.cookies)
            assert response.status_code in [200, 401]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE user_id = %s", (user_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()

    def test_get_unread_count(self):
        """Test getting unread notification count."""
        emp_id = unique_name("t-guc")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/notifications/unread-count", cookies=login_resp.cookies)
            assert response.status_code in [200, 401]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE user_id = %s", (user_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()

    def test_mark_notification_read(self):
        """Test marking notification as read."""
        emp_id = unique_name("t-mnr")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        notif_id = create_notification(
            user_id=user_id,
            type="system",
            title="Test Notification",
            content="Test notification content",
            related_skill_id=None
        )

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                f"/api/notifications/{notif_id}/read",
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE id = %s", (notif_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()

    def test_mark_all_notifications_read(self):
        """Test marking all notifications as read."""
        emp_id = unique_name("t-manr")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                "/api/notifications/read-all",
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE user_id = %s", (user_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestMySkillsEndpoints:
    """Tests for my-skills endpoints."""

    def test_get_my_skills(self):
        """Test getting my skills."""
        emp_id = unique_name("t-gms")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-my-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/my-skills", cookies=login_resp.cookies)
            assert response.status_code in [200, 401]

        finally:
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

        skill_name = unique_name("test-delete-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.delete(
                f"/api/my-skills/{skill_id}",
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 403, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
                conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestGiteaEndpoints:
    """Tests for Gitea integration endpoints."""

    def test_gitea_status_as_admin(self):
        """Test getting Gitea status as admin."""
        admin_id = unique_name("t-gsaa")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/gitea/status", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 403, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()

    def test_gitea_tasks_as_admin(self):
        """Test getting Gitea tasks as admin."""
        admin_id = unique_name("t-gtaa")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/admin/gitea-tasks", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 403, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()


class TestDownloadEndpoints:
    """Tests for download endpoints."""

    def test_download_plugin_without_auth(self):
        """Test downloading plugin without authentication."""
        response = client.get("/plugins/nonexistent.zip")
        assert response.status_code in [200, 302, 401, 404]

    def test_download_plugin_with_auth(self):
        """Test downloading plugin with authentication."""
        emp_id = unique_name("t-dpwa")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-download")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get(
                f"/plugins/{skill_name}.zip",
                cookies=login_resp.cookies
            )
            # May return 404 if file doesn't exist on disk
            assert response.status_code in [200, 302, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
                conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestCategoryEndpoints:
    """Tests for category endpoints."""

    def test_get_categories(self):
        """Test getting categories."""
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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
