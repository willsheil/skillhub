#!/usr/bin/env python3
"""
Claude Code Skill Registry - Private Marketplace Server
"""

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import json
import os
import shutil
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel

# Configuration
PLUGINS_DIR = Path(os.getenv("PLUGINS_DIR", "./plugins"))
PLUGINS_DIR.mkdir(exist_ok=True)

# Admin credentials (can be overridden via environment variables)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # 默认密码，生产环境应修改

# Session secret key (should be changed in production)
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")

app = FastAPI(title="Skill Registry", version="1.0.0")

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def require_auth(request: Request):
    """Check if user is logged in."""
    if request.session.get("user") != ADMIN_USERNAME:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/admin/login"}
        )
    return True


def verify_credentials(username: str, password: str) -> bool:
    """Verify admin credentials."""
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


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

        for collection_dir in org_dir.iterdir():
            if not collection_dir.is_dir():
                continue
            collection = collection_dir.name

            for plugin_dir in collection_dir.iterdir():
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
                metadata = extract_metadata(organization, collection, plugin_dir.name, latest_zip)

                plugins.append({
                    "name": plugin_dir.name,
                    "organization": organization,
                    "collection": collection,
                    "metadata": metadata,
                    "versions": versions,
                    "latest_version": versions[-1]["version"]
                })

    return sorted(plugins, key=lambda x: (x["organization"], x["collection"], x["name"]))


def extract_metadata(organization: str, collection: str, plugin_name: str, zip_path: Path) -> Optional[dict]:
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
                    metadata["collection"] = collection
                    return metadata
    except Exception:
        pass

    # Fallback: return basic info
    return {
        "name": plugin_name,
        "organization": organization,
        "collection": collection,
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
            "collection": plugin["collection"],
            "version": latest["version"],
            "description": meta.get("description", "No description"),
            "author": meta.get("author", {"name": "Unknown"}),
            "source": f"{base_url}/{plugin['organization']}/{plugin['collection']}/{plugin['name']}/{latest['filename']}"
        })

    return marketplace


@app.get("/plugins/{organization}/{collection}/{plugin_name}/{filename}")
async def download_plugin(organization: str, collection: str, plugin_name: str, filename: str):
    """Download plugin ZIP file."""
    file_path = PLUGINS_DIR / organization / collection / plugin_name / filename

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


@app.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    """Display login page."""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error
    })


@app.post("/admin/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Process login."""
    if verify_credentials(username, password):
        request.session["user"] = username
        return RedirectResponse(url="/admin/upload", status_code=302)
    return RedirectResponse(url="/admin/login?error=invalid", status_code=302)


@app.get("/admin/logout")
async def logout(request: Request):
    """Logout admin."""
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)


@app.get("/admin/upload", response_class=HTMLResponse)
async def upload_page(request: Request, _: bool = Depends(require_auth)):
    """Display upload page (requires auth)."""
    return templates.TemplateResponse("admin_upload.html", {
        "request": request,
        "success": None,
        "error": None
    })


