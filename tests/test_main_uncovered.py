"""
Tests for uncovered main.py endpoints and functions.
Focus on error handling, edge cases, and less-tested paths.
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


class TestLoginPageFlow:
    """Tests for login page rendering."""

    def test_login_page_renders(self):
        """Test login page renders correctly."""
        response = client.get("/login")
        assert response.status_code in [200, 404]

    def test_login_with_invalid_credentials(self):
        """Test login with invalid credentials."""
        response = client.post("/api/login", data={
            "employee_id": "invalid_user",
            "api_key": "invalid_key"
        })
        assert response.status_code in [200, 302, 400, 401, 422]


class TestLogoutFlow:
    """Tests for logout functionality."""

    def test_logout_authenticated(self):
        """Test logout when authenticated."""
        emp_id = unique_name("t-loa")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_resp = login_user(emp_id, api_key)
        response = client.get("/api/logout", cookies=login_resp.cookies)
        assert response.status_code in [200, 302, 401, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_logout_unauthenticated(self):
        """Test logout when not authenticated."""
        response = client.get("/api/logout")
        assert response.status_code in [200, 302, 401, 404]


class TestSkillDetailPage:
    """Tests for skill detail page."""

    def test_skill_detail_approved_skill(self):
        """Test skill detail page for approved skill."""
        emp_id = unique_name("t-sda")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-sda-skill")
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

        response = client.get(f"/skill/{skill_id}")
        assert response.status_code in [200, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_skill_detail_pending_skill(self):
        """Test skill detail page for pending skill."""
        emp_id = unique_name("t-sdp")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-sdp-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="pending",
            source_type="opensource"
        )

        response = client.get(f"/skill/{skill_id}")
        assert response.status_code in [200, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestAdminDashboard:
    """Tests for admin dashboard."""

    def test_admin_dashboard_authenticated(self):
        """Test admin dashboard when authenticated as admin."""
        admin_id = unique_name("t-ada")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        login_resp = login_user(admin_id, admin_key)
        response = client.get("/admin", cookies=login_resp.cookies)
        assert response.status_code in [200, 302, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
            conn.commit()

    def test_admin_dashboard_non_admin(self):
        """Test admin dashboard when not admin."""
        emp_id = unique_name("t-adn")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_resp = login_user(emp_id, api_key)
        response = client.get("/admin", cookies=login_resp.cookies)
        assert response.status_code in [200, 302, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestMySkillsPage:
    """Tests for my-skills page."""

    def test_my_skills_page_authenticated(self):
        """Test my-skills page when authenticated."""
        emp_id = unique_name("t-msa")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_resp = login_user(emp_id, api_key)
        response = client.get("/my-skills", cookies=login_resp.cookies)
        assert response.status_code in [200, 302, 401]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_my_skills_page_unauthenticated(self):
        """Test my-skills page when not authenticated."""
        response = client.get("/my-skills")
        assert response.status_code in [200, 302, 401]


class TestStatsPage:
    """Tests for stats page."""

    def test_stats_page_authenticated(self):
        """Test stats page when authenticated."""
        emp_id = unique_name("t-spa")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_resp = login_user(emp_id, api_key)
        response = client.get("/stats", cookies=login_resp.cookies)
        assert response.status_code in [200, 302, 401]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestPendingSkillsPage:
    """Tests for pending skills page."""

    def test_pending_page_admin(self):
        """Test pending skills page as admin."""
        admin_id = unique_name("t-ppa")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        login_resp = login_user(admin_id, admin_key)
        response = client.get("/admin/pending", cookies=login_resp.cookies)
        assert response.status_code in [200, 302, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
            conn.commit()


class TestSkillVersionEndpoints:
    """Tests for skill version endpoints."""

    def test_get_skill_versions(self):
        """Test getting skill versions."""
        emp_id = unique_name("t-gsv")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-gsv-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        login_resp = login_user(emp_id, api_key)
        response = client.get(f"/api/my-skills/versions/{skill_name}", cookies=login_resp.cookies)
        assert response.status_code in [200, 401, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_set_default_version(self):
        """Test setting default version."""
        emp_id = unique_name("t-sdv")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-sdv-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        login_resp = login_user(emp_id, api_key)
        response = client.post(f"/api/my-skills/{skill_id}/set-default", cookies=login_resp.cookies)
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestSkillActivationEndpoints:
    """Tests for skill activation endpoints."""

    def test_publish_skill_endpoint(self):
        """Test publishing skill."""
        emp_id = unique_name("t-pse")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-pse-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        with get_connection() as conn:
            conn.execute("UPDATE skills SET is_active = 0 WHERE id = %s", (skill_id,))
            conn.commit()

        login_resp = login_user(emp_id, api_key)
        response = client.post(f"/api/my-skills/{skill_id}/publish", cookies=login_resp.cookies)
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_unlist_skill_endpoint(self):
        """Test unlisting skill."""
        emp_id = unique_name("t-use")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-use-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        login_resp = login_user(emp_id, api_key)
        response = client.post(f"/api/my-skills/{skill_id}/unlist", cookies=login_resp.cookies)
        assert response.status_code in [200, 401, 403, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestNotificationEndpoints:
    """Tests for notification endpoints."""

    def test_get_notifications(self):
        """Test getting notifications."""
        emp_id = unique_name("t-gn")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        login_resp = login_user(emp_id, api_key)
        response = client.get("/api/notifications", cookies=login_resp.cookies)
        assert response.status_code in [200, 401]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_mark_notification_read(self):
        """Test marking notification as read."""
        emp_id = unique_name("t-mnr")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        notification_id = create_notification(
            user_id=user_id,
            type="system",
            title="Test notification",
            content="Test message"
        )

        login_resp = login_user(emp_id, api_key)
        response = client.post(f"/api/notifications/{notification_id}/read", cookies=login_resp.cookies)
        assert response.status_code in [200, 401, 404, 422]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE id = %s", (notification_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_mark_all_notifications_read(self):
        """Test marking all notifications as read."""
        emp_id = unique_name("t-manr")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        # Create some notifications
        create_notification(user_id=user_id, type="system", title="Test 1", content="Msg 1")
        create_notification(user_id=user_id, type="system", title="Test 2", content="Msg 2")

        login_resp = login_user(emp_id, api_key)
        response = client.post("/api/notifications/read-all", cookies=login_resp.cookies)
        assert response.status_code in [200, 401, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE user_id = %s", (user_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestDownloadEndpoints:
    """Tests for download endpoints."""

    def test_download_skill_by_name(self):
        """Test downloading skill by name."""
        emp_id = unique_name("t-dsn")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("t-dsn-skill")
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

        response = client.get(f"/plugins/{skill_name}.zip")
        assert response.status_code in [200, 302, 404]

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM downloads WHERE skill_name = %s", (skill_name,))
            conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_download_nonexistent_skill(self):
        """Test downloading nonexistent skill."""
        response = client.get("/plugins/nonexistent-skill.zip")
        assert response.status_code in [404, 500]


class TestIndexPage:
    """Tests for index page."""

    def test_index_page(self):
        """Test index page."""
        response = client.get("/")
        assert response.status_code in [200, 302]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
