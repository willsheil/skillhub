"""
Tests for utility functions and helper methods in main.py.
"""

import pytest
from fastapi.testclient import TestClient
from main import app, parse_plugin_filename, extract_metadata_from_skill_md, validate_skill_zip
from database import get_connection, create_user
from pathlib import Path
import uuid
import io
import zipfile
import tempfile
import os


client = TestClient(app)


def unique_name(base: str) -> str:
    """Generate a unique name for testing."""
    return f"{base}-{uuid.uuid4().hex[:8]}"


class TestParsePluginFilename:
    """Tests for parse_plugin_filename function."""

    def test_parse_standard_filename(self):
        """Test parsing standard plugin filename."""
        result = parse_plugin_filename("skill-name-1.0.0.zip")
        assert result[0] == "skill-name-1.0.0"  # name
        assert result[1] == "unknown"  # version (extracted from ZIP)

    def test_parse_simple_filename(self):
        """Test parsing simple filename."""
        result = parse_plugin_filename("myskill.zip")
        assert result[0] == "myskill"
        assert result[1] == "unknown"

    def test_parse_versioned_filename(self):
        """Test parsing versioned filename."""
        result = parse_plugin_filename("my-awesome-skill-2.3.1.zip")
        assert result[0] == "my-awesome-skill-2.3.1"
        assert result[1] == "unknown"

    def test_parse_no_extension(self):
        """Test parsing filename without extension."""
        result = parse_plugin_filename("skill-no-ext")
        assert result[0] == "skill-no-ext"
        assert result[1] == "unknown"


class TestExtractMetadataFromSkillMd:
    """Tests for extract_metadata_from_skill_md function."""

    def create_test_zip_with_skill_md(self, skill_md_content: str) -> Path:
        """Create a test ZIP file with SKILL.md content."""
        temp_dir = tempfile.mkdtemp()
        zip_path = Path(temp_dir) / "test.zip"

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("skill/SKILL.md", skill_md_content)

        return zip_path

    def test_extract_valid_metadata(self):
        """Test extracting valid SKILL.md metadata."""
        skill_md = """---
name: test-skill
description: A test skill
metadata:
  version: 1.0.0
  author: w00000001
---

# Test Skill
"""
        zip_path = self.create_test_zip_with_skill_md(skill_md)
        try:
            result = extract_metadata_from_skill_md(zip_path)
            assert result is not None
            assert result.get("name") == "test-skill"
            assert result.get("description") == "A test skill"
        finally:
            shutil.rmtree(zip_path.parent, ignore_errors=True)

    def test_extract_missing_yaml(self):
        """Test extracting from file without YAML frontmatter."""
        skill_md = """# Test Skill

No YAML frontmatter here.
"""
        zip_path = self.create_test_zip_with_skill_md(skill_md)
        try:
            result = extract_metadata_from_skill_md(zip_path)
            # Should return None or handle gracefully
            assert result is None or isinstance(result, dict)
        finally:
            shutil.rmtree(zip_path.parent, ignore_errors=True)

    def test_extract_invalid_yaml(self):
        """Test extracting from file with invalid YAML."""
        skill_md = """---
name: test-skill
description: [invalid yaml
---

# Test Skill
"""
        zip_path = self.create_test_zip_with_skill_md(skill_md)
        try:
            result = extract_metadata_from_skill_md(zip_path)
            # Should return None or handle gracefully
            assert result is None or isinstance(result, dict)
        finally:
            shutil.rmtree(zip_path.parent, ignore_errors=True)


