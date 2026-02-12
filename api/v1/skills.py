"""
Skills API v1 Routes

This module contains all skill-related routes:
- GET /api/skills - List all skills (paginated)
- GET /api/skills/{name} - Get skill details
- GET /plugins/{filename} - Download skill ZIP file
- POST /api/upload - Upload skill ZIP file
"""

import logging
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from database import (
    create_skill_record,
    get_skill_by_id,
    get_skill_versions,
    record_download,
)
from logging_config import audit_log

logger = logging.getLogger("skillhub")

# Configuration
PLUGINS_DIR = Path("./plugins")
PENDING_DIR = Path("./data/pending")

templates = Jinja2Templates(directory="templates")

router = APIRouter()


# Helper functions migrated from main.py

def parse_skill_md(content: str) -> Tuple[Optional[dict], str]:
    """Parse SKILL.md content to extract YAML frontmatter and markdown body.

    Args:
        content: Raw SKILL.md content

    Returns:
        Tuple of (yaml_metadata_dict, markdown_body)
        If no YAML frontmatter found, returns (None, content)
    """
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

    Args:
        zip_path: Path to the skill ZIP file

    Returns:
        Metadata dict or None if parsing fails
    """
    import zipfile

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()

            skill_md_paths = [name for name in namelist
                             if name.endswith('SKILL.md') or name == 'SKILL.md']

            if not skill_md_paths:
                return None

            skill_md_path = skill_md_paths[0]
            content = zf.read(skill_md_path).decode('utf-8')

            metadata, _ = parse_skill_md(content)
            return metadata

    except Exception as e:
        logger.warning(f"Failed to extract metadata from {zip_path}: {e}")
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


def get_skill_dir_name(filename: str) -> str:
    """Extract skill directory name from ZIP filename.

    Args:
        filename: ZIP filename (e.g., "skill-name-1.0.0.zip")

    Returns:
        Directory name (e.g., "skill-name")
    """
    return filename[:-4] if filename.endswith('.zip') else filename


def parse_plugin_filename(filename: str) -> tuple[str, str]:
    """Parse plugin filename to extract skill name.

    Format: {skill-name}.zip (version is in SKILL.md metadata)

    Returns: (skill_name, "unknown")
    """
    skill_name = filename[:-4] if filename.endswith('.zip') else filename
    return skill_name, "unknown"


def extract_metadata(zip_filename: str) -> Optional[dict]:
    """Extract metadata from SKILL.md inside zip.

    Args:
        zip_filename: Name of the ZIP file

    Returns:
        Metadata dict or fallback info
    """
    import json

    zip_path = PLUGINS_DIR / zip_filename
    skill_name, version = parse_plugin_filename(zip_filename)

    metadata = extract_metadata_from_skill_md(zip_path)

    if metadata:
        skill_metadata = metadata.get("metadata", {})
        if isinstance(skill_metadata, dict):
            spec_version = skill_metadata.get("version")
        else:
            spec_version = None
            skill_metadata = {}

        author = skill_metadata.get("author") or metadata.get("author")
        normalized = {
            "name": metadata.get("name", skill_name),
            "version": spec_version if spec_version else (version if version != "unknown" else "1.0.0"),
            "description": metadata.get("description", "No description available"),
            "author": author,
            "license": metadata.get("license"),
            "compatibility": metadata.get("compatibility"),
            "metadata": {**skill_metadata, "author": author},
            "allowed_tools": metadata.get("allowed-tools")
        }
        return normalized

    # Fallback: try legacy package.json format
    try:
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()

            for name in namelist:
                if name == 'package.json' or (name.endswith('/package.json')):
                    content = zf.read(name)
                    legacy_metadata = json.loads(content)
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


def validate_skill_zip(zip_path: Path) -> tuple[bool, dict]:
    """Validate a skill ZIP file according to Agent Skills specification.

    Args:
        zip_path: Path to the skill ZIP file

    Returns:
        (is_valid, metadata or error_info)
    """
    import zipfile

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()

            skill_md_paths = [name for name in namelist
                             if name.endswith('SKILL.md') or name == 'SKILL.md']

            if not skill_md_paths:
                return False, {"error": "Missing SKILL.md in ZIP"}

            skill_md_path = skill_md_paths[0]
            content = zf.read(skill_md_path).decode('utf-8')
            metadata, _ = parse_skill_md(content)

            if metadata is None:
                return False, {"error": "Invalid YAML frontmatter in SKILL.md"}

            # Validate required fields
            required_fields = ["name", "description"]
            for field in required_fields:
                if field not in metadata:
                    return False, {"error": f"Missing required field '{field}' in SKILL.md YAML frontmatter"}

            # Validate skill name
            skill_name = metadata.get("name")
            is_valid_name, name_error = validate_skill_name(skill_name)
            if not is_valid_name:
                return False, {"error": f"Invalid skill name: {name_error}"}

            # Validate metadata.version and metadata.author
            skill_metadata = metadata.get("metadata", {})
            if not isinstance(skill_metadata, dict):
                skill_metadata = {}

            version = skill_metadata.get("version")
            if not version or not isinstance(version, str) or not version.strip():
                return False, {"error": "Missing required field 'metadata.version' in SKILL.md"}

            author = skill_metadata.get("author")
            if not author or not isinstance(author, str) or not author.strip():
                return False, {"error": "Missing required field 'metadata.author' in SKILL.md"}

            return True, metadata

    except zipfile.BadZipFile:
        return False, {"error": "Invalid ZIP file"}
    except Exception as e:
        return False, {"error": str(e)}


def require_auth(request: Request) -> bool:
    """Dependency to require authentication."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return True


