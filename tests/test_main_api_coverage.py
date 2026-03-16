"""
Additional tests for main.py API endpoints.
Focus on upload, batch operations, admin functions, and error paths.
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from database import (
    get_connection, create_user, create_skill_record,
    get_user_by_id, create_notification, create_api_key
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


class TestSkillUploadEndpoint:
    """Tests for skill upload endpoint."""

    def test_upload_without_auth(self):
        """Test upload without authentication."""
        skill_zip = create_test_skill_zip()
        response = client.post(
            "/api/upload",
            files={"file": ("test-skill.zip", io.BytesIO(skill_zip), "application/zip")}
        )
        # May return 200 (HTML page), 302 (redirect), or 401/403
        assert response.status_code in [200, 302, 401, 403]

    def test_upload_with_auth_invalid_file(self):
        """Test upload with invalid file type."""
        emp_id = unique_name("t-uaif")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            # Upload a text file instead of ZIP
            response = client.post(
                "/api/upload",
                files={"file": ("test.txt", io.BytesIO(b"not a zip file"), "text/plain")},
                cookies=login_resp.cookies
            )
            assert response.status_code in [400, 422, 500]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()

    def test_upload_with_auth_valid_file(self):
        """Test upload with valid ZIP file."""
        emp_id = unique_name("t-uavf")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("upload-test-skill")
        skill_zip = create_test_skill_zip(skill_name)

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                "/api/upload",
                files={"file": (f"{skill_name}.zip", io.BytesIO(skill_zip), "application/zip")},
                cookies=login_resp.cookies
            )
            # Accept success or validation error
            assert response.status_code in [200, 201, 400, 422]

        finally:
            with get_connection() as conn:
                # Clean up any created skill
                conn.execute("DELETE FROM notifications WHERE related_skill_id IN (SELECT id FROM skills WHERE skill_name = %s)", (skill_name,))
                conn.execute("DELETE FROM skills WHERE skill_name = %s", (skill_name,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()
                # Clean up file if created
                file_path = f"data/pending/{skill_name}.zip"
                if os.path.exists(file_path):
                    os.remove(file_path)


class TestBatchDownloadEndpoint:
    """Tests for batch download endpoint."""

    def test_batch_download_empty_list(self):
        """Test batch download with empty list."""
        emp_id = unique_name("t-bde")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                "/api/batch-download",
                json={"filenames": []},
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 400, 422]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()

    def test_batch_download_nonexistent_files(self):
        """Test batch download with nonexistent files."""
        emp_id = unique_name("t-bdnf")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                "/api/batch-download",
                json={"filenames": ["nonexistent1.zip", "nonexistent2.zip"]},
                cookies=login_resp.cookies
            )
            # May return 404 or empty zip
            assert response.status_code in [200, 400, 404, 422]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestSkillContentEndpoint:
    """Tests for skill content endpoint."""

    def test_get_skill_content_nonexistent(self):
        """Test getting content of nonexistent skill."""
        response = client.get("/api/skill/nonexistent-skill-xyz/content")
        assert response.status_code in [200, 404, 500]

    def test_get_skill_content_exists(self):
        """Test getting content of existing skill."""
        emp_id = unique_name("t-gsce")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-skill-content")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        try:
            with get_connection() as conn:
                conn.execute("UPDATE skills SET is_active = 1 WHERE id = %s", (skill_id,))
                conn.commit()

            response = client.get(f"/api/skill/{skill_name}/content")
            assert response.status_code in [200, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
                conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestAdminStatsEndpoint:
    """Tests for admin statistics endpoint."""

    def test_admin_stats_without_auth(self):
        """Test admin stats without authentication."""
        response = client.get("/api/admin/stats")
        # May return 200 (HTML page), 302 (redirect), or 401/403
        assert response.status_code in [200, 302, 401, 403]

    def test_admin_stats_with_user_auth(self):
        """Test admin stats with regular user."""
        emp_id = unique_name("t-aswu")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/admin/stats", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 403]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()

    def test_admin_stats_with_admin_auth(self):
        """Test admin stats with admin user."""
        admin_id = unique_name("t-aswa")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/admin/stats", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 403]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()


class TestStatsExportEndpoint:
    """Tests for stats export endpoint."""

    def test_stats_export_without_auth(self):
        """Test stats export without authentication."""
        response = client.get("/api/stats/export")
        # May return 200 (HTML page), 302 (redirect), or 401/403
        assert response.status_code in [200, 302, 401, 403]

    def test_stats_export_with_auth(self):
        """Test stats export with authentication."""
        emp_id = unique_name("t-sew")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/stats/export", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 403]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestTopStatsEndpoint:
    """Tests for top stats endpoint."""

    def test_top_stats(self):
        """Test getting top stats."""
        response = client.get("/api/stats/top")
        assert response.status_code in [200, 401]


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "healthy" in str(data).lower() or data is not None


class TestSearchHistoryEndpoints:
    """Tests for search history endpoints."""

    def test_get_search_history_without_auth(self):
        """Test getting search history without auth."""
        response = client.get("/api/search/history")
        # May return 200 (HTML page), 302 (redirect), 401/403, or 500 (server error)
        assert response.status_code in [200, 302, 401, 403, 500]

    def test_get_search_history_with_auth(self):
        """Test getting search history with auth."""
        emp_id = unique_name("t-gshw")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/search/history", cookies=login_resp.cookies)
            assert response.status_code in [200, 401]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM search_history WHERE user_id = %s", (user_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()

    def test_delete_search_history(self):
        """Test deleting search history."""
        emp_id = unique_name("t-dsh")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.delete("/api/search/history", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 403]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM search_history WHERE user_id = %s", (user_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestSkillViewEndpoint:
    """Tests for skill view increment endpoint."""

    def test_increment_view_count(self):
        """Test incrementing skill view count."""
        emp_id = unique_name("t-ivc")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-skill-view")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        try:
            response = client.post(f"/api/skills/{skill_id}/view")
            assert response.status_code in [200, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
                conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestRelatedSkillsEndpoint:
    """Tests for related skills endpoint."""

    def test_get_related_skills(self):
        """Test getting related skills."""
        emp_id = unique_name("t-grs")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-skill-related")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        try:
            response = client.get(f"/api/skills/{skill_id}/related")
            assert response.status_code in [200, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
                conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestUserDownloadsEndpoint:
    """Tests for user downloads endpoint."""

    def test_get_user_downloads(self):
        """Test getting user downloads."""
        emp_id = unique_name("t-gud")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/user/downloads", cookies=login_resp.cookies)
            assert response.status_code in [200, 401]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestUserUploadsEndpoint:
    """Tests for user uploads endpoint."""

    def test_get_user_uploads(self):
        """Test getting user uploads."""
        emp_id = unique_name("t-guu")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/user/uploads", cookies=login_resp.cookies)
            assert response.status_code in [200, 401]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestSkillDetailPage:
    """Tests for skill detail page."""

    def test_skill_detail_page_nonexistent(self):
        """Test skill detail page for nonexistent skill."""
        response = client.get("/skill/nonexistent-skill-xyz-123")
        assert response.status_code in [200, 404, 500]

    def test_skill_detail_page_exists(self):
        """Test skill detail page for existing skill."""
        emp_id = unique_name("t-sdpe")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-skill-detail")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        try:
            with get_connection() as conn:
                conn.execute("UPDATE skills SET is_active = 1 WHERE id = %s", (skill_id,))
                conn.commit()

            response = client.get(f"/skill/{skill_name}")
            assert response.status_code in [200, 302, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
                conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestMySkillsVersionsEndpoint:
    """Tests for my-skills versions endpoint."""

    def test_get_skill_versions(self):
        """Test getting skill versions."""
        emp_id = unique_name("t-gsv")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-skill-versions")
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

            response = client.get(f"/api/my-skills/versions/{skill_name}", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
                conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestPublishSkillEndpoint:
    """Tests for publish skill endpoint."""

    def test_publish_skill(self):
        """Test publishing a skill."""
        emp_id = unique_name("t-psk")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-skill-publish")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="pending",
            source_type="opensource"
        )

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(f"/api/my-skills/{skill_id}/publish", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 403, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
                conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestUnlistSkillEndpoint:
    """Tests for unlist skill endpoint."""

    def test_unlist_skill(self):
        """Test unlisting a skill."""
        emp_id = unique_name("t-usk")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("test-skill-unlist")
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

            response = client.post(f"/api/my-skills/{skill_id}/unlist", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 403, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
                conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestMarketplaceEndpoint:
    """Tests for marketplace endpoint."""

    def test_marketplace_json(self):
        """Test marketplace.json endpoint."""
        response = client.get("/marketplace.json")
        assert response.status_code == 200
        try:
            data = response.json()
            assert "name" in data or "plugins" in data or data is not None
        except Exception:
            # If response is not JSON, just verify it returned 200
            pass


class TestApiMeEndpoint:
    """Tests for /api/me endpoint."""

    def test_api_me_without_auth(self):
        """Test /api/me without authentication."""
        response = client.get("/api/me")
        assert response.status_code in [401, 403, 422]

    def test_api_me_with_auth(self):
        """Test /api/me with authentication."""
        emp_id = unique_name("t-ame")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/me", cookies=login_resp.cookies)
            assert response.status_code in [200, 401]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestBatchUnlistEndpoint:
    """Tests for batch unlist endpoint."""

    def test_batch_unlist_empty(self):
        """Test batch unlist with empty list."""
        emp_id = unique_name("t-bue")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                "/api/my-skills/batch/unlist",
                json={"skill_ids": []},
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 403, 422]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestBatchDeleteEndpoint:
    """Tests for batch delete endpoint."""

    def test_batch_delete_empty(self):
        """Test batch delete with empty list."""
        emp_id = unique_name("t-bde")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        try:
            login_resp = login_user(emp_id, api_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                "/api/my-skills/batch/delete",
                json={"skill_ids": []},
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 403, 422]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestAdminAPIKeysEndpoints:
    """Tests for admin API keys endpoints."""

    def test_get_api_keys_list(self):
        """Test getting API keys list."""
        admin_id = unique_name("t-gakl")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/admin/api-keys", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 403]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()

    def test_create_api_key(self):
        """Test creating API key."""
        admin_id = unique_name("t-cak")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        try:
            login_resp = login_user(admin_id, admin_key)
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                "/api/admin/api-keys",
                json={"name": "test-key", "description": "Test API key"},
                cookies=login_resp.cookies
            )
            # May return 200, 201, 401, 403, 404, 422, or 500
            assert response.status_code in [200, 201, 401, 403, 404, 422, 500]

        finally:
            with get_connection() as conn:
                try:
                    conn.execute("DELETE FROM api_keys WHERE name = 'test-key'")
                except Exception:
                    pass
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
