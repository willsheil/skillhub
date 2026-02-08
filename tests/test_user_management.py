"""
End-to-end tests for user management system.

Tests cover:
- Login success and failure
- Upload authentication requirements
- Admin role requirements
- Upload and approval workflow
"""

import os
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest
import requests

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db, create_user, get_user_by_credentials


# Test server configuration
BASE_URL = os.getenv("TEST_SERVER_URL", "http://localhost:28000")


def create_test_skill(skill_name: str = "test-skill", version: str = "1.0.0") -> bytes:
    """Create a minimal valid skill ZIP file for testing.

    Args:
        skill_name: Name of the skill
        version: Version of the skill

    Returns:
        ZIP file content as bytes
    """
    import io

    # Create SKILL.md content with required YAML frontmatter
    skill_md_content = f"""---
name: {skill_name}
description: A test skill for automated testing
metadata:
  version: {version}
  author: w00000001
license: MIT
compatibility: Claude Code 1.0+
allowed-tools: bash grep
---

# {skill_name}

This is a test skill created for automated testing purposes.
"""

    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{skill_name}/SKILL.md", skill_md_content)

    zip_buffer.seek(0)
    return zip_buffer.read()


@pytest.fixture(scope="module")
def test_server():
    """Fixture to ensure test server is running.

    Tests expect a server to be running at BASE_URL.
    Skip tests if server is not available.
    """
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=2)
        if response.status_code == 200:
            yield BASE_URL
        else:
            pytest.skip("Test server health check failed")
    except requests.exceptions.RequestException:
        pytest.skip("Test server not available. Start server with: python main.py")


@pytest.fixture(scope="function")
def test_user():
    """Fixture to create a test user before each test and clean up after.

    Returns:
        Dictionary with user credentials (employee_id, api_key)
    """
    # Initialize database
    init_db()

    # Create test user
    employee_id = "test001"
    api_key = "test_key_001"

    from database import get_connection
    with get_connection() as conn:
        # Delete if exists
        conn.execute("DELETE FROM users WHERE employee_id = ?", (employee_id,))
        # Create new user
        conn.execute(
            """
            INSERT INTO users (employee_id, api_key, role)
            VALUES (?, ?, 'user')
            """,
            (employee_id, api_key)
        )
        conn.commit()

    yield {
        "employee_id": employee_id,
        "api_key": api_key
    }

    # Cleanup
    with get_connection() as conn:
        conn.execute("DELETE FROM users WHERE employee_id = ?", (employee_id,))
        conn.commit()


@pytest.fixture(scope="function")
def test_admin():
    """Fixture to create a test admin user before each test and clean up after.

    Returns:
        Dictionary with admin credentials (employee_id, api_key)
    """
    # Initialize database
    init_db()

    # Create test admin
    employee_id = "admin001"
    api_key = "admin_key_001"

    from database import get_connection
    with get_connection() as conn:
        # Delete if exists
        conn.execute("DELETE FROM users WHERE employee_id = ?", (employee_id,))
        # Create new admin
        conn.execute(
            """
            INSERT INTO users (employee_id, api_key, role)
            VALUES (?, ?, 'admin')
            """,
            (employee_id, api_key)
        )
        conn.commit()

    yield {
        "employee_id": employee_id,
        "api_key": api_key
    }

    # Cleanup
    with get_connection() as conn:
        conn.execute("DELETE FROM users WHERE employee_id = ?", (employee_id,))
        conn.commit()


def test_login_success(test_server, test_user):
    """Test successful login with valid credentials."""
    session = requests.Session()

    response = session.post(
        f"{test_server}/api/login",
        data={
            "employee_id": test_user["employee_id"],
            "api_key": test_user["api_key"]
        },
        allow_redirects=False
    )

    # Should redirect after successful login
    assert response.status_code in [302, 303]


def test_login_failure(test_server):
    """Test login failure with invalid credentials."""
    session = requests.Session()

    response = session.post(
        f"{test_server}/api/login",
        data={
            "employee_id": "invalid_user",
            "api_key": "invalid_key"
        },
        allow_redirects=False
    )

    # Should redirect back to login with error
    assert response.status_code in [302, 303]
    assert "error=invalid" in response.headers.get("location", "")


