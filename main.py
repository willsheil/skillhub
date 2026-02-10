#!/usr/bin/env python3
"""
Claude Code Skill Registry - Private Marketplace Server
"""

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
import logging
import os
import re
import secrets
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date

import yaml
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, status, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel

# Configuration
PLUGINS_DIR = Path(os.getenv("PLUGINS_DIR", "./plugins"))
PLUGINS_DIR.mkdir(exist_ok=True)

# Pending uploads directory
PENDING_DIR = Path("./data/pending")
PENDING_DIR.mkdir(parents=True, exist_ok=True)

# Import database module
from database import (
    init_db, record_download, get_download_stats, get_stats_with_author,
    get_user_by_credentials, get_user_by_id, update_last_login,
    create_skill_record, get_pending_skills, get_skill_by_id,
    update_skill_status, get_user_uploads, get_total_users_count,
    get_skills_count_by_status, get_today_downloads_count,
    get_top_skills_by_downloads, get_top_users_by_downloads,
    get_skill_source_type, create_notification, update_skill_active_status,
    get_skill_active_status, get_my_skills, set_default_skill_version,
    get_skill_versions, get_user_notifications, get_unread_notifications_count,
    mark_notification_read, mark_all_notifications_read, cleanup_old_notifications,
    get_users_list, create_user, update_user_role, disable_user,
    enable_user, reset_user_api_key, get_user_skills_count,
    get_default_skill_version, get_all_default_skill_versions,
    get_skill_approval_status, delete_skill_version, batch_unlist_skills,
    batch_delete_skills
)

# Configure logging
logger = logging.getLogger(__name__)

# Admin credentials (can be overridden via environment variables)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # 默认密码，生产环境应修改

# Session secret key (should be changed in production)
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")

# API key reset rate limiting (user_id -> last_reset_time)
_api_key_reset_times = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    init_db()

    # Start Gitea push service if configured
    if os.getenv("GITEA_REPO_URL"):
        try:
            from gitea_push_service import GiteaPushService

            push_service = GiteaPushService(
                interval=int(os.getenv("GITEA_PUSH_INTERVAL", "30"))
            )

            # Start service in background
            asyncio.create_task(push_service.run())

            logger.info("Gitea push service started")
        except Exception as e:
            logger.error(f"Failed to start Gitea push service: {e}")
    else:
        logger.info("Gitea integration disabled (GITEA_REPO_URL not set)")

    yield

    # Shutdown
    logger.info("Shutting down...")


app = FastAPI(title="Skill Registry", version="1.0.0", lifespan=lifespan)

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def require_auth(request: Request):
    """Check if user is authenticated.

    Raises HTTP 401 if user is not logged in.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return True


def require_admin(request: Request):
    """Check if user is authenticated and has admin role.

    Raises HTTP 401 if user is not logged in.
    Raises HTTP 403 if user is not an admin.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    role = request.session.get("role")
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return True


def get_current_user(request: Request) -> Optional[dict]:
    """Get the current authenticated user from session.

    Returns:
        User dictionary if authenticated, None otherwise
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    return get_user_by_id(user_id)


def verify_credentials(username: str, password: str) -> bool:
    """Verify admin credentials."""
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


class PluginMetadata(BaseModel):
    name: str
    version: str
    description: str
    author: dict
    updated_at: Optional[str] = None


def get_skill_dir_name(filename: str) -> str:
    """Get the skill directory name from filename.

    Removes .zip extension to get the directory name.
    Example: skill-name-1.0.0.zip -> skill-name-1.0.0
    """
    return filename[:-4] if filename.endswith('.zip') else filename


def parse_skill_md(content: str) -> Tuple[Optional[dict], str]:
    """Parse SKILL.md content to extract YAML frontmatter and markdown body.

    Args:
        content: Raw SKILL.md content

    Returns:
        Tuple of (yaml_metadata_dict, markdown_body)
        If no YAML frontmatter found, returns (None, content)
    """
    # Pattern to match YAML frontmatter between --- markers
    # Use .+? instead of .*? to ensure we match at least one character
    # Remove ^ anchor since content might have leading whitespace
    pattern = r'---\s*\n(.+?)\n---\s*\n(.*)'
    match = re.match(pattern, content, re.DOTALL)

    if match:
        yaml_content = match.group(1)
        markdown_body = match.group(2).strip()
        try:
            metadata = yaml.safe_load(yaml_content)
            if not isinstance(metadata, dict):
                metadata = {}
            return metadata, markdown_body
        except yaml.YAMLError:
            return None, content

    return None, content


def extract_metadata_from_skill_md(zip_path: Path) -> Optional[dict]:
    """Extract metadata from SKILL.md inside zip.

    The ZIP should have structure:
        skill-name/
        └── SKILL.md

    Args:
        zip_path: Path to the skill ZIP file

    Returns:
        Metadata dict or None if parsing fails
    """
    import zipfile

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()

            # Find SKILL.md (may be in root or subdirectory)
            skill_md_paths = [name for name in namelist
                             if name.endswith('SKILL.md') or name == 'SKILL.md']

            if not skill_md_paths:
                return None

            # Use the first SKILL.md found
            skill_md_path = skill_md_paths[0]
            content = zf.read(skill_md_path).decode('utf-8')

            metadata, _ = parse_skill_md(content)
            return metadata

    except Exception as e:
        print(f"Failed to extract metadata from {zip_path}: {e}")
        return None


def validate_skill_name(name: str) -> tuple[bool, str]:
    """Validate skill name according to specification.

    Requirements:
    - Must be 1-64 characters
    - May only contain lowercase letters, numbers, and hyphens
    - Must not start or end with '-'
    - Must not contain consecutive hyphens ('--')

    Returns:
        (is_valid, error_message)
    """
    if not name or not isinstance(name, str):
        return False, "Name is required"

    if len(name) < 1 or len(name) > 64:
        return False, "Name must be 1-64 characters"

    if not re.match(r'^[a-z0-9-]+$', name):
        return False, "Name may only contain lowercase letters, numbers, and hyphens"

    if name.startswith('-') or name.endswith('-'):
        return False, "Name must not start or end with hyphen"

    if '--' in name:
        return False, "Name must not contain consecutive hyphens"

    return True, ""


def package_skill_with_installer(
    original_zip_path: Path,
    skill_name: str,
    version: str
) -> bytes:
    """Package skill with installer scripts.

    Reads the original skill ZIP, adds install.bat and install.sh scripts,
    and returns the new ZIP as bytes.

    Args:
        original_zip_path: Path to the original skill ZIP file
        skill_name: Name of the skill
        version: Version of the skill

    Returns:
        ZIP file content as bytes with installer scripts included
    """
    import zipfile
    import io

    # Read script templates
    templates_dir = Path(__file__).parent / "templates" / "install_scripts"

    # Render script templates
    skill_dir_name = get_skill_dir_name(original_zip_path.name)

    script_vars = {
        "skill_name": skill_name,
        "version": version,
        "skill_dir_name": skill_dir_name
    }

    # Read and render install.bat
    bat_template = (templates_dir / "install.bat").read_text(encoding='utf-8')
    bat_content = bat_template
    for key, value in script_vars.items():
        bat_content = bat_content.replace(f"{{{{{key}}}}}", value)

    # Read and render install.sh
    sh_template = (templates_dir / "install.sh").read_text(encoding='utf-8')
    sh_content = sh_template
    for key, value in script_vars.items():
        sh_content = sh_content.replace(f"{{{{{key}}}}}", value)

    # Create new ZIP with installer scripts
    output = io.BytesIO()

    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf_out:
        # Copy all content from original ZIP
        with zipfile.ZipFile(original_zip_path, 'r') as zf_in:
            for item in zf_in.namelist():
                zf_out.writestr(item, zf_in.read(item))

        # Add installer scripts at root level (BAT with UTF-8 BOM for Windows)
        zf_out.writestr('install.bat', bat_content.encode('utf-8-sig'))
        zf_out.writestr('install.sh', sh_content.encode('utf-8'))

        # Add README
        readme_content = f"""Claude Code Skill: {skill_name} v{version}
{'=' * 50}

一键安装 (推荐):
----------------
Windows:
  1. 解压此 ZIP 文件
  2. 双击运行 install.bat
  3. 按提示完成安装

Linux / macOS:
  1. 解压此 ZIP 文件
  2. 打开终端，cd 到解压目录
  3. 运行: chmod +x install.sh && ./install.sh
  4. 按提示完成安装

手动安装:
---------
1. 将此 ZIP 解压到 Claude Code Skills 目录:
   - Windows: %USERPROFILE%\\.claude\\skills\
   - Linux/Mac: ~/.claude/skills/

2. 重启 Claude Code 以加载新技能

环境变量设置 (可选):
--------------------
设置 CLAUDE_SKILLS_PATH 环境变量可让安装脚本自动识别路径:
  - Windows: setx CLAUDE_SKILLS_PATH "C:\\path\\to\\skills"
  - Linux/Mac: export CLAUDE_SKILLS_PATH="/path/to/skills"

