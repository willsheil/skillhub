#!/usr/bin/env python3
"""
Import skills from skills-marketplace.zip into Registry
"""

import json
import shutil
import zipfile
from pathlib import Path
import sys


def extract_and_repackage(skills_zip: Path, output_dir: Path, organization: str = "default", collection: str = "default"):
    """Extract skills from marketplace zip and repackage as individual plugin zips.

    Args:
        skills_zip: Path to the skills marketplace zip file
        output_dir: Base output directory for plugins
        organization: Organization name (default: "default")
        collection: Skill collection name (default: "default")
    """


    output_dir.mkdir(exist_ok=True)
    temp_dir = Path("temp_extract")

    print(f"Extracting {skills_zip}...")
    with zipfile.ZipFile(skills_zip, 'r') as zf:
        zf.extractall(temp_dir)

    skills_path = temp_dir / "skills" / "plugins"
    if not skills_path.exists():
        print("Error: Invalid skills structure")
        return

    imported = 0

    for plugin_dir in skills_path.iterdir():
        if not plugin_dir.is_dir():
            continue

        plugin_name = plugin_dir.name
        target_dir = output_dir / organization / collection / plugin_name
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
            print(f"  ⚠️  {plugin_name}@{version} already exists, skipping")
            continue

        # Create zip
        print(f"  📦 Packaging {plugin_name}@{version}...")
        with zipfile.ZipFile(target_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in plugin_dir.rglob("*"):
                if file_path.is_file():
                    arcname = str(file_path.relative_to(plugin_dir))
                    zf.write(file_path, arcname)

        imported += 1

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)

    print(f"\n✅ Imported {imported} plugins to {output_dir}/{organization}/{collection}")
    print(f"\nOrganization: {organization}")
    print(f"Collection: {collection}")
    print(f"\nNext steps:")
    print(f"  1. Start registry: docker-compose up -d")
    print(f"  2. Visit: http://localhost:8000")
    print(f"  3. Add to Claude Code: /plugins marketplace add http://localhost:8000/marketplace.json")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import skills from marketplace zip")
    parser.add_argument("zip_file", nargs="?", default="skills-marketplace.zip",
                       help="Path to skills marketplace zip file")
    parser.add_argument("-o", "--org", default="default",
                       help="Organization name (default: default)")
    parser.add_argument("-c", "--collection", default="default",
                       help="Skill collection name (default: default)")
    parser.add_argument("-d", "--output", default="plugins",
                       help="Output directory (default: plugins)")

    args = parser.parse_args()

    zip_file = Path(args.zip_file)

    if not zip_file.exists():
        print(f"Error: {zip_file} not found")
        sys.exit(1)

    extract_and_repackage(zip_file, Path(args.output), args.org, args.collection)
