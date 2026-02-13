#!/usr/bin/env python3
"""
Migrate existing plugins to three-level organization structure.
Moves plugins/{skill}/{version}.zip -> plugins/{org}/{collection}/{skill}/{version}.zip
"""

import shutil
import argparse
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

PLUGINS_DIR = Path("./plugins")


def migrate_plugins(target_org: str = "default", target_collection: str = "default"):
    """Migrate legacy plugins to target organization and collection."""
    migrated = 0
    skipped = 0
    migrated_plugins = []

    for item in list(PLUGINS_DIR.iterdir()):
        if not item.is_dir():
            continue

        # 检测是否是旧结构
        has_zip_files = any(item.glob("*.zip"))
        has_subdirs_with_zips = any(
            subdir.is_dir() and any(subdir.glob("*.zip"))
            for subdir in item.iterdir()
        )

        if has_zip_files or has_subdirs_with_zips:
            # 这是旧结构，需要迁移
            target_dir = PLUGINS_DIR / target_org / target_collection / item.name

            if target_dir.exists():
                logger.debug(f"Plugin already exists, skipping", extra={
                    "plugin_name": item.name,
                    "target": f"{target_org}/{target_collection}/{item.name}"
                })
                skipped += 1
                continue

            logger.info(f"Migrating plugin...", extra={
                "source": item.name,
                "target": f"{target_org}/{target_collection}/{item.name}"
            })
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item), str(target_dir))
            migrated += 1
            migrated_plugins.append(item.name)
        else:
            logger.debug(f"Skipping plugin (no plugins found or already migrated)", extra={"plugin_name": item.name})
            skipped += 1

    logger.info(f"Migration completed", extra={
        "migrated": migrated,
        "skipped": skipped,
        "target_org": target_org,
        "target_collection": target_collection,
        "migrated_plugins": migrated_plugins
    })

    logger.info(f"New structure: plugins/{{organization}}/{{collection}}/{{skill-name}}/{{version}}.zip")

    # 记录审计日志
    audit_log(
        logger,
        action="config_change",
        user_id="system",
        change_type="plugin_structure_migration",
        target_org=target_org,
        target_collection=target_collection,
        migrated=migrated,
        skipped=skipped,
        result="success"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate plugins to three-level structure")
    parser.add_argument("-o", "--org", default="default",
                       help="Target organization (default: default)")
    parser.add_argument("-c", "--collection", default="default",
                       help="Target collection (default: default)")

    args = parser.parse_args()
    migrate_plugins(args.org, args.collection)
