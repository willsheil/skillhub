#!/usr/bin/env python3
"""
Migrate existing plugins to three-level organization structure.
Moves plugins/{skill}/{version}.zip -> plugins/{org}/{collection}/{skill}/{version}.zip
"""

import shutil
import argparse
from pathlib import Path

PLUGINS_DIR = Path("./plugins")


def migrate_plugins(target_org: str = "default", target_collection: str = "default"):
    """Migrate legacy plugins to target organization and collection."""
    migrated = 0
    skipped = 0

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
                print(f"  ⚠️  {item.name} already exists, skipping")
                skipped += 1
                continue

            print(f"  📦 Migrating {item.name} -> {target_org}/{target_collection}/{item.name}")
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item), str(target_dir))
            migrated += 1
        else:
            print(f"  ⏭️  Skipping {item.name} (no plugins found or already migrated)")
            skipped += 1

    print(f"\n✅ Migrated {migrated} plugins to {target_org}/{target_collection}/")
    print(f"   Skipped: {skipped}")
    print(f"\nNew structure:")
    print(f"  plugins/{{organization}}/{{collection}}/{{skill-name}}/{{version}}.zip")
    print(f"\nYou can later reorganize skills into different collections using:")
    print(f"  mv plugins/default/default/my-skill plugins/default/my-collection/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate plugins to three-level structure")
    parser.add_argument("-o", "--org", default="default",
                       help="Target organization (default: default)")
    parser.add_argument("-c", "--collection", default="default",
                       help="Target collection (default: default)")

    args = parser.parse_args()
    migrate_plugins(args.org, args.collection)
