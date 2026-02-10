#!/usr/bin/env python3
"""Create test plugins for batch download testing"""
import zipfile
from pathlib import Path
import json
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

PLUGINS_DIR = Path("plugins")

# Create test plugins
test_plugins = [
    {
        "collection": "default",
        "name": "test-skill-1",
        "version": "1.0.0",
        "description": "Test skill 1 for batch download"
    },
    {
        "collection": "default",
        "name": "test-skill-2",
        "version": "1.0.0",
        "description": "Test skill 2 for batch download"
    },
    {
        "collection": "tools",
        "name": "helper-skill",
        "version": "2.0.0",
        "description": "Helper skill in tools collection"
    }
]

created_plugins = []
for plugin in test_plugins:
    plugin_dir = PLUGINS_DIR / plugin["collection"] / plugin["name"]
    plugin_dir.mkdir(parents=True, exist_ok=True)

    # Create plugin.json
    plugin_json = {
        "name": plugin["name"],
        "version": plugin["version"],
        "description": plugin["description"],
        "author": {"name": "Test Author"}
    }

    # Create ZIP file
    zip_path = plugin_dir / f"{plugin['version']}.zip"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add plugin.json
        zf.writestr(".claude-plugin/plugin.json", json.dumps(plugin_json, indent=2))

        # Add a dummy skill file
        zf.writestr("skills/skill.md", f"# {plugin['name']}\n\n{plugin['description']}")

    logger.info(f"Created test plugin", extra={
        "collection": plugin['collection'],
        "name": plugin['name'],
        "version": plugin['version']
    })
    created_plugins.append(f"{plugin['collection']}/{plugin['name']}@{plugin['version']}")

logger.info(f"Created {len(test_plugins)} test plugins", extra={
    "total_count": len(test_plugins),
    "plugins": created_plugins
})
logger.info("You can now test batch download at http://localhost:28000")
