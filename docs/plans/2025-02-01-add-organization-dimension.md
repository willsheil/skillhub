# 添加组织维度支持 - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 改造 Skill Registry 以支持多组织隔离，将目录结构从 `plugins/{skill}/{version}.zip` 改为 `plugins/{org}/{skill}/{version}.zip`，同时保持向后兼容。

**Architecture:** 引入 organization 作为一级命名空间，修改扫描逻辑以支持嵌套目录结构。在 marketplace.json 和 API 中暴露组织信息。现有无组织插件归入默认组织 `default`。

**Tech Stack:** Python 3.11, FastAPI, pathlib

---

## Task 1: 修改 main.py - 更新目录扫描逻辑

**Files:**
- Modify: `main.py:38-71`

**Step 1: 理解当前扫描逻辑**

当前 `scan_plugins()` 函数遍历 `PLUGINS_DIR` 下的直接子目录作为 Skill 目录。
需要修改为：遍历组织目录 -> 遍历 Skill 目录 -> 遍历版本文件。

**Step 2: 修改 scan_plugins 函数**

```python
def scan_plugins() -> List[dict]:
    """Scan plugins directory and return metadata list.

    Directory structure: plugins/{organization}/{skill-name}/{version}.zip
    Legacy structure (no org): plugins/{skill-name}/{version}.zip -> treated as 'default' org
    """
    plugins = []

    for org_dir in PLUGINS_DIR.iterdir():
        if not org_dir.is_dir():
            continue

        organization = org_dir.name

        for plugin_dir in org_dir.iterdir():
            if not plugin_dir.is_dir():
                continue

            # Find all versions (zip files)
            versions = []
            for zip_file in sorted(plugin_dir.glob("*.zip")):
                version = zip_file.stem
                versions.append({
                    "version": version,
                    "filename": zip_file.name,
                    "size": zip_file.stat().st_size,
                    "updated_at": datetime.fromtimestamp(zip_file.stat().st_mtime).isoformat()
                })

            if not versions:
                continue

            # Get latest version metadata
            latest_zip = plugin_dir / versions[-1]["filename"]
            metadata = extract_metadata(organization, plugin_dir.name, latest_zip)

            plugins.append({
                "name": plugin_dir.name,
                "organization": organization,
                "metadata": metadata,
                "versions": versions,
                "latest_version": versions[-1]["version"]
            })

    return sorted(plugins, key=lambda x: (x["organization"], x["name"]))
```

**Step 3: 修改 extract_metadata 函数签名**

```python
def extract_metadata(organization: str, plugin_name: str, zip_path: Path) -> Optional[dict]:
    """Extract metadata from plugin.json inside zip."""
    import zipfile

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Try to find plugin.json
            for name in zf.namelist():
                if name.endswith('.claude-plugin/plugin.json'):
                    content = zf.read(name)
                    data = json.loads(content)
                    # Inject organization into metadata
                    data['organization'] = organization
                    return data
    except Exception:
        pass

    # Fallback: return basic info
    return {
        "name": plugin_name,
        "organization": organization,
        "version": "unknown",
        "description": "No description available",
        "author": {"name": "Unknown"}
    }
```

**Step 4: 更新 marketplace_json 函数**

```python
@app.get("/marketplace.json")
async def marketplace_json():
    """Claude Code marketplace index."""
    plugins = scan_plugins()

    marketplace = {
        "name": "private-registry",
        "owner": {
            "name": "Internal Registry",
            "email": "admin@company.local"
        },
        "metadata": {
            "version": "1.0.0",
            "description": "Internal Claude Code Skill Registry",
            "updated_at": datetime.now().isoformat()
        },
        "plugins": []
    }

    base_url = "/plugins"

    for plugin in plugins:
        meta = plugin["metadata"]
        latest = plugin["versions"][-1]
        org = plugin["organization"]
        name = plugin["name"]

        marketplace["plugins"].append({
            "name": meta.get("name", name),
            "organization": org,
            "version": latest["version"],
            "description": meta.get("description", "No description"),
            "author": meta.get("author", {"name": "Unknown"}),
            "source": f"{base_url}/{org}/{name}/{latest['filename']}"
        })

    return marketplace
```