def process_skill_collection(
    zip_path: Path,
    output_dir: Path,
    organization: str,
    collection: str
) -> List[dict]:
    """Process a skill collection ZIP and extract individual skills.

    Args:
        zip_path: Path to the uploaded ZIP file
        output_dir: Base output directory (PLUGINS_DIR)
        organization: Organization name
        collection: Collection name

    Returns:
        List of processed skills with name and version
    """
    import zipfile
    import tempfile

    processed_skills = []
    temp_dir = tempfile.mkdtemp()

    try:
        # Extract ZIP to temp directory
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(temp_dir)

        # Look for skills in common locations
        skills_base_paths = [
            Path(temp_dir) / "skills" / "plugins",
            Path(temp_dir) / "plugins",
            Path(temp_dir),
        ]

        skills_found = False
        for skills_path in skills_base_paths:
            if not skills_path.exists():
                continue

            # Iterate through potential skill directories
            for item in skills_path.iterdir():
                if not item.is_dir():
                    continue

                # Check if this is a skill directory (has .claude-plugin/plugin.json)
                plugin_json = item / ".claude-plugin" / "plugin.json"
                if not plugin_json.exists():
                    # Try alternative location
                    plugin_json = item / "plugin.json"

                if plugin_json.exists():
                    try:
                        # Read skill metadata
                        with open(plugin_json, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)

                        skill_name = metadata.get("name", item.name)
                        skill_version = metadata.get("version", "1.0.0")

                        # Create target directory
                        skill_dir = output_dir / organization / collection / skill_name
                        skill_dir.mkdir(parents=True, exist_ok=True)

                        # Create ZIP for this skill
                        target_zip = skill_dir / f"{skill_version}.zip"

                        with zipfile.ZipFile(target_zip, 'w', zipfile.ZIP_DEFLATED) as zf_out:
                            for file_path in item.rglob("*"):
                                if file_path.is_file():
                                    arcname = str(file_path.relative_to(item))
                                    zf_out.write(file_path, arcname)

                        processed_skills.append({
                            "name": skill_name,
                            "version": skill_version,
                            "path": str(target_zip)
                        })
                        skills_found = True

                    except Exception as e:
                        print(f"Error processing skill {item.name}: {e}")
                        continue

        # If no skills found in collection structure, treat as single skill
        if not skills_found:
            return []

        return processed_skills

    finally:
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.post("/admin/upload")
async def upload_plugin(
    request: Request,
    name: str = Form(""),
    version: str = Form(""),
    organization: str = Form("default"),
    collection: str = Form("default"),
    file: UploadFile = File(...),
    _: bool = Depends(require_auth)
):
    """Upload a new plugin or skill collection (requires auth)."""
    import zipfile
    import tempfile

    # Validate file extension
    if not file.filename.endswith('.zip'):
        return templates.TemplateResponse("admin_upload.html", {
            "request": request,
            "success": None,
            "error": "Only ZIP files allowed"
        })

    # Save uploaded file to temp location
    temp_dir = tempfile.mkdtemp()
    temp_zip = Path(temp_dir) / "upload.zip"

    try:
        with open(temp_zip, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Try to process as skill collection first
        processed_skills = process_skill_collection(
            temp_zip, PLUGINS_DIR, organization, collection
        )

        if processed_skills:
            # Successfully processed as skill collection
            skill_names = ", ".join([s["name"] for s in processed_skills])
            return templates.TemplateResponse("admin_upload.html", {
                "request": request,
                "success": f"Successfully uploaded {len(processed_skills)} skills: {skill_names}",
                "error": None
            })

        # Treat as single skill upload
        if not name or not version:
            return templates.TemplateResponse("admin_upload.html", {
                "request": request,
                "success": None,
                "error": "For single skill upload, name and version are required"
            })

        # Create plugin directory
        plugin_dir = PLUGINS_DIR / organization / collection / name
        plugin_dir.mkdir(parents=True, exist_ok=True)

        # Save file
        target_path = plugin_dir / f"{version}.zip"

        shutil.copy(temp_zip, target_path)

        return templates.TemplateResponse("admin_upload.html", {
            "request": request,
            "success": f"Successfully uploaded {organization}/{collection}/{name}@{version}",
            "error": None
        })

    except Exception as e:
        return templates.TemplateResponse("admin_upload.html", {
            "request": request,
            "success": None,
            "error": f"Upload failed: {str(e)}"
        })

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.delete("/admin/plugins/{organization}/{collection}/{plugin_name}/{version}")
async def delete_plugin(
    organization: str,
    collection: str,
    plugin_name: str,
    version: str,
    _: bool = Depends(require_auth)
):
    """Delete a plugin version (requires auth)."""
    file_path = PLUGINS_DIR / organization / collection / plugin_name / f"{version}.zip"

    if not file_path.exists():
        raise HTTPException(404, "Plugin version not found")

    file_path.unlink()

    # Remove empty plugin directory
    plugin_dir = PLUGINS_DIR / organization / collection / plugin_name
    if plugin_dir.exists() and not any(plugin_dir.iterdir()):
        plugin_dir.rmdir()

    # Remove empty collection directory
    collection_dir = PLUGINS_DIR / organization / collection
    if collection_dir.exists() and not any(collection_dir.iterdir()):
        collection_dir.rmdir()

    # Remove empty organization directory
    org_dir = PLUGINS_DIR / organization
    if org_dir.exists() and not any(org_dir.iterdir()):
        org_dir.rmdir()

    return {"success": True, "message": f"Deleted {organization}/{collection}/{plugin_name}@{version}"}


@app.get("/api/collections")
async def list_collections():
    """List all skill collections grouped by organization."""
    plugins = scan_plugins()
    collections = {}

    for plugin in plugins:
        org = plugin["organization"]
        coll = plugin["collection"]

        if org not in collections:
            collections[org] = {}
        if coll not in collections[org]:
            collections[org][coll] = {
                "organization": org,
                "collection": coll,
                "skills": []
            }

        collections[org][coll]["skills"].append(plugin)

    return collections


@app.get("/api/collections/{organization}/{collection}")
async def get_collection_skills(organization: str, collection: str):
    """Get all skills in a specific collection."""
    plugins = scan_plugins()
    collection_skills = [
        p for p in plugins
        if p["organization"] == organization and p["collection"] == collection
    ]

    if not collection_skills:
        raise HTTPException(404, "Collection not found")

    return {
        "organization": organization,
        "collection": collection,
        "skills": collection_skills,
        "skill_count": len(collection_skills)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=28000)
