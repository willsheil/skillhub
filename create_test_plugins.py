#!/usr/bin/env python3
"""Create test plugins for batch download testing"""
import zipfile
from pathlib import Path
import json

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

    print(f"[OK] Created: {plugin['collection']}/{plugin['name']}@{plugin['version']}")

print(f"\n[OK] Created {len(test_plugins)} test plugins")
print("\nYou can now test batch download at http://localhost:28000")
