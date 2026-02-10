#!/usr/bin/env python3
"""
Migrate existing plugins from package.json format to SKILL.md format.

This script:
1. Extracts existing ZIP files
2. Reads package.json
3. Generates SKILL.md with YAML frontmatter (per Agent Skills spec)
4. Repackages the ZIP with SKILL.md instead of package.json
"""

import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional
import logging

# 导入日志配置
from logging_config import setup_logging, audit_log

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

PLUGINS_DIR = Path("./plugins")


def parse_name_from_legacy(name: str) -> str:
    """Extract valid skill name from legacy name.

    Agent Skills spec requires:
    - lowercase letters, numbers, hyphens only
    - no consecutive hyphens
    - cannot start or end with hyphen
    """
    if not name:
        return "migrated-skill"

    # Convert to lowercase
    name = name.lower()

    # Replace invalid characters with hyphens
    name = re.sub(r'[^a-z0-9-]', '-', name)

    # Remove consecutive hyphens
    while '--' in name:
        name = name.replace('--', '-')

    # Remove leading/trailing hyphens
    name = name.strip('-')

    # Ensure not empty and max 64 chars
    if not name:
        name = "migrated-skill"
    name = name[:64]

    return name


def parse_author_from_legacy(author: dict or str) -> str:
    """Extract author from legacy format for metadata field.

    Legacy format: {"name": "Author Name", "email": "email@example.com"}
    Agent Skills format: arbitrary string (stored in metadata.author)
    """
    if isinstance(author, str):
        return author

    if isinstance(author, dict):
        name = author.get('name', '')
        email = author.get('email', '')
        if name and email:
            return f"{name} ({email})"
        return name or email or "Unknown"

    return "Unknown"


def generate_skill_md(metadata: dict) -> str:
    """Generate SKILL.md content from metadata per Agent Skills spec.

    Args:
        metadata: Legacy metadata from package.json

    Returns:
        SKILL.md content with YAML frontmatter
    """
    name = parse_name_from_legacy(metadata.get('name', 'unknown-skill'))
    description = metadata.get('description', 'No description available')
    version = metadata.get('version', '1.0.0')

    # Extract author
    legacy_author = metadata.get('author', {})
    author = parse_author_from_legacy(legacy_author)

    # Build YAML frontmatter per Agent Skills spec
    yaml_data = {
        'name': name,
        'description': description,
        'license': 'Unknown',
        'metadata': {
            'author': author,
            'version': version,
            'migrated_from_package_json': True
        }
    }

    # Generate YAML string
    yaml_content = yaml.dump(yaml_data, allow_unicode=True, sort_keys=False, default_flow_style=False)

    # Build full SKILL.md content
    skill_md = f"""---
{yaml_content}---

# {name}

{description}

## 使用说明

此技能由 package.json 格式迁移至 SKILL.md 格式。

## 元数据

- **名称**: {name}
- **版本**: {version}
- **作者**: {author}
- **许可证**: Unknown（迁移前未指定）

## 迁移说明

此技能已按照 [Agent Skills Specification](https://agentskills.io/specification) 进行格式迁移。
"""

    return skill_md


def migrate_skill_zip(zip_path: Path) -> bool:
    """Migrate a single skill ZIP from package.json to SKILL.md format.

    Args:
        zip_path: Path to the skill ZIP file

    Returns:
        True if migration was successful
    """
    logger.info(f"Processing ZIP file", extra={"zip_file": zip_path.name})

    try:
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Extract ZIP
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(temp_path)

            # Find package.json
            package_json_paths = list(temp_path.rglob('package.json'))
            if not package_json_paths:
                logger.warning(f"No package.json found, skipping", extra={"zip_file": zip_path.name})
                return False

            package_json_path = package_json_paths[0]

            # Read package.json
            with open(package_json_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # Generate SKILL.md
            skill_md_content = generate_skill_md(metadata)

            # Determine where to place SKILL.md (same directory as package.json)
            skill_dir = package_json_path.parent
            skill_md_path = skill_dir / 'SKILL.md'

            # Write SKILL.md
            with open(skill_md_path, 'w', encoding='utf-8') as f:
                f.write(skill_md_content)

            # Remove package.json
            package_json_path.unlink()

            # Create new ZIP
            new_zip_path = zip_path.with_suffix('.zip.new')

            with zipfile.ZipFile(new_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file_path in temp_path.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(temp_path)
                        zf.write(file_path, arcname)

            # Replace original ZIP
            shutil.move(new_zip_path, zip_path)

            skill_name = metadata.get('name', 'unknown')
            author_info = metadata.get('author', {})
            logger.info(f"Successfully migrated skill", extra={
                "skill_name": skill_name,
                "author": str(author_info),
                "zip_file": zip_path.name
            })
            return True

    except Exception as e:
        logger.error(f"Migration failed", extra={"zip_file": zip_path.name, "error": str(e)})
        return False


def migrate_all_plugins():
    """Migrate all plugins in the plugins directory."""
    logger.info("Starting migration from package.json to SKILL.md format")

    migrated = 0
    failed = 0
    skipped = 0

    # Find all ZIP files
    zip_files = list(PLUGINS_DIR.glob('*.zip'))

    if not zip_files:
        logger.warning("No ZIP files found in plugins directory")
        return

    logger.info(f"Found plugins to migrate", extra={"count": len(zip_files)})

    for zip_path in zip_files:
        # Check if already migrated (contains SKILL.md)
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                has_skill_md = any('SKILL.md' in name for name in zf.namelist())
                has_package_json = any('package.json' in name for name in zf.namelist())

                if has_skill_md and not has_package_json:
                    logger.debug(f"Already migrated, skipping", extra={"zip_file": zip_path.name})
                    skipped += 1
                    continue

                if not has_package_json:
                    logger.warning(f"No package.json found, skipping", extra={"zip_file": zip_path.name})
                    skipped += 1
                    continue

        except zipfile.BadZipFile:
            logger.error(f"Invalid ZIP file", extra={"zip_file": zip_path.name})
            failed += 1
            continue

        # Migrate
        if migrate_skill_zip(zip_path):
            migrated += 1
        else:
            failed += 1

    logger.info(f"Migration summary", extra={
        "migrated": migrated,
        "skipped": skipped,
        "failed": failed
    })

    # 记录审计日志
    audit_log(
        logger,
        action="config_change",
        user_id="system",
        change_type="skill_format_migration",
        migrated=migrated,
        skipped=skipped,
        failed=failed,
        result="success" if failed == 0 else "partial"
    )


if __name__ == "__main__":
    migrate_all_plugins()
