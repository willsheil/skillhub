"""
Tests for main.py helper functions and utilities.
"""

import pytest
import sys
import os
import io
import zipfile
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from main import (
    parse_plugin_filename,
    get_skill_dir_name,
    extract_metadata_from_skill_md,
    validate_skill_zip,
    extract_metadata,
    validate_skill_name
)
from database import get_connection
from conftest import create_test_user, create_test_skill_zip, cleanup_test_data
import main


def unique_id():
    return uuid.uuid4().hex[:6]


class TestParsePluginFilename:
    """测试解析插件文件名。"""

    def test_parse_simple_filename(self):
        """测试解析简单文件名。"""
        skill_name, version = parse_plugin_filename("my-skill.zip")
        assert skill_name == "my-skill"
        assert version == "unknown"

    def test_parse_complex_filename(self):
        """测试解析复杂文件名。"""
        skill_name, version = parse_plugin_filename("ask-questions-if-underspecified.zip")
        assert skill_name == "ask-questions-if-underspecified"
        assert version == "unknown"

    def test_parse_without_extension(self):
        """测试解析无扩展名文件名。"""
        skill_name, version = parse_plugin_filename("my-skill")
        assert skill_name == "my-skill"
        assert version == "unknown"


class TestGetSkillDirName:
    """测试获取技能目录名。"""

    def test_simple_zip_name(self):
        """测试简单ZIP名称。"""
        result = get_skill_dir_name("my-skill.zip")
        assert result == "my-skill"

    def test_versioned_zip_name(self):
        """测试带版本号的ZIP名称。"""
        result = get_skill_dir_name("my-skill-1.0.0.zip")
        # Should extract skill name
        assert "my-skill" in result or "skill" in result

    def test_complex_name(self):
        """测试复杂名称。"""
        result = get_skill_dir_name("ask-questions-if-underspecified.zip")
        assert "ask" in result


class TestExtractMetadataFromSkillMd:
    """测试从SKILL.md提取元数据。"""

    def test_extract_valid_metadata(self):
        """测试提取有效元数据。"""
        skill_md_content = """---
name: test-skill
description: A test skill
metadata:
  version: 1.0.0
  author: w00000001
  tags: test, demo
license: MIT
---
# Skill Content
"""
        metadata = extract_metadata_from_skill_md(skill_md_content)
        assert metadata is not None
        assert metadata.get("name") == "test-skill"
        assert metadata.get("description") == "A test skill"
        assert metadata.get("metadata", {}).get("version") == "1.0.0"

    def test_extract_invalid_yaml(self):
        """测试无效YAML。"""
        skill_md_content = """---
invalid: yaml: content:
---
"""
        metadata = extract_metadata_from_skill_md(skill_md_content)
        assert metadata is None or "error" in str(metadata)

    def test_extract_missing_frontmatter(self):
        """测试缺少frontmatter。"""
        skill_md_content = "# Just a heading\nNo frontmatter here"
        metadata = extract_metadata_from_skill_md(skill_md_content)
        # Should return None or empty dict
        assert metadata is None or metadata == {}


class TestExtractMetadata:
    """测试从文件名提取元数据。"""

    def test_extract_metadata_from_filename(self):
        """测试从文件名提取元数据。"""
        metadata = extract_metadata("test-skill.zip")
        assert metadata is not None
        assert metadata.get("name") == "test-skill"


class TestValidateSkillName:
    """测试技能名称验证。"""

    def test_valid_skill_name(self):
        """测试有效技能名称。"""
        is_valid, error = validate_skill_name("my-skill-123")
        assert is_valid is True

    def test_invalid_skill_name_uppercase(self):
        """测试无效技能名称（大写）。"""
        is_valid, error = validate_skill_name("My-Skill")
        assert is_valid is False

    def test_invalid_skill_name_spaces(self):
        """测试无效技能名称（空格）。"""
        is_valid, error = validate_skill_name("my skill")
        assert is_valid is False

    def test_invalid_skill_name_special_chars(self):
        """测试无效技能名称（特殊字符）。"""
        is_valid, error = validate_skill_name("my@skill!")
        assert is_valid is False

    def test_skill_name_too_long(self):
        """测试过长的技能名称。"""
        long_name = "a" * 65
        is_valid, error = validate_skill_name(long_name)
        assert is_valid is False


class TestValidateSkillZip:
    """测试验证技能ZIP。"""

    def test_validate_valid_zip(self):
        """测试验证有效ZIP。"""
        skill_name = f"vs-{unique_id()}"
        zip_content = create_test_skill_zip(skill_name, "1.0.0", "w00000001")

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(zip_content)
            temp_path = Path(f.name)

        try:
            is_valid, result = validate_skill_zip(temp_path)
            assert is_valid is True
            assert result.get("name") == skill_name
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_validate_invalid_zip(self):
        """测试验证无效ZIP。"""
        # Create invalid ZIP content
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(b"not a valid zip file")
            temp_path = Path(f.name)

        try:
            is_valid, result = validate_skill_zip(temp_path)
            assert is_valid is False
            assert "error" in result
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_validate_zip_missing_skill_md(self):
        """测试缺少SKILL.md的ZIP。"""
        # Create ZIP without SKILL.md
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('readme.txt', 'No skill md here')

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(output.getvalue())
            temp_path = Path(f.name)

        try:
            is_valid, result = validate_skill_zip(temp_path)
            assert is_valid is False
            assert "SKILL.md" in result.get("error", "")
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_validate_with_allow_missing(self):
        """测试allow_missing参数。"""
        skill_name = f"vam-{unique_id()}"
        zip_content = create_test_skill_zip(skill_name, "1.0.0", "w00000001")

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(zip_content)
            temp_path = Path(f.name)

        try:
            is_valid, result = validate_skill_zip(temp_path, allow_missing=True)
            # Should still be valid with complete metadata
            assert is_valid is True or result.get("error") == "MISSING_FIELDS"
        finally:
            if temp_path.exists():
                temp_path.unlink()


class TestLegacyPackageJsonFormat:
    """测试遗留package.json格式兼容性。"""

    def test_legacy_package_json_format(self):
        """测试遗留package.json格式。"""
        # Create ZIP with package.json instead of SKILL.md
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
            package_json = {
                "name": "legacy-skill",
                "version": "1.0.0",
                "description": "A legacy skill",
                "author": {"name": "w00000001"}
            }
            import json
            zf.writestr('package.json', json.dumps(package_json))

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(output.getvalue())
            temp_path = Path(f.name)

        try:
            is_valid, result = validate_skill_zip(temp_path)
            # Should fail because SKILL.md is required
            assert is_valid is False
            assert "SKILL.md" in result.get("error", "")
        finally:
            if temp_path.exists():
                temp_path.unlink()
