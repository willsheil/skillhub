"""
Tests for batch operations in SkillHub.

Tests cover:
- Batch unlist operations
- Batch delete operations
- Foreign key constraint handling
- Error handling for batch operations
"""

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from main import app, get_current_user, require_auth, require_admin
from database import get_connection, init_db
import tempfile
import zipfile
import io

# 存储测试创建的用户ID，用于认证覆盖
_test_user_id = None

def get_test_user_id():
    """Get the current test user ID for auth override."""
    return _test_user_id

# 覆盖认证依赖
def override_get_current_user(request: Request):
    global _test_user_id
    uid = _test_user_id if _test_user_id else 1
    return {"id": uid, "employee_id": "test-batch-user", "role": "admin"}

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
description: A test skill for batch operations
metadata:
  version: {version}
  author: w00000001
license: MIT
compatibility: Claude Code 1.0+
---

# {skill_name}

Test skill for batch operations.
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
    # Clean up any existing test data
    with get_connection() as conn:
        conn.execute("DELETE FROM notifications WHERE related_skill_id IN (SELECT id FROM skills WHERE skill_name LIKE 'test-batch-%')")
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-batch-%'")
        conn.execute("DELETE FROM users WHERE employee_id LIKE 'test-batch-%'")
        conn.commit()
    yield
    # Cleanup after test
    with get_connection() as conn:
        conn.execute("DELETE FROM notifications WHERE related_skill_id IN (SELECT id FROM skills WHERE skill_name LIKE 'test-batch-%')")
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-batch-%'")
        conn.execute("DELETE FROM users WHERE employee_id LIKE 'test-batch-%'")
        conn.commit()


def create_test_user(employee_id: str = "test-batch-user", role: str = "admin") -> int:
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


def create_test_skill(skill_name: str, user_id: int, status: str = "approved") -> int:
    """Create a test skill and return skill ID."""
    filename = f"{skill_name}-1.0.0.zip"
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO skills (skill_name, version, filename, uploader_id, status, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (skill_name, "1.0.0", filename, user_id, status, 1)
        )
        skill_id = cursor.lastrowid
        conn.commit()
        return skill_id


