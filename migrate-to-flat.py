#!/usr/bin/env python3
"""
Migrate existing plugins from three-level to two-level structure.
Moves plugins from: plugins/{org}/{collection}/{skill}/
                  to: plugins/{collection}/{skill}/
"""

import shutil
from pathlib import Path

PLUGINS_DIR = Path("plugins")


def migrate_plugins():
    """Migrate all plugins to flat structure."""
    migrated = 0
    skipped = 0
    errors = 0

    print("Scanning for plugins to migrate...\n")

    # Walk through old structure
    for org_dir in PLUGINS_DIR.iterdir():
        if not org_dir.is_dir():
            continue

        # Skip temp directories
        if org_dir.name.startswith('.') or org_dir.name.startswith('_'):
            continue

        organization = org_dir.name
        print(f"[ORG] {organization}")

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
                    print(f"  [SKIP] {organization}/{collection}/{plugin_name} -> {collection}/{plugin_name} (target exists)")
                    skipped += 1
                    continue

                # Move the entire plugin directory
                print(f"  [MOVE] {organization}/{collection}/{plugin_name} -> {collection}/{plugin_name}")
                try:
                    target_dir.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(plugin_dir), str(target_dir))
                    migrated += 1
                except Exception as e:
                    print(f"  [ERROR] Failed to move {plugin_name}: {e}")
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

    print(f"\n{'='*50}")
    print(f"Migration complete:")
    print(f"  Moved:   {migrated}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors:  {errors}")
    print(f"\nNew structure: plugins/{{collection}}/{{skill}}/{{version}}.zip")


if __name__ == "__main__":
    print("=" * 50)
    print("Plugin Structure Migration Tool")
    print("Migrating: org/collection/skill -> collection/skill")
    print("=" * 50)
    print()

    if not PLUGINS_DIR.exists():
        print(f"Error: {PLUGINS_DIR} not found")
        exit(1)

    response = input("This will move all plugins to the new structure. Continue? (y/N): ")
    if response.lower() != 'y':
        print("Aborted.")
        exit(0)

    migrate_plugins()
