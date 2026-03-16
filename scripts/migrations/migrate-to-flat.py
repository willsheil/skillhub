#!/usr/bin/env python3
"""
Migrate existing plugins from three-level to two-level structure.
Moves plugins from: plugins/{org}/{collection}/{skill}/
                  to: plugins/{collection}/{skill}/
"""

import shutil
from pathlib import Path
import logging
import os

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

PLUGINS_DIR = Path("plugins")


def migrate_plugins():
    """Migrate all plugins to flat structure."""
    migrated = 0
    skipped = 0
    errors = 0
    organizations = []

    logger.info("Scanning for plugins to migrate...")

    # Walk through old structure
    for org_dir in PLUGINS_DIR.iterdir():
        if not org_dir.is_dir():
            continue

        # Skip temp directories
        if org_dir.name.startswith('.') or org_dir.name.startswith('_'):
            continue

        organization = org_dir.name
        organizations.append(organization)
        logger.info(f"Processing organization", extra={"organization": organization})

        for collection_dir in org_dir.iterdir():
            if not collection_dir.is_dir():
                continue

            collection = collection_dir.name

            for plugin_dir in collection_dir.iterdir():
                if not plugin_dir.is_dir():
                    continue

                plugin_name = plugin_dir.name

                # New location (flat structure)
                target_dir = PLUGINS_DIR / collection / plugin_name

                if target_dir.exists():
                    logger.debug(f"Plugin already exists, skipping", extra={
                        "source": f"{organization}/{collection}/{plugin_name}",
                        "target": f"{collection}/{plugin_name}"
                    })
                    skipped += 1
                    continue

                # Move the entire plugin directory
                logger.info(f"Moving plugin...", extra={
                    "source": f"{organization}/{collection}/{plugin_name}",
                    "target": f"{collection}/{plugin_name}"
                })
                try:
                    target_dir.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(plugin_dir), str(target_dir))
                    migrated += 1
                except Exception as e:
                    logger.error(f"Failed to move plugin", extra={
                        "plugin_name": plugin_name,
                        "error": str(e)
                    })
                    errors += 1

            # Try to remove empty collection directory
            try:
                if collection_dir.exists() and not any(collection_dir.iterdir()):
                    collection_dir.rmdir()
            except:
                pass

        # Try to remove empty organization directory
        try:
            if org_dir.exists() and not any(org_dir.iterdir()):
                org_dir.rmdir()
        except:
            pass

    logger.info(f"Migration complete", extra={
        "migrated": migrated,
        "skipped": skipped,
        "errors": errors,
        "organizations": organizations
    })

    # 记录审计日志
    audit_log(
        logger,
        action="config_change",
        user_id="system",
        change_type="plugin_structure_migration",
        migrated=migrated,
        skipped=skipped,
        errors=errors,
        result="success" if errors == 0 else "partial"
    )


if __name__ == "__main__":
    migrate_plugins()
