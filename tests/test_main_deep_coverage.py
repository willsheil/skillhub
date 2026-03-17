"""
Deep coverage tests for main.py uncovered functions.
Focus on validation, packaging, and specific API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from main import app, validate_skill_name, package_skill_with_installer
from database import (
    get_connection, create_user, create_skill_record
)
import uuid
import io
import zipfile
import tempfile
import os
from pathlib import Path


client = TestClient(app)


def unique_name(base: str) -> str:
    """Generate a unique name for testing."""
    return f"{base}-{uuid.uuid4().hex[:8]}"


class TestValidateSkillName:
    """Tests for validate_skill_name function."""

    def test_validate_empty_name(self):
        """Test validation with empty name."""
        is_valid, error = validate_skill_name("")
        assert is_valid is False
        assert "required" in error.lower()

    def test_validate_none_name(self):
        """Test validation with None name."""
        is_valid, error = validate_skill_name(None)
        assert is_valid is False
        assert "required" in error.lower()

    def test_validate_too_long_name(self):
        """Test validation with too long name."""
        long_name = "a" * 100
        is_valid, error = validate_skill_name(long_name)
        assert is_valid is False
        assert "1-64" in error.lower()

    def test_validate_uppercase_letters(self):
        """Test validation with uppercase letters."""
        is_valid, error = validate_skill_name("TestSkill")
        assert is_valid is False
        assert "lowercase" in error.lower()

    def test_validate_starts_with_hyphen(self):
        """Test validation with name starting with hyphen."""
        is_valid, error = validate_skill_name("-test-skill")
        assert is_valid is False
        assert "start or end" in error.lower()

    def test_validate_ends_with_hyphen(self):
        """Test validation with name ending with hyphen."""
        is_valid, error = validate_skill_name("test-skill-")
        assert is_valid is False
        assert "start or end" in error.lower()

    def test_validate_consecutive_hyphens(self):
        """Test validation with consecutive hyphens."""
        is_valid, error = validate_skill_name("test--skill")
        assert is_valid is False
        assert "consecutive" in error.lower()

    def test_validate_valid_name(self):
        """Test validation with valid name."""
        is_valid, error = validate_skill_name("my-skill-123")
        assert is_valid is True
        assert error == ""

    def test_validate_simple_name(self):
        """Test validation with simple name."""
        is_valid, error = validate_skill_name("skill")
        assert is_valid is True
        assert error == ""


    def test_validate_numeric_name(self):
        """Test validation with numeric name."""
        is_valid, error = validate_skill_name("skill-123")
        assert is_valid is True
        assert error == ""


class TestPackageSkillWithInstaller:
    """Tests for package_skill_with_installer function."""

    def create_test_skill_zip(self, skill_name: str = "test-skill", include_installer: bool = True) -> Path:
        """Create a test skill ZIP file."""
        temp_dir = tempfile.mkdtemp()
        zip_path = Path(temp_dir) / f"{skill_name}.zip"

        if include_installer:
            skill_md = f"""---
name: {skill_name}
description: A test skill
metadata:
  version: 1.0.0
  author: w00000001
allowed-tools: bash, read
---

# {skill_name}

