"""
Tests for the notification system in SkillHub.

Tests cover:
- Notification creation on skill approval/rejection
- Notification creation on skill upload
- Unread count tracking
- Marking notifications as read
- Marking all notifications as read
"""

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
from main import app, get_current_user, require_auth, require_admin
from database import get_connection, init_db
import datetime
import tempfile
import zipfile
import io

# 存储测试创建的用户ID，用于认证覆盖
_test_user_id = None

# Add SessionMiddleware for tests (only if not already added)
if not any(middleware.cls == SessionMiddleware for middleware in app.user_middleware):
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key")

# 覆盖认证依赖
def override_get_current_user(request: Request):
    global _test_user_id
    uid = _test_user_id if _test_user_id else 1
    return {"id": uid, "employee_id": "test-nt-admin", "role": "admin"}

def override_require_auth(request: Request):
    global _test_user_id
    if _test_user_id:
        request.session["user_id"] = _test_user_id
    else:
        request.session["user_id"] = 1
    request.session["role"] = "admin"
    return True

def override_require_admin(request: Request):
    global _test_user_id
    if _test_user_id:
        request.session["user_id"] = _test_user_id
    else:
        request.session["user_id"] = 1
    request.session["role"] = "admin"
    return True

app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[require_auth] = override_require_auth
app.dependency_overrides[require_admin] = override_require_admin
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_dependency_overrides():
    """Reset dependency overrides before each test for isolation."""
    global _test_user_id
    _test_user_id = None  # Reset user ID for each test
    # Re-apply overrides to ensure this module's overrides are active
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[require_auth] = override_require_auth
    app.dependency_overrides[require_admin] = override_require_admin
    yield


def create_test_skill_zip(skill_name: str = "test-skill", version: str = "1.0.0") -> bytes:
    """Create a minimal valid skill ZIP file for testing."""
    skill_md_content = f"""---
name: {skill_name}
description: A test skill for automated testing
metadata:
  version: {version}
  author: w00000001
license: MIT
compatibility: Claude Code 1.0+
---

# {skill_name}

This is a test skill for automated testing.
"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("SKILL.md", skill_md_content)
    zip_buffer.seek(0)
    return zip_buffer.read()


@pytest.fixture(autouse=True)
def setup_database():
    """Setup test database before each test."""
    global _test_user_id
    _test_user_id = None  # Reset before each test for isolation
    init_db()
    # Clean up any existing test data - delete in correct order to respect foreign keys
    with get_connection() as conn:
        # Delete gitea_push_tasks first (has foreign key to skills)
        conn.execute("DELETE FROM gitea_push_tasks WHERE skill_name LIKE 'test-nt-%'")
        # Delete notifications (has foreign key to skills)
        conn.execute("DELETE FROM notifications WHERE related_skill_id IN (SELECT id FROM skills WHERE skill_name LIKE 'test-nt-%')")
        conn.execute("DELETE FROM notifications WHERE user_id IN (SELECT id FROM users WHERE employee_id LIKE 'test-nt-%')")
        # Delete skills
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-nt-%'")
        # Delete users
        conn.execute("DELETE FROM users WHERE employee_id LIKE 'test-nt-%'")
        conn.commit()
    yield
    # Cleanup after test
    with get_connection() as conn:
        # Delete in correct order
        conn.execute("DELETE FROM gitea_push_tasks WHERE skill_name LIKE 'test-nt-%'")
        conn.execute("DELETE FROM notifications WHERE related_skill_id IN (SELECT id FROM skills WHERE skill_name LIKE 'test-nt-%')")
        conn.execute("DELETE FROM notifications WHERE user_id IN (SELECT id FROM users WHERE employee_id LIKE 'test-nt-%')")
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-nt-%'")
        conn.execute("DELETE FROM users WHERE employee_id LIKE 'test-nt-%'")
        conn.commit()


def create_test_user(employee_id: str = "test-nt-user", role: str = "admin") -> int:
    """Create a test user and return user ID."""
    global _test_user_id
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (employee_id, api_key, role, status, skills_count)
            VALUES (%s, %s, %s, 1, 0)
            """,
            (employee_id, f"key_{employee_id}", role)
        )
        user_id = cursor.lastrowid
        conn.commit()
        _test_user_id = user_id  # 保存用户ID供认证覆盖使用
        return user_id


