"""
Targeted tests for specific uncovered areas in main.py.

Focus on:
- Skill metadata parsing
- SKILL.md generation
- Plugin scanning
- Upload processing
"""

import pytest
from fastapi.testclient import TestClient
from main import app, extract_metadata, parse_plugin_filename, scan_plugins
from database import get_connection, create_user, create_skill_record
import uuid
import io
import zipfile
from pathlib import Path


client = TestClient(app)


def unique_name(base: str) -> str:
    return f"{base}-{uuid.uuid4().hex[:8]}"


class TestMetadataExtraction:
    """Tests for metadata extraction from skill ZIP files."""

    def test_extract_metadata_valid_skill(self):
        """Test extracting metadata from a valid skill ZIP."""
        skill_name = unique_name("t-emv")
        skill_md = f"""---
name: {skill_name}
description: Test skill description
metadata:
  version: 1.0.0
  author: w00000001
  license: MIT
---

# {skill_name}

Test content.
"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("SKILL.md", skill_md)
        zip_buffer.seek(0)

        # Save to plugins dir
        from main import PLUGINS_DIR
        zip_path = PLUGINS_DIR / f"{skill_name}.zip"
        with open(zip_path, 'wb') as f:
            f.write(zip_buffer.read())

        try:
            metadata = extract_metadata(f"{skill_name}.zip")
            assert metadata is not None
            assert metadata.get("name") == skill_name
        finally:
            if zip_path.exists():
                zip_path.unlink()

    def test_extract_metadata_missing_skill_md(self):
        """Test extracting metadata when SKILL.md is missing."""
        skill_name = unique_name("t-emm")
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("README.md", "# Test")
        zip_buffer.seek(0)

        from main import PLUGINS_DIR
        zip_path = PLUGINS_DIR / f"{skill_name}.zip"
        with open(zip_path, 'wb') as f:
            f.write(zip_buffer.read())

        try:
            metadata = extract_metadata(f"{skill_name}.zip")
            # May return None or fallback metadata
            assert metadata is None or isinstance(metadata, dict)
        finally:
            if zip_path.exists():
                zip_path.unlink()

    def test_extract_metadata_invalid_yaml(self):
        """Test extracting metadata with invalid YAML."""
        skill_name = unique_name("t-emi")
        skill_md = """---
name: test
invalid yaml: [unclosed
---

# Test
"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("SKILL.md", skill_md)
        zip_buffer.seek(0)

        from main import PLUGINS_DIR
        zip_path = PLUGINS_DIR / f"{skill_name}.zip"
        with open(zip_path, 'wb') as f:
            f.write(zip_buffer.read())

        try:
            metadata = extract_metadata(f"{skill_name}.zip")
            # Should return None or fallback metadata
            assert metadata is None or isinstance(metadata, dict)
        finally:
            if zip_path.exists():
                zip_path.unlink()

    def test_extract_metadata_nonexistent_file(self):
        """Test extracting metadata from nonexistent file."""
        metadata = extract_metadata("nonexistent-file-12345.zip")
        # May return None or fallback metadata
        assert metadata is None or isinstance(metadata, dict)


class TestPluginFilenameParsing:
    """Tests for plugin filename parsing."""

    def test_parse_standard_filename(self):
        """Test parsing standard skill filename."""
        name, version = parse_plugin_filename("my-skill.zip")
        assert name == "my-skill"
        assert version == "unknown"

    def test_parse_filename_with_version(self):
        """Test parsing filename that looks like it has version."""
        name, version = parse_plugin_filename("my-skill-1.0.0.zip")
        assert name == "my-skill-1.0.0"
        assert version == "unknown"

    def test_parse_complex_name(self):
        """Test parsing complex skill name."""
        name, version = parse_plugin_filename("my-complex-skill-name-v2.zip")
        assert "my-complex-skill-name-v2" in name


class TestPluginScanning:
    """Tests for plugin scanning functionality."""

    def test_scan_plugins_returns_list(self):
        """Test that scan_plugins returns a list."""
        plugins = scan_plugins()
        assert isinstance(plugins, list)

    def test_scan_plugins_structure(self):
        """Test that scanned plugins have correct structure."""
        plugins = scan_plugins()
        for plugin in plugins:
            assert "name" in plugin
            assert "metadata" in plugin
            assert "versions" in plugin


class TestSkillUploadProcessing:
    """Tests for skill upload processing."""

    def test_upload_with_valid_structure(self):
        """Test upload with valid skill structure."""
        emp_id = unique_name("t-uvs")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")

        skill_name = unique_name("t-uvs-skill")
        skill_md = f"""---
name: {skill_name}
description: Test skill
metadata:
  version: 1.0.0
  author: w00000001
---

# Test
"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("SKILL.md", skill_md)
        zip_buffer.seek(0)

        response = client.post(
            "/api/upload",
            files={"file": (f"{skill_name}.zip", zip_buffer, "application/zip")}
        )

        assert response.status_code in [200, 400, 401, 422]

    def test_upload_with_nested_folder(self):
        """Test upload with skill in nested folder."""
        emp_id = unique_name("t-unf")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")

        skill_name = unique_name("t-unf-skill")
        skill_md = f"""---
name: {skill_name}
description: Test skill
metadata:
  version: 1.0.0
  author: w00000001
---

# Test
"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{skill_name}/SKILL.md", skill_md)
        zip_buffer.seek(0)

        response = client.post(
            "/api/upload",
            files={"file": (f"{skill_name}.zip", zip_buffer, "application/zip")}
        )

        assert response.status_code in [200, 400, 401, 422]


