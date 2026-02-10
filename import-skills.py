#!/usr/bin/env python3
"""
Import skills from skills-marketplace.zip into Registry
"""

import json
import shutil
import zipfile
from pathlib import Path
import sys
import logging
import os

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


def extract_and_repackage(skills_zip: Path, output_dir: Path, collection: str = "default"):
    """Extract skills from marketplace zip and repackage as individual plugin zips.

    Args:
        skills_zip: Path to the skills marketplace zip file
        output_dir: Base output directory for plugins
        collection: Skill collection name (default: "default")
    """

    output_dir.mkdir(exist_ok=True)
    temp_dir = Path("temp_extract")

    logger.info(f"Extracting {skills_zip}...", extra={"zip_file": str(skills_zip)})
    with zipfile.ZipFile(skills_zip, 'r') as zf:
        zf.extractall(temp_dir)

    skills_path = temp_dir / "skills" / "plugins"
    if not skills_path.exists():
        logger.error("Invalid skills structure", extra={"skills_path": str(skills_path)})
        return

    imported = 0
    skipped = 0

    for plugin_dir in skills_path.iterdir():
        if not plugin_dir.is_dir():
            continue

        plugin_name = plugin_dir.name
        target_dir = output_dir / collection / plugin_name
        target_dir.mkdir(parents=True, exist_ok=True)

        # Read plugin.json for version
        plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
        version = "1.0.0"
        if plugin_json.exists():
            try:
                meta = json.loads(plugin_json.read_text())
                version = meta.get("version", "1.0.0")
            except:
                pass

        # Check if already exists
        target_zip = target_dir / f"{version}.zip"
        if target_zip.exists():
            logger.warning(f"Plugin already exists, skipping", extra={
                "plugin_name": plugin_name,
                "version": version
            })
            skipped += 1
            continue

        # Create zip
        logger.info(f"Packaging plugin...", extra={
            "plugin_name": plugin_name,
            "version": version
        })
        with zipfile.ZipFile(target_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in plugin_dir.rglob("*"):
                if file_path.is_file():
                    arcname = str(file_path.relative_to(plugin_dir))
                    zf.write(file_path, arcname)

        imported += 1

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)

    logger.info(f"Import completed", extra={
        "imported": imported,
        "skipped": skipped,
        "collection": collection,
        "output_dir": str(output_dir)
    })
    logger.info(f"Collection: {collection}")
    logger.info("Next steps: Start registry with 'docker-compose up -d', visit http://localhost:8000")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import skills from marketplace zip")
    parser.add_argument("zip_file", nargs="?", default="skills-marketplace.zip",
                       help="Path to skills marketplace zip file")
    parser.add_argument("-c", "--collection", default="default",
                       help="Skill collection name (default: default)")
    parser.add_argument("-d", "--output", default="plugins",
                       help="Output directory (default: plugins)")

    args = parser.parse_args()

    zip_file = Path(args.zip_file)

    if not zip_file.exists():
        logger.error(f"Zip file not found", extra={"zip_file": str(zip_file)})
        sys.exit(1)

    extract_and_repackage(zip_file, Path(args.output), args.collection)
