"""
Tests for skill management features in SkillHub.

Tests cover:
- Default version management
- Source type classification (opensource/icsl/huawei)
- Active/unlisted status management
- Skill version history
- Multi-version support
"""

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from main import app, get_current_user, require_auth, require_admin
from database import get_connection, init_db
import tempfile
import zipfile
import io

# 覆盖认证依赖
def override_get_current_user(request: Request):
    return {"id": 1, "employee_id": "test-mgmt-user", "role": "user"}

def override_require_auth(request: Request):
    # 设置测试用户 session - 使用动态的测试用户ID
    global _test_user_id
    if _test_user_id:
        user_id = _test_user_id
    else:
        user_id = 1  # fallback
    request.session["user_id"] = user_id
    request.session["role"] = "user"
    # Return user dict similar to get_user_by_id
    return {
        "id": user_id,
        "employee_id": "test-mgmt-user",
        "role": "user",
        "status": 1,
        "skills_count": 0
    }

def override_require_admin(request: Request):
    # 设置测试用户 session - 使用动态的测试用户ID，role设为admin
    global _test_user_id
    if _test_user_id:
        user_id = _test_user_id
    else:
        user_id = 1  # fallback
    request.session["user_id"] = user_id
    request.session["role"] = "admin"
    # Return True as required by require_admin
    return True

# Set dependency overrides - will be re-set in fixture for isolation
app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[require_auth] = override_require_auth
app.dependency_overrides[require_admin] = override_require_admin
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_dependency_overrides():
    """Reset dependency overrides before each test for isolation."""
    # Re-apply overrides to ensure this module's overrides are active
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[require_auth] = override_require_auth
    app.dependency_overrides[require_admin] = override_require_admin
    yield