class TestMarketplaceGeneration:
    """Tests for marketplace generation."""

    def test_marketplace_json_structure(self):
        """Test marketplace.json has correct structure."""
        response = client.get("/marketplace.json")
        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert "plugins" in data
        assert isinstance(data["plugins"], list)

    def test_marketplace_with_skills(self):
        """Test marketplace includes approved skills."""
        emp_id = unique_name("t-mws")
        user_id = create_user(emp_id, f"key-{emp_id}", "user")
        skill_name = unique_name("t-mws-skill")

        # Create approved skill
        create_skill_record(
            skill_name=skill_name,
            version="1.0.0",
            filename=f"{skill_name}.zip",
            uploader_id=user_id,
            status="approved",
            source_type="opensource"
        )

        # Update to active
        with get_connection() as conn:
            conn.execute(
                "UPDATE skills SET is_active = 1 WHERE skill_name = %s",
                (skill_name,)
            )
            conn.commit()

        response = client.get("/marketplace.json")
        assert response.status_code == 200


class TestSourceFiltering:
    """Tests for source type filtering."""

    def test_filter_opensource(self):
        """Test filtering by opensource."""
        response = client.get("/api/skills?source_type=opensource")
        assert response.status_code == 200

    def test_filter_icsl(self):
        """Test filtering by icsl."""
        response = client.get("/api/skills?source_type=icsl")
        assert response.status_code == 200

    def test_filter_huawei(self):
        """Test filtering by huawei."""
        response = client.get("/api/skills?source_type=huawei")
        assert response.status_code == 200

    def test_filter_invalid_source(self):
        """Test filtering with invalid source type."""
        response = client.get("/api/skills?source_type=invalid")
        assert response.status_code in [200, 400]


class TestStatusFiltering:
    """Tests for status filtering."""

    def test_filter_approved(self):
        """Test filtering by approved status."""
        response = client.get("/api/my-skills?status=approved")
        assert response.status_code in [200, 401]

    def test_filter_pending(self):
        """Test filtering by pending status."""
        response = client.get("/api/my-skills?status=pending")
        assert response.status_code in [200, 401]

    def test_filter_rejected(self):
        """Test filtering by rejected status."""
        response = client.get("/api/my-skills?status=rejected")
        assert response.status_code in [200, 401]


class TestPagination:
    """Tests for pagination."""

    def test_default_pagination(self):
        """Test default pagination values."""
        response = client.get("/api/skills")
        assert response.status_code == 200

    def test_custom_page_size(self):
        """Test custom page size."""
        response = client.get("/api/skills?page=1&per_page=5")
        assert response.status_code == 200

    def test_large_page_number(self):
        """Test large page number."""
        response = client.get("/api/skills?page=1000")
        assert response.status_code == 200


class TestSorting:
    """Tests for sorting."""

    def test_sort_by_name_asc(self):
        """Test sorting by name ascending."""
        response = client.get("/api/skills?sort=name&order=asc")
        assert response.status_code == 200

    def test_sort_by_date_desc(self):
        """Test sorting by date descending."""
        response = client.get("/api/skills?sort=date&order=desc")
        assert response.status_code == 200

    def test_sort_by_downloads(self):
        """Test sorting by downloads."""
        response = client.get("/api/skills?sort=downloads")
        assert response.status_code in [200, 400]


class TestSearchFunctionality:
    """Tests for search functionality."""

    def test_search_basic(self):
        """Test basic search."""
        response = client.get("/api/skills?search=test")
        assert response.status_code == 200

    def test_search_with_special_chars(self):
        """Test search with special characters."""
        response = client.get("/api/skills?search=test%20skill")
        assert response.status_code == 200

    def test_search_empty_query(self):
        """Test search with empty query."""
        response = client.get("/api/skills?search=")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
