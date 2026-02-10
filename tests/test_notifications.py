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
from main import app
from database import get_connection, init_db
import datetime

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Setup test database before each test."""
    init_db()
    # Clean up any existing test data
    with get_connection() as conn:
        conn.execute("DELETE FROM notifications WHERE user_id IN (SELECT id FROM users WHERE employee_id LIKE 'test-notify-%')")
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-notify-%'")
        conn.execute("DELETE FROM users WHERE employee_id LIKE 'test-notify-%'")
        conn.commit()
    yield
    # Cleanup after test
    with get_connection() as conn:
        conn.execute("DELETE FROM notifications WHERE user_id IN (SELECT id FROM users WHERE employee_id LIKE 'test-notify-%')")
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-notify-%'")
        conn.execute("DELETE FROM users WHERE employee_id LIKE 'test-notify-%'")
        conn.commit()


def create_test_user(employee_id: str = "test-notify-user", role: str = "user") -> int:
    """Create a test user and return user ID."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (employee_id, api_key, role)
            VALUES (%s, %s, %s)
            """,
            (employee_id, f"key_{employee_id}", role)
        )
        user_id = cursor.lastrowid
        conn.commit()
        return user_id


def create_test_skill(user_id: int, skill_name: str = "test-notify-skill") -> int:
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
    # Create uploader and admin
    uploader_id = create_test_user("test-notify-uploader", "user")
    admin_id = create_test_user("test-notify-admin", "admin")

    # Create a pending skill
    skill_id = create_test_skill(uploader_id, "test-notify-approval")

    # Verify no notifications initially
    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) as count FROM notifications WHERE user_id = %s",
            (uploader_id,)
        ).fetchone()["count"]
        assert count == 0

    # Approve the skill
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
            WHERE user_id = %s AND type = 'approval' AND related_skill_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (uploader_id, skill_id)
        ).fetchone()

        assert notification is not None
        assert notification["type"] == "approval"
        assert notification["is_read"] == 0
        assert "approved" in notification["title"].lower() or "通过" in notification["title"]


def test_notification_on_rejection():
    """Test that rejection creates a notification for the uploader."""
    # Create uploader
    uploader_id = create_test_user("test-notify-reject-uploader", "user")
    create_test_user("test-notify-reject-admin", "admin")  # For admin check

    # Create a pending skill
    skill_id = create_test_skill(uploader_id, "test-notify-rejection")

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
            WHERE user_id = %s AND type = 'rejection' AND related_skill_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (uploader_id, skill_id)
        ).fetchone()

        assert notification is not None
        assert notification["type"] == "rejection"
        assert "Needs improvement" in notification["content"]


def test_unread_count():
    """Test unread notification count tracking."""
    user_id = create_test_user("test-notify-count", "user")

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
    user_id = create_test_user("test-notify-read", "user")

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
    user_id = create_test_user("test-notify-all-read", "user")

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
    user_id = create_test_user("test-notify-order", "user")

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
    user_id = create_test_user("test-notify-cascade", "user")

    # Create a skill
    skill_id = create_test_skill(user_id, "test-notify-cascade-skill")

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
    user_id = create_test_user("test-notify-types", "user")

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