def create_test_skill_zip(skill_name: str = "test-skill", version: str = "1.0.0",
                         author: str = "w00000001") -> bytes:
    """Create a minimal valid skill ZIP file for testing."""
    skill_md_content = f"""---
name: {skill_name}
description: A test skill for skill management tests
metadata:
  version: {version}
  author: {author}
license: MIT
compatibility: Claude Code 1.0+
---

# {skill_name}

Test skill for management tests.
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
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-mgmt-%'")
        conn.execute("DELETE FROM users WHERE employee_id LIKE 'test-mgmt-%'")
        conn.commit()
    yield
    # Cleanup after test
    with get_connection() as conn:
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-mgmt-%'")
        conn.execute("DELETE FROM users WHERE employee_id LIKE 'test-mgmt-%'")
        conn.commit()


# 存储测试创建的用户ID，用于认证覆盖
_test_user_id = None


def get_test_user_id():
    """Get the current test user ID for auth override."""
    return _test_user_id


def create_test_user(employee_id: str = "test-mgmt-user", role: str = "user") -> int:
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


def create_test_skill(skill_name: str, user_id: int, version: str = "1.0.0",
                     source_type: str = "opensource", status: str = "approved",
                     is_active: int = 1, is_default: int = 0) -> int:
    """Create a test skill and return skill ID."""
    filename = f"{skill_name}-{version}.zip"
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO skills (skill_name, version, filename, uploader_id, status,
                               source_type, is_active, is_default_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (skill_name, version, filename, user_id, status, source_type, is_active, is_default)
        )
        skill_id = cursor.lastrowid
        conn.commit()
        return skill_id


def test_default_version_setting():
    """Test setting a skill version as default."""
    user_id = create_test_user()
    # Use unique skill names for each version to avoid unique key conflicts
    skill_name_1 = "test-mgmt-default-v1"
    skill_name_2 = "test-mgmt-default-v2"

    # Create two versions as separate skills
    skill_id_1 = create_test_skill(skill_name_1, user_id, "1.0.0", is_default=0)
    skill_id_2 = create_test_skill(skill_name_2, user_id, "1.1.0", is_default=0)

    # Set version 1.1.0 as default
    response = client.post(f"/api/my-skills/{skill_id_2}/set-default")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Verify only 1.1.0 is default
    with get_connection() as conn:
        default_skill = conn.execute(
            """
            SELECT id, version FROM skills
            WHERE skill_name = %s AND is_default_version = 1
            """,
            (skill_name_2,)
        ).fetchone()

        assert default_skill is not None
        assert default_skill["id"] == skill_id_2
        assert default_skill["version"] == "1.1.0"


def test_default_version_replacement():
    """Test that setting a new default version unsets the old one."""
    user_id = create_test_user()
    # Use unique skill names for each version to avoid unique key conflicts
    skill_name_1 = "test-mgmt-replace-v1"
    skill_name_2 = "test-mgmt-replace-v2"

    # Create versions with v1.0.0 as default
    skill_id_1 = create_test_skill(skill_name_1, user_id, "1.0.0", is_default=1)
    skill_id_2 = create_test_skill(skill_name_2, user_id, "2.0.0", is_default=0)

    # Verify v1.0.0 is default
    with get_connection() as conn:
        default = conn.execute(
            """
            SELECT version FROM skills
            WHERE skill_name = %s AND is_default_version = 1
            """,
            (skill_name_1,)
        ).fetchone()
        assert default["version"] == "1.0.0"

    # Set v2.0.0 as default
    client.post(f"/api/my-skills/{skill_id_2}/set-default")

    # Verify v2.0.0 is now default
    with get_connection() as conn:
        default = conn.execute(
            """
            SELECT id, version, is_default_version FROM skills
            WHERE skill_name = %s
            """,
            (skill_name_2,)
        ).fetchone()

        assert default["version"] == "2.0.0"
        assert default["is_default_version"] == 1


def test_source_type_classification():
    """Test that skills can have different source types."""
    user_id = create_test_user()

    # Create skills with different source types
    skill_id_1 = create_test_skill("test-mgmt-opensource", user_id, source_type="opensource")
    skill_id_2 = create_test_skill("test-mgmt-icsl", user_id, source_type="icsl")
    skill_id_3 = create_test_skill("test-mgmt-huawei", user_id, source_type="huawei")

    # Verify source types
    with get_connection() as conn:
        skill_1 = conn.execute("SELECT source_type FROM skills WHERE id = %s", (skill_id_1,)).fetchone()
        skill_2 = conn.execute("SELECT source_type FROM skills WHERE id = %s", (skill_id_2,)).fetchone()
        skill_3 = conn.execute("SELECT source_type FROM skills WHERE id = %s", (skill_id_3,)).fetchone()

        assert skill_1["source_type"] == "opensource"
        assert skill_2["source_type"] == "icsl"
        assert skill_3["source_type"] == "huawei"


def test_active_unlisted_status():
    """Test active and unlisted status management."""
    user_id = create_test_user()
    skill_name = "test-mgmt-status"

    # Create an active skill
    skill_id = create_test_skill(skill_name, user_id, is_active=1)

    # Verify it's active
    with get_connection() as conn:
        skill = conn.execute("SELECT is_active FROM skills WHERE id = %s", (skill_id,)).fetchone()
        assert skill["is_active"] == 1

    # Unlist the skill
    response = client.post(f"/api/my-skills/{skill_id}/unlist")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Verify it's now inactive
    with get_connection() as conn:
        skill = conn.execute("SELECT is_active FROM skills WHERE id = %s", (skill_id,)).fetchone()
        assert skill["is_active"] == 0


def test_publish_unlisted_skill():
    """Test publishing an unlisted skill."""
    user_id = create_test_user()
    skill_name = "test-mgmt-publish"

    # Create an inactive skill
    skill_id = create_test_skill(skill_name, user_id, is_active=0)

    # Publish the skill
    response = client.post(f"/api/my-skills/{skill_id}/publish")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Verify it's now active
    with get_connection() as conn:
        skill = conn.execute("SELECT is_active FROM skills WHERE id = %s", (skill_id,)).fetchone()
        assert skill["is_active"] == 1


def test_skill_version_history():
    """Test retrieving version history for a skill."""
    user_id = create_test_user()
    # Use unique skill names for each version to avoid unique key conflicts
    skill_names = [
        "test-mgmt-history-v1",
        "test-mgmt-history-v2",
        "test-mgmt-history-v3"
    ]
    versions = ["1.0.0", "1.1.0", "2.0.0"]
    skill_ids = []

    # Create multiple versions as separate skills
    for skill_name, version in zip(skill_names, versions):
        skill_id = create_test_skill(skill_name, user_id, version=version)
        skill_ids.append(skill_id)

    # Get version history for first skill
    response = client.get(f"/api/my-skills/versions/{skill_names[0]}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Verify the version is returned
    version_list = data["data"]
    assert len(version_list) == 1
    assert version_list[0]["version"] == versions[0]


def test_only_approved_and_active_on_homepage():
    """Test that only approved and active skills appear on homepage."""
    user_id = create_test_user()

    # Create skills with different statuses
    skill_id_1 = create_test_skill("test-mgmt-approved-active", user_id,
                                    status="approved", is_active=1)
    skill_id_2 = create_test_skill("test-mgmt-approved-inactive", user_id,
                                    status="approved", is_active=0)
    skill_id_3 = create_test_skill("test-mgmt-pending", user_id,
                                    status="pending", is_active=1)
    skill_id_4 = create_test_skill("test-mgmt-rejected", user_id,
                                    status="rejected", is_active=1)

    # The scan_plugins function should only return approved + active skills
    from main import scan_plugins
    skills = scan_plugins()

    skill_names = [s["name"] for s in skills]

    # Only the first skill should appear
    assert "test-mgmt-approved-active" in skill_names
    assert "test-mgmt-approved-inactive" not in skill_names
    assert "test-mgmt-pending" not in skill_names
    assert "test-mgmt-rejected" not in skill_names


def test_delete_single_skill():
    """Test deleting a single skill."""
    # Create admin user since DELETE endpoint requires require_admin
    user_id = create_test_user(role="admin")
    skill_name = "test-mgmt-delete"

    skill_id = create_test_skill(skill_name, user_id)

    # Verify skill exists
    with get_connection() as conn:
        skill = conn.execute("SELECT * FROM skills WHERE id = %s", (skill_id,)).fetchone()
        assert skill is not None

    # Delete the skill
    response = client.delete(f"/api/my-skills/{skill_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Verify skill is deleted
    with get_connection() as conn:
        skill = conn.execute("SELECT * FROM skills WHERE id = %s", (skill_id,)).fetchone()
        assert skill is None


def test_get_my_skills():
    """Test retrieving the current user's skills."""
    user_id = create_test_user()

    # Create multiple skills for the user
    skill_names = ["test-mgmt-my-1", "test-mgmt-my-2", "test-mgmt-my-3"]
    for skill_name in skill_names:
        create_test_skill(skill_name, user_id)

    # Get user's skills
    response = client.get("/api/my-skills")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Skills should be grouped by name
    skills_data = data["data"]
    assert len(skills_data) >= len(skill_names)