**Step 5: 更新下载端点**

```python
@app.get("/plugins/{organization}/{plugin_name}/{filename}")
async def download_plugin(organization: str, plugin_name: str, filename: str):
    """Download plugin ZIP file."""
    file_path = PLUGINS_DIR / organization / plugin_name / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Plugin not found")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/zip"
    )
```

**Step 6: 更新上传端点**

```python
@app.post("/admin/upload")
async def upload_plugin(
    organization: str = Form("default"),  # 新增组织参数，默认 default
    name: str = Form(...),
    version: str = Form(...),
    file: UploadFile = File(...)
):
    """Upload a new plugin version."""
    # Validate file extension
    if not file.filename.endswith('.zip'):
        raise HTTPException(400, "Only ZIP files allowed")

    # Create plugin directory (包含组织层级)
    plugin_dir = PLUGINS_DIR / organization / name
    plugin_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    target_path = plugin_dir / f"{version}.zip"

    with open(target_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {
        "success": True,
        "organization": organization,
        "name": name,
        "version": version,
        "path": str(target_path),
        "size": target_path.stat().st_size
    }
```

**Step 7: 更新删除端点**

```python
@app.delete("/admin/plugins/{organization}/{plugin_name}/{version}")
async def delete_plugin(organization: str, plugin_name: str, version: str):
    """Delete a plugin version."""
    file_path = PLUGINS_DIR / organization / plugin_name / f"{version}.zip"

    if not file_path.exists():
        raise HTTPException(404, "Plugin version not found")

    file_path.unlink()

    # Remove empty directories
    plugin_dir = PLUGINS_DIR / organization / plugin_name
    if not any(plugin_dir.iterdir()):
        plugin_dir.rmdir()
        org_dir = PLUGINS_DIR / organization
        if not any(org_dir.iterdir()):
            org_dir.rmdir()

    return {"success": True, "message": f"Deleted {organization}/{plugin_name}@{version}"}
```

**Step 8: 测试**

运行：`python main.py`
访问：`http://localhost:28000/marketplace.json`
预期：返回空列表（因为现有插件需要迁移）

**Step 9: Commit**

```bash
git add main.py
git commit -m "feat: add organization dimension to plugin structure"
```

---

## Task 2: 修改 import-skills.py - 支持组织参数

**Files:**
- Modify: `import-skills.py`

**Step 1: 修改函数签名**

```python
def extract_and_repackage(skills_zip: Path, output_dir: Path, organization: str = "default"):
    """Extract skills from marketplace zip and repackage as individual plugin zips.

    Args:
        skills_zip: Path to the skills marketplace zip file
        output_dir: Base output directory for plugins
        organization: Organization name (default: "default")
    """
```

**Step 2: 修改目标目录创建逻辑**

```python
    for plugin_dir in skills_path.iterdir():
        if not plugin_dir.is_dir():
            continue

        plugin_name = plugin_dir.name
        # 现在包含组织层级
        target_dir = output_dir / organization / plugin_name
        target_dir.mkdir(parents=True, exist_ok=True)
```

**Step 3: 修改 main 块以支持组织参数**

```python
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import skills from marketplace zip")
    parser.add_argument("zip_file", nargs="?", default="skills-marketplace.zip",
                       help="Path to skills marketplace zip file")
    parser.add_argument("-o", "--org", default="default",
                       help="Organization name (default: default)")
    parser.add_argument("-d", "--output", default="plugins",
                       help="Output directory (default: plugins)")

    args = parser.parse_args()

    zip_file = Path(args.zip_file)

    if not zip_file.exists():
        print(f"Error: {zip_file} not found")
        sys.exit(1)

    extract_and_repackage(zip_file, Path(args.output), args.org)
```

**Step 4: 修改输出信息**

```python
    print(f"\n✅ Imported {imported} plugins to {output_dir}/{organization}")
    print(f"\nOrganization: {organization}")
    print(f"\nNext steps:")
    print(f"  1. Start registry: docker-compose up -d")
    print(f"  2. Visit: http://localhost:8000")
    print(f"  3. Add to Claude Code: /plugins marketplace add http://localhost:8000/marketplace.json")
```

