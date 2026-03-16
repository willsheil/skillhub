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
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

import yaml
import markdown
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, status, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel

# Import and setup logging configuration
from utils.logging_config import setup_logging, audit_log, PerformanceTracker

# Initialize logging system
setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_dir="./logs",
    enable_json=True,
    enable_console=True
)

# Configuration
PLUGINS_DIR = Path(os.getenv("PLUGINS_DIR", "./plugins"))
PLUGINS_DIR.mkdir(exist_ok=True)

# Markdown extensions for rendering
MARKDOWN_EXTENSIONS = ["tables", "fenced_code", "toc", "nl2br"]

# Pending uploads directory
PENDING_DIR = Path("./data/pending")
PENDING_DIR.mkdir(parents=True, exist_ok=True)

# Import database module (only used functions)
from database import init_db, record_download, get_user_by_id

# Configure logging - get application logger with proper configuration
logger = logging.getLogger("skillhub")

# Admin credentials (can be overridden via environment variables)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # 默认密码，生产环境应修改

# Session secret key (should be changed in production)
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")

# API key reset rate limiting (user_id -> last_reset_time)
_api_key_reset_times = {}


# Global scheduler instance
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    init_db()

    # Start Gitea push service if configured
    gitea_url = os.getenv("GITEA_REPO_URL")
    logger.info(f"GITEA_REPO_URL = {gitea_url}")
    if gitea_url:
        try:
            logger.info("Starting Gitea push service with APScheduler...")
            from services.gitea import GiteaPushService

            push_service = GiteaPushService(
                interval=int(os.getenv("GITEA_PUSH_INTERVAL", "30"))
            )

            # Import the sync wrapper
            from services.gitea.gitea_push_service import run_push_task

            # Start APScheduler with interval trigger
            interval_seconds = int(os.getenv("GITEA_PUSH_INTERVAL", "30"))
            scheduler.add_job(
                run_push_task,
                trigger=IntervalTrigger(seconds=interval_seconds),
                id="gitea_push_task",
                name="Gitea Push Service",
                replace_existing=True
            )
            scheduler.start()
            logger.info(f"Gitea push service scheduled every {interval_seconds} seconds")
        except Exception as e:
            import traceback
            logger.error(f"Failed to start Gitea push service: {e}")
            logger.error(traceback.format_exc())
    else:
        logger.info("Gitea integration disabled (GITEA_REPO_URL not set)")

    yield

    # Shutdown
    logger.info("Shutting down...")
    scheduler.shutdown()


app = FastAPI(
    title="SkillHub API",
    description="Claude Code 技能插件管理系统 API",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    lifespan=lifespan
)

# Register external API v1 router
from apps import router as api_v1_router
app.include_router(api_v1_router)