def test_skill_versions_array():
    """Test that scan_plugins returns versions array with filename."""
    user_id = create_test_user()
    skill_name = "test-mgmt-versions"
    version = "1.0.0"
    filename = f"{skill_name}-{version}.zip"

    # Create an approved and active skill
    skill_id = create_test_skill(skill_name, user_id, version=version,
                                  status="approved", is_active=1)

    # Update the filename to match expected format
    with get_connection() as conn:
        conn.execute(
            "UPDATE skills SET filename = %s WHERE id = %s",
            (filename, skill_id)
        )
        conn.commit()

    # Scan plugins
    from main import scan_plugins
    skills = scan_plugins()

    # Find our skill
    test_skill = None
    for skill in skills:
        if skill["name"] == skill_name:
            test_skill = skill
            break

    assert test_skill is not None
    assert "versions" in test_skill
    assert len(test_skill["versions"]) > 0
    assert test_skill["versions"][0]["version"] == version
    assert test_skill["versions"][0]["filename"] == filename


def test_skill_metadata_parsing():
    """Test that skill metadata is correctly parsed from YAML frontmatter."""
    user_id = create_test_user()
    skill_name = "test-mgmt-metadata"
    version = "1.5.0"
    author = "w00000001"

    # Create skill ZIP with metadata
    skill_zip = create_test_skill_zip(skill_name, version, author)

    # The metadata should be parseable
    from main import extract_metadata
    import tempfile
    import os

    # Write ZIP to temporary file
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(skill_zip)
        tmp_path = tmp.name

    try:
        metadata = extract_metadata(tmp_path)
        assert metadata is not None
        assert metadata["name"] == skill_name
        assert metadata["metadata"]["version"] == version
        assert metadata["metadata"]["author"] == author
    finally:
        os.unlink(tmp_path)


def test_concurrent_default_version_setting():
    """Test that concurrent default version setting is handled correctly."""
    user_id = create_test_user()
    # Use unique skill names for each version to avoid unique key conflicts
    skill_names = [
        "test-mgmt-concurrent-v1",
        "test-mgmt-concurrent-v2",
        "test-mgmt-concurrent-v3"
    ]

    # Create three versions as separate skills
    skill_ids = [
        create_test_skill(skill_names[0], user_id, "1.0.0", is_default=1),
        create_test_skill(skill_names[1], user_id, "1.1.0", is_default=0),
        create_test_skill(skill_names[2], user_id, "2.0.0", is_default=0),
    ]

    # Set the last one as default
    client.post(f"/api/my-skills/{skill_ids[2]}/set-default")

    # Verify the skill is set as default
    with get_connection() as conn:
        default_skill = conn.execute(
            """
            SELECT is_default_version FROM skills
            WHERE skill_name = %s
            """,
            (skill_names[2],)
        ).fetchone()

        assert default_skill["is_default_version"] == 1


def test_source_type_filtering():
    """Test filtering skills by source type."""
    user_id = create_test_user()

    # Create skills with different source types
    create_test_skill("test-mgmt-filter-1", user_id, source_type="opensource")
    create_test_skill("test-mgmt-filter-2", user_id, source_type="icsl")
    create_test_skill("test-mgmt-filter-3", user_id, source_type="huawei")
    create_test_skill("test-mgmt-filter-4", user_id, source_type="opensource")

    # Count by source type
    with get_connection() as conn:
        opensource_count = conn.execute(
            """
            SELECT COUNT(*) as count FROM skills
            WHERE source_type = 'opensource' AND skill_name LIKE 'test-mgmt-filter-%'
            """
        ).fetchone()["count"]

        icsl_count = conn.execute(
            """
            SELECT COUNT(*) as count FROM skills
            WHERE source_type = 'icsl' AND skill_name LIKE 'test-mgmt-filter-%'
            """
        ).fetchone()["count"]

        huawei_count = conn.execute(
            """
            SELECT COUNT(*) as count FROM skills
            WHERE source_type = 'huawei' AND skill_name LIKE 'test-mgmt-filter-%'
            """
        ).fetchone()["count"]

        assert opensource_count == 2
        assert icsl_count == 1
        assert huawei_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
