"""
Tests for database.py operations.

Tests cover:
- User CRUD operations
- Skill CRUD operations
- Statistics functions
- Rating system
- Notification system
"""

import pytest
from database import (
    get_connection,
    create_user, get_user_by_id, get_user_by_credentials,
    get_users_list, get_user_skills_count, delete_user,
    get_skill_by_name, get_skill_by_id, get_pending_skills,
    get_skill_ratings, submit_rating, get_download_stats,
    create_notification, get_user_notifications,
    mark_notification_read, mark_all_notifications_read, get_unread_notifications_count,
    create_skill_record, get_skill_active_status, update_skill_status
)
import uuid


def unique_name(base: str) -> str:
    """Generate a unique name for testing."""
    return f"{base}-{uuid.uuid4().hex[:8]}"


class TestUserCRUD:
    """Tests for user CRUD operations."""

    def test_create_and_get_user_by_credentials(self):
        """Test creating a user and retrieving by credentials."""
        emp_id = unique_name("t-emp")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        assert user_id is not None
        assert user_id > 0

        user = get_user_by_credentials(emp_id, api_key)
        assert user is not None
        assert user["employee_id"] == emp_id
        assert user["role"] == "user"

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE employee_id = %s", (emp_id,))
            conn.commit()

    def test_get_user_by_id(self):
        """Test retrieving user by ID."""
        emp_id = unique_name("t-gui")
        user_id = create_user(emp_id, f"key-{emp_id}", "admin")

        user = get_user_by_id(user_id)
        assert user is not None
        assert user["id"] == user_id
        assert user["role"] == "admin"

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_get_nonexistent_user(self):
        """Test retrieving nonexistent user."""
        user = get_user_by_id(99999999)
        assert user is None

        user = get_user_by_credentials("nonexistent-emp-12345", "invalid-key")
        assert user is None

    def test_get_users_list(self):
        """Test retrieving users list (returns dict with pagination)."""
        result = get_users_list()
        assert isinstance(result, dict)
        assert "users" in result
        assert isinstance(result["users"], list)

    def test_get_user_skills_count(self):
        """Test getting user's skills count."""
        emp_id = unique_name("t-usc")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")

        count = get_user_skills_count(user_id)
        assert isinstance(count, int)

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_delete_user(self):
        """Test deleting a user."""
        emp_id = unique_name("t-del")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")

        # Delete user
        result = delete_user(user_id)
        assert result is True or result is not None

        # Verify deletion
        user = get_user_by_id(user_id)
        assert user is None


class TestSkillCRUD:
    """Tests for skill CRUD operations."""

    def test_create_and_get_skill_by_name(self):
        """Test creating and retrieving skill by name."""
        emp_id = unique_name("t-sk")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")
        skill_name = unique_name("t-skill")

        # Create skill
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        # Get skill
        skill = get_skill_by_name(skill_name)
        assert skill is not None
        assert skill["skill_name"] == skill_name

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE skill_name = %s", (skill_name,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_get_skill_by_id(self):
        """Test retrieving skill by ID."""
        emp_id = unique_name("t-ski")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")
        skill_name = unique_name("t-ski-skill")

        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        skill = get_skill_by_id(skill_id)
        assert skill is not None
        assert skill["id"] == skill_id

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_get_nonexistent_skill(self):
        """Test retrieving nonexistent skill."""
        skill = get_skill_by_id(99999999)
        assert skill is None

        skill = get_skill_by_name("nonexistent-skill-12345")
        assert skill is None

    def test_get_pending_skills(self):
        """Test retrieving pending skills."""
        skills = get_pending_skills()
        assert isinstance(skills, list)

        # All pending skills should have status=pending
        for skill in skills:
            assert skill.get("status") == "pending"

    def test_get_skill_active_status(self):
        """Test getting skill active status (takes skill_name, not skill_id)."""
        emp_id = unique_name("t-sas")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")
        skill_name = unique_name("t-sas-skill")

        create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        # Update is_active directly since create_skill_record doesn't have that param
        with get_connection() as conn:
            conn.execute("UPDATE skills SET is_active = 1 WHERE skill_name = %s", (skill_name,))
            conn.commit()

        status = get_skill_active_status(skill_name)
        assert status is True or status == 1

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE skill_name = %s", (skill_name,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_update_skill_status(self):
        """Test updating skill status."""
        emp_id = unique_name("t-uss")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")
        skill_name = unique_name("t-uss-skill")

        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="pending",
            source_type="opensource"
        )

        # Update status
        result = update_skill_status(skill_id, "approved")
        assert result is None or result is True  # Returns None on success

        # Verify update
        skill = get_skill_by_id(skill_id)
        assert skill["status"] == "approved"

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestRatingSystem:
    """Tests for skill rating system."""

    def test_get_skill_ratings_no_ratings(self):
        """Test getting ratings for skill with no ratings."""
        emp_id = unique_name("t-rt")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")
        skill_name = unique_name("t-rt-skill")

        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        ratings = get_skill_ratings(skill_id)
        assert isinstance(ratings, dict)
        assert "average" in ratings
        assert "total" in ratings

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_submit_rating(self):
        """Test submitting a skill rating."""
        emp_id = unique_name("t-rate")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")
        skill_name = unique_name("t-rate-skill")

        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        # Submit rating
        result = submit_rating(skill_id, user_id, 5)
        assert isinstance(result, dict)

        # Verify rating
        ratings = get_skill_ratings(skill_id)
        assert ratings["total"] >= 1

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM skill_ratings WHERE skill_id = %s", (skill_id,))
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestNotificationSystem:
    """Tests for notification system."""

    def test_create_notification(self):
        """Test creating a notification."""
        emp_id = unique_name("t-notif")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")

        result = create_notification(user_id, "system", "Test notification")
        assert result is not None

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE user_id = %s", (user_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_get_user_notifications(self):
        """Test getting user notifications (returns dict)."""
        emp_id = unique_name("t-gn")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")

        # Create a notification
        create_notification(user_id, "system", "Test notification")

        result = get_user_notifications(user_id)
        assert isinstance(result, dict)
        assert "notifications" in result

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE user_id = %s", (user_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_mark_notification_read(self):
        """Test marking notification as read (requires user_id)."""
        emp_id = unique_name("t-mnr")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")

        # Create notification
        notif_id = create_notification(user_id, "system", "Test")

        # Mark as read
        result = mark_notification_read(notif_id, user_id)
        assert result is True or result is not None

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE user_id = %s", (user_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_mark_all_notifications_read(self):
        """Test marking all notifications as read."""
        emp_id = unique_name("t-manr")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")

        # Create multiple notifications
        create_notification(user_id, "system", "Test 1")
        create_notification(user_id, "system", "Test 2")

        # Mark all as read
        result = mark_all_notifications_read(user_id)
        assert result is True or result is not None

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE user_id = %s", (user_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

    def test_get_unread_notifications_count(self):
        """Test getting unread notification count."""
        emp_id = unique_name("t-guc")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")

        # Create unread notification
        create_notification(user_id, "system", "Test")

        count = get_unread_notifications_count(user_id)
        assert isinstance(count, int)
        assert count >= 1

        # Cleanup
        with get_connection() as conn:
            conn.execute("DELETE FROM notifications WHERE user_id = %s", (user_id,))
            conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


class TestDownloadStats:
    """Tests for download statistics."""

    def test_get_download_stats(self):
        """Test getting download statistics (returns dict)."""
        stats = get_download_stats()
        assert isinstance(stats, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
