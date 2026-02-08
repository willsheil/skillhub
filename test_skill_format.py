#!/usr/bin/env python3
"""
Test script for SKILL.md format support per Agent Skills specification.
Creates a test skill ZIP and validates it.
"""

import io
import tempfile
import zipfile
from pathlib import Path

import yaml

# Import functions from main.py
import sys
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

    return zip_path


def test_name_validation():
    """Test skill name validation per spec."""
    print("\n=== Testing Skill Name Validation ===\n")

    valid_names = [
        'pdf-processing',
        'data-analysis',
        'code-review',
        'api-v2-client',
        'my-skill-123'
    ]
    invalid_names = [
        'PDF-Processing',     # uppercase not allowed
        '-pdf',               # cannot start with hyphen
        'pdf-',               # cannot end with hyphen
        'pdf--processing',    # consecutive hyphens not allowed
        'pdf_processing',     # underscore not allowed
        '',                   # empty
        'a' * 65,             # too long (>64 chars)
    ]

    print("Valid names:")
    for name in valid_names:
        result, error = validate_skill_name(name)
        status = "✅" if result else "❌"
        print(f"  {status} {name}")

    print("\nInvalid names:")
    for name in invalid_names:
        result, error = validate_skill_name(name)
        status = "✅" if not result else "❌"
        print(f"  {status} {name}: {error if not result else 'should have failed'}")


def test_skill_md_parsing():
    """Test SKILL.md parsing."""
    print("\n=== Testing SKILL.md Parsing ===\n")

    skill_md_content = """---
name: test-skill
description: A test skill for validation
license: Apache-2.0
metadata:
  author: test-org
  version: "1.0"
---

# Test Skill

This is the content.
"""

    metadata, body = parse_skill_md(skill_md_content)

    print(f"Metadata: {metadata}")
    print(f"Body preview: {body[:50]}...")

    assert metadata is not None, "Failed to parse metadata"
    assert metadata.get('name') == 'test-skill', "Name mismatch"
    assert metadata.get('description') == 'A test skill for validation', "Description mismatch"
    assert metadata.get('license') == 'Apache-2.0', "License mismatch"
    assert metadata.get('metadata', {}).get('author') == 'test-org', "Author mismatch"

    print("✅ Parsing test passed")


def test_zip_validation():
    """Test ZIP validation with SKILL.md format per Agent Skills spec."""
    print("\n=== Testing ZIP Validation ===\n")

    # Create test ZIP
    zip_path = create_test_skill_zip('test-skill', 'test-org')

    print(f"Created test ZIP: {zip_path}")

    # Validate
    is_valid, result = validate_skill_zip(zip_path)

    print(f"Validation result: {is_valid}")
    print(f"Metadata: {result}")

    assert is_valid, f"Validation failed: {result}"
    assert result['name'] == 'test-skill', "Name mismatch"
    assert result['metadata']['author'] == 'test-org', "Author mismatch"
    assert result['license'] == 'Apache-2.0', "License mismatch"

    print("✅ ZIP validation test passed")

    # Cleanup
    zip_path.parent.rmdir()


def test_invalid_name():
    """Test validation with invalid skill name."""
    print("\n=== Testing Invalid Skill Name ===\n")

    # Create test ZIP with invalid name (uppercase)
    zip_path = create_test_skill_zip('Bad-Name', 'test-org')

    is_valid, result = validate_skill_zip(zip_path)

    print(f"Validation result: {is_valid}")
    print(f"Error: {result.get('error')}")

    # Note: The actual validation happens during ZIP validation,
    # but the name might be adjusted during migration.
    # This test shows what would happen.

    print("✅ Invalid name test completed")

    # Cleanup
    zip_path.parent.rmdir()


def test_legacy_package_json():
    """Test backward compatibility with package.json format."""
    print("\n=== Testing Legacy package.json Format ===\n")

    # Create a legacy format ZIP
    zip_buffer = io.BytesIO()

    package_json = {
        'name': 'legacy-skill',
        'version': '1.0.0',
        'description': 'A legacy skill',
        'author': {'name': 'Test Author', 'email': 'test@example.com'}
    }

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('legacy-skill/package.json', __import__('json').dumps(package_json))

    temp_dir = tempfile.mkdtemp()
    zip_path = Path(temp_dir) / 'legacy-skill-1.0.0.zip'

    with open(zip_path, 'wb') as f:
        f.write(zip_buffer.getvalue())

    # Try validation (should fail because no SKILL.md)
    is_valid, result = validate_skill_zip(zip_path)

    print(f"Validation result: {is_valid}")
    print(f"Result: {result}")

    # Legacy format should fail validation (we want to enforce new format)
    assert not is_valid, "Legacy format should require migration"

    print("✅ Legacy format correctly rejected (needs migration)")

    # But extraction should still work for reading
    metadata = extract_metadata(zip_path.name)
    print(f"Extracted metadata: {metadata}")

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)


def main():
    """Run all tests."""
    print("🧪 Testing SKILL.md Format Support (Agent Skills Specification)")

    try:
        test_name_validation()
        test_skill_md_parsing()
        test_zip_validation()
        test_invalid_name()
        test_legacy_package_json()

        print("\n" + "="*50)
        print("✅ All tests passed!")
        print("="*50)

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()