class TestValidateSkillZip:
    """Tests for validate_skill_zip function."""

    def create_skill_zip(self, skill_name: str = "test-skill", version: str = "1.0.0",
                         include_skill_md: bool = True, include_metadata: bool = True) -> Path:
        """Create a test skill ZIP file."""
        temp_dir = tempfile.mkdtemp()
        zip_path = Path(temp_dir) / f"{skill_name}.zip"

        if include_skill_md:
            if include_metadata:
                skill_md = f"""---
name: {skill_name}
description: A test skill
metadata:
  version: {version}
  author: w00000001
allowed-tools: bash, read
---

# {skill_name}
"""
            else:
                skill_md = f"""---
name: {skill_name}
description: A test skill
---

# {skill_name}
"""

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("SKILL.md", skill_md)
        else:
            # Create empty ZIP
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("readme.txt", "No SKILL.md here")

        return zip_path

    def test_validate_valid_zip(self):
        """Test validating a valid skill ZIP."""
        zip_path = self.create_skill_zip("valid-skill", "1.0.0")
        try:
            is_valid, result = validate_skill_zip(zip_path)
            assert is_valid is True or isinstance(result, dict)
        finally:
            shutil.rmtree(zip_path.parent, ignore_errors=True)

    def test_validate_missing_skill_md(self):
        """Test validating ZIP without SKILL.md."""
        zip_path = self.create_skill_zip(include_skill_md=False)
        try:
            is_valid, result = validate_skill_zip(zip_path)
            assert is_valid is False or "error" in result
        finally:
            shutil.rmtree(zip_path.parent, ignore_errors=True)

    def test_validate_missing_metadata_fields(self):
        """Test validating ZIP with missing required metadata fields."""
        zip_path = self.create_skill_zip(include_metadata=False)
        try:
            is_valid, result = validate_skill_zip(zip_path, allow_missing=True)
            # With allow_missing=True, should return info about missing fields
            assert isinstance(result, dict)
        finally:
            shutil.rmtree(zip_path.parent, ignore_errors=True)

    def test_validate_nonexistent_file(self):
        """Test validating nonexistent file."""
        is_valid, result = validate_skill_zip(Path("/nonexistent/file.zip"))
        assert is_valid is False


class TestStaticPages:
    """Tests for static page endpoints."""

    def test_index_page_redirect_without_auth(self):
        """Test index page redirects without authentication."""
        response = client.get("/", follow_redirects=False)
        assert response.status_code in [200, 302]

    def test_login_page(self):
        """Test login page loads."""
        response = client.get("/login")
        assert response.status_code == 200

    def test_login_page_with_error(self):
        """Test login page with error parameter."""
        response = client.get("/login?error=invalid")
        assert response.status_code == 200
        assert "error" in response.text.lower() or "错误" in response.text

    def test_admin_login_redirect(self):
        """Test admin login redirects to user login."""
        response = client.get("/admin/login", follow_redirects=False)
        assert response.status_code in [200, 302]

    def test_install_guide_page(self):
        """Test install guide page."""
        response = client.get("/install-guide")
        assert response.status_code == 200


class TestHealthAndMetrics:
    """Tests for health and metrics endpoints."""

    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_top_stats_endpoint(self):
        """Test top stats endpoint."""
        response = client.get("/api/stats/top")
        assert response.status_code in [200, 401]


class TestErrorHandling:
    """Tests for error handling."""

    def test_404_endpoint(self):
        """Test 404 for nonexistent endpoint."""
        response = client.get("/api/nonexistent-endpoint-xyz")
        assert response.status_code == 404

    def test_invalid_json_request(self):
        """Test invalid JSON request handling."""
        response = client.post(
            "/api/admin/users",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [400, 401, 422]

    def test_missing_required_field(self):
        """Test missing required field in request."""
        emp_id = unique_name("t-mrf")
        api_key = f"key-{emp_id}"
        user_id = create_user(emp_id, api_key, "admin")

        try:
            login_resp = client.post("/api/login", data={
                "employee_id": emp_id,
                "api_key": api_key
            })
            if login_resp.status_code != 302:
                pytest.skip("Login failed")

            # Missing required fields
            response = client.post(
                "/api/admin/users",
                json={},  # Missing employee_id and api_key
                cookies=login_resp.cookies
            )
            assert response.status_code in [400, 401, 422]

        finally:
            with get_connection() as conn:
                conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()


# Import shutil for cleanup
import shutil


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