**Step 5: 测试**

运行：`python import-skills.py skills-marketplace.zip -o my-org`
预期：插件被导入到 `plugins/my-org/{skill-name}/`

**Step 6: Commit**

```bash
git add import-skills.py
git commit -m "feat: add organization parameter to import script"
```

---

## Task 3: 创建迁移脚本 - 迁移现有插件

**Files:**
- Create: `migrate-to-org.py`

**Step 1: 编写迁移脚本**

```python
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
    print(f"  plugins/default/{'{skill-name}'}/{'{version}'}.zip")

if __name__ == "__main__":
    migrate_plugins()
```

**Step 2: 测试迁移脚本**

运行：`python migrate-to-org.py`
预期：现有插件被移动到 `plugins/default/` 目录下

**Step 3: Commit**

```bash
git add migrate-to-org.py
git commit -m "feat: add migration script for organization structure"
```

---

## Task 4: 更新前端模板

**Files:**
- Modify: `templates/index.html`

**Step 1: 更新模板以显示组织信息**

在插件卡片中添加组织标签：

```html
<!-- 在插件名称旁添加组织标签 -->
<div class="plugin-header">
    <h3>{{ plugin.name }}</h3>
    <span class="org-badge">{{ plugin.organization }}</span>
</div>
```

**Step 2: 添加样式**

```css
.org-badge {
    background: #e3f2fd;
    color: #1976d2;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 12px;
    margin-left: 8px;
}
```

**Step 3: Commit**

```bash
git add templates/index.html
git commit -m "ui: display organization badge in plugin cards"
```

---

## Task 5: 更新 README 文档

**Files:**
- Modify: `README.md`

**Step 1: 添加组织相关说明**

在文档中添加：

```markdown
## 目录结构

插件按组织隔离存放：
```
plugins/
├── default/              # 默认组织（无组织归属的插件）
│   ├── my-skill/
│   │   └── 1.0.0.zip
│   └── another-skill/
│       └── 1.0.0.zip
├── company-a/            # 公司A的插件
│   └── their-skill/
│       └── 1.0.0.zip
└── company-b/            # 公司B的插件
    └── their-skill/
        └── 1.0.0.zip
```

## 导入插件

指定组织导入：
```bash
python import-skills.py marketplace.zip -o company-a
```

## API 变更

- 上传：`POST /admin/upload` 新增 `organization` 参数（默认：default）
- 下载：`GET /plugins/{organization}/{plugin_name}/{filename}`
- 删除：`DELETE /admin/plugins/{organization}/{plugin_name}/{version}`
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README with organization structure"
```

---

## Task 6: 运行完整测试

**Step 1: 迁移现有插件**

```bash
python migrate-to-org.py
```

**Step 2: 启动服务**

```bash
python main.py
```

**Step 3: 验证 marketplace.json**

```bash
curl http://localhost:28000/marketplace.json | python -m json.tool
```

预期输出包含 `organization` 字段：
```json
{
  "plugins": [
    {
      "name": "ask-questions-if-underspecified",
      "organization": "default",
      "version": "1.0.1",
      ...
    }
  ]
}
```

**Step 4: 测试上传新插件**

```bash
curl -X POST http://localhost:28000/admin/upload \
  -F "organization=acme-corp" \
  -F "name=test-skill" \
  -F "version=1.0.0" \
  -F "file=@test-skill.zip"
```

**Step 5: Commit**

```bash
git commit -m "test: verify organization structure works end-to-end"
```

---

## Summary

实施完成后：

1. **目录结构**: `plugins/{org}/{skill}/{version}.zip`
2. **向后兼容**: 现有插件迁移到 `default` 组织
3. **API 变更**: 所有端点支持 organization 参数
4. **导入脚本**: 支持 `-o/--org` 参数指定组织
5. **前端显示**: 插件卡片显示组织标签

**关键设计决策:**
- 默认组织名为 `default`，保持简单
- 上传时 organization 默认为 `default`，向后兼容
- 迁移脚本一次性处理现有插件