def scan_plugins() -> List[dict]:
    """Get approved and active skills from database with metadata from ZIP files.

    Returns:
        List of skill dictionaries with metadata
    """
    result = []

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

            if skill_name not in skills_by_name or is_default:
                skills_by_name[skill_name] = row
            elif not skills_by_name[skill_name]["is_default_version"]:
                continue

        # Build result list with metadata from ZIP files
        for skill_name, row in skills_by_name.items():
            metadata = extract_metadata(row["filename"])
            if not metadata:
                metadata = {
                    "name": skill_name,
                    "description": f"{skill_name} - 技能描述",
                    "version": row["version"],
                    "license": None,
                    "compatibility": None,
                    "metadata": {"version": row["version"], "author": "未知"},
                    "allowed_tools": None
                }

            result.append({
                "name": skill_name,
                "metadata": metadata,
                "latest_version": row["version"],
                "source_type": row["source_type"] or "opensource",
                "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
                "download_count": 0,
                "versions": [{
                    "version": row["version"],
                    "filename": row["filename"]
                }]
            })

    return result


# API Routes

@router.get("/api/skills")
async def api_skills(page: int = 1, per_page: int = 1000):
    """API endpoint for skill list with pagination support.

    Args:
        page: Page number (1-indexed)
        per_page: Number of items per page

    Returns:
        JSON response with paginated skills
    """
    all_plugins = scan_plugins()

    total = len(all_plugins)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    paginated_plugins = all_plugins[start_idx:end_idx]

    return {
        "data": paginated_plugins,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    }


@router.get("/api/skills/{name}")
async def api_skill_detail(name: str):
    """API endpoint for skill detail by name.

    Args:
        name: Skill name

    Returns:
        JSON response with skill details including versions
    """
    from database import get_connection

    with get_connection() as conn:
        # Get all approved versions of this skill
        rows = conn.execute(
            """
            SELECT
                id, skill_name, version, filename, uploader_id, status,
                source_type, uploaded_at, reviewed_at, reviewer_id,
                review_comment, is_active, is_default_version
            FROM skills
            WHERE skill_name = ? AND status = 'approved' AND is_active = 1
            ORDER BY uploaded_at DESC
            """,
            (name,)
        ).fetchall()

        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Skill '{name}' not found"
            )

        # Get metadata for each version
        versions = []
        for row in rows:
            metadata = extract_metadata(row["filename"])
            versions.append({
                "version": row["version"],
                "filename": row["filename"],
                "is_default": bool(row["is_default_version"]),
                "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
                "metadata": metadata
            })

        # Find default version
        default_version = next((v for v in versions if v["is_default"]), versions[0])

        return {
            "name": name,
            "metadata": default_version["metadata"],
            "versions": versions
        }