"""
        zf_out.writestr('README.txt', readme_content)

    return output.getvalue()


def parse_plugin_filename(filename: str) -> tuple[str, str]:
    """Parse plugin filename to extract skill name.

    Format: {skill-name}.zip (version is no longer extracted from filename)
    Example: ask-questions-if-underspecified.zip
             semgrep-rule-creator.zip

    Note: Version is now specified in SKILL.md metadata instead of filename.

    Returns: (skill_name, "unknown") - version always returns "unknown" to indicate
             it should be read from SKILL.md metadata
    """
    # Remove .zip extension
    skill_name = filename[:-4] if filename.endswith('.zip') else filename

    # Version is no longer parsed from filename
    # It should be read from SKILL.md metadata
    return skill_name, "unknown"


def scan_plugins() -> List[dict]:
    """Get approved and active skills from database with metadata from ZIP files.

    This is optimized to only show skills that are both approved and active,
    avoiding the need to scan all ZIP files repeatedly.
    """
    result = []

    # Get all approved and active skills directly from database
    from database import get_connection

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id, skill_name, version, filename, uploader_id, status,
                source_type, uploaded_at, reviewed_at, reviewer_id,
                review_comment, is_active, is_default_version
            FROM skills
            WHERE status = 'approved' AND is_active = 1
            ORDER BY skill_name, uploaded_at DESC
            """
        ).fetchall()

        # Group by skill_name to get only one entry per skill (the default version if exists)
        skills_by_name = {}
        for row in rows:
            skill_name = row["skill_name"]
            is_default = row["is_default_version"]

            # If we haven't added this skill yet, or this is the default version
            if skill_name not in skills_by_name or is_default:
                skills_by_name[skill_name] = row
            # If current is not default and existing is not default, keep the first one
            elif not skills_by_name[skill_name]["is_default_version"]:
                continue  # Keep the existing one

        # Build result list with metadata from ZIP files
        for skill_name, row in skills_by_name.items():
            # Extract metadata from ZIP file
            metadata = extract_metadata(row["filename"])
            if not metadata:
                # Fallback if ZIP file doesn't exist or is invalid
                metadata = {
                    "name": skill_name,
                    "description": f"{skill_name} - 技能描述",
                    "version": row["version"],
                    "license": None,
                    "compatibility": None,
                    "metadata": {"version": row["version"]},
                    "allowed_tools": None
                }

            result.append({
                "name": skill_name,
                "metadata": metadata,
                "latest_version": row["version"],
                "source_type": row["source_type"] or "opensource",
                "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
                "download_count": 0,  # TODO: Add download count if tracking
                "versions": [{
                    "version": row["version"],
                    "filename": row["filename"]
                }]
            })

    return result


def extract_metadata(zip_filename: str) -> Optional[dict]:
    """Extract metadata from SKILL.md inside zip per Agent Skills specification.

    The ZIP should have structure:
        skill-name-1.0.0.zip
        └── skill-name/
            ├── SKILL.md
            ├── scripts/
            └── ...

    Args:
        zip_filename: Name of the ZIP file (e.g., "skill-name-1.0.0.zip")

    Returns:
        Metadata dict or fallback info
    """
    zip_path = PLUGINS_DIR / zip_filename
    skill_name, version = parse_plugin_filename(zip_filename)

    # Try to extract from SKILL.md
    metadata = extract_metadata_from_skill_md(zip_path)

    if metadata:
        # Extract version from metadata field (per Agent Skills spec)
        skill_metadata = metadata.get("metadata", {})
        if isinstance(skill_metadata, dict):
            spec_version = skill_metadata.get("version")
        else:
            spec_version = None
            skill_metadata = {}

        # Normalize metadata format per Agent Skills spec
        normalized = {
            "name": metadata.get("name", skill_name),
            "version": spec_version if spec_version else (version if version != "unknown" else "1.0.0"),
            "description": metadata.get("description", "No description available"),
            "license": metadata.get("license"),
            "compatibility": metadata.get("compatibility"),
            "metadata": skill_metadata,
            "allowed_tools": metadata.get("allowed-tools")
        }
        return normalized

    # Fallback: try legacy package.json format for backward compatibility
    try:
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()

            for name in namelist:
                if name == 'package.json' or (name.endswith('/package.json')):
                    content = zf.read(name)
                    legacy_metadata = json.loads(content)
                    # Convert legacy format to Agent Skills format
                    legacy_author = legacy_metadata.get("author", {})
                    author_name = "Unknown"
                    if isinstance(legacy_author, dict):
                        author_name = legacy_author.get("name", "Unknown")
                    elif isinstance(legacy_author, str):
                        author_name = legacy_author

                    return {
                        "name": legacy_metadata.get("name", skill_name),
                        "version": legacy_metadata.get("version", version if version != "unknown" else "1.0.0"),
                        "description": legacy_metadata.get("description", "No description available"),
                        "license": None,
                        "compatibility": None,
                        "metadata": {
                            "author": author_name,
                            "version": legacy_metadata.get("version", version if version != "unknown" else "1.0.0")
                        },
                        "legacy": True
                    }
    except Exception:
        pass

    # Final fallback
    return {
        "name": skill_name,
        "version": version if version != "unknown" else "1.0.0",
        "description": "No description available",
        "license": None,
        "compatibility": None,
        "metadata": {}
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Web UI - Display all skills."""
    # Check if user is authenticated
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    plugins = scan_plugins()

    # Get current user if authenticated
    user = get_current_user(request)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "plugins": plugins,
        "registry_name": "Private Skill Registry",
        "plugin_count": len(plugins),
        "user": user
    })


@app.get("/install-guide", response_class=HTMLResponse)
async def install_guide(request: Request):
    """Installation guide page."""
    return templates.TemplateResponse("install_guide.html", {
        "request": request
    })


@app.get("/marketplace.json")
async def marketplace_json(request: Request):
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

    for plugin in plugins:
        meta = plugin["metadata"]
        latest = plugin["versions"][-1]

        marketplace["plugins"].append({
            "name": meta.get("name", plugin["name"]),
            "version": latest["version"],
            "description": meta.get("description", "No description"),
            "author": meta.get("author", {"name": "Unknown"}),
            "download_url": f"http://{request.headers.get('host', 'localhost:28000')}/plugins/{latest['filename']}",
            "size_kb": round(latest["size"] / 1024, 1)
        })

    return marketplace


@app.get("/plugins/{filename}")
async def download_plugin(filename: str, request: Request, raw: bool = False):
    """Download plugin ZIP file.

    Args:
        filename: Name of the plugin file
        request: HTTP request
        raw: If True, return original ZIP without installer scripts

    Returns:
        ZIP file with installer scripts included (by default)
        or original ZIP if raw=True
    """
    # Require authentication
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/admin/login", status_code=302)

    file_path = PLUGINS_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Get skill name from filename (version is now in SKILL.md metadata)
    skill_name = filename[:-4] if filename.endswith('.zip') else filename

    # Extract version from SKILL.md inside the ZIP
    metadata = extract_metadata_from_skill_md(file_path)
    if metadata and metadata.get("metadata"):
        version = metadata.get("metadata", {}).get("version", "unknown")
    else:
        version = "unknown"

    # Record download
    try:
        record_download(
            skill_name=skill_name,
            version=version,
            filename=filename,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            user_id=user_id
        )
    except Exception as e:
        # Log error but don't block download
        print(f"Failed to record download: {e}")

    # Return raw ZIP if requested
    if raw:
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/zip"
        )

    # Package with installer scripts
    try:
        zip_data = package_skill_with_installer(file_path, skill_name, version)
        return Response(
            content=zip_data,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        print(f"Failed to package with installer: {e}")
        # Fallback to raw file if packaging fails
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/zip"
        )


@app.get("/api/skills")
async def api_skills(page: int = 1, per_page: int = 1000):
    """API endpoint for skill list (for AJAX requests) with pagination support."""
    all_plugins = scan_plugins()

    # Calculate pagination
    total = len(all_plugins)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    # Return paginated results
    paginated_plugins = all_plugins[start_idx:end_idx]

    return {
        "data": paginated_plugins,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    }


@app.get("/login", response_class=HTMLResponse)
async def user_login_page(request: Request, error: str = None):
    """Display user login page."""
    error_msg = None
    if error == "invalid":
        error_msg = "工号或 API 密钥错误"

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error_msg
    })


@app.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    """Display admin login page (legacy, redirects to user login)."""
    return RedirectResponse(url="/login", status_code=302)


@app.post("/admin/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Process login."""
    if verify_credentials(username, password):
        request.session["user"] = username
        return RedirectResponse(url="/admin/upload", status_code=302)
    return RedirectResponse(url="/admin/login?error=invalid", status_code=302)


@app.post("/api/login")
async def api_login(
    request: Request,
    employee_id: str = Form(...),
    api_key: str = Form(...)
):
    """User login API endpoint.

    Accepts employee_id and api_key as form parameters.
    Sets session variables on success.
    Updates last login timestamp.
    Returns success response or redirects on failure.
    """
    # Query user by credentials
    user = get_user_by_credentials(employee_id, api_key)

    if user:
        # Set session variables
        request.session["user_id"] = user["id"]
        request.session["employee_id"] = user["employee_id"]
        request.session["role"] = user["role"]

        # Update last login
        update_last_login(user["id"])

        # Redirect to homepage after login
        return RedirectResponse(url="/", status_code=302)
    else:
        return RedirectResponse(
            url="/login?error=invalid",
            status_code=302
        )


@app.get("/logout")
async def logout(request: Request):
    """Logout and clear session."""
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)


@app.get("/api/me")
async def api_me(request: Request):
    """Get current user information.

    Returns the current authenticated user's details.
    Raises HTTP 401 if not authenticated.
    """
    user = get_current_user(request)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    return {
        "id": user["id"],
        "employee_id": user["employee_id"],
        "role": user["role"],
        "created_at": user["created_at"],
        "last_login": user["last_login"]
    }


@app.get("/upload", response_class=HTMLResponse)
async def user_upload_page(request: Request):
    """Display user upload page (requires auth)."""
    # Get current user
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("upload.html", {
        "request": request,
        "user": user,
        "success": None,
        "error": None
    })