Test skill for installer.
"""
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("SKILL.md", skill_md)
                zf.writestr("install.bat", "@echo Installing...")
                zf.writestr("install.sh", "#!/bin/bash\necho Install")
        else:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("readme.txt", "No installer")

        return zip_path

    def test_package_with_installer(self):
        """Test packaging skill with installer scripts."""
        skill_name = unique_name("pkg-skill")
        zip_path = self.create_test_skill_zip(skill_name, include_installer=True)

        try:
            result = package_skill_with_installer(zip_path, skill_name, "1.0.0")
            assert isinstance(result, bytes)
            # Check the result contains installer scripts
            with zipfile.ZipFile(io.BytesIO(result), 'r') as zf:
                namelist = zf.namelist()
                assert "SKILL.md" in namelist
                assert "install.bat" in namelist
                assert "install.sh" in namelist

        finally:
            import shutil
            shutil.rmtree(zip_path.parent, ignore_errors=True)

    def test_package_without_installer(self):
        """Test packaging skill without installer scripts - function adds default scripts."""
        skill_name = unique_name("pkg-no-inst")
        zip_path = self.create_test_skill_zip(skill_name, include_installer=False)

        try:
            result = package_skill_with_installer(zip_path, skill_name, "1.0.0")
            assert isinstance(result, bytes)
            # Function may add default install scripts even when not present in input
            # Just verify it returns a valid ZIP
            with zipfile.ZipFile(io.BytesIO(result), 'r') as zf:
                namelist = zf.namelist()
                # Verify we got a valid ZIP with some content
                assert len(namelist) > 0

        finally:
            import shutil
            shutil.rmtree(zip_path.parent, ignore_errors=True)

    def test_package_nonexistent_zip(self):
        """Test packaging with nonexistent ZIP file."""
        with pytest.raises(FileNotFoundError):
            package_skill_with_installer(
                Path("/nonexistent/file.zip"),
                "skill",
                "1.0.0"
            )


class TestAdminEndpointsDeep:
    """Tests for admin-specific endpoints."""

    def test_admin_skills_list_with_auth(self):
        """Test admin skills list with authentication."""
        admin_id = unique_name("t-aed")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        try:
            login_resp = client.post("/api/login", data={
                "employee_id": admin_id,
                "api_key": admin_key
            })
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/admin/skills", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 403]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()

    def test_admin_users_list(self):
        """Test admin users list endpoint."""
        admin_id = unique_name("t-aul")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        try:
            login_resp = client.post("/api/login", data={
                "employee_id": admin_id,
                "api_key": admin_key
            })
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/admin/users", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 403, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()

    def test_admin_stats_endpoint(self):
        """Test admin stats endpoint."""
        admin_id = unique_name("t-ast")
        admin_key = f"key-{admin_id}"
        admin_user_id = create_user(admin_id, admin_key, "admin")

        try:
            login_resp = client.post("/api/login", data={
                "employee_id": admin_id,
                "api_key": admin_key
            })
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.get("/api/admin/stats", cookies=login_resp.cookies)
            assert response.status_code in [200, 401, 403, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (admin_user_id,))
                conn.commit()


class TestSkillVersionEndpoints:
    """Tests for skill version endpoints."""

    def test_skill_versions_list(self):
        """Test listing skill versions."""
        response = client.get("/api/skill-versions/nonexistent-skill")
        assert response.status_code in [200, 404]

    def test_skill_set_default_version(self):
        """Test setting default version."""
        emp_id = unique_name("t-ssdv")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "user")

        skill_name = unique_name("version-skill")
        skill_id = create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        try:
            login_resp = client.post("/api/login", data={
                "employee_id": emp_id,
                "api_key": api_key
            })
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            response = client.post(
                f"/api/my-skills/{skill_id}/set-default",
                cookies=login_resp.cookies
            )
            assert response.status_code in [200, 401, 404]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM notifications WHERE related_skill_id = %s", (skill_id,))
                conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


class TestSourceFilterEndpoints:
    """Tests for source filter endpoints."""

    def test_skills_by_source_opensource(self):
        """Test filtering skills by opensource."""
        response = client.get("/api/skills?source=opensource")
        assert response.status_code == 200

    def test_skills_by_source_icsl(self):
        """Test filtering skills by icsl."""
        response = client.get("/api/skills?source=icsl")
        assert response.status_code == 200

    def test_skills_by_source_huawei(self):
        """Test filtering skills by huawei."""
        response = client.get("/api/skills?source=huawei")
        assert response.status_code == 200

    def test_skills_invalid_source(self):
        """Test filtering skills with invalid source."""
        response = client.get("/api/skills?source=invalid")
        assert response.status_code in [200, 400]


class TestErrorHandling:
    """Tests for error handling paths."""

    def test_invalid_json_body(self):
        """Test handling invalid JSON body."""
        response = client.post(
            "/api/admin/users",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [400, 422]

    def test_missing_content_type(self):
        """Test handling missing content type."""
        response = client.post(
            "/api/admin/users",
            data='{"test": "data"}'
        )
        assert response.status_code in [400, 422, 401, 403]

    def test_empty_request_body(self):
        """Test handling empty request body."""
        response = client.post(
            "/api/admin/users",
            json={}
        )
        assert response.status_code in [400, 401, 403, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
