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
from datetime import datetime, date
from typing import List, Optional

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

# Import database module
from database import init_db, record_download, get_download_stats, get_stats_with_author

# Initialize database on startup
init_db()

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


def get_skill_dir_name(filename: str) -> str:
    """Get the skill directory name from filename.

    Removes .zip extension to get the directory name.
    Example: skill-name-1.0.0.zip -> skill-name-1.0.0
    """
    return filename[:-4] if filename.endswith('.zip') else filename


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
    """Parse plugin filename to extract name and version.

    Format: {skill-name}-{version}.zip
    Example: ask-questions-if-underspecified-1.0.0.zip
             semgrep-rule-creator-1.1.0.zip

    Returns: (skill_name, version)
    """
    # Remove .zip extension
    name_without_ext = filename[:-4] if filename.endswith('.zip') else filename

    # Find the last occurrence of version pattern (x.x.x)
    parts = name_without_ext.split('-')

    # Look for version pattern from the end
    for i in range(len(parts) - 1, -1, -1):
        part = parts[i]
        # Check if this part looks like a version (contains digits and dots)
        if any(c.isdigit() for c in part) and ('.' in part or part.isdigit()):
            # This and everything after is the version
            skill_name = '-'.join(parts[:i])
            version = '-'.join(parts[i:])
            return skill_name, version

    # Fallback: treat everything as name, version as unknown
    return name_without_ext, "unknown"


def scan_plugins() -> List[dict]:
    """Scan plugins directory and return metadata list."""
    plugins = {}

    for zip_file in PLUGINS_DIR.glob("*.zip"):
        if not zip_file.is_file():
            continue

        skill_name, version = parse_plugin_filename(zip_file.name)

        if skill_name not in plugins:
            plugins[skill_name] = {
                "name": skill_name,
                "metadata": None,
                "versions": []
            }

        plugins[skill_name]["versions"].append({
            "version": version,
            "filename": zip_file.name,
            "size": zip_file.stat().st_size,
            "updated_at": datetime.fromtimestamp(zip_file.stat().st_mtime).isoformat()
        })

    # Sort versions and get metadata for each skill
    result = []
    for skill_name, skill_data in sorted(plugins.items()):
        # Sort versions
        skill_data["versions"].sort(key=lambda x: x["version"])

        # Get metadata from latest version
        latest = skill_data["versions"][-1]
        metadata = extract_metadata(latest["filename"])
        skill_data["metadata"] = metadata
        skill_data["latest_version"] = latest["version"]

        result.append(skill_data)

    return result


def extract_metadata(zip_filename: str) -> Optional[dict]:
    """Extract metadata from package.json inside zip.

    The ZIP may have an outer folder:
        skill-name-1.0.0.zip
        └── skill-name/
            ├── package.json
            └── ...

    Args:
        zip_filename: Name of the ZIP file (e.g., "skill-name-1.0.0.zip")

    Returns:
        Metadata dict or fallback info
    """
    import zipfile

    zip_path = PLUGINS_DIR / zip_filename
    skill_name, _ = parse_plugin_filename(zip_filename)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()

            # First, try to find package.json directly in root
            for name in namelist:
                if name == 'package.json':
                    content = zf.read(name)
                    metadata = json.loads(content)
                    return metadata

            # Second, try to find package.json in a subdirectory
            # This handles the case: skill-name/package.json
            for name in namelist:
                parts = name.split('/')
                # Check if it's a subdirectory containing package.json
                if len(parts) == 2 and parts[1] == 'package.json':
                    content = zf.read(name)
                    metadata = json.loads(content)
                    return metadata

    except Exception:
        pass

    # Fallback: return basic info
    return {
        "name": skill_name,
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
    file_path = PLUGINS_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Parse skill name and version from filename
    skill_name, version = parse_plugin_filename(filename)

    # Record download
    try:
        record_download(
            skill_name=skill_name,
            version=version,
            filename=filename,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
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


def validate_skill_zip(zip_path: Path) -> tuple[bool, dict]:
    """Validate a skill ZIP file.

    The ZIP may have an outer folder:
        skill-name-1.0.0.zip
        └── skill-name/
            ├── package.json
            └── ...

    Args:
        zip_path: Path to the skill ZIP file

    Returns:
        (is_valid, metadata or error_info)
    """
    import zipfile

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()
            package_json = None

            # First, try to find package.json directly in root
            for name in namelist:
                if name == 'package.json':
                    content = zf.read(name)
                    package_json = json.loads(content)
                    break

            # Second, try to find package.json in a subdirectory
            if not package_json:
                for name in namelist:
                    parts = name.split('/')
                    # Check if it's a subdirectory containing package.json
                    if len(parts) == 2 and parts[1] == 'package.json':
                        content = zf.read(name)
                        package_json = json.loads(content)
                        break

            if not package_json:
                return False, {"error": "Missing package.json in ZIP"}

            # Validate required fields
            if "name" not in package_json:
                return False, {"error": "Missing 'name' in package.json"}
            if "version" not in package_json:
                return False, {"error": "Missing 'version' in package.json"}

            return True, package_json

    except zipfile.BadZipFile:
        return False, {"error": "Invalid ZIP file"}
    except json.JSONDecodeError:
        return False, {"error": "Invalid JSON in package.json"}
    except Exception as e:
        return False, {"error": str(e)}


def save_skill_zip(temp_zip: Path, metadata: dict) -> Path:
    """Save a skill ZIP to the plugins directory.

    Args:
        temp_zip: Path to the temporary ZIP file
        metadata: Skill metadata from package.json

    Returns:
        Path to the saved ZIP file
    """
    skill_name = metadata["name"]
    version = metadata["version"]
    target_filename = f"{skill_name}-{version}.zip"
    target_path = PLUGINS_DIR / target_filename

    # Copy file to target location
    shutil.copy(temp_zip, target_path)

    return target_path


@app.post("/admin/upload")
async def upload_plugin(
    request: Request,
    file: UploadFile = File(...),
    _: bool = Depends(require_auth)
):
    """Upload a single skill ZIP file (requires auth)."""
    import tempfile

    # Validate file extension
    if not file.filename or not file.filename.endswith('.zip'):
        return templates.TemplateResponse("admin_upload.html", {
            "request": request,
            "success": None,
            "error": "Only ZIP files are allowed"
        })

    # Save uploaded file to temp location
    temp_dir = tempfile.mkdtemp()
    temp_zip = Path(temp_dir) / "upload.zip"

    try:
        with open(temp_zip, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Validate the ZIP file
        is_valid, result = validate_skill_zip(temp_zip)

        if not is_valid:
            return templates.TemplateResponse("admin_upload.html", {
                "request": request,
                "success": None,
                "error": f"Validation failed: {result.get('error', 'Unknown error')}"
            })

        # Save the skill ZIP
        target_path = save_skill_zip(temp_zip, result)

        return templates.TemplateResponse("admin_upload.html", {
            "request": request,
            "success": f"Successfully uploaded {result['name']}@{result['version']}",
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


@app.post("/admin/upload-batch")
async def upload_batch(
    request: Request,
    files: List[UploadFile] = File(...),
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

    for file in files:
        # Skip non-ZIP files
        if not file.filename or not file.filename.endswith('.zip'):
            results["failed"].append({"file": file.filename, "error": "Not a ZIP file"})
            continue

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

            # Save the skill ZIP
            target_path = save_skill_zip(temp_zip, metadata)
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

                # Parse skill info
                skill_name, version = parse_plugin_filename(filename)

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=28000)