@app.get("/admin/upload", response_class=HTMLResponse)
async def upload_page(request: Request, _: bool = Depends(require_auth)):
    """Display admin upload page (requires auth)."""
    user = get_current_user(request)

    return templates.TemplateResponse("admin_upload.html", {
        "request": request,
        "user": user,
        "success": None,
        "error": None
    })


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Display admin dashboard (requires admin)."""
    # Get current user
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Check admin role
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user
    })


@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request):
    """Display user management page (requires admin)."""
    # Get current user
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Check admin role
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "user": user
    })


def validate_skill_zip(zip_path: Path) -> tuple[bool, dict]:
    """Validate a skill ZIP file according to Agent Skills specification.

    The ZIP should have structure:
        skill-name/
        ├── SKILL.md          # Required
        ├── scripts/          # Optional
        ├── references/       # Optional
        └── assets/           # Optional

    SKILL.md must contain YAML frontmatter with required fields:
        - name: skill identifier (max 64 chars, lowercase letters/numbers/hyphens only)
        - description: what the skill does (max 1024 chars)
        - metadata.version: version string (e.g., "1.0.0")
        - metadata.author: author identifier (format: lowercase letter + 8 digits, e.g., "w00545471")

    Optional fields:
        - license: license name or reference
        - compatibility: environment requirements (max 500 chars)
        - metadata: arbitrary key-value mapping (other custom fields)
        - allowed-tools: space-delimited list of pre-approved tools

    Args:
        zip_path: Path to the skill ZIP file

    Returns:
        (is_valid, metadata or error_info)
    """
    import zipfile

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()

            # Find SKILL.md (may be in root or subdirectory)
            skill_md_paths = [name for name in namelist
                             if name.endswith('SKILL.md') or name == 'SKILL.md']

            if not skill_md_paths:
                return False, {"error": "Missing SKILL.md in ZIP"}

            # Read and parse SKILL.md
            skill_md_path = skill_md_paths[0]
            content = zf.read(skill_md_path).decode('utf-8')
            print("111",content)
            metadata, _ = parse_skill_md(content)

            if metadata is None:
                return False, {"error": "Invalid YAML frontmatter in SKILL.md"}

            # Validate required fields
            if "name" not in metadata:
                return False, {"error": "Missing required field 'name' in SKILL.md YAML frontmatter"}
            if "description" not in metadata:
                return False, {"error": "Missing required field 'description' in SKILL.md YAML frontmatter"}

            # Validate name format
            is_name_valid, name_error = validate_skill_name(metadata["name"])
            if not is_name_valid:
                return False, {"error": f"Invalid skill name: {name_error}"}

            # Validate description length (max 1024 chars)
            description = metadata["description"]
            if not isinstance(description, str) or len(description) == 0 or len(description) > 1024:
                return False, {"error": "Description must be 1-1024 characters"}

            # Validate optional fields if present
            # compatibility: max 500 chars
            if "compatibility" in metadata:
                compat = metadata["compatibility"]
                if not isinstance(compat, str) or len(compat) == 0 or len(compat) > 500:
                    return False, {"error": "Compatibility must be 1-500 characters if provided"}

            # Extract and validate metadata fields (version and author are required)
            skill_metadata = metadata.get("metadata", {})
            if not isinstance(skill_metadata, dict):
                return False, {"error": "Metadata must be a key-value mapping"}

            # Validate version is required in metadata
            version = skill_metadata.get("version")
            if not version:
                return False, {"error": "Missing required field 'metadata.version' in SKILL.md"}
            if not isinstance(version, str) or len(version) == 0:
                return False, {"error": "Metadata.version must be a non-empty string"}

            # Validate author is required in metadata
            author = skill_metadata.get("author")
            if not author:
                return False, {"error": "Missing required field 'metadata.author' in SKILL.md"}
            if not isinstance(author, str) or len(author) == 0:
                return False, {"error": "Metadata.author must be a non-empty string"}

            # Validate author format: lowercase letter followed by 8 digits (e.g., w00545471)
            import re
            if not re.match(r'^[a-z]\d{8}$', author):
                return False, {"error": "Invalid author format. Must be a lowercase letter followed by 8 digits (e.g., w00545471)"}

            # Normalize metadata for return (matching API format)
            normalized_metadata = {
                "name": metadata["name"],
                "description": metadata["description"],
                "version": version,
                "license": metadata.get("license"),
                "compatibility": metadata.get("compatibility"),
                "metadata": skill_metadata,
                "allowed_tools": metadata.get("allowed-tools")
            }

            return True, normalized_metadata

    except zipfile.BadZipFile:
        return False, {"error": "Invalid ZIP file"}
    except yaml.YAMLError as e:
        return False, {"error": f"Invalid YAML in SKILL.md: {str(e)}"}
    except Exception as e:
        return False, {"error": str(e)}


def save_skill_zip(temp_zip: Path, metadata: dict) -> Path:
    """Save a skill ZIP to the plugins directory.

    Args:
        temp_zip: Path to the temporary ZIP file
        metadata: Skill metadata from SKILL.md

    Returns:
        Path to the saved ZIP file
    """
    skill_name = metadata["name"]
    version = metadata.get("version", "1.0.0")
    target_filename = f"{skill_name}-{version}.zip"
    target_path = PLUGINS_DIR / target_filename

    # Copy file to target location
    shutil.copy(temp_zip, target_path)

    return target_path


def approve_skill_file(skill_id: int) -> bool:
    """Approve a skill by moving it from pending to plugins directory.

    Args:
        skill_id: The ID of the skill to approve

    Returns:
        True if successful, False otherwise
    """
    # Get skill record
    skill = get_skill_by_id(skill_id)
    if not skill:
        return False

    if skill["status"] != "pending":
        return False

    # File paths
    pending_path = PENDING_DIR / skill["filename"]
    plugins_path = PLUGINS_DIR / skill["filename"]

    try:
        # Check if file is in pending directory
        if pending_path.exists():
            # Move file from pending to plugins
            # Remove existing file if it exists (prevents FileExistsError on re-approval)
            if plugins_path.exists():
                logger.info(f"Removing existing file: {plugins_path}")
                plugins_path.unlink()

            shutil.move(str(pending_path), str(plugins_path))
        elif not plugins_path.exists():
            # File not in pending and not in plugins - error
            logger.error(f"Skill file not found: {skill['filename']} (checked both pending and plugins directories)")
            return False
        else:
            # File already in plugins directory (possibly from old batch upload)
            logger.info(f"File already in plugins directory: {plugins_path}")

        # Update database status
        update_skill_status(skill_id, "approved")

        # Set is_active=1 on approval
        update_skill_active_status(skill_id, True)

        # Create notification for uploader
        uploader_id = skill.get("uploader_id")
        if uploader_id:
            content = f"您的技能 {skill['skill_name']} (版本 {skill['version']}) 已通过审核并上线。"
            create_notification(
                user_id=uploader_id,
                type="review_success",
                title="您的技能已通过审核",
                content=content,
                related_skill_id=skill_id
            )

        return True
    except Exception as e:
        logger.error(f"Failed to approve skill {skill_id}: {e}")
        return False


def reject_skill_file(skill_id: int, comment: Optional[str] = None) -> bool:
    """Reject a skill by deleting the pending file.

    Args:
        skill_id: The ID of the skill to reject
        comment: Optional rejection comment

    Returns:
        True if successful, False otherwise
    """
    # Get skill record
    skill = get_skill_by_id(skill_id)
    if not skill:
        return False

    if skill["status"] != "pending":
        return False

    # Delete pending file
    pending_path = PENDING_DIR / skill["filename"]

    try:
        if pending_path.exists():
            pending_path.unlink()

        # Update database status
        update_skill_status(skill_id, "rejected", comment=comment)

        # Create notification for uploader
        uploader_id = skill.get("uploader_id")
        if uploader_id:
            content = f"您的技能 {skill['skill_name']} (版本 {skill['version']}) 未通过审核。"
            if comment:
                content += f" 原因: {comment}"
            create_notification(
                user_id=uploader_id,
                type="review_rejected",
                title="您的技能未通过审核",
                content=content,
                related_skill_id=skill_id
            )

        return True
    except Exception as e:
        logger.error(f"Failed to reject skill {skill_id}: {e}")
        return False


@app.get("/api/pending")
async def api_pending_skills(
    _: bool = Depends(require_admin)
):
    """Get all pending skills awaiting approval (admin only)."""
    try:
        pending = get_pending_skills()
        return {
            "success": True,
            "data": pending,
            "count": len(pending)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending skills: {str(e)}"
        )


@app.post("/api/review/{skill_id}")
async def api_review_skill(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_admin)
):
    """Approve or reject a pending skill (admin only).

    Expects JSON body with:
    {
        "action": "approve" | "reject",
        "comment": "optional comment"
    }
    """
    try:
        # Get current user (reviewer)
        reviewer_id = request.session.get("user_id")
        if not reviewer_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Parse request body
        data = await request.json()
        action = data.get("action")
        comment = data.get("comment")

        if action not in ["approve", "reject"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid action. Must be 'approve' or 'reject'"
            )

        # Get skill record
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        if skill["status"] != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Skill {skill_id} is not in pending status"
            )

        # Perform action
        if action == "approve":
            success = approve_skill_file(skill_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to approve skill {skill_id}"
                )

            # Update with reviewer info
            update_skill_status(skill_id, "approved", reviewer_id=reviewer_id, comment=comment)

            # NEW: Create Gitea push task
            task_id = None
            try:
                from gitea_integration import create_push_task
                task_id = create_push_task(skill_id)
                logger.info(f"Created Gitea push task {task_id} for skill {skill_id}")
            except Exception as e:
                # Log error but don't block approval
                logger.error(f"Failed to create Gitea push task: {e}")

            return {
                "success": True,
                "message": f"Skill {skill['skill_name']}@{skill['version']} approved",
                "skill_id": skill_id,
                "push_task_id": task_id
            }

        else:  # reject
            success = reject_skill_file(skill_id, comment)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to reject skill {skill_id}"
                )

            # Update with reviewer info
            update_skill_status(skill_id, "rejected", reviewer_id=reviewer_id, comment=comment)

            return {
                "success": True,
                "message": f"Skill {skill['skill_name']}@{skill['version']} rejected",
                "skill_id": skill_id
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Review failed: {str(e)}"
        )


@app.get("/api/user/downloads")
async def api_user_downloads(
    request: Request,
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    _: bool = Depends(require_auth)
):
    """Get the current user's download history with pagination.

    Query parameters:
    - page: Page number (default: 1, min: 1)
    - per_page: Items per page (default: 20, min: 1, max: 100)

    Returns paginated list of downloads for the authenticated user.
    """
    try:
        # Get current user
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Calculate offset from page number
        offset = (page - 1) * per_page

        # Get user downloads from database
        result = get_user_downloads(
            user_id=user_id,
            limit=per_page,
            offset=offset
        )

        # Calculate pagination metadata
        total = result["total"]
        total_pages = (total + per_page - 1) // per_page

        return {
            "success": True,
            "data": result["downloads"],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch downloads: {str(e)}"
        )


@app.get("/api/user/uploads")
async def api_user_uploads(
    request: Request,
    _: bool = Depends(require_auth)
):
    """Get the current user's upload history."""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        uploads = get_user_uploads(user_id)

        return {
            "success": True,
            "data": uploads,
            "count": len(uploads)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch uploads: {str(e)}"
        )