@router.get("/plugins/{filename}")
async def download_plugin(filename: str, request: Request):
    """Download plugin ZIP file (original uploaded file).

    Args:
        filename: Name of the plugin file
        request: HTTP request

    Returns:
        Original ZIP file as uploaded by the user
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    file_path = PLUGINS_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Plugin not found")

    skill_name = filename[:-4] if filename.endswith('.zip') else filename

    metadata = extract_metadata_from_skill_md(file_path)
    if metadata and metadata.get("metadata"):
        version = metadata.get("metadata", {}).get("version", "unknown")
    else:
        version = "unknown"

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
        logger.warning(f"Failed to record download: {e}")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/zip"
    )


@router.post("/api/upload")
async def upload_plugin(
    request: Request,
    file: UploadFile = File(...),
    source_type: str = Form(default="opensource"),
    _: bool = Depends(require_auth)
):
    """Upload a single skill ZIP file (requires auth).

    Saves to pending directory and creates database record with status='pending'.
    Requires admin approval before being made available.

    Args:
        request: HTTP request
        file: Uploaded ZIP file
        source_type: Source type (opensource or internal)

    Returns:
        JSON response with upload result
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "error": "请先登录"}
        )

    if not file.filename or not file.filename.endswith('.zip'):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "error": "只支持 ZIP 格式的文件"}
        )

    temp_dir = tempfile.mkdtemp()
    temp_zip = Path(temp_dir) / "upload.zip"

    try:
        with open(temp_zip, "wb") as f:
            shutil.copyfileobj(file.file, f)

        is_valid, result = validate_skill_zip(temp_zip)

        if not is_valid:
            error_msg = result.get('error', 'Unknown error')

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

            if "Invalid skill name:" in error_msg:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"success": False, "error": f"技能名称格式错误: {error_msg.split(':', 1)[1].strip() if ':' in error_msg else error_msg}"}
                )

            user_friendly_error = error_messages.get(error_msg, error_msg)

            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"success": False, "error": user_friendly_error}
            )

        skill_name = result["name"]
        version = result.get("version", "1.0.0")
        target_filename = f"{skill_name}-{version}.zip"
        target_path = PENDING_DIR / target_filename

        from database import check_skill_exists
        if check_skill_exists(skill_name, version):
            error_msg = f"技能 {skill_name}@{version} 已存在，请使用不同的版本号"
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"success": False, "error": error_msg}
            )

        shutil.copy(temp_zip, target_path)

        skill_id = create_skill_record(
            skill_name=skill_name,
            version=version,
            filename=target_filename,
            uploader_id=user_id,
            status='pending',
            source_type=source_type
        )

        success_msg = f"成功上传 {result['name']}@{result['version']}，等待管理员审核"

        audit_log(
            action="skill_upload",
            user_id=user_id,
            details={"skill_name": skill_name, "version": version, "skill_id": skill_id}
        )

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
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": error_msg}
        )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# Router Initialization
# ============================================================================

def init_skills_router(templates_instance: Jinja2Templates) -> APIRouter:
    """Initialize and return the skills router.

    This function is called from the v1 package to integrate
    skills routes into the main API router.

    Args:
        templates_instance: Jinja2Templates instance for rendering templates

    Returns:
        Configured APIRouter with all skills routes
    """
    global templates
    templates = templates_instance
    return router