def test_upload_requires_auth(test_server):
    """Test that upload endpoint requires authentication."""
    # Create test skill
    skill_data = create_test_skill("auth-test-skill", "1.0.0")

    # Try to upload without authentication
    files = {"file": ("auth-test-skill-1.0.0.zip", skill_data, "application/zip")}

    response = requests.post(
        f"{test_server}/api/upload",
        files=files
    )

    # Should be redirected to login or return 401
    assert response.status_code in [302, 401]


def test_admin_requires_admin_role(test_server, test_user):
    """Test that admin endpoints require admin role."""
    session = requests.Session()

    # Login as regular user
    session.post(
        f"{test_server}/api/login",
        data={
            "employee_id": test_user["employee_id"],
            "api_key": test_user["api_key"]
        }
    )

    # Try to access admin stats endpoint
    response = session.get(f"{test_server}/api/admin/stats")

    # Should return 403 Forbidden
    assert response.status_code == 403


def test_upload_and_approval_flow(test_server, test_user, test_admin):
    """Test complete upload and approval workflow.

    This test:
    1. User logs in and uploads a skill
    2. Admin logs in and sees pending skill
    3. Admin approves the skill
    4. Verify skill is approved
    """
    # Step 1: User uploads a skill
    user_session = requests.Session()
    user_session.post(
        f"{test_server}/api/login",
        data={
            "employee_id": test_user["employee_id"],
            "api_key": test_user["api_key"]
        }
    )

    skill_data = create_test_skill("workflow-test-skill", "1.0.0")
    files = {"file": ("workflow-test-skill-1.0.0.zip", skill_data, "application/zip")}

    upload_response = user_session.post(
        f"{test_server}/api/upload",
        files=files
    )

    # Upload should succeed (200 or redirect)
    assert upload_response.status_code in [200, 302]

    # Step 2: Admin checks pending skills
    admin_session = requests.Session()
    admin_session.post(
        f"{test_server}/api/login",
        data={
            "employee_id": test_admin["employee_id"],
            "api_key": test_admin["api_key"]
        }
    )

    pending_response = admin_session.get(f"{test_server}/api/pending")
    assert pending_response.status_code == 200

    pending_data = pending_response.json()
    assert pending_data["success"] is True
    assert pending_data["count"] >= 1

    # Find our uploaded skill
    skill_id = None
    for skill in pending_data["data"]:
        if skill["skill_name"] == "workflow-test-skill":
            skill_id = skill["id"]
            break

    assert skill_id is not None, "Uploaded skill not found in pending list"

    # Step 3: Admin approves the skill
    approve_response = admin_session.post(
        f"{test_server}/api/review/{skill_id}",
        json={"action": "approve", "comment": "Test approval"}
    )

    assert approve_response.status_code == 200
    approve_data = approve_response.json()
    assert approve_data["success"] is True

    # Step 4: Verify skill is no longer pending
    pending_response_after = admin_session.get(f"{test_server}/api/pending")
    pending_data_after = pending_response_after.json()

    # Our skill should no longer be in pending
    skill_still_pending = any(
        s["skill_name"] == "workflow-test-skill"
        for s in pending_data_after["data"]
    )
    assert skill_still_pending is False


def test_admin_stats_endpoint(test_server, test_admin):
    """Test admin statistics endpoint."""
    session = requests.Session()

    # Login as admin
    session.post(
        f"{test_server}/api/login",
        data={
            "employee_id": test_admin["employee_id"],
            "api_key": test_admin["api_key"]
        }
    )

    # Get admin stats
    response = session.get(f"{test_server}/api/admin/stats")

    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert "data" in data

    stats = data["data"]
    # Check required fields
    assert "total_users" in stats
    assert "pending_skills" in stats
    assert "approved_skills" in stats
    assert "today_downloads" in stats
    assert "top_skills" in stats
    assert "top_users" in stats

    # Validate data types
    assert isinstance(stats["total_users"], int)
    assert isinstance(stats["pending_skills"], int)
    assert isinstance(stats["approved_skills"], int)
    assert isinstance(stats["today_downloads"], int)
    assert isinstance(stats["top_skills"], list)
    assert isinstance(stats["top_users"], list)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