def create_test_notification(user_id: int, skill_id: int) -> int:
    """Create a test notification for a skill."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO notifications (user_id, type, title, content, related_skill_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, "approval", "Test", "Test notification", skill_id)
        )
        notification_id = cursor.lastrowid
        conn.commit()
        return notification_id


def test_batch_unlist_skills():
    """Test batch unlisting multiple skills."""
    # Create test user and skills
    user_id = create_test_user()
    skill_ids = [
        create_test_skill("test-batch-skill-1", user_id),
        create_test_skill("test-batch-skill-2", user_id),
        create_test_skill("test-batch-skill-3", user_id),
    ]

    # Verify skills are active
    with get_connection() as conn:
        for skill_id in skill_ids:
            skill = conn.execute("SELECT is_active FROM skills WHERE id = %s", (skill_id,)).fetchone()
            assert skill["is_active"] == 1

    # Perform batch unlist
    response = client.post(
        "/api/my-skills/batch/unlist",
        json={"skill_ids": skill_ids}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["success_count"] == 3

    # Verify skills are now inactive
    with get_connection() as conn:
        for skill_id in skill_ids:
            skill = conn.execute("SELECT is_active FROM skills WHERE id = %s", (skill_id,)).fetchone()
            assert skill["is_active"] == 0


def test_batch_delete_skills():
    """Test batch deleting multiple skills with notifications."""
    # Create test user
    user_id = create_test_user()

    # Create skills with notifications
    skill_ids = []
    for i in range(3):
        skill_id = create_test_skill(f"test-batch-delete-{i}", user_id)
        create_test_notification(user_id, skill_id)
        skill_ids.append(skill_id)

    # Verify skills and notifications exist
    with get_connection() as conn:
        for skill_id in skill_ids:
            skill = conn.execute("SELECT * FROM skills WHERE id = %s", (skill_id,)).fetchone()
            assert skill is not None
            notification = conn.execute(
                "SELECT * FROM notifications WHERE related_skill_id = %s",
                (skill_id,)
            ).fetchone()
            assert notification is not None

    # Perform batch delete
    response = client.post(
        "/api/my-skills/batch/delete",
        json={"skill_ids": skill_ids}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["success_count"] == 3

    # Verify skills and notifications are deleted
    with get_connection() as conn:
        for skill_id in skill_ids:
            skill = conn.execute("SELECT * FROM skills WHERE id = %s", (skill_id,)).fetchone()
            assert skill is None
            notification = conn.execute(
                "SELECT * FROM notifications WHERE related_skill_id = %s",
                (skill_id,)
            ).fetchone()
            assert notification is None


def test_batch_unlist_empty_list():
    """Test batch unlist with empty skill list."""
    response = client.post(
        "/api/my-skills/batch/unlist",
        json={"skill_ids": []}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["success_count"] == 0


def test_batch_delete_empty_list():
    """Test batch delete with empty skill list."""
    response = client.post(
        "/api/my-skills/batch/delete",
        json={"skill_ids": []}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["success_count"] == 0


def test_batch_unlist_nonexistent_skills():
    """Test batch unlist with some non-existent skill IDs."""
    user_id = create_test_user()
    skill_id = create_test_skill("test-batch-mixed", user_id)

    # Mix of valid and invalid IDs
    skill_ids = [skill_id, 99999, 99998]

    response = client.post(
        "/api/my-skills/batch/unlist",
        json={"skill_ids": skill_ids}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # Only the valid skill should be unlisted
    assert data["success_count"] == 1


def test_batch_delete_foreign_key_handling():
    """Test that batch delete properly handles foreign key constraints."""
    user_id = create_test_user()
    skill_id = create_test_skill("test-batch-fk", user_id)

    # Create notification (foreign key reference)
    notification_id = create_test_notification(user_id, skill_id)

    # Verify notification exists
    with get_connection() as conn:
        notification = conn.execute(
            "SELECT * FROM notifications WHERE id = %s",
            (notification_id,)
        ).fetchone()
        assert notification is not None

    # Delete skill - should also delete notification
    response = client.post(
        "/api/my-skills/batch/delete",
        json={"skill_ids": [skill_id]}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Verify both skill and notification are deleted
    with get_connection() as conn:
        skill = conn.execute("SELECT * FROM skills WHERE id = %s", (skill_id,)).fetchone()
        assert skill is None
        notification = conn.execute(
            "SELECT * FROM notifications WHERE id = %s",
            (notification_id,)
        ).fetchone()
        assert notification is None


def test_batch_unlist_already_unlisted():
    """Test batch unlist with skills already unlisted."""
    user_id = create_test_user()

    # Create one active and one inactive skill
    skill_id_1 = create_test_skill("test-batch-active", user_id)
    skill_id_2 = create_test_skill("test-batch-inactive", user_id)

    # Unlist the second skill
    with get_connection() as conn:
        conn.execute("UPDATE skills SET is_active = 0 WHERE id = %s", (skill_id_2,))
        conn.commit()

    # Batch unlist both
    response = client.post(
        "/api/my-skills/batch/unlist",
        json={"skill_ids": [skill_id_1, skill_id_2]}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # Both should be counted as processed
    assert data["success_count"] == 2

    # Verify both are inactive
    with get_connection() as conn:
        for skill_id in [skill_id_1, skill_id_2]:
            skill = conn.execute("SELECT is_active FROM skills WHERE id = %s", (skill_id,)).fetchone()
            assert skill["is_active"] == 0


def test_batch_operation_limit():
    """Test batch operation with a large number of skills."""
    user_id = create_test_user()

    # Create 50 skills (common batch limit)
    skill_ids = []
    for i in range(50):
        skill_id = create_test_skill(f"test-batch-limit-{i}", user_id)
        skill_ids.append(skill_id)

    # Batch delete all
    response = client.post(
        "/api/my-skills/batch/delete",
        json={"skill_ids": skill_ids}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["success_count"] == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
