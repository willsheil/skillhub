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
    return get_templates().TemplateResponse("skill_specification.html", {"request": request})


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
async def skill_detail_page(request: Request, skill_name: str):
    """Skill detail page."""
    return get_templates().TemplateResponse("skill_detail.html", {"request": request, "skill_name": skill_name})


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
    """Get current user from session.

    Returns user dictionary if authenticated, None otherwise.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    from db.repositories.user_repo import UserRepository
    user = UserRepository.get_by_id(user_id)
    if user:
        return {
            "id": user.id,
            "employee_id": user.employee_id,
            "role": user.role,
            "name": user.name,
            "status": user.status
        }
    return None