# 配置 API Key 安全方案
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="SkillHub External API",
        version="1.0.0",
        routes=app.routes,
    )

    # 添加安全方案
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "请输入您的 API Key"
        }
    }

    # 全局应用安全方案
    for path in openapi_schema["paths"].values():
        for operation in path.values():
            operation["security"] = [{"ApiKeyAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Add session middleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Set templates for pages router
from apps.pages import set_templates
set_templates(templates)


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

    # 快速检查文件是否存在，避免不必要的异常处理和日志
    if not zip_path.exists():
        return None

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
        logger.debug(f"Failed to extract metadata from {zip_path}: {e}")
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
            ORDER BY skill_name, is_default_version DESC, version DESC
            """
        ).fetchall()

        # Deduplicate: only keep the first (default/latest) version for each skill
        seen_skills = set()
        deduplicated_rows = []
        for row in rows:
            if row["skill_name"] not in seen_skills:
                seen_skills.add(row["skill_name"])
                deduplicated_rows.append(row)
        rows = deduplicated_rows

        # Build result list with metadata from ZIP files
        for row in rows:
            skill_name = row["skill_name"]
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
                    "metadata": {"version": row["version"], "author": "未知"},
                    "allowed_tools": None
                }

            # Get uploader employee_id from database
            uploader_id = row.get("uploader_id")
            uploader_employee_id = None
            if uploader_id:
                try:
                    uploader_row = conn.execute(
                        "SELECT employee_id FROM users WHERE id = %s",
                        (uploader_id,)
                    ).fetchone()
                    if uploader_row:
                        uploader_employee_id = uploader_row["employee_id"]
                except Exception:
                    pass

            # Use uploader employee_id as author if no author in metadata
            if uploader_employee_id:
                inner_meta = metadata.get("metadata", {})
                if not inner_meta.get("author"):
                    metadata["metadata"] = {**inner_meta, "author": uploader_employee_id}

            # Get file size
            file_size = 0
            plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
            file_path = os.path.join(plugins_dir, row["filename"])
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)

            # Extract category from metadata
            inner_meta = metadata.get("metadata", {})
            category = inner_meta.get("category") if isinstance(inner_meta, dict) else None

            result.append({
                "name": skill_name,
                "metadata": metadata,
                "category": category,  # Add category field
                "latest_version": row["version"],
                "source_type": row["source_type"] or "opensource",
                "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
                "updated_at": row["uploaded_at"].strftime("%Y-%m-%d") if row["uploaded_at"] else None,
                "download_count": 0,  # TODO: Add download count if tracking
                "rating": 4.5,  # Default rating, TODO: Add actual rating
                "uploader_employee_id": uploader_employee_id,  # Add uploader info
                "versions": [{
                    "version": row["version"],
                    "filename": row["filename"],
                    "size": file_size,
                    "updated_at": row["uploaded_at"].strftime("%Y-%m-%d") if row["uploaded_at"] else None
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

    # 快速检查文件是否存在，避免不必要的 ZIP 操作和日志
    if not zip_path.exists():
        return {
            "name": skill_name,
            "description": f"{skill_name} - 技能描述",
            "version": version if version != "unknown" else "1.0.0",
            "author": None,
            "license": None,
            "compatibility": None,
            "metadata": {"version": version, "author": "未知"},
            "allowed_tools": None
        }

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
        # Author is in metadata.author from SKILL.md
        author = skill_metadata.get("author") or metadata.get("author")
        normalized = {
            "name": metadata.get("name", skill_name),
            "version": spec_version if spec_version else (version if version != "unknown" else "1.0.0"),
            "description": metadata.get("description", "No description available"),
            "author": author,  # Include author field
            "license": metadata.get("license"),
            "compatibility": metadata.get("compatibility"),
            "metadata": {**skill_metadata, "author": author},  # Include author in metadata for frontend
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
        "metadata": {"author": "未知"}
    }


# 隐藏安装指南页面


@lru_cache(maxsize=1)
def _get_spec_html() -> str:
    """Load and render the spec markdown file once, cache result."""
    spec_file = Path(__file__).parent / "docs" / "skill_specification_v1.md"
    try:
        with open(spec_file, "r", encoding="utf-8") as f:
            return markdown.markdown(f.read(), extensions=MARKDOWN_EXTENSIONS)
    except (FileNotFoundError, OSError):
        return "<h1>规范文档未找到</h1><p>请联系管理员添加规范文档。</p>"



@app.get("/.well-known/skills/index.json")
async def skills_well_known_index(request: Request):
    """Skills index for npx skills CLI.

    Format follows vercel-labs/skills WellKnownIndex specification:
    - name: skill identifier (required)
    - description: skill description (required)
    - files: array of files in the skill (required, must include SKILL.md)
    """
    plugins = scan_plugins()

    skills_index = {
        "skills": []
    }

    for plugin in plugins:
        meta = plugin["metadata"]
        latest = plugin["versions"][-1]
        skill_name = meta.get("name", plugin["name"])

        # Normalize skill name: lowercase, alphanumeric and hyphens only
        normalized_name = skill_name.lower().replace("_", "-")
        # Remove any characters that aren't alphanumeric or hyphens
        import re
        normalized_name = re.sub(r'[^a-z0-9-]', '-', normalized_name)
        normalized_name = re.sub(r'-+', '-', normalized_name).strip('-')

        skills_index["skills"].append({
            "name": normalized_name,
            "description": meta.get("description", "No description"),
            "files": ["SKILL.md"]
        })

    return skills_index



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
async def download_plugin(filename: str, request: Request):
    """Download plugin ZIP file (original uploaded file).

    Public endpoint - no authentication required for downloads.

    Args:
        filename: Name of the plugin file
        request: HTTP request

    Returns:
        Original ZIP file as uploaded by the user
    """
    # No authentication required - public download
    user_id = request.session.get("user_id")

    file_path = PLUGINS_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Get skill name from filename (version is now in SKILL.md metadata)
    skill_name = filename[:-4] if filename.endswith('.zip') else filename

    # Extract version from SKILL.md inside the ZIP for download tracking
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
        logger.warning(f"Failed to record download: {e}", extra={"skill_name": skill_name, "filename": filename})

    # Return original ZIP file
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/zip"
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


def validate_skill_zip(zip_path: Path, allow_missing: bool = False, default_author: str = None) -> tuple[bool, dict]:
    """Validate a skill ZIP file according to Agent Skills specification.

    Args:
        zip_path: Path to the ZIP file
        allow_missing: If True, return missing fields info instead of rejecting
        default_author: Default author to use if not specified in SKILL.md

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
        allow_missing: If True, return missing fields info instead of rejecting

    Returns:
        (is_valid, metadata or error_info)
        When allow_missing=True and fields are missing, returns:
        (False, {"error": "MISSING_FIELDS", "missing_fields": [...], "metadata": {...}})
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
            metadata, markdown_body = parse_skill_md(content)

            warnings = []

            # If YAML parsing fails, try to extract info from content
            if metadata is None:
                warnings.append("SKILL.md 的 YAML 格式无法解析，将使用默认值")
                metadata = {}

            # Extract name - try to get from ZIP filename if missing
            skill_name = metadata.get("name")
            if not skill_name:
                # Try to extract from ZIP filename (e.g., skill-name-1.0.0.zip -> skill-name)
                zip_name = zip_path.stem
                import re
                # Remove version suffix like -1.0.0, -1.0, etc.
                skill_name = re.sub(r'-\d+(\.\d+)*$', '', zip_name)
                warnings.append(f"未找到 name 字段，将使用文件名: {skill_name}")

            # Extract description - use markdown body or default
            description = metadata.get("description")
            if not description:
                # Use first line of markdown body as description
                if markdown_body:
                    first_line = markdown_body.strip().split('\n')[0][:200]
                    description = first_line if first_line else f"Skill: {skill_name}"
                else:
                    description = f"Skill: {skill_name}"
                warnings.append("未找到 description 字段，将使用默认描述")

            # Validate name format - DISABLED: 取消name格式校验
            # Validate description length (max 1024 chars)
            if not isinstance(description, str) or len(description) == 0 or len(description) > 1024:
                description = description[:1024] if description else f"Skill: {skill_name}"

            # Validate optional fields if present
            # compatibility: max 500 chars
            if "compatibility" in metadata:
                compat = metadata["compatibility"]
                if not isinstance(compat, str) or len(compat) == 0 or len(compat) > 500:
                    return False, {"error": "Compatibility must be 1-500 characters if provided"}

            # Extract metadata fields (version and author are optional, will use defaults if missing)
            skill_metadata = metadata.get("metadata") or {}
            # If metadata is None or not a dict (e.g., empty in YAML), use empty dict
            if skill_metadata and not isinstance(skill_metadata, dict):
                return False, {"error": "Metadata must be a key-value mapping"}

            # 获取 version 和 author，如果未填写则使用默认值
            version = skill_metadata.get("version") or "1.0.0"  # 默认版本号
            # author 如果未填写，使用传入的 default_author（上传用户的id）
            author = skill_metadata.get("author") or default_author

            # Normalize metadata for return (matching API format)
            normalized_metadata = {
                "name": skill_name,
                "description": description,
                "version": version,
                "author": author,
                "license": metadata.get("license"),
                "compatibility": metadata.get("compatibility"),
                "metadata": skill_metadata,
                "allowed_tools": metadata.get("allowed-tools")
            }

            # Add warnings to metadata if any
            if warnings:
                normalized_metadata["_warnings"] = warnings

            return True, normalized_metadata

    except zipfile.BadZipFile:
        return False, {"error": "Invalid ZIP file"}
    except yaml.YAMLError as e:
        return False, {"error": f"Invalid YAML in SKILL.md: {str(e)}"}
    except Exception as e:
        return False, {"error": str(e)}






@app.delete("/admin/plugins/{filename}")
async def delete_plugin(
    filename: str,
):
    """Delete a plugin (admin only)."""
    file_path = PLUGINS_DIR / filename

    if not file_path.exists():
        raise HTTPException(404, "Plugin not found")

    file_path.unlink()

    return {"success": True, "message": f"Deleted {filename}"}






if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=28000)