@app.get("/api/notifications")
async def api_get_notifications(
    request: Request,
    unread_only: bool = Query(False, description="Filter to only unread notifications"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of notifications to return"),
    offset: int = Query(0, ge=0, description="Number of notifications to skip"),
    _: bool = Depends(require_auth)
):
    """Get notifications for the current user with pagination.

    Query parameters:
    - unread_only: If True, only return unread notifications (default: False)
    - limit: Maximum number of notifications to return (default: 50, max: 100)
    - offset: Number of notifications to skip for pagination (default: 0)

    Returns notifications sorted newest first.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        result = get_user_notifications(user_id, unread_only, limit, offset)

        return {
            "success": True,
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch notifications: {str(e)}"
        )


@app.get("/api/notifications/unread-count")
async def api_get_unread_count(
    request: Request,
    _: bool = Depends(require_auth)
):
    """Get the count of unread notifications for the current user."""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        count = get_unread_notifications_count(user_id)

        return {
            "success": True,
            "data": {
                "unread_count": count
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch unread count: {str(e)}"
        )


@app.post("/api/notifications/{notification_id}/read")
async def api_mark_notification_read(
    notification_id: int,
    request: Request,
    _: bool = Depends(require_auth)
):
    """Mark a specific notification as read.

    Verifies that the user owns this notification before marking it as read.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        success = mark_notification_read(notification_id, user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found or does not belong to this user"
            )

        return {
            "success": True,
            "data": {
                "message": "Notification marked as read"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark notification as read: {str(e)}"
        )


@app.post("/api/notifications/read-all")
async def api_mark_all_read(
    request: Request,
    _: bool = Depends(require_auth)
):
    """Mark all notifications as read for the current user."""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        count = mark_all_notifications_read(user_id)

        return {
            "success": True,
            "data": {
                "message": f"Marked {count} notifications as read",
                "count": count
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark all notifications as read: {str(e)}"
        )


@app.get("/api/my-skills")
async def api_my_skills(
    request: Request,
    status: str = Query("all", description="Filter by status: all, active, unlisted, pending, rejected"),
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    _: bool = Depends(require_auth)
):
    """Get current user's skills with pagination and filtering.

    Query parameters:
    - status: Filter by status ('all', 'active', 'unlisted', 'pending', 'rejected')
    - page: Page number (default: 1, min: 1)
    - per_page: Items per page (default: 20, min: 1, max: 100)

    Returns paginated list of skills for the authenticated user.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Calculate offset from page number
        offset = (page - 1) * per_page

        # Get user skills from database
        result = get_my_skills(
            user_id=user_id,
            status_filter=status,
            limit=per_page,
            offset=offset
        )

        # Calculate pagination metadata
        total = result["total"]
        total_pages = (total + per_page - 1) // per_page

        return {
            "success": True,
            "data": result["skills"],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch skills: {str(e)}"
        )


@app.get("/my-skills", response_class=HTMLResponse)
async def my_skills_page(request: Request):
    """Render the my_skills.html page (requires auth)."""
    user = get_current_user(request)

    return templates.TemplateResponse("my_skills.html", {
        "request": request,
        "user": user
    })


class BatchOperationRequest(BaseModel):
    """Request model for batch operations."""
    skill_ids: List[int]


@app.post("/api/my-skills/batch/unlist")
async def api_batch_unlist_skills(
    request_data: BatchOperationRequest,
    request: Request,
    _: bool = Depends(require_auth)
):
    """Unlist multiple skills at once.

    User must own all the skills to unlist them.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        result = batch_unlist_skills(user_id, request_data.skill_ids)

        message = f"已下架 {result['success_count']} 个技能"
        if result["failed_ids"]:
            message += f"，{len(result['failed_ids'])} 个失败"

        return {
            "success": True,
            "message": message,
            "success_count": result["success_count"],
            "failed_ids": result["failed_ids"]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to batch unlist skills: {str(e)}"
        )


@app.post("/api/my-skills/batch/delete")
async def api_batch_delete_skills(
    request_data: BatchOperationRequest,
    request: Request,
    _: bool = Depends(require_auth)
):
    """Delete multiple skills at once.

    User must own all the skills to delete them. The physical ZIP files will also be removed.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        result = batch_delete_skills(user_id, request_data.skill_ids)

        message = f"已删除 {result['success_count']} 个技能"
        if result["failed_ids"]:
            message += f"，{len(result['failed_ids'])} 个失败"

        return {
            "success": True,
            "message": message,
            "success_count": result["success_count"],
            "failed_ids": result["failed_ids"]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to batch delete skills: {str(e)}"
        )


@app.post("/api/my-skills/{skill_id}/unlist")
async def api_unlist_skill(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_auth)
):
    """Unlist a skill (set is_active = 0).

    User must own the skill to unlist it.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Get skill record
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        # Verify ownership
        if skill["uploader_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't own this skill"
            )

        # Update active status
        update_skill_active_status(skill_id, False)

        return {
            "success": True,
            "message": f"Skill {skill['skill_name']}@{skill['version']} has been unlisted",
            "skill_id": skill_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unlist skill: {str(e)}"
        )


@app.post("/api/my-skills/{skill_id}/publish")
async def api_publish_skill(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_auth)
):
    """Publish a skill (set is_active = 1).

    User must own the skill to publish it.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Get skill record
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        # Verify ownership
        if skill["uploader_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't own this skill"
            )

        # Update active status
        update_skill_active_status(skill_id, True)

        return {
            "success": True,
            "message": f"Skill {skill['skill_name']}@{skill['version']} has been published",
            "skill_id": skill_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish skill: {str(e)}"
        )


@app.post("/api/my-skills/{skill_id}/set-default")
async def api_set_default_skill(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_auth)
):
    """Set a skill version as the default for its skill name.

    User must own the skill. All other versions of the same skill
    will have is_default_version set to 0.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Get skill record
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        # Verify ownership
        if skill["uploader_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't own this skill"
            )

        # Set as default version
        success = set_default_skill_version(
            user_id=user_id,
            skill_name=skill["skill_name"],
            skill_id=skill_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to set default version"
            )

        return {
            "success": True,
            "message": f"Skill {skill['skill_name']}@{skill['version']} is now the default version",
            "skill_id": skill_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set default version: {str(e)}"
        )


@app.get("/api/my-skills/versions/{skill_name}")
async def api_get_skill_versions(
    skill_name: str,
    request: Request,
    _: bool = Depends(require_auth)
):
    """Get all versions of a skill owned by the current user.

    Returns versions sorted newest first. User must own at least
    one version of the skill.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Get skill versions (function already verifies ownership by filtering on uploader_id)
        versions = get_skill_versions(user_id, skill_name)

        # Check if user owns any version of this skill
        if not versions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No versions found for skill '{skill_name}' or you don't own this skill"
            )

        return {
            "success": True,
            "data": versions,
            "skill_name": skill_name,
            "count": len(versions)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch skill versions: {str(e)}"
        )


@app.delete("/api/my-skills/{skill_id}")
async def api_delete_skill(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_auth)
):
    """Delete a skill version.

    User must own the skill to delete it. The physical ZIP file will also be removed.
    If this is the default version and there are other versions, another version will be set as default.
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Get skill record for response message
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        # Verify ownership
        if skill["uploader_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't own this skill"
            )

        # Delete the skill
        success = delete_skill_version(user_id, skill_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete skill"
            )

        return {
            "success": True,
            "message": f"Skill {skill['skill_name']}@{skill['version']} has been deleted",
            "skill_id": skill_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete skill: {str(e)}"
        )


@app.post("/api/upload")
async def upload_plugin(
    request: Request,
    file: UploadFile = File(...),
    source_type: str = Form(default="opensource"),
    _: bool = Depends(require_auth)
):
    """Upload a single skill ZIP file (requires auth).

    Saves to pending directory and creates database record with status='pending'.
    Requires admin approval before being made available.

    Returns JSON response for AJAX requests.
    """
    import tempfile
    from fastapi.responses import JSONResponse

    # Get current user
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "请先登录"}
        )

    # Validate file extension
    if not file.filename or not file.filename.endswith('.zip'):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": "只支持 ZIP 格式的文件"}
        )

    # Save uploaded file to temp location
    temp_dir = tempfile.mkdtemp()
    temp_zip = Path(temp_dir) / "upload.zip"

    try:
        with open(temp_zip, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Validate the ZIP file
        is_valid, result = validate_skill_zip(temp_zip)

        if not is_valid:
            error_msg = result.get('error', 'Unknown error')

            # Map validation errors to user-friendly messages
            error_messages = {
                "Missing SKILL.md in ZIP": "ZIP 文件中缺少 SKILL.md 文件",
                "Invalid YAML frontmatter in SKILL.md": "SKILL.md 中的 YAML 格式无效",
                "Missing required field 'name' in SKILL.md YAML frontmatter": "SKILL.md 中缺少必需字段 'name'",
                "Missing required field 'description' in SKILL.md YAML frontmatter": "SKILL.md 中缺少必需字段 'description'",
                "Missing required field 'metadata.version' in SKILL.md": "SKILL.md 中缺少 metadata.version 字段",
                "Metadata.version must be a non-empty string": "版本号不能为空",
                "Missing required field 'metadata.author' in SKILL.md": "SKILL.md 中缺少 metadata.author 字段",
                "Metadata.author must be a non-empty string": "作者信息不能为空",
                "Invalid ZIP file": "无效的 ZIP 文件",
            }

            # Check for skill name validation errors
            if "Invalid skill name:" in error_msg:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"success": False, "error": f"技能名称格式错误: {error_msg.split(':', 1)[1].strip() if ':' in error_msg else error_msg}"}
                )

            # Use user-friendly message if available, otherwise use original
            user_friendly_error = error_messages.get(error_msg, error_msg)

            # Return HTML error for admin_upload page
            if "admin" in request.headers.get("referer", ""):
                return templates.TemplateResponse("admin_upload.html", {
                    "request": request,
                    "success": None,
                    "error": user_friendly_error
                })
            else:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"success": False, "error": user_friendly_error}
                )

        # Save the skill ZIP to pending directory
        skill_name = result["name"]
        version = result.get("version", "1.0.0")
        target_filename = f"{skill_name}-{version}.zip"
        target_path = PENDING_DIR / target_filename

        # Check if skill with same name and version already exists
        from database import check_skill_exists
        if check_skill_exists(skill_name, version):
            error_msg = f"技能 {skill_name}@{version} 已存在，请使用不同的版本号"

            # Return HTML error for admin_upload page
            if "admin" in request.headers.get("referer", ""):
                return templates.TemplateResponse("admin_upload.html", {
                    "request": request,
                    "success": None,
                    "error": error_msg
                })
            else:
                return JSONResponse(
                    status_code=status.HTTP_409_CONFLICT,
                    content={"success": False, "error": error_msg}
                )

        # Copy file to pending location
        shutil.copy(temp_zip, target_path)

        # Create database record with status='pending'
        from database import create_skill_record
        skill_id = create_skill_record(
            skill_name=skill_name,
            version=version,
            filename=target_filename,
            uploader_id=user_id,
            status='pending',
            source_type=source_type
        )

        # Return success response
        success_msg = f"成功上传 {result['name']}@{result['version']}，等待管理员审核"

        # Return HTML success for admin_upload page
        if "admin" in request.headers.get("referer", ""):
            return templates.TemplateResponse("admin_upload.html", {
                "request": request,
                "success": success_msg,
                "error": None
            })
        else:
            # Return JSON for AJAX requests
            return JSONResponse(
                content={
                    "success": True,
                    "message": success_msg,
                    "skill_name": result['name'],
                    "version": result['version'],
                    "skill_id": skill_id
                }
            )

    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = f"上传失败: {str(e)}"

        if "admin" in request.headers.get("referer", ""):
            return templates.TemplateResponse("admin_upload.html", {
                "request": request,
                "success": None,
                "error": error_msg
            })
        else:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"success": False, "error": error_msg}
            )

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.post("/admin/upload-batch")
async def upload_batch(
    request: Request,
    files: List[UploadFile] = File(...),
    source_type: str = Form(default="opensource"),
    _: bool = Depends(require_auth)
):
    """Upload multiple skill ZIP files (batch upload)."""
    import tempfile

    if not files:
        return templates.TemplateResponse("admin_upload.html", {
            "request": request,
            "success": None,
            "error": "No files selected"
        })

    results = {
        "success": [],
        "failed": []
    }

    # Get source_type for each file from form data (source_type_0, source_type_1, etc.)
    form_data = await request.form()

    for idx, file in enumerate(files):
        # Skip non-ZIP files
        if not file.filename or not file.filename.endswith('.zip'):
            results["failed"].append({"file": file.filename, "error": "Not a ZIP file"})
            continue

        # Get source type for this specific file (default to 'opensource' or use global source_type)
        file_source_type = form_data.get(f"source_type_{idx}", source_type)

        temp_dir = tempfile.mkdtemp()
        temp_zip = Path(temp_dir) / "upload.zip"

        try:
            # Save uploaded file
            with open(temp_zip, "wb") as f:
                shutil.copyfileobj(file.file, f)

            # Validate the ZIP file
            is_valid, metadata = validate_skill_zip(temp_zip)

            if not is_valid:
                results["failed"].append({
                    "file": file.filename,
                    "error": metadata.get('error', 'Unknown error')
                })
                continue

            # Check if skill with same name and version already exists
            from database import check_skill_exists
            skill_name = metadata["name"]
            skill_version = metadata.get("version", "1.0.0")
            target_filename = f"{skill_name}-{skill_version}.zip"

            if check_skill_exists(skill_name, skill_version):
                results["failed"].append({
                    "file": file.filename,
                    "error": f"Skill {skill_name}@{skill_version} already exists"
                })
                continue

            # Save the skill ZIP to pending directory for review
            target_path = PENDING_DIR / target_filename
            shutil.copy(temp_zip, target_path)

            # Create database record with source_type
            user_id = request.session.get("user_id")
            create_skill_record(
                skill_name=skill_name,
                version=skill_version,
                filename=target_filename,
                uploader_id=user_id,
                status='pending',  # Batch uploads also require admin approval
                source_type=file_source_type
            )

            results["success"].append({
                "name": metadata["name"],
                "version": metadata["version"]
            })

        except Exception as e:
            results["failed"].append({"file": file.filename, "error": str(e)})

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # Build result message
    success_count = len(results["success"])
    failed_count = len(results["failed"])

    if success_count > 0 and failed_count == 0:
        success_msg = f"Successfully uploaded {success_count} skill(s): " + \
                      ", ".join([f"{s['name']}@{s['version']}" for s in results["success"]])
        return templates.TemplateResponse("admin_upload.html", {
            "request": request,
            "success": success_msg,
            "error": None
        })
    elif success_count > 0 and failed_count > 0:
        success_msg = f"Uploaded {success_count} skill(s), {failed_count} failed"
        error_msg = "; ".join([f"{f['file']}: {f['error']}" for f in results["failed"]])
        return templates.TemplateResponse("admin_upload.html", {
            "request": request,
            "success": success_msg,
            "error": error_msg
        })
    else:
        error_msg = "All uploads failed: " + \
                    "; ".join([f"{f['file']}: {f['error']}" for f in results["failed"]])
        return templates.TemplateResponse("admin_upload.html", {
            "request": request,
            "success": None,
            "error": error_msg
        })


