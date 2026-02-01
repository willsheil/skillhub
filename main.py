#!/usr/bin/env python3
"""
Claude Code Skill Registry - Private Marketplace Server
"""

import json
import shutil
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from pydantic import BaseModel

# Configuration
PLUGINS_DIR = Path("./plugins")
PLUGINS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Skill Registry", version="1.0.0")

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


class PluginMetadata(BaseModel):
    name: str
    version: str
    description: str
    author: dict
    updated_at: Optional[str] = None


def scan_plugins() -> List[dict]:
    """Scan plugins directory and return metadata list."""
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
                version = zip_file.stem  # e.g., "1.0.0" from "1.0.0.zip"
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


def extract_metadata(organization: str, plugin_name: str, zip_path: Path) -> Optional[dict]:
    """Extract metadata from plugin.json inside zip."""
    import zipfile

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Try to find plugin.json
            for name in zf.namelist():
                if name.endswith('.claude-plugin/plugin.json'):
                    content = zf.read(name)
                    metadata = json.loads(content)
                    metadata["organization"] = organization
                    return metadata
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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Web UI - Display all skills."""
    plugins = scan_plugins()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "plugins": plugins,
        "registry_name": "Private Skill Registry",
        "plugin_count": len(plugins)
    })


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

    base_url = "/plugins"  # Relative URL

    for plugin in plugins:
        meta = plugin["metadata"]
        latest = plugin["versions"][-1]

        marketplace["plugins"].append({
            "name": meta.get("name", plugin["name"]),
            "organization": plugin["organization"],
            "version": latest["version"],
            "description": meta.get("description", "No description"),
            "author": meta.get("author", {"name": "Unknown"}),
            "source": f"{base_url}/{plugin['organization']}/{plugin['name']}/{latest['filename']}"
        })

    return marketplace


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


@app.get("/api/skills")
async def api_skills():
    """API endpoint for skill list (for AJAX requests)."""
    return scan_plugins()


@app.post("/admin/upload")
async def upload_plugin(
    name: str = Form(...),
    version: str = Form(...),
    organization: str = Form("default"),
    file: UploadFile = File(...)
):
    """Upload a new plugin version."""
    # Validate file extension
    if not file.filename.endswith('.zip'):
        raise HTTPException(400, "Only ZIP files allowed")

    # Create plugin directory
    plugin_dir = PLUGINS_DIR / organization / name
    plugin_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    target_path = plugin_dir / f"{version}.zip"

    with open(target_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {
        "success": True,
        "name": name,
        "organization": organization,
        "version": version,
        "path": str(target_path),
        "size": target_path.stat().st_size
    }


@app.delete("/admin/plugins/{organization}/{plugin_name}/{version}")
async def delete_plugin(organization: str, plugin_name: str, version: str):
    """Delete a plugin version."""
    file_path = PLUGINS_DIR / organization / plugin_name / f"{version}.zip"

    if not file_path.exists():
        raise HTTPException(404, "Plugin version not found")

    file_path.unlink()

    # Remove empty plugin directory
    plugin_dir = PLUGINS_DIR / organization / plugin_name
    if plugin_dir.exists() and not any(plugin_dir.iterdir()):
        plugin_dir.rmdir()

    # Remove empty organization directory
    org_dir = PLUGINS_DIR / organization
    if org_dir.exists() and not any(org_dir.iterdir()):
        org_dir.rmdir()

    return {"success": True, "message": f"Deleted {organization}/{plugin_name}@{version}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=28000)
