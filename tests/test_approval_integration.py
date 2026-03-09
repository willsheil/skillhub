"""
Integration tests for approval workflow with Gitea push task creation.

Tests cover:
- Push task creation on skill approval
- Non-blocking error handling when Gitea integration fails
- Push task ID returned in approval response
"""

import pytest
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from main import app, get_current_user, require_auth, require_admin
from database import get_connection, init_db, create_user, get_user_by_credentials
import tempfile
import zipfile
import io

# 存储测试创建的用户ID，用于认证覆盖
_test_user_id = None

# Add SessionMiddleware for tests (only if not already added)
if not any(middleware.cls == SessionMiddleware for middleware in app.user_middleware):
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key")

# Override authentication for tests - with proper Request type hints
def override_get_current_user(request: Request):
    global _test_user_id
    uid = _test_user_id if _test_user_id else 1
    return {"id": uid, "employee_id": "test-apv-admin", "role": "admin"}

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


# Use TestClient with session context
def make_client_with_session():
    """Create a TestClient with admin session."""
    return TestClient(app)

client = make_client_with_session()


def create_test_skill_zip(skill_name: str = "test-skill", version: str = "1.0.0") -> bytes:
    """Create a minimal valid skill ZIP file for testing.

    Args:
        skill_name: Name of the skill
        version: Version of the skill

    Returns:
        ZIP file content as bytes
    """
    # Create SKILL.md content with required YAML frontmatter
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

    # Create ZIP file in memory
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
        # Delete notifications first (has foreign key to skills)
        conn.execute("DELETE FROM notifications WHERE related_skill_id IN (SELECT id FROM skills WHERE skill_name LIKE 'test-apv-%')")
        # Delete gitea_push_tasks
        conn.execute("DELETE FROM gitea_push_tasks WHERE skill_name LIKE 'test-apv-%'")
        # Delete skills
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-apv-%'")
        # Delete users
        conn.execute("DELETE FROM users WHERE employee_id LIKE 'test-apv-%'")
        conn.commit()
    yield
    # Cleanup after test
    with get_connection() as conn:
        # Delete in correct order
        conn.execute("DELETE FROM notifications WHERE related_skill_id IN (SELECT id FROM skills WHERE skill_name LIKE 'test-apv-%')")
        conn.execute("DELETE FROM gitea_push_tasks WHERE skill_name LIKE 'test-apv-%'")
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-apv-%'")
        conn.execute("DELETE FROM users WHERE employee_id LIKE 'test-apv-%'")
        conn.commit()


def test_approval_creates_push_task():
    """Test that approving a skill creates a Gitea push task."""
    global _test_user_id

    # Create test user (admin role for review)
    with get_connection() as conn:
        # Clean up first to avoid duplicates
        conn.execute("DELETE FROM users WHERE employee_id = 'test-apv-admin'")
        cursor = conn.execute("""
            INSERT INTO users (employee_id, api_key, role, status, skills_count)
            VALUES ('test-apv-admin', 'key_test_apv_admin', 'admin', 1, 0)
        """)
        uploader_id = cursor.lastrowid
        conn.commit()
        _test_user_id = uploader_id  # 设置认证覆盖使用的用户ID

    # Upload a skill first (this creates the actual file)
    skill_zip = create_test_skill_zip("test-apv-skill", "1.0.0")
    upload_response = client.post(
        "/api/upload",
        files={"file": ("test-apv-skill.zip", skill_zip, "application/zip")}
    )
    assert upload_response.status_code == 200
    upload_data = upload_response.json()
    skill_id = upload_data["skill_id"]

    # Approve skill
    response = client.post(f"/api/review/{skill_id}", json={
        "action": "approve",
        "comment": "LGTM"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "push_task_id" in data
    assert data["push_task_id"] is not None
    assert data["push_task_id"] > 0

    # Verify push task was created in database
    with get_connection() as conn:
        task = conn.execute("""
            SELECT * FROM gitea_push_tasks WHERE id = %s
        """, (data["push_task_id"],)).fetchone()

        assert task is not None
        assert task["skill_id"] == skill_id
        assert task["skill_name"] == "test-apv-skill"
        assert task["version"] == "1.0.0"
        assert task["status"] == "pending"


def test_approval_non_blocking_on_gitea_error():
    """Test that approval succeeds even if Gitea push task creation fails."""
    global _test_user_id
    # This test verifies that the approval workflow is resilient to Gitea integration failures
    # by using a mock that simulates an error in create_push_task

    # Create test user
    with get_connection() as conn:
        conn.execute("DELETE FROM users WHERE employee_id = 'test-apv-admin2'")
        cursor = conn.execute("""
            INSERT INTO users (employee_id, api_key, role, status, skills_count)
            VALUES ('test-apv-admin2', 'key_test_apv_admin2', 'admin', 1, 0)
        """)
        uploader_id = cursor.lastrowid
        conn.commit()
        _test_user_id = uploader_id  # 设置认证覆盖使用的用户ID

    # Upload a skill first
    skill_zip = create_test_skill_zip("test-apv-non-blocking", "1.0.0")
    upload_response = client.post(
        "/api/upload",
        files={"file": ("test-apv-non-blocking.zip", skill_zip, "application/zip")}
    )
    assert upload_response.status_code == 200
    upload_data = upload_response.json()
    skill_id = upload_data["skill_id"]

    # Mock create_push_task to raise an exception
    import main
    original_create = None

    def mock_create_push_task(skill_id):
        raise Exception("Simulated Gitea integration failure")

    try:
        # Temporarily replace the import
        import gitea_integration
        original_create = gitea_integration.create_push_task
        gitea_integration.create_push_task = mock_create_push_task

        # Approve skill - should still succeed despite Gitea error
        response = client.post(f"/api/review/{skill_id}", json={
            "action": "approve",
            "comment": "LGTM"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["skill_id"] == skill_id
        # push_task_id should be None when creation fails
        assert data.get("push_task_id") is None

    finally:
        # Restore original function
        if original_create:
            import gitea_integration
            gitea_integration.create_push_task = original_create


def test_rejection_does_not_create_push_task():
    """Test that rejecting a skill does NOT create a Gitea push task."""
    global _test_user_id
    # Create test user
    with get_connection() as conn:
        conn.execute("DELETE FROM users WHERE employee_id = 'test-apv-admin3'")
        cursor = conn.execute("""
            INSERT INTO users (employee_id, api_key, role, status, skills_count)
            VALUES ('test-apv-admin3', 'key_test_apv_admin3', 'admin', 1, 0)
        """)
        uploader_id = cursor.lastrowid
        conn.commit()
        _test_user_id = uploader_id  # 设置认证覆盖使用的用户ID

    # Upload a skill first
    skill_zip = create_test_skill_zip("test-apv-rejection", "1.0.0")
    upload_response = client.post(
        "/api/upload",
        files={"file": ("test-apv-rejection.zip", skill_zip, "application/zip")}
    )
    assert upload_response.status_code == 200
    upload_data = upload_response.json()
    skill_id = upload_data["skill_id"]

    # Reject skill
    response = client.post(f"/api/review/{skill_id}", json={
        "action": "reject",
        "comment": "Not ready"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # No push_task_id in response for rejection
    assert "push_task_id" not in data or data.get("push_task_id") is None

    # Verify no push task was created
    with get_connection() as conn:
        task = conn.execute("""
            SELECT * FROM gitea_push_tasks WHERE skill_id = %s
        """, (skill_id,)).fetchone()

        assert task is None