@app.delete("/admin/plugins/{filename}")
async def delete_plugin(
    filename: str,
    _: bool = Depends(require_auth)
):
    """Delete a plugin (requires auth)."""
    file_path = PLUGINS_DIR / filename

    if not file_path.exists():
        raise HTTPException(404, "Plugin not found")

    file_path.unlink()

    return {"success": True, "message": f"Deleted {filename}"}




@app.post("/api/batch-download")
async def batch_download(request: Request):
    """Generate a batch download package (ZIP) for selected skills.

    Each skill is packaged with installer scripts (install.bat and install.sh).
    Also includes install-all scripts at the root level for installing all skills at once.
    """
    import zipfile
    from io import BytesIO

    try:
        # Parse request data
        data = await request.json()
        selected_filenames = data.get("filenames", [])

        if not selected_filenames:
            raise HTTPException(400, "No skills selected")

        # Create ZIP in memory
        zip_buffer = BytesIO()

        added_skills = []  # Track successfully added skills for install-all scripts

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filename in selected_filenames:
                target_zip = PLUGINS_DIR / filename

                if not target_zip.exists():
                    print(f"Warning: ZIP file not found: {filename}")
                    continue

                # Get skill name from filename
                skill_name = filename[:-4] if filename.endswith('.zip') else filename

                # Extract version from SKILL.md inside the ZIP
                skill_metadata = extract_metadata_from_skill_md(target_zip)
                if skill_metadata and skill_metadata.get("metadata"):
                    version = skill_metadata.get("metadata", {}).get("version", "unknown")
                else:
                    version = "unknown"

                # Add skill to batch package (without individual installer scripts)
                try:
                    # Extract original ZIP contents directly to skill directory
                    with zipfile.ZipFile(target_zip, 'r') as skill_zf:
                        for item in skill_zf.namelist():
                            zf.writestr(f"{skill_name}/{item}", skill_zf.read(item))

                    added_skills.append({
                        'name': skill_name,
                        'version': version,
                        'dir': get_skill_dir_name(filename)
                    })
                except Exception as e:
                    print(f"Warning: Failed to package {filename}: {e}")
                    # Fallback: add original ZIP at root level
                    zf.write(target_zip, filename)
                    added_skills.append({
                        'name': skill_name,
                        'version': version,
                        'dir': get_skill_dir_name(filename),
                        'fallback': True
                    })

            if len(added_skills) == 0:
                raise HTTPException(404, "No valid skill files found")

            # Add install-all scripts at root level
            if len(added_skills) > 0:
                # Generate install-all.bat (with UTF-8 BOM for Windows)
                install_all_bat = generate_install_all_bat(added_skills)
                zf.writestr('install-all.bat', install_all_bat.encode('utf-8-sig'))

                # Generate install-all.sh (UTF-8 without BOM is fine for Linux/Mac)
                install_all_sh = generate_install_all_sh(added_skills)
                zf.writestr('install-all.sh', install_all_sh.encode('utf-8'))

                # Add batch README
                batch_readme = generate_batch_readme(added_skills)
                zf.writestr('README.txt', batch_readme.encode('utf-8'))

        # Get ZIP data
        zip_data = zip_buffer.getvalue()

        # Return response with ZIP data
        return Response(
            content=zip_data,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=skills-batch-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Failed to create batch package: {str(e)}")


def generate_install_all_bat(skills: list) -> str:
    """Generate Windows batch script to install all skills."""
    skill_list = '\n'.join([f'echo   - {s["name"]} v{s["version"]}' for s in skills])

    # Build skill installation block
    install_blocks = []
    for skill in skills:
        skill_name = skill['name']
        skill_dir = skill['dir']
        install_blocks.append(f"""
echo 正在安装 {skill_name}...
call :install_skill "{skill_name}" "{skill_dir}"
if %INSTALL_ERRORS% gtr 0 (
    echo {skill_name} 安装失败
)
echo.""")

    install_block_str = '\n'.join(install_blocks)

    content = f"""@echo off
chcp 65001 >nul
title Claude Code Skills 批量安装程序

setlocal EnableDelayedExpansion

echo ========================================
echo   Claude Code Skills 批量安装程序
echo ========================================
echo.
echo 将安装 {len(skills)} 个技能:
{skill_list}
echo.

:: ====================
:: 步骤1: 检测 CLAUDE_SKILLS_PATH
:: ====================
if defined CLAUDE_SKILLS_PATH (
    if exist "%CLAUDE_SKILLS_PATH%" (
        set SKILLS_DIR=%CLAUDE_SKILLS_PATH%
        echo [OK] 从环境变量检测到 Skills 目录: %SKILLS_DIR%
        goto :start_install
    )
)

:: ====================
:: 步骤2: 检测默认路径
:: ====================
set DEFAULT_PATH=%USERPROFILE%\\.claude\\skills
if exist "%DEFAULT_PATH%" (
    set SKILLS_DIR=%DEFAULT_PATH%
    echo [OK] 从默认位置检测到 Skills 目录: %SKILLS_DIR%
    goto :start_install
)

:: ====================
:: 步骤3: 交互式输入
:: ====================
echo.
echo [WARN] 未自动检测到 Claude Code Skills 目录
echo.
echo 常见位置:
echo   - Windows: %%USERPROFILE%%\\.claude\\skills\
echo.

:input_loop
set /p SKILLS_DIR="请输入 Skills 目录完整路径: "

:: 去除首尾空格
for /f "tokens=*" %%a in ("%SKILLS_DIR%") do set SKILLS_DIR=%%a

:: 检查路径是否存在
if not exist "%SKILLS_DIR%" (
    echo [ERR] 路径不存在: %SKILLS_DIR%
    choice /c YN /n /m "是否创建此目录? (Y/N) "
    if errorlevel 2 goto :input_loop
    if errorlevel 1 (
        mkdir "%SKILLS_DIR%" 2>nul
        if errorlevel 1 (
            echo [ERR] 创建目录失败，请检查权限
            goto :input_loop
        )
        echo [OK] 已创建目录: %SKILLS_DIR%
    )
)

:start_install
echo.
echo 目标安装路径: %SKILLS_DIR%
echo.
pause
echo.
echo 开始安装...
echo.

set INSTALL_ERRORS=0
set SCRIPT_DIR=%~dp0

{install_block_str}

echo ========================================
if %INSTALL_ERRORS% == 0 (
    echo 所有技能安装完成!
) else (
    echo 安装完成，部分技能可能未成功 (错误数: %INSTALL_ERRORS%)
)
echo ========================================
echo.
echo 请重启 Claude Code 以加载新技能
echo.
pause
exit /b 0

:: ====================
:: 安装单个技能的子程序
:: ====================
:install_skill
set SKILL_NAME=%~1
set SKILL_DIR=%~2
set SOURCE_PATH=%SCRIPT_DIR%%SKILL_NAME%
set TARGET_PATH=%SKILLS_DIR%\\%SKILL_DIR%

:: 检查源目录是否存在
if not exist "%SOURCE_PATH%" (
    echo [ERR] 未找到技能目录: %SKILL_NAME%
    set /a INSTALL_ERRORS+=1
    exit /b 1
)

:: 检查目标是否已存在
if exist "%TARGET_PATH%" (
    echo [WARN] 技能已存在: %SKILL_DIR%
    choice /c OSB /n /m "请选择 [O]覆盖 [S]跳过 [B]备份: "

    if errorlevel 3 (
        :: 备份
        set BACKUP_NAME=%SKILL_DIR%.backup.%date:~0,4%%date:~5,2%%date:~8,2%-%time:~0,2%%time:~3,2%%time:~6,2%
        set BACKUP_NAME=!BACKUP_NAME: =0!
        rename "%TARGET_PATH%" "!BACKUP_NAME!" >nul 2>&1
        if errorlevel 1 (
            echo [ERR] 备份失败
            set /a INSTALL_ERRORS+=1
            exit /b 1
        )
        echo [OK] 已备份旧版本为: !BACKUP_NAME!
    )

    if errorlevel 2 (
        :: 跳过
        echo [WARN] 已跳过 %SKILL_NAME%
        exit /b 0
    )

    if errorlevel 1 (
        :: 覆盖
        rmdir /s /q "%TARGET_PATH%" >nul 2>&1
        if errorlevel 1 (
            echo [ERR] 删除旧版本失败
            set /a INSTALL_ERRORS+=1
            exit /b 1
        )
        echo [OK] 已删除旧版本
    )
)

:: 执行复制
xcopy "%SOURCE_PATH%" "%TARGET_PATH%\" /s /e /i /q >nul 2>&1
if errorlevel 1 (
    echo [ERR] 复制失败: %SKILL_NAME%
    set /a INSTALL_ERRORS+=1
    exit /b 1
)

echo [OK] %SKILL_NAME% 安装成功
exit /b 0
"""
    return "\ufeff" + content


def generate_install_all_sh(skills: list) -> str:
    """Generate Linux/macOS shell script to install all skills."""
    skill_list = '\n'.join([f'echo "  - {s["name"]} v{s["version"]}"' for s in skills])

    # Build skill installation block
    install_blocks = []
    for skill in skills:
        skill_name = skill['name']
        skill_dir = skill['dir']
        install_blocks.append(f'''echo "安装 {skill_name}..."
install_skill "{skill_name}" "{skill_dir}"
if [ $? -ne 0 ]; then
    INSTALL_ERRORS=$((INSTALL_ERRORS + 1))
fi''')

    install_block_str = '\n'.join(install_blocks)

    return f"""#!/bin/bash

# Claude Code Skills 批量安装脚本

# Colors
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
RED='\\033[0;31m'
CYAN='\\033[0;36m'
NC='\\033[0m'

echo ''
echo -e "${{CYAN}}========================================${{NC}}"
echo -e "${{CYAN}}  Claude Code Skills 批量安装程序${{NC}}"
echo -e "${{CYAN}}========================================${{NC}}"
echo ''
echo "将安装 {len(skills)} 个技能:"
{skill_list}
echo ''

# ====================
# 步骤1: 检测 CLAUDE_SKILLS_PATH
# ====================
if [ -n "$CLAUDE_SKILLS_PATH" ] && [ -d "$CLAUDE_SKILLS_PATH" ]; then
    SKILLS_DIR="$CLAUDE_SKILLS_PATH"
    echo -e "${{GREEN}}[✓]${{NC}} 从环境变量检测到 Skills 目录: $SKILLS_DIR"
elif [ -d "$HOME/.claude/skills" ]; then
    SKILLS_DIR="$HOME/.claude/skills"
    echo -e "${{GREEN}}[✓]${{NC}} 从默认位置检测到 Skills 目录: $SKILLS_DIR"
else
    echo -e "${{YELLOW}}[!]${{NC}} 未自动检测到 Claude Code Skills 目录"
    echo ''
    echo '常见位置:'
    echo '  - macOS/Linux: ~/.claude/skills/'
    echo ''

    while true; do
        read -rp "请输入 Skills 目录完整路径: " SKILLS_DIR
        SKILLS_DIR="${{SKILLS_DIR/#\\~/$HOME}}"
        SKILLS_DIR="$(echo "$SKILLS_DIR" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

        if [ -z "$SKILLS_DIR" ]; then
            echo -e "${{RED}}[✗]${{NC}} 路径不能为空"
            continue
        fi

        if [ ! -d "$SKILLS_DIR" ]; then
            echo -e "${{YELLOW}}[!]${{NC}} 路径不存在: $SKILLS_DIR"
            read -rp "是否创建此目录? (Y/N) " create_choice
            if [[ $create_choice =~ ^[Yy]$ ]]; then
                if mkdir -p "$SKILLS_DIR"; then
                    echo -e "${{GREEN}}[✓]${{NC}} 已创建目录: $SKILLS_DIR"
                    break
                else
                    echo -e "${{RED}}[✗]${{NC}} 创建目录失败，请检查权限"
                    continue
                fi
            else
                continue
            fi
        fi
        break
    done
fi

echo ''
echo "目标安装路径: $SKILLS_DIR"
echo ''
read -rp "按 Enter 键开始安装..."
echo ''
echo "开始安装..."
echo ''

INSTALL_ERRORS=0
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"

# 安装单个技能的函数
install_skill() {{
    local SKILL_NAME="$1"
    local SKILL_DIR="$2"
    local SOURCE_PATH="$SCRIPT_DIR/$SKILL_NAME"
    local TARGET_PATH="$SKILLS_DIR/$SKILL_DIR"

    # 检查源目录
    if [ ! -d "$SOURCE_PATH" ]; then
        echo -e "${{RED}}[✗]${{NC}} 未找到技能目录: $SKILL_NAME"
        return 1
    fi

    # 检查目标是否已存在
    if [ -d "$TARGET_PATH" ]; then
        echo -e "${{YELLOW}}[!]${{NC}} 技能已存在: $SKILL_DIR"
        echo "请选择: [O]覆盖 [S]跳过 [B]备份"
        read -rp "> " choice

        case "$choice" in
            [Bb])
                local BACKUP_NAME="${{SKILL_DIR}}.backup.$(date +%Y%m%d-%H%M%S)"
                if mv "$TARGET_PATH" "$SKILLS_DIR/$BACKUP_NAME"; then
                    echo -e "${{GREEN}}[✓]${{NC}} 已备份旧版本为: $BACKUP_NAME"
                else
                    echo -e "${{RED}}[✗]${{NC}} 备份失败"
                    return 1
                fi
                ;;
            [Ss])
                echo -e "${{YELLOW}}[!]${{NC}} 已跳过 $SKILL_NAME"
                return 0
                ;;
            [Oo]|*)
                rm -rf "$TARGET_PATH"
                if [ $? -eq 0 ]; then
                    echo -e "${{GREEN}}[✓]${{NC}} 已删除旧版本"
                else
                    echo -e "${{RED}}[✗]${{NC}} 删除旧版本失败"
                    return 1
                fi
                ;;
        esac
    fi

    # 执行复制
    if cp -R "$SOURCE_PATH" "$TARGET_PATH"; then
        echo -e "${{GREEN}}[✓]${{NC}} $SKILL_NAME 安装成功"
        return 0
    else
        echo -e "${{RED}}[✗]${{NC}} 复制失败: $SKILL_NAME"
        return 1
    fi
}}

{install_block_str}

echo ''
echo -e "${{CYAN}}========================================${{NC}}"
if [ $INSTALL_ERRORS -eq 0 ]; then
    echo -e "${{GREEN}}所有技能安装完成!${{NC}}"
else
    echo -e "${{YELLOW}}安装完成，部分技能可能未成功 (错误数: $INSTALL_ERRORS)${{NC}}"
fi
echo -e "${{CYAN}}========================================${{NC}}"
echo ''
echo "请重启 Claude Code 以加载新技能"
echo ''
read -rp "按 Enter 键退出..."
"""


def generate_batch_readme(skills: list) -> str:
    """Generate README for batch download package."""
    skill_list = '\n'.join([f"  - {s['name']} v{s['version']}" for s in skills])

    return f"""Claude Code Skills 批量安装包
{'=' * 50}

包含技能 ({len(skills)}个):
{skill_list}

一键安装所有技能:
-----------------
Windows:
  1. 解压此 ZIP 文件
  2. 双击运行 install-all.bat
  3. 按提示完成所有技能的安装

Linux / macOS:
  1. 解压此 ZIP 文件
  2. 打开终端，cd 到解压目录
  3. 运行: chmod +x install-all.sh \u0026\u0026 ./install-all.sh
  4. 按提示完成所有技能的安装

目录结构:
---------
skills-batch/
├── install-all.bat      # Windows 批量安装脚本（安装所有技能）
├── install-all.sh       # Linux/macOS 批量安装脚本（安装所有技能）
├── README.txt           # 本文件
├── skill-name-1/        # 第一个技能目录
│   ├── package.json
│   └── ...
├── skill-name-2/        # 第二个技能目录
│   └── ...
└── ...

注意事项:
---------
1. install-all 脚本会安装所有包含的技能
2. 安装脚本会自动检测 Claude Code Skills 目录
3. 支持设置 CLAUDE_SKILLS_PATH 环境变量指定自定义路径
4. 如果技能已存在，会提示选择：覆盖/跳过/备份
5. 安装完成后需要重启 Claude Code 以加载新技能

单独安装某个技能:
-----------------
如需单独安装某个技能，可以直接将该技能的目录复制到 Claude Code Skills 目录下:
  - Windows: %USERPROFILE%\\.claude\\skills\
  - Linux/Mac: ~/.claude/skills/

或者下载单个技能的安装包（包含独立安装脚本）。

"""


# Health check endpoint for third-party monitoring
@app.get("/api/health")
async def health_check():
    """Health check endpoint for monitoring services.

    Returns:
        Service status information including:
        - status: "healthy" or "unhealthy"
        - timestamp: Current server time
        - version: API version
        - uptime: Service uptime (if available)
    """
    import time

    # Basic health checks
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "service": "Skill Registry"
    }

    # Check if plugins directory is accessible
    try:
        if not PLUGINS_DIR.exists():
            health_status["status"] = "unhealthy"
            health_status["error"] = "Plugins directory not accessible"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)

    # Return appropriate status code
    if health_status["status"] == "healthy":
        return health_status
    else:
        raise HTTPException(status_code=503, detail=health_status)


