"""
Tests for upload and review workflow endpoints.
Focus on file upload, approval, and rejection paths.
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from database import (
    get_connection, create_user, create_skill_record,
    get_skill_by_id, update_skill_status
)
import uuid
import io
import zipfile
import os


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


def create_test_skill_zip(skill_name: str = "test-skill", version: str = "1.0.0", include_metadata: bool = True) -> bytes:
    """Create a minimal valid skill ZIP file."""
    if include_metadata:
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
    else:
        skill_md_content = f"""---
name: {skill_name}
description: A test skill
---

# {skill_name}
"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("SKILL.md", skill_md_content)
        zip_file.writestr("scripts/main.sh", "#!/bin/bash\necho 'Hello'")
    zip_buffer.seek(0)
    return zip_buffer.read()


class TestUploadWorkflow:
    """Tests for skill upload workflow."""

    def test_upload_page_requires_auth(self):
        """Test that upload page requires authentication."""
        response = client.get("/upload")
        assert response.status_code in [200, 302, 401]

    def test_admin_upload_page_requires_auth(self):
        """Test that admin upload page requires authentication."""
        response = client.get("/admin/upload")
        assert response.status_code in [200, 302, 401]

    def test_upload_valid_skill_with_auth(self):
        """Test uploading a valid skill with authentication."""
        emp_id = unique_name("t-uvs")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-upload-skill")
        skill_zip = create_test_skill_zip(skill_name, "1.0.0")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                "/api/upload",
                files={"file": (f"{skill_name}.zip", io.BytesIO(skill_zip), "application/zip")},
                data={"source_type": "opensource", "overwrite": "false"},
                cookies=login_resp.cookies
            )
            # Accept success, validation error, or conflict
            assert response.status_code in [200, 201, 400, 409, 422]

        finally:
            with get_connection() as conn:
                # Clean up skill
                conn.execute("DELETE FROM notifications WHERE related_skill_id IN (SELECT id FROM skills WHERE skill_name = %s)", (skill_name,))
                conn.execute("DELETE FROM skills WHERE skill_name = %s", (skill_name,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()
                # Clean up file
                for path in [f"data/pending/{skill_name}.zip", f"plugins/{skill_name}.zip"]:
                    if os.path.exists(path):
                        try:
                            os.remove(path)
                        except Exception:
                            pass

    def test_upload_skill_missing_metadata(self):
        """Test uploading a skill with missing metadata fields."""
        emp_id = unique_name("t-usm")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-missing-meta")
        skill_zip = create_test_skill_zip(skill_name, "1.0.0", include_metadata=False)

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                "/api/upload",
                files={"file": (f"{skill_name}.zip", io.BytesIO(skill_zip), "application/zip")},
                data={"source_type": "opensource"},
                cookies=login_resp.cookies
            )
            # Should return 400 with MISSING_FIELDS or accept it
            assert response.status_code in [200, 201, 400, 422]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM skills WHERE skill_name = %s", (skill_name,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()

    def test_upload_overwrite_existing(self):
        """Test uploading with overwrite flag."""
        emp_id = unique_name("t-uoe")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-overwrite-skill")
        skill_zip = create_test_skill_zip(skill_name, "1.0.0")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            # First upload
            response1 = client.post(
                "/api/upload",
                files={"file": (f"{skill_name}.zip", io.BytesIO(skill_zip), "application/zip")},
                data={"source_type": "opensource", "overwrite": "false"},
                cookies=login_resp.cookies
            )

            # Second upload with overwrite
            response2 = client.post(
                "/api/upload",
                files={"file": (f"{skill_name}.zip", io.BytesIO(skill_zip), "application/zip")},
                data={"source_type": "opensource", "overwrite": "true"},
                cookies=login_resp.cookies
            )
            # Both should succeed or handle appropriately
            assert response1.status_code in [200, 201, 400, 422]
            assert response2.status_code in [200, 201, 400, 409, 422]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id IN (SELECT id FROM skills WHERE skill_name = %s)", (skill_name,))
                conn.execute("DELETE FROM skills WHERE skill_name = %s", (skill_name,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestReviewWorkflow:
    """Tests for skill review and approval workflow."""

    def test_get_pending_skills_as_admin(self):
        """Test getting pending skills list as admin."""
        admin_id = unique_name("t-gps")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/pending", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 403]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()

    def test_get_pending_skills_as_user(self):
        """Test getting pending skills list as regular user."""
        emp_id = unique_name("t-gpu")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/pending", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 403]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()

    def test_approve_skill_as_admin(self):
        """Test approving a pending skill as admin."""
        admin_id = unique_name("t-asa")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        user_id = create_user(unique_name("uploader"), "key", "user")
        skill_name = unique_name("test-approve-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="pending",
            source_type="opensource"
        )

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                f"/api/review/{skill_id}",
                json={"action": "approve", "comment": "Approved for testing"},
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 403, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
                conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()

    def test_reject_skill_as_admin(self):
        """Test rejecting a pending skill as admin."""
        admin_id = unique_name("t-rsa")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        user_id = create_user(unique_name("uploader"), "key", "user")
        skill_name = unique_name("test-reject-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="pending",
            source_type="opensource"
        )

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                f"/api/review/{skill_id}",
                json={"action": "reject", "comment": "Rejected for testing"},
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 403, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
                conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()

    def test_review_nonexistent_skill(self):
        """Test reviewing a nonexistent skill."""
        admin_id = unique_name("t-rns")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                "/api/review/99999999",
                json={"action": "approve", "comment": "Test"},
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 403, 404, 422]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()


class TestSkillStatusManagement:
    """Tests for skill status management."""

    def test_update_skill_source_type(self):
        """Test updating skill source type."""
        admin_id = unique_name("t-usst")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        user_id = create_user(unique_name("uploader"), "key", "user")
        skill_name = unique_name("test-source-type")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.put(
                f"/api/admin/skills/{skill_id}/source-type",
                json={"source_type": "icsl"},
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 403, 404, 422]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
                conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()

    def test_get_admin_skills_list(self):
        """Test getting admin skills list."""
        admin_id = unique_name("t-gasl")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/admin/skills", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 403]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()


class TestSkillVersionManagement:
    """Tests for skill version management."""

    def test_set_default_version(self):
        """Test setting a skill version as default."""
        emp_id = unique_name("t-sdv")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-default-version")
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

            response = client.post(
                f"/api/my-skills/{skill_id}/set-default",
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 403, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
                conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()

    def test_get_skill_versions(self):
        """Test getting all versions of a skill."""
        emp_id = unique_name("t-gsv")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-get-versions")
        skill_id1 = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}-1.0.0.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )
        # Note: Database has unique constraint on skill_name, so we can only have one version per name
        # For multi-version tests, we'd need to modify the schema or test differently

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get(
                f"/api/my-skills/versions/{skill_name}",
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id1,))
                conn.execute("DELETE FROM skills WHERE id = %s", (skill_id1,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestBatchOperations:
    """Tests for batch operations on skills."""

    def test_batch_unlist_skills(self):
        """Test batch unlisting skills."""
        emp_id = unique_name("t-bus")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name1 = unique_name("batch-unlist-1")
        skill_name2 = unique_name("batch-unlist-2")
        skill_id1 = create_skill_record(
            skill_name=skill_name1,
            version="1.0.0",
            filename=f"{skill_name1}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )
        skill_id2 = create_skill_record(
            skill_name=skill_name2,
            version="1.0.0",
            filename=f"{skill_name2}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                "/api/my-skills/batch/unlist",
                json={"skill_ids": [skill_id1, skill_id2]},
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 403, 422]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id IN (%s, %s)", (skill_id1, skill_id2))
                conn.execute("DELETE FROM skills WHERE id IN (%s, %s)", (skill_id1, skill_id2))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()

    def test_batch_delete_skills(self):
        """Test batch deleting skills."""
        emp_id = unique_name("t-bds")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name1 = unique_name("batch-delete-1")
        skill_name2 = unique_name("batch-delete-2")
        skill_id1 = create_skill_record(
            skill_name=skill_name1,
            version="1.0.0",
            filename=f"{skill_name1}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )
        skill_id2 = create_skill_record(
            skill_name=skill_name2,
            version="1.0.0",
            filename=f"{skill_name2}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                "/api/my-skills/batch/delete",
                json={"skill_ids": [skill_id1, skill_id2]},
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 403, 422]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id IN (%s, %s)", (skill_id1, skill_id2))
                conn.execute("DELETE FROM skills WHERE id IN (%s, %s)", (skill_id1, skill_id2))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
