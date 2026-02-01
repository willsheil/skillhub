#!/usr/bin/env python3
"""
Migrate existing plugins to organization structure.
Moves plugins/{skill}/{version}.zip -> plugins/default/{skill}/{version}.zip
"""

import shutil
from pathlib import Path

PLUGINS_DIR = Path("./plugins")


def migrate_plugins():
    """Migrate legacy plugins to default organization."""
    migrated = 0
    skipped = 0

    # 找到所有直接子目录（这些是需要迁移的Skill目录）
    for item in list(PLUGINS_DIR.iterdir()):
        if not item.is_dir():
            continue

        # 跳过已经是组织目录的结构
        # 判断依据：如果子目录下直接有zip文件，则是旧结构
        has_zip_files = any(item.glob("*.zip"))
        has_subdirs_with_zips = any(
            subdir.is_dir() and any(subdir.glob("*.zip"))
            for subdir in item.iterdir()
        )

        if has_zip_files or has_subdirs_with_zips:
            # 这是旧结构，需要迁移
            target_dir = PLUGINS_DIR / "default" / item.name

            if target_dir.exists():
                print(f"  ⚠️  {item.name} already exists in default/, skipping")
                skipped += 1
                continue

            print(f"  📦 Migrating {item.name} -> default/{item.name}")
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item), str(target_dir))
            migrated += 1
        else:
            # 可能是空目录或新结构
            print(f"  ⏭️  Skipping {item.name} (no plugins found)")
            skipped += 1

    print(f"\n✅ Migrated {migrated} plugins to default/ organization")
    print(f"   Skipped: {skipped}")
    print(f"\nNew structure:")
    print(f"  plugins/default/{{skill-name}}/{{version}}.zip")


if __name__ == "__main__":
    migrate_plugins()