# Statistics APIs
@app.get("/api/stats/top")
async def api_stats_top(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """Get download statistics with rankings."""
    try:
        # Parse dates
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None

        # Get plugins for author mapping
        plugins = scan_plugins()

        # Get stats with author info
        stats = get_stats_with_author(plugins, start, end)

        return {
            "period": {
                "start_date": start_date or "all-time",
                "end_date": end_date or "all-time"
            },
            "total_downloads": stats["total_downloads"],
            "rankings": stats["rankings"]
        }

    except ValueError as e:
        raise HTTPException(400, f"Invalid date format: {e}")
    except Exception as e:
        raise HTTPException(500, f"Failed to get stats: {e}")


@app.get("/api/stats/export")
async def api_stats_export(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """Export download statistics as Excel file."""
    try:
        import io
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

        # Parse dates
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None

        # Get plugins for author mapping
        plugins = scan_plugins()

        # Get stats with author info
        stats = get_stats_with_author(plugins, start, end)

        # Create Excel workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Download Statistics"

        # Header row
        headers = ["排名", "Skill 名称", "作者", "下载次数"]
        ws.append(headers)

        # Style header
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="667eea", end_color="667eea", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center")

        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment

        # Data rows
        for idx, ranking in enumerate(stats["rankings"], 1):
            ws.append([
                idx,
                ranking["skill_name"],
                ranking["author"],
                ranking["downloads"]
            ])

        # Style data rows
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        for row in range(2, len(stats["rankings"]) + 2):
            for col in range(1, len(headers) + 1):
                cell = ws.cell(row=row, column=col)
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="center" if col in [1, 4] else "left", vertical="center")

        # Adjust column widths
        ws.column_dimensions['A'].width = 10
        ws.column_dimensions['B'].width = 30
        ws.column_dimensions['C'].width = 20
        ws.column_dimensions['D'].width = 15

        # Freeze header row
        ws.freeze_panes = 'A2'

        # Save to memory
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        # Generate filename
        period_str = f"{start_date or 'all'}_to_{end_date or 'all'}"
        filename = f"download_stats_{period_str}.xlsx"

        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except ImportError:
        raise HTTPException(500, "Excel export requires openpyxl: pip install openpyxl")
    except ValueError as e:
        raise HTTPException(400, f"Invalid date format: {e}")
    except Exception as e:
        raise HTTPException(500, f"Failed to export stats: {e}")


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    """Display download statistics page (public access)."""
    return templates.TemplateResponse("stats.html", {
        "request": request
    })


@app.get("/skill/{skill_name}", response_class=HTMLResponse)
async def skill_detail_page(request: Request, skill_name: str):
    """Display skill detail page with Skill.md content."""
    # Check if user is authenticated
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=302)

    # First, try to get the default version from database
    default_version = get_default_skill_version(skill_name)

    skill_zip = None

    if default_version:
        # Use the default version's filename
        skill_zip = PLUGINS_DIR / default_version["filename"]
        if not skill_zip.exists():
            # Default version file not found, fall back to searching
            skill_zip = None

    if not skill_zip:
        # No default version or file not found, try exact match
        skill_zip = PLUGINS_DIR / f"{skill_name}.zip"
        if not skill_zip.exists():
            # Try to find a ZIP that starts with skill_name-
            matching_zips = list(PLUGINS_DIR.glob(f"{skill_name}-*.zip"))
            if matching_zips:
                skill_zip = matching_zips[0]  # Use the first match
            else:
                raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")

    # Extract metadata from the skill
    metadata = extract_metadata(skill_zip.name)

    # Get the real skill name from metadata
    real_skill_name = metadata.get("name", skill_name) if metadata else skill_name

    # Get download count from database
    from database import get_download_stats
    stats = get_download_stats()
    download_count = 0
    for ranking in stats["rankings"]:
        if ranking["skill_name"] == real_skill_name:
            download_count = ranking["downloads"]
            break

    # Get author from metadata
    author = "Unknown"
    if metadata and "metadata" in metadata:
        author_meta = metadata["metadata"].get("author", "Unknown")
        if isinstance(author_meta, dict):
            author = author_meta.get("name", "Unknown")
        else:
            author = str(author_meta) if author_meta else "Unknown"

    # Get version
    version = metadata.get("version", "1.0.0") if metadata else "1.0.0"

    # Get updated_at from file modification time
    updated_at = datetime.fromtimestamp(skill_zip.stat().st_mtime).strftime("%Y-%m-%d")

    # Get current user
    user = get_current_user(request)

    return templates.TemplateResponse("skill_detail.html", {
        "request": request,
        "skill_name": real_skill_name,
        "author": author,
        "download_count": download_count,
        "version": version,
        "updated_at": updated_at,
        "download_url": f"/plugins/{skill_zip.name}",
        "user": user
    })