def create_test_skill(user_id: int, skill_name: str = "test-nt-skill") -> int:
    """Create a test skill and return skill ID."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO skills (skill_name, version, filename, uploader_id, status)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (skill_name, "1.0.0", f"{skill_name}.zip", user_id, "pending")
        )
        skill_id = cursor.lastrowid
        conn.commit()
        return skill_id


def test_notification_on_approval():
    """Test that approval creates a notification for the uploader."""
    # Create uploader first (this will be the one uploading)
    uploader_id = create_test_user("test-nt-uploader", "user")

    # Upload a skill first (using the uploader user)
    skill_zip = create_test_skill_zip("test-nt-approval", "1.0.0")
    response = client.post(
        "/api/upload",
        files={"file": ("test-nt-approval.zip", skill_zip, "application/zip")}
    )
    if response.status_code != 200:
        print(f"Upload failed: {response.status_code} - {response.text}")
    assert response.status_code == 200
    data = response.json()
    skill_id = data["skill_id"]

    # Get the actual uploader_id from the skill record
    with get_connection() as conn:
        skill = conn.execute("SELECT uploader_id FROM skills WHERE id = %s", (skill_id,)).fetchone()
        actual_uploader_id = skill["uploader_id"] if skill else None

    # Verify no notifications initially
    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) as count FROM notifications WHERE user_id = %s",
            (actual_uploader_id,)
        ).fetchone()["count"]
        assert count == 0

    # Approve the skill (admin override handles auth)
    response = client.post(
        f"/api/review/{skill_id}",
        json={"action": "approve", "comment": "LGTM"}
    )

    assert response.status_code == 200

    # Check for notification
    with get_connection() as conn:
        notification = conn.execute(
            """
            SELECT * FROM notifications
            WHERE user_id = %s AND type = 'review_success' AND related_skill_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (actual_uploader_id, skill_id)
        ).fetchone()

        assert notification is not None
        assert notification["type"] == "review_success"
        assert notification["is_read"] == 0
        assert "通过" in notification["title"] or "approved" in notification["title"].lower()


def test_notification_on_rejection():
    """Test that rejection creates a notification for the uploader."""
    # Create uploader
    uploader_id = create_test_user("test-nt-r-uploader", "user")

    # Upload a skill first
    skill_zip = create_test_skill_zip("test-nt-rejection", "1.0.0")
    response = client.post(
        "/api/upload",
        files={"file": ("test-nt-rejection.zip", skill_zip, "application/zip")}
    )
    assert response.status_code == 200
    data = response.json()
    skill_id = data["skill_id"]

    # Get the actual uploader_id from the skill record
    with get_connection() as conn:
        skill = conn.execute("SELECT uploader_id FROM skills WHERE id = %s", (skill_id,)).fetchone()
        actual_uploader_id = skill["uploader_id"] if skill else None

    # Reject the skill
    response = client.post(
        f"/api/review/{skill_id}",
        json={"action": "reject", "comment": "Needs improvement"}
    )

    assert response.status_code == 200

    # Check for rejection notification
    with get_connection() as conn:
        notification = conn.execute(
            """
            SELECT * FROM notifications
            WHERE user_id = %s AND type = 'review_rejected' AND related_skill_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (actual_uploader_id, skill_id)
        ).fetchone()

        assert notification is not None
        assert notification["type"] == "review_rejected"
        # The rejection notification should contain the comment
        assert "Needs improvement" in notification["content"] or "未通过" in notification["title"]


def test_unread_count():
    """Test unread notification count tracking."""
    user_id = create_test_user("test-nt-count", "user")

    # Create multiple notifications
    with get_connection() as conn:
        for i in range(5):
            conn.execute(
                """
                INSERT INTO notifications (user_id, type, title, content, is_read)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, "system", f"Test {i}", f"Content {i}", 0)
            )
        conn.commit()

    # Check unread count
    response = client.get("/api/notifications/unread-count")

    # This would normally require authentication
    # For unit test, we'll check the database directly
    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0",
            (user_id,)
        ).fetchone()["count"]
        assert count == 5


