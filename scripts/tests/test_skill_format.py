#!/usr/bin/env python3
"""
Test script for SKILL.md format support per Agent Skills specification.
Creates a test skill ZIP and validates it.
"""

import io
import tempfile
import zipfile
from pathlib import Path
import logging
import os
import sys

# 导入日志配置
from logging_config import setup_logging

# 初始化日志系统
setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_dir="./logs",
    enable_json=True,
    enable_console=True
)

# 获取logger
logger = logging.getLogger(__name__)

import yaml

# Import functions from main.py
sys.path.insert(0, str(Path(__file__).parent))

from main import validate_skill_zip, parse_skill_md, validate_skill_name, extract_metadata


def create_test_skill_zip(skill_name: str, author: str, version: str = "1.0.0") -> Path:
    """Create a test skill ZIP with SKILL.md format per Agent Skills spec."""

    # Create SKILL.md content per spec
    yaml_data = {
        'name': skill_name,
        'description': f'This is a test skill: {skill_name}. Use this skill for testing purposes.',
        'license': 'Apache-2.0',
        'metadata': {
            'author': author,
            'version': version,
            'category': 'test'
        }
    }

    yaml_content = yaml.dump(yaml_data, allow_unicode=True, sort_keys=False, default_flow_style=False)

    skill_md_content = f"""---
{yaml_content}---

# {skill_name}

This is a test skill for validating the SKILL.md format per Agent Skills specification.

## When to Use

Use this skill when testing the registry functionality.

## Instructions

1. Test the validation logic
2. Test the metadata extraction
3. Test the API responses

## References

- [Agent Skills Specification](https://agentskills.io/specification)
"""

    # Create ZIP in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add SKILL.md at root level
        zf.writestr(f'{skill_name}/SKILL.md', skill_md_content)
        # Add a dummy script
        zf.writestr(f'{skill_name}/scripts/test.py', '# Test script\nprint("Hello")\n')

    # Save to temp file
    temp_dir = tempfile.mkdtemp()
    zip_path = Path(temp_dir) / f"{skill_name}-{version}.zip"

    with open(zip_path, 'wb') as f:
        f.write(zip_buffer.getvalue())

    logger.debug(f"Created test skill ZIP", extra={"skill_name": skill_name, "version": version})
    return zip_path


def test_name_validation():
    """Test skill name validation per spec."""
    logger.info("Testing skill name validation...")

    # Valid names
    valid_names = ['test-skill', 'my-awesome-skill', 'skill123', 'a']
    for name in valid_names:
        result = validate_skill_name(name)
        if result:
            logger.info(f"Valid name test passed", extra={"name": name})
        else:
            logger.error(f"Valid name test failed", extra={"name": name})

    # Invalid names
    invalid_names = ['Test_Skill', 'skill name', 'skill--name', '-skill', 'skill-', 'A'*65]
    for name in invalid_names:
        result = validate_skill_name(name)
        if not result:
            logger.info(f"Invalid name test passed", extra={"name": name})
        else:
            logger.error(f"Invalid name test failed", extra={"name": name})


def test_metadata_extraction():
    """Test metadata extraction from SKILL.md."""
    logger.info("Testing metadata extraction...")

    skill_name = "test-skill"
    author = "Test Author"
    version = "1.0.0"

    zip_path = create_test_skill_zip(skill_name, author, version)

    try:
        metadata = extract_metadata(zip_path)
        logger.info("Metadata extraction successful", extra={
            "name": metadata.get('name'),
            "author": metadata.get('metadata', {}).get('author'),
            "version": metadata.get('metadata', {}).get('version')
        })
    except Exception as e:
        logger.error(f"Metadata extraction failed: {e}", exc_info=True)


def main():
    """Run all tests."""
    logger.info("="*60)
    logger.info("SKILL.md Format Tests")
    logger.info("="*60)

    test_name_validation()
    test_metadata_extraction()

    logger.info("All tests completed!")


if __name__ == "__main__":
    main()