@app.get("/api/skill/{skill_name}/content")
async def get_skill_content_api(skill_name: str):
    """Get Skill.md content for a skill.

    Returns the complete SKILL.md file content (including YAML frontmatter).
    """
    print(f"[DEBUG] API called with skill_name: '{skill_name}'")

    # Find the skill ZIP file
    # First try exact match, then try with version pattern
    skill_zip = PLUGINS_DIR / f"{skill_name}.zip"
    print(f"[DEBUG] Trying exact match: {skill_zip}, exists: {skill_zip.exists()}")

    if not skill_zip.exists():
        # Try to find a ZIP that starts with skill_name-
        matching_zips = list(PLUGINS_DIR.glob(f"{skill_name}-*.zip"))
        print(f"[DEBUG] Pattern match found: {len(matching_zips)} files")
        if matching_zips:
            skill_zip = matching_zips[0]  # Use the first match
            print(f"[DEBUG] Using: {skill_zip}")
        else:
            raise HTTPException(status_code=404, detail=f"Skill ZIP file not found for: {skill_name}")

    try:
        import zipfile

        with zipfile.ZipFile(skill_zip, 'r') as zf:
            # Find SKILL.md (may be in root or subdirectory)
            skill_md_paths = [name for name in zf.namelist()
                             if 'SKILL.md' in name or name.endswith('SKILL.md')]

            print(f"[DEBUG] Found SKILL.md files: {skill_md_paths}")

            if not skill_md_paths:
                return {"content": None}

            # Read SKILL.md content
            skill_md_path = skill_md_paths[0]
            content = zf.read(skill_md_path).decode('utf-8')

            print(f"[DEBUG] SKILL.md content length: {len(content)} bytes")

            # Return the complete SKILL.md content (including YAML frontmatter)
            return {"content": content}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read skill content: {str(e)}"
        )