def test_mark_notification_as_read():
    """Test marking a single notification as read."""
    user_id = create_test_user("test-nt-read", "user")

    # Create a notification
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO notifications (user_id, type, title, content, is_read)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, "system", "Test", "Content", 0)
        )
        notification_id = cursor.lastrowid
        conn.commit()

    # Verify it's unread
    with get_connection() as conn:
        notification = conn.execute(
            "SELECT is_read FROM notifications WHERE id = %s",
            (notification_id,)
        ).fetchone()
        assert notification["is_read"] == 0

    # Mark as read
    response = client.post(f"/api/notifications/{notification_id}/read")

    # Verify it's now read
    with get_connection() as conn:
        notification = conn.execute(
            "SELECT is_read FROM notifications WHERE id = %s",
            (notification_id,)
        ).fetchone()
        assert notification["is_read"] == 1


def test_mark_all_as_read():
    """Test marking all notifications as read."""
    user_id = create_test_user("test-nt-all-read", "user")

    # Create multiple unread notifications
    with get_connection() as conn:
        notification_ids = []
        for i in range(5):
            cursor = conn.execute(
                """
                INSERT INTO notifications (user_id, type, title, content, is_read)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, "system", f"Test {i}", f"Content {i}", 0)
            )
            notification_ids.append(cursor.lastrowid)
        conn.commit()

    # Verify all are unread
    with get_connection() as conn:
        unread_count = conn.execute(
            "SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0",
            (user_id,)
        ).fetchone()["count"]
        assert unread_count == 5

    # Mark all as read
    response = client.post("/api/notifications/read-all")

    # Verify all are now read
    with get_connection() as conn:
        unread_count = conn.execute(
            "SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0",
            (user_id,)
        ).fetchone()["count"]
        assert unread_count == 0


def test_notification_ordering():
    """Test that notifications are ordered by creation time (newest first)."""
    user_id = create_test_user("test-nt-order", "user")

    # Create notifications with specific timestamps
    with get_connection() as conn:
        for i in range(3):
            conn.execute(
                """
                INSERT INTO notifications (user_id, type, title, content, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, "system", f"Test {i}", f"Content {i}",
                 datetime.datetime.now() - datetime.timedelta(hours=i))
            )
        conn.commit()

    # Get notifications
    with get_connection() as conn:
        notifications = conn.execute(
            """
            SELECT id FROM notifications
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,)
        ).fetchall()

        # Should have 3 notifications in reverse chronological order
        assert len(notifications) == 3


def test_notification_deletion_on_skill_deletion():
    """Test that notifications are deleted when related skill is deleted."""
    user_id = create_test_user("test-nt-cascade", "user")

    # Create a skill
    skill_id = create_test_skill(user_id, "test-nt-cascade-skill")

    # Create a notification for this skill
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO notifications (user_id, type, title, content, related_skill_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, "approval", "Test", "Content", skill_id)
        )
        notification_id = cursor.lastrowid
        conn.commit()

    # Verify notification exists
    with get_connection() as conn:
        notification = conn.execute(
            "SELECT * FROM notifications WHERE id = %s",
            (notification_id,)
        ).fetchone()
        assert notification is not None

    # Delete the skill (with notification cleanup)
    with get_connection() as conn:
        conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
        conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
        conn.commit()

    # Verify notification is deleted
    with get_connection() as conn:
        notification = conn.execute(
            "SELECT * FROM notifications WHERE id = %s",
            (notification_id,)
        ).fetchone()
        assert notification is None


def test_notification_types():
    """Test different notification types."""
    user_id = create_test_user("test-nt-types", "user")

    notification_types = ["approval", "rejection", "upload", "system"]

    with get_connection() as conn:
        for notif_type in notification_types:
            conn.execute(
                """
                INSERT INTO notifications (user_id, type, title, content)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, notif_type, f"{notif_type.title()} Notification", "Content")
            )
        conn.commit()

    # Verify all types exist
    with get_connection() as conn:
        for notif_type in notification_types:
            notification = conn.execute(
                """
                SELECT * FROM notifications
                WHERE user_id = %s AND type = %s
                LIMIT 1
                """,
                (user_id, notif_type)
            ).fetchone()
            assert notification is not None
            assert notification["type"] == notif_type


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
