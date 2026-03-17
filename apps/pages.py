"""HTML page routes."""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

router = APIRouter()

# templates 会在 main.py 初始化后导入
_templates = None


def set_templates(templates):
    """Set templates for pages router."""
    global _templates
    _templates = templates


def get_templates():
    """Get templates, raise if not set."""
    if _templates is None:
        raise RuntimeError("Templates not initialized. Call set_templates() first.")
    return _templates


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Home page."""
    return get_templates().TemplateResponse("index.html", {"request": request})


@router.get("/skill-specification", response_class=HTMLResponse)
async def skill_specification(request: Request):
    """Skill specification page."""
    from main import _get_spec_html
    content = _get_spec_html()
    return get_templates().TemplateResponse("skill_specification.html", {
        "request": request,
        "content": content,
        "version": "v1.0"
    })


@router.get("/.well-known/skills/index.json")
async def skills_well_known_index(request: Request):
    """Skills index for Claude Code discovery."""
    from main import scan_plugins
    skills = scan_plugins()
    return {
        "format_version": 1,
        "plugins": skills
    }


@router.get("/.well-known/skills/{skill_name}/skill.md", response_class=PlainTextResponse)
async def get_skill_well_known(skill_name: str):
    """Get skill.md for a specific skill."""
    from core.constants import SourceType
    from db.repositories import SkillRepository

    skill = SkillRepository.get_by_name(skill_name)
    if not skill:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Skill not found")

    # Find the skill.md in the plugin directory
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    skill_dir = os.path.join(base_dir, "plugins")

    # Try different source type directories
    for source in [SourceType.OPENSOURCE.value, SourceType.ICSL.value, SourceType.HUAWEI.value]:
        skill_path = os.path.join(skill_dir, source, skill_name, "SKILL.md")
        if os.path.exists(skill_path):
            with open(skill_path, "r", encoding="utf-8") as f:
                return f.read()

    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="SKILL.md not found")


@router.get("/marketplace.json")
async def marketplace_json(request: Request):
    """Marketplace JSON for Claude Code."""
    from main import scan_plugins
    skills = scan_plugins()
    return {
        "format_version": 1,
        "plugins": skills
    }


@router.get("/plugins/{filename}")
async def download_plugin(filename: str, request: Request):
    """Download a skill plugin."""
    from fastapi.responses import FileResponse
    import os

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(base_dir, "plugins", filename)

    if not os.path.exists(file_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")

    # Record download
    from db.repositories import SkillRepository
    skill_name = filename.replace(".zip", "")
    skill = SkillRepository.get_by_name(skill_name)
    if skill:
        SkillRepository.record_download(skill.id, request)

    return FileResponse(
        file_path,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    """Login page."""
    return get_templates().TemplateResponse("login.html", {"request": request, "error": error})


@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request, error: str = None):
    """Admin login page."""
    return get_templates().TemplateResponse("login.html", {"request": request, "error": error, "admin": True})


@router.post("/admin/login")
async def admin_login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Admin login handler."""
    from fastapi import HTTPException
    from fastapi.responses import RedirectResponse

    # First verify against ADMIN_USERNAME/ADMIN_PASSWORD (static admin)
    from main import verify_credentials
    if verify_credentials(username, password):
        # Get user from database
        from db.repositories import UserRepository
        from main import get_user_by_credentials, get_user_by_id
        user = get_user_by_credentials(username, "static_admin") or get_user_by_id(1)
        if user:
            request.session["user_id"] = user["id"]
            request.session["employee_id"] = user["employee_id"]
            request.session["role"] = user["role"]
            return RedirectResponse(url="/admin", status_code=302)

    # Verify against database users
    from db.repositories import UserRepository
    user = UserRepository.get_by_credentials(username, password)

    if not user:
        return RedirectResponse(url="/admin/login?error=invalid_credentials", status_code=302)

    if user.role != "admin":
        return RedirectResponse(url="/admin/login?error=not_admin", status_code=302)

    # Create session
    request.session["user_id"] = user.id
    request.session["employee_id"] = user.employee_id
    request.session["role"] = user.role

    return RedirectResponse(url="/admin", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    """Logout handler."""
    from fastapi.responses import RedirectResponse
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@router.get("/upload", response_class=HTMLResponse)
async def user_upload_page(request: Request):
    """User upload page."""
    user = get_current_user(request)
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login", status_code=302)
    return get_templates().TemplateResponse("upload.html", {"request": request, "user": user})


@router.get("/admin/upload", response_class=HTMLResponse)
async def upload_page(request: Request, _: bool = None):
    """Admin upload page."""
    from main import require_admin
    # This route is for admin, check in handler
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login", status_code=302)
    return get_templates().TemplateResponse("admin_upload.html", {"request": request, "user": user})


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin dashboard."""
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login", status_code=302)
    return get_templates().TemplateResponse("admin.html", {"request": request, "user": user})


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request):
    """User management page."""
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login", status_code=302)
    return get_templates().TemplateResponse("admin_users.html", {"request": request, "user": user})


@router.get("/admin/api-keys", response_class=HTMLResponse)
async def admin_api_keys_page(request: Request):
    """API Keys management page."""
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login", status_code=302)
    return get_templates().TemplateResponse("admin_api_keys.html", {"request": request, "user": user})


@router.get("/my-skills", response_class=HTMLResponse)
async def my_skills_page(request: Request):
    """My skills page."""
    user = get_current_user(request)
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login", status_code=302)
    return get_templates().TemplateResponse("my_skills.html", {"request": request, "user": user})


@router.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    """Statistics page."""
    user = get_current_user(request)
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login", status_code=302)
    return get_templates().TemplateResponse("stats.html", {"request": request, "user": user})


@router.get("/skill/{skill_name}", response_class=HTMLResponse)
async def skill_detail_page(request: Request, skill_name: str, version: str = None, compare: str = None):
    """Skill detail page with version support."""
    from pathlib import Path
    import os
    import re
    from datetime import datetime
    from fastapi import HTTPException
    from main import PLUGINS_DIR, extract_metadata

    # Input validation
    if not skill_name or not re.match(r'^[a-zA-Z0-9_-]+$', skill_name):
        raise HTTPException(status_code=400, detail="Invalid skill name format")
    if version and not re.match(r'^[a-zA-Z0-9._-]+$', version):
        raise HTTPException(status_code=400, detail="Invalid version format")
    if compare and not re.match(r'^[a-zA-Z0-9._-]+$', compare):
        raise HTTPException(status_code=400, detail="Invalid compare version format")

    # Get all versions of this skill
    from db.repositories import SkillRepository
    all_versions = SkillRepository.get_versions(skill_name)
    approved_versions = [v for v in all_versions if v.get("status") == "approved"]

    skill_zip = None
    real_skill_name = skill_name
    selected_version = version

    # Function to find skill zip by version
    def find_skill_zip(name, ver=None):
        if ver:
            exact = PLUGINS_DIR / f"{name}-{ver}.zip"
            if exact.exists():
                return exact
        # Try default or latest
        if skill and skill["status"] == "approved" and skill["is_active"]:
            zip_path = PLUGINS_DIR / skill["filename"]
            if zip_path.exists():
                return zip_path
        exact_match = PLUGINS_DIR / f"{name}.zip"
        if exact_match.exists():
            return exact_match
        matching_zips = list(PLUGINS_DIR.glob(f"{name}-*.zip"))
        if matching_zips:
            return matching_zips[0]
        return None

    # Get skill from database
    from main import get_skill_by_name
    skill = get_skill_by_name(skill_name)

    skill_zip = find_skill_zip(skill_name, version)

    if not skill_zip:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")

    # Extract metadata
    metadata = extract_metadata(skill_zip.name)
    real_skill_name = metadata.get("name", skill_name) if metadata else skill_name
    version = metadata.get("version", "1.0.0") if metadata else "1.0.0"

    # Get download count
    from main import get_download_stats
    stats = get_download_stats()
    download_count = 0
    for ranking in stats["rankings"]:
        if ranking["skill_name"] == real_skill_name:
            download_count = ranking["downloads"]
            break

    # Get author
    author = "Unknown"
    if metadata and "metadata" in metadata:
        author_meta = metadata["metadata"].get("author", "")
        if isinstance(author_meta, dict):
            author = author_meta.get("name", "")
        else:
            author = str(author_meta) if author_meta else ""

    if not author or author == "Unknown":
        skill_record = get_skill_by_name(real_skill_name)
        if skill_record and skill_record.get("uploader_id"):
            from main import get_user_by_id
            uploader = get_user_by_id(skill_record["uploader_id"])
            if uploader:
                author = uploader.get("employee_id", "Unknown")

    # Get updated_at
    updated_at = datetime.fromtimestamp(skill_zip.stat().st_mtime).strftime("%Y-%m-%d")

    # Get user
    user = get_current_user(request)

    # Get Gitea repo URL
    gitea_repo_url = os.getenv("GITEA_REPO_URL", "")
    skill_dir = real_skill_name

    # Version list for template
    display_version = selected_version if selected_version else version
    version_list = []
    for v in approved_versions:
        v_info = {
            "version": v.get("version", "unknown"),
            "is_default": v.get("is_default_version", 0) == 1,
            "is_active": v.get("is_active", 1) == 1,
            "created_at": v.get("created_at", "").strftime("%Y-%m-%d") if hasattr(v.get("created_at"), "strftime") else str(v.get("created_at", ""))
        }
        version_list.append(v_info)

    # Compare version content
    compare_content = None
    compare_version_display = None
    if compare:
        compare_zip = find_skill_zip(skill_name, compare)
        if compare_zip:
            import zipfile
            try:
                with zipfile.ZipFile(compare_zip, 'r') as zf:
                    skill_md_paths = [name for name in zf.namelist()
                                     if 'SKILL.md' in name or name.endswith('SKILL.md')]
                    if skill_md_paths:
                        compare_content = zf.read(skill_md_paths[0]).decode('utf-8')
            except Exception as e:
                import logging
                logging.warning(f"Failed to load compare version content: {e}")
            compare_version_display = compare

    return get_templates().TemplateResponse("skill_detail.html", {
        "request": request,
        "skill_name": real_skill_name,
        "author": author,
        "download_count": download_count,
        "version": display_version,
        "updated_at": updated_at,
        "download_url": f"/plugins/{skill_zip.name}",
        "filename": skill_zip.name,
        "request_url": str(request.base_url).rstrip("/"),
        "user": user,
        "gitea_repo_url": gitea_repo_url,
        "skill_dir": skill_dir,
        "version_list": version_list,
        "selected_version": selected_version,
        "compare": compare,
        "compare_content": compare_content,
        "compare_version_display": compare_version_display
    })


@router.get("/skill/{skill_name}/skill.md", response_class=PlainTextResponse)
async def get_skill_md_file(skill_name: str):
    """Get skill.md content."""
    from core.constants import SourceType
    import os

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    skill_dir = os.path.join(base_dir, "plugins")

    for source in [SourceType.OPENSOURCE.value, SourceType.ICSL.value, SourceType.HUAWEI.value]:
        skill_path = os.path.join(skill_dir, source, skill_name, "SKILL.md")
        if os.path.exists(skill_path):
            with open(skill_path, "r", encoding="utf-8") as f:
                return f.read()

    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="SKILL.md not found")


@router.get("/admin/gitea-tasks", response_class=HTMLResponse)
async def gitea_tasks_page(request: Request):
    """Gitea tasks monitoring page."""
    user = get_current_user(request)
    if not user or user.get("role") != "admin":
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/login", status_code=302)
    return get_templates().TemplateResponse("gitea_tasks.html", {"request": request, "user": user})


# Helper function from main.py
def get_current_user(request: Request):
    """Get current user from session."""
    return request.session.get("user_id") or request.session.get("employee_id")
