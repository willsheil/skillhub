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
from main import app, get_current_user, require_auth, require_admin
from database import get_connection, init_db, create_user, get_user_by_credentials
import tempfile
import zipfile
import io

# Add SessionMiddleware for tests
app.add_middleware(SessionMiddleware, secret_key="test-secret-key")

# Override authentication for tests - completely skip checks
async def override_require_admin_skip():
    return True

app.dependency_overrides[require_admin] = override_require_admin_skip

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
    init_db()
    # Clean up any existing test data
    with get_connection() as conn:
        conn.execute("DELETE FROM gitea_push_tasks WHERE skill_name LIKE 'test-%'")
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-%'")
        conn.execute("DELETE FROM users WHERE employee_id LIKE 'test-%'")
        conn.commit()
    yield
    # Cleanup after test
    with get_connection() as conn:
        conn.execute("DELETE FROM gitea_push_tasks WHERE skill_name LIKE 'test-%'")
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-%'")
        conn.execute("DELETE FROM users WHERE employee_id LIKE 'test-%'")
        conn.commit()


def test_approval_creates_push_task(monkeypatch):
    """Test that approving a skill creates a Gitea push task."""
    # Mock request.session to return test user data
    class MockSession(dict):
        def get(self, key, default=None):
            if key == "user_id":
                return 1
            elif key == "role":
                return "admin"
            return super().get(key, default)

    def mock_request():
        req = type('MockRequest', (), {})()
        req.session = MockSession()
        return req

    # Patch main.py to use mock session
    import main
    monkeypatch.setattr(main, "Request", lambda: mock_request())

    # Create test user
    with get_connection() as conn:
        # Clean up first to avoid duplicates
        conn.execute("DELETE FROM users WHERE employee_id = 'test_approver'")
        cursor = conn.execute("""
            INSERT INTO users (employee_id, api_key, role)
            VALUES ('test_approver', 'key_test_approver', 'admin')
        """)
        uploader_id = cursor.lastrowid
        conn.commit()

    # Create test skill in pending state
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO skills (skill_name, version, filename, uploader_id, status)
            VALUES ('test-approval-skill', '1.0.0', 'test.zip', %s, 'pending')
        """, (uploader_id,))
        skill_id = cursor.lastrowid
        conn.commit()

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
        assert task["skill_name"] == "test-approval-skill"
        assert task["version"] == "1.0.0"
        assert task["status"] == "pending"


def test_approval_non_blocking_on_gitea_error():
    """Test that approval succeeds even if Gitea push task creation fails."""
    # This test verifies that the approval workflow is resilient to Gitea integration failures
    # by using a mock that simulates an error in create_push_task

    # Create test user
    with get_connection() as conn:
        conn.execute("DELETE FROM users WHERE employee_id = 'test_approver2'")
        cursor = conn.execute("""
            INSERT INTO users (employee_id, api_key, role)
            VALUES ('test_approver2', 'key_test_approver2', 'admin')
        """)
        uploader_id = cursor.lastrowid
        conn.commit()

    # Create test skill in pending state
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO skills (skill_name, version, filename, uploader_id, status)
            VALUES ('test-non-blocking', '1.0.0', 'test.zip', %s, 'pending')
        """, (uploader_id,))
        skill_id = cursor.lastrowid
        conn.commit()

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
    # Create test user
    with get_connection() as conn:
        conn.execute("DELETE FROM users WHERE employee_id = 'test_rejecter'")
        cursor = conn.execute("""
            INSERT INTO users (employee_id, api_key, role)
            VALUES ('test_rejecter', 'key_test_rejecter', 'admin')
        """)
        uploader_id = cursor.lastrowid
        conn.commit()

    # Create test skill in pending state
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO skills (skill_name, version, filename, uploader_id, status)
            VALUES ('test-rejection-skill', '1.0.0', 'test.zip', %s, 'pending')
        """, (uploader_id,))
        skill_id = cursor.lastrowid
        conn.commit()

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