@app.get("/api/admin/stats")
async def api_admin_stats(
    _: bool = Depends(require_admin)
):
    """Get admin statistics (admin only).

    Returns comprehensive statistics about the registry including:
    - Total users count
    - Pending skills count
    - Approved skills count
    - Today's downloads count
    - Top 10 skills by downloads
    - Top 10 users by downloads
    """
    try:
        # Get counts
        total_users = get_total_users_count()
        pending_skills = get_skills_count_by_status("pending")
        approved_skills = get_skills_count_by_status("approved")
        today_downloads = get_today_downloads_count()

        # Get top rankings
        top_skills = get_top_skills_by_downloads(10)
        top_users = get_top_users_by_downloads(10)

        return {
            "success": True,
            "data": {
                "total_users": total_users,
                "pending_skills": pending_skills,
                "approved_skills": approved_skills,
                "today_downloads": today_downloads,
                "top_skills": top_skills,
                "top_users": top_users
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch admin statistics: {str(e)}"
        )


@app.put("/api/admin/skills/{skill_id}/source-type")
async def api_update_skill_source_type(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_admin)
):
    """Update the source_type of a skill (admin only).

    Expects JSON body with:
    {
        "source_type": "opensource" | "icsl" | "huawei"
    }
    """
    try:
        # Get current user
        reviewer_id = request.session.get("user_id")
        if not reviewer_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        # Parse request body
        data = await request.json()
        source_type = data.get("source_type")

        # Validate source_type
        valid_types = ["opensource", "icsl", "huawei"]
        if source_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source_type. Must be one of: {', '.join(valid_types)}"
            )

        # Get skill record
        skill = get_skill_by_id(skill_id)
        if not skill:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill {skill_id} not found"
            )

        # Update source_type in database
        from database import get_connection
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE skills
                SET source_type = %s
                WHERE id = %s
                """,
                (source_type, skill_id)
            )
            conn.commit()

        return {
            "success": True,
            "message": f"Updated source_type for {skill['skill_name']} to {source_type}",
            "skill_id": skill_id,
            "source_type": source_type
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update source_type: {str(e)}"
        )


@app.get("/api/admin/skills")
async def api_get_all_skills(
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Get all skills with optional status filter (admin only).

    Args:
        status: Filter by status (pending/approved/rejected)
        limit: Maximum number of skills to return

    Returns:
        List of skills with full details
    """
    try:
        from database import get_connection

        with get_connection() as conn:
            if status:
                rows = conn.execute("""
                    SELECT s.id, s.skill_name, s.version, s.filename, s.status,
                           s.source_type, s.uploaded_at, u.employee_id as uploader_name
                    FROM skills s
                    LEFT JOIN users u ON s.uploader_id = u.id
                    WHERE s.status = %s
                    ORDER BY s.uploaded_at DESC
                    LIMIT %s
                """, (status, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT s.id, s.skill_name, s.version, s.filename, s.status,
                           s.source_type, s.uploaded_at, u.employee_id as uploader_name
                    FROM skills s
                    LEFT JOIN users u ON s.uploader_id = u.id
                    ORDER BY s.uploaded_at DESC
                    LIMIT %s
                """, (limit,)).fetchall()

            return {
                "success": True,
                "data": rows,
                "count": len(rows)
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch skills: {str(e)}"
        )


@app.get("/api/admin/gitea-tasks")
async def api_get_gitea_tasks(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Get Gitea push tasks with optional status filter.

    Args:
        status: Filter by status (pending/pushing/success/failed)
        limit: Maximum number of tasks to return

    Returns:
        List of push tasks with skill info
    """
    try:
        from database import get_connection

        with get_connection() as conn:
            if status:
                rows = conn.execute("""
                    SELECT t.*, s.skill_name, s.uploader_id, u.employee_id as uploader_name
                    FROM gitea_push_tasks t
                    JOIN skills s ON t.skill_id = s.id
                    LEFT JOIN users u ON s.uploader_id = u.id
                    WHERE t.status = %s
                    ORDER BY t.created_at DESC
                    LIMIT %s
                """, (status, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT t.*, s.skill_name, s.uploader_id, u.employee_id as uploader_name
                    FROM gitea_push_tasks t
                    JOIN skills s ON t.skill_id = s.id
                    LEFT JOIN users u ON s.uploader_id = u.id
                    ORDER BY t.created_at DESC
                    LIMIT %s
                """, (limit,)).fetchall()

            return {
                "success": True,
                "data": rows,
                "count": len(rows)
            }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tasks: {str(e)}"
        )


# ==================== User Management API Endpoints ====================

@app.get("/api/admin/users")
async def api_get_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    role: Optional[str] = Query(None, regex="^(admin|user)$"),
    status_filter: Optional[str] = Query(None, regex="^(active|disabled)$"),
    search: Optional[str] = Query(None, max_length=50),
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Get paginated list of users with optional filters.

    Query params:
        page: Page number (default: 1)
        per_page: Users per page (default: 20, max: 100)
        role: Filter by role ('admin' or 'user')
        status_filter: Filter by status ('active' or 'disabled')
        search: Search by employee_id (partial match)

    Returns:
        Paginated user list with total count
    """
    try:
        result = get_users_list(
            page=page,
            per_page=per_page,
            role=role,
            status_filter=status_filter,
            search=search
        )
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )


@app.post("/api/admin/users")
async def api_create_user(
    request: Request,
    employee_id: str = Form(..., max_length=50),
    role: str = Form(..., regex="^(admin|user)$"),
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Create a new user.

    Form data:
        employee_id: Employee ID (alphanumeric, max 50 chars)
        role: User role ('admin' or 'user')

    Returns:
        Created user data with API key (shown only once)
    """
    try:
        # Validate employee_id format
        if not employee_id or not re.match(r'^[a-zA-Z0-9_-]+$', employee_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid employee_id format. Must be alphanumeric with underscores/hyphens only."
            )

        # Check if employee_id already exists
        existing_user = get_user_by_credentials(employee_id, "dummy")
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with employee_id '{employee_id}' already exists"
            )

        # Generate 32-char API key
        api_key = secrets.token_hex(16)

        # Create user
        user_id = create_user(employee_id=employee_id, api_key=api_key, role=role)

        # Get the created user
        user = get_user_by_id(user_id)

        return {
            "success": True,
            "data": {
                "id": user["id"],
                "employee_id": user["employee_id"],
                "role": user["role"],
                "api_key": api_key,  # Only shown once on creation
                "created_at": user["created_at"]
            },
            "message": "User created successfully. Save the API key now as it won't be shown again."
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@app.put("/api/admin/users/{user_id}")
async def api_update_user_role(
    user_id: int,
    request: Request,
    role: str = Form(..., regex="^(admin|user)$"),
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Update a user's role.

    Form data:
        role: New role ('admin' or 'user')

    Prevents editing own role.
    """
    try:
        # Prevent editing own role
        current_user_id = request.session.get("user_id")
        if current_user_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify your own role"
            )

        # Check if user exists
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Update role
        success = update_user_role(user_id, role)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to update user role"
            )

        return {
            "success": True,
            "data": {
                "id": user_id,
                "employee_id": user["employee_id"],
                "role": role
            },
            "message": "User role updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user role: {str(e)}"
        )


@app.delete("/api/admin/users/{user_id}")
async def api_disable_user(
    user_id: int,
    request: Request,
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Disable (soft delete) a user.

    Prevents disabling if user has active skills (skills_count > 0).
    Prevents disabling self.
    """
    try:
        # Prevent disabling self
        current_user_id = request.session.get("user_id")
        if current_user_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot disable your own account"
            )

        # Check if user exists
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Check if user has active skills
        skills_count = get_user_skills_count(user_id)
        if skills_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot disable user with {skills_count} active skill(s). Please reassign or remove skills first."
            )

        # Disable user
        success = disable_user(user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to disable user"
            )

        return {
            "success": True,
            "data": {
                "id": user_id,
                "employee_id": user["employee_id"],
                "status": "disabled"
            },
            "message": "User disabled successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable user: {str(e)}"
        )


@app.patch("/api/admin/users/{user_id}/enable")
async def api_enable_user(
    user_id: int,
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Re-enable a disabled user.

    Sets status back to 'active'.
    """
    try:
        # Check if user exists
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Enable user
        success = enable_user(user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to enable user"
            )

        return {
            "success": True,
            "data": {
                "id": user_id,
                "employee_id": user["employee_id"],
                "status": "active"
            },
            "message": "User enabled successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable user: {str(e)}"
        )


@app.post("/api/admin/users/{user_id}/reset-key")
async def api_reset_user_api_key(
    user_id: int,
    _: bool = Depends(require_admin)
) -> Dict[str, Any]:
    """Reset a user's API key.

    Generates a new 32-character API key.
    Old key is immediately invalidated.
    Rate limited to once per 5 minutes per user.
    """
    try:
        # Check rate limit (5 minutes)
        from datetime import timedelta
        rate_limit_minutes = 5
        current_time = datetime.now()

        if user_id in _api_key_reset_times:
            last_reset_time = _api_key_reset_times[user_id]
            time_since_reset = current_time - last_reset_time
            if time_since_reset < timedelta(minutes=rate_limit_minutes):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"API key reset too frequently. Please wait {rate_limit_minutes} minutes between resets."
                )

        # Check if user exists
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Generate new API key
        new_api_key = secrets.token_hex(16)

        # Reset API key
        success = reset_user_api_key(user_id, new_api_key)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to reset API key"
            )

        # Store reset time after successful reset
        _api_key_reset_times[user_id] = current_time

        return {
            "success": True,
            "data": {
                "id": user_id,
                "employee_id": user["employee_id"],
                "api_key": new_api_key
            },
            "message": "API key reset successfully. Save the new key now as it won't be shown again."
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset API key: {str(e)}"
        )


# ==================== UI Routes ====================

@app.get("/admin/gitea-tasks", response_class=HTMLResponse)
async def gitea_tasks_page(request: Request):
    """Display Gitea push tasks status page."""
    return templates.TemplateResponse("gitea_tasks.html", {
        "request": request
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=28000)
