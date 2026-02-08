# 用户管理系统实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标:** 为 Skill Registry 添加完整的用户管理系统，支持基于工号和 API KEY 的登录认证、角色权限控制、Skill 审批流程以及下载审计功能。

**架构:** 基于 FastAPI + SQLite 的扩展设计。在现有 `database.py` 和 `main.py` 基础上添加用户认证、审批流程和审计功能。使用 SessionMiddleware 管理会话，添加装饰器进行权限控制。

**技术栈:** FastAPI, SQLite (已有), PyYAML (已有), SessionMiddleware

---

## Phase 1: 数据库与认证基础

### Task 1.1: 扩展数据库 schema - 添加 users 表

**Files:**
- Modify: `database.py:15-38` (init_db 函数)

**Step 1: 扩展 init_db() 函数添加 users 表**

在 `init_db()` 函数中现有的 downloads 表创建之后添加：

```python
# Create users table
conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT UNIQUE NOT NULL,
        api_key TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    )
""")

# Index for employee_id lookups
conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_users_employee_id
    ON users(employee_id)
""")
```

**Step 2: 添加用户查询辅助函数**

在 `database.py` 文件末尾添加：

```python
def get_user_by_credentials(employee_id: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Get user by employee_id and api_key.

    Args:
        employee_id: Employee ID (e.g., w00545471)
        api_key: API key for authentication

    Returns:
        User dict if found, None otherwise
    """
    with get_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE employee_id = ? AND api_key = ?",
            (employee_id, api_key)
        ).fetchone()

        if user:
            return dict(user)
        return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID.

    Args:
        user_id: User ID from session

    Returns:
        User dict if found, None otherwise
    """
    with get_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if user:
            return dict(user)
        return None


def update_last_login(user_id: int) -> None:
    """Update user's last login timestamp.

    Args:
        user_id: User ID
    """
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,)
        )
        conn.commit()
```

**Step 3: Commit changes**

```bash
git add database.py
git commit -m "feat: add users table and user authentication functions"
```

---

### Task 1.2: 添加 skills 表用于审批流程

**Files:**
- Modify: `database.py:15-38` (init_db 函数)

**Step 1: 在 init_db() 中添加 skills 表**

在 users 表创建之后添加：

```python
# Create skills table for approval workflow
conn.execute("""
    CREATE TABLE IF NOT EXISTS skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        skill_name TEXT NOT NULL,
        version TEXT NOT NULL,
        filename TEXT NOT NULL,
        uploader_id INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reviewed_at TIMESTAMP,
        reviewer_id INTEGER,
        review_comment TEXT,
        FOREIGN KEY (uploader_id) REFERENCES users(id),
        FOREIGN KEY (reviewer_id) REFERENCES users(id)
    )
""")

# Indexes for skills table
conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_skills_status
    ON skills(status)
""")

conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_skills_uploader
    ON skills(uploader_id)
""")
```

**Step 2: 添加 skills 相关辅助函数**

在 `database.py` 文件末尾添加：

```python
def create_skill_record(
    skill_name: str,
    version: str,
    filename: str,
    uploader_id: int,
    status: str = "pending"
) -> int:
    """Create a skill record in database.

    Args:
        skill_name: Name of the skill
        version: Version string
        filename: ZIP filename
        uploader_id: User ID who uploaded
        status: 'pending', 'approved', or 'rejected'

    Returns:
        skill_id
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO skills (skill_name, version, filename, uploader_id, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (skill_name, version, filename, uploader_id, status)
        )
        conn.commit()
        return cursor.lastrowid


def get_pending_skills() -> List[Dict[str, Any]]:
    """Get all pending skills for admin review.

    Returns:
        List of pending skill dicts with uploader info
    """
    with get_connection() as conn:
        skills = conn.execute(
            """
            SELECT
                s.*,
                u.employee_id as uploader_employee_id
            FROM skills s
            JOIN users u ON s.uploader_id = u.id
            WHERE s.status = 'pending'
            ORDER BY s.uploaded_at DESC
            """
        ).fetchall()

        return [dict(skill) for skill in skills]


def get_skill_by_id(skill_id: int) -> Optional[Dict[str, Any]]:
    """Get skill by ID.

    Args:
        skill_id: Skill ID

    Returns:
        Skill dict if found, None otherwise
    """
    with get_connection() as conn:
        skill = conn.execute(
            "SELECT * FROM skills WHERE id = ?",
            (skill_id,)
        ).fetchone()

        if skill:
            return dict(skill)
        return None


def update_skill_status(
    skill_id: int,
    status: str,
    reviewer_id: Optional[int] = None,
    comment: Optional[str] = None
) -> bool:
    """Update skill status.

    Args:
        skill_id: Skill ID
        status: New status ('approved' or 'rejected')
        reviewer_id: Admin user ID
        comment: Optional review comment

    Returns:
        True if updated, False otherwise
    """
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE skills
            SET status = ?, reviewer_id = ?, review_comment = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, reviewer_id, comment, skill_id)
        )
        conn.commit()
        return True


def get_user_uploads(user_id: int) -> List[Dict[str, Any]]:
    """Get all uploads by a user.

    Args:
        user_id: User ID

    Returns:
        List of skill dicts
    """
    with get_connection() as conn:
        skills = conn.execute(
            "SELECT * FROM skills WHERE uploader_id = ? ORDER BY uploaded_at DESC",
            (user_id,)
        ).fetchall()

        return [dict(skill) for skill in skills]
```

**Step 3: Commit changes**

```bash
git add database.py
git commit -m "feat: add skills table for approval workflow"
```

---

### Task 1.3: 修改 downloads 表添加 user_id

**Files:**
- Modify: `database.py:52-74` (record_download 函数)
- Modify: `database.py:76-133` (get_download_stats 函数)

**Step 1: 修改 record_download 函数签名**

更新函数签名添加 user_id 参数：

```python
def record_download(
    skill_name: str,
    version: str,
    filename: str,
    user_id: Optional[int] = None,  # 新增
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> int:
```

**Step 2: 修改 SQL INSERT 语句**

将 INSERT 语句改为：

```python
cursor = conn.execute(
    """
    INSERT INTO downloads (skill_name, version, filename, user_id, ip_address, user_agent)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    (skill_name, version, filename, user_id, ip_address, user_agent)
)
```

**Step 3: 添加数据库迁移函数**

在 `database.py` 文件末尾添加：

```python
def migrate_add_user_id_to_downloads():
    """Add user_id column to downloads table if not exists."""
    with get_connection() as conn:
        # Check if column exists
        cursor = conn.execute("PRAGMA table_info(downloads)")
        columns = [row["name"] for row in cursor.fetchall()]

        if "user_id" not in columns:
            conn.execute("ALTER TABLE downloads ADD COLUMN user_id INTEGER REFERENCES users(id)")
            conn.commit()
            print("Added user_id column to downloads table")
        else:
            print("user_id column already exists in downloads table")
```

**Step 4: 在 init_db() 开头调用迁移**

在 `init_db()` 函数开头添加：

```python
def init_db():
    """Initialize database and create tables."""
    DB_PATH.parent.mkdir(exist_ok=True)

    with get_connection() as conn:
        # Migration: add user_id to downloads table
        migrate_add_user_id_to_downloads()

        # ... rest of the function
```

**Step 5: 添加用户下载历史函数**

在 `database.py` 文件末尾添加：

```python
def get_user_downloads(
    user_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 100,
    offset: int = 0
) -> Dict[str, Any]:
    """Get download history for a user.

    Args:
        user_id: User ID
        start_date: Start date filter (optional)
        end_date: End date filter (optional)
        limit: Max results
        offset: Pagination offset

    Returns:
        Dict with downloads list and total count
    """
    # Default to all time if no dates provided
    if start_date is None:
        start_date = date(1970, 1, 1)
    if end_date is None:
        end_date = date.today()

    with get_connection() as conn:
        # Get total count
        count_row = conn.execute(
            """
            SELECT COUNT(*) as total FROM downloads
            WHERE user_id = ? AND date(downloaded_at) BETWEEN ? AND ?
            """,
            (user_id, start_date.isoformat(), end_date.isoformat())
        ).fetchone()

        total = count_row["total"] if count_row else 0

        # Get downloads with pagination
        downloads = conn.execute(
            """
            SELECT
                skill_name, version, downloaded_at
            FROM downloads
            WHERE user_id = ? AND date(downloaded_at) BETWEEN ? AND ?
            ORDER BY downloaded_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, start_date.isoformat(), end_date.isoformat(), limit, offset)
        ).fetchall()

        return {
            "downloads": [dict(d) for d in downloads],
            "total": total,
            "limit": limit,
            "offset": offset
        }
```

**Step 6: Commit changes**

```bash
git add database.py
git commit -m "feat: add user_id tracking to downloads table"
```

---

### Task 1.4: 创建用户初始化脚本

**Files:**
- Create: `scripts/init_users.py`

**Step 1: 创建初始化脚本**

```python
#!/usr/bin/env python3
"""
Initialize users in the database.

Run this script to add initial users for testing.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db, get_connection
import getpass

def init_users():
    """Initialize users table with test users."""
    init_db()

    # Default users
    users = [
        ("w00000001", "sk-test-admin-key-1", "admin"),
        ("w00000002", "sk-test-user-key-1", "user"),
        ("w00000003", "sk-test-user-key-2", "user"),
    ]

    print("Adding initial users...")

    with get_connection() as conn:
        for employee_id, api_key, role in users:
            # Check if user already exists
            existing = conn.execute(
                "SELECT id FROM users WHERE employee_id = ?",
                (employee_id,)
            ).fetchone()

            if existing:
                print(f"  User {employee_id} already exists, skipping...")
                continue

            conn.execute(
                "INSERT INTO users (employee_id, api_key, role) VALUES (?, ?, ?)",
                (employee_id, api_key, role)
            )
            print(f"  Added user: {employee_id} ({role})")

        conn.commit()

    print("\n✓ User initialization complete!")
    print("\nTest credentials:")
    print("  Admin: w00000001 / sk-test-admin-key-1")
    print("  User 1: w00000002 / sk-test-user-key-1")
    print("  User 2: w00000003 / sk-test-user-key-2")

if __name__ == "__main__":
    init_users()
```

**Step 2: 运行脚本初始化用户**

```bash
python scripts/init_users.py
```

Expected output:
```
Adding initial users...
  Added user: w00000001 (admin)
  Added user: w00000002 (user)
  Added user: w00000003 (user)

✓ User initialization complete!

Test credentials:
  Admin: w00000001 / sk-test-admin-key-1
  User 1: w00000002 / sk-test-user-key-1
  User 2: w00000003 / sk-test-user-key-2
```

**Step 3: Commit changes**

```bash
git add scripts/init_users.py
git commit -m "feat: add user initialization script"
```

---

### Task 1.5: 添加认证和权限装饰器

**Files:**
- Modify: `main.py:54-66` (在 require_auth 之后添加新函数)

**Step 1: 修改现有的 require_auth 函数**

将现有的 `require_auth` 函数改为：

```python
def require_auth(request: Request):
    """Check if user is logged in."""
    if "user_id" not in request.session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return True
```

**Step 2: 添加 require_admin 装饰器**

在 `require_auth` 函数之后添加：

```python
def require_admin(request: Request):
    """Check if user has admin role."""
    if "user_id" not in request.session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    if request.session.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return True
```

**Step 3: 添加 get_current_user 辅助函数**

```python
def get_current_user(request: Request) -> Optional[dict]:
    """Get current logged-in user from session.

    Returns:
        User dict if logged in, None otherwise
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    from database import get_user_by_id
    return get_user_by_id(user_id)
```

**Step 4: Commit changes**

```bash
git add main.py
git commit -m "feat: add authentication and authorization decorators"
```

---

### Task 1.6: 实现登录 API

**Files:**
- Modify: `main.py` (在 verify_credentials 函数之后)

**Step 1: 添加登录端点**

在 `@app.post("/admin/login")` 之后添加新的登录端点：

```python
@app.post("/api/login")
async def login_api(request: Request, employee_id: str = Form(...), api_key: str = Form(...)):
    """User login API using employee ID and API key.

    Args:
        request: FastAPI request
        employee_id: Employee ID (e.g., w00545471)
        api_key: LiteLLM API key

    Returns:
        JSON response with success status and user info
    """
    from database import get_user_by_credentials, update_last_login

    user = get_user_by_credentials(employee_id, api_key)

    if not user:
        return {"success": False, "error": "Invalid credentials"}

    # Set session
    request.session["user_id"] = user["id"]
    request.session["employee_id"] = user["employee_id"]
    request.session["role"] = user["role"]

    # Update last login
    update_last_login(user["id"])

    return {
        "success": True,
        "user": {
            "employee_id": user["employee_id"],
            "role": user["role"]
        }
    }
```

**Step 2: 添加登出端点**

修改现有的 `/admin/logout` 端点，使其更通用：

```python
@app.get("/logout")
async def logout(request: Request):
    """Logout current user."""
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)
```

**Step 3: 添加当前用户信息端点**

```python
@app.get("/api/me")
async def get_me(request: Request):
    """Get current logged-in user info.

    Returns:
        Current user info or 401 if not logged in
    """
    user = get_current_user(request)

    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {
        "user": {
            "id": user["id"],
            "employee_id": user["employee_id"],
            "role": user["role"]
        }
    }
```

**Step 4: Commit changes**

```bash
git add main.py
git commit -m "feat: add login/logout/me API endpoints"
```

---

## Phase 2: 上传与审批流程

### Task 2.1: 创建临时文件存储目录

**Files:**
- Modify: `main.py:27-29` (configuration section)

**Step 1: 添加 pending 目录配置**

在 PLUGINS_DIR 配置之后添加：

```python
# Configuration
PLUGINS_DIR = Path(os.getenv("PLUGINS_DIR", "./plugins"))
PLUGINS_DIR.mkdir(exist_ok=True)

# Pending uploads directory
PENDING_DIR = Path("./data/pending")
PENDING_DIR.mkdir(parents=True, exist_ok=True)
```

**Step 2: Commit changes**

```bash
git add main.py
git commit -m "feat: add pending uploads directory"
```

---

### Task 2.2: 修改上传端点支持审批流程

**Files:**
- Modify: `main.py:756-810` (upload_plugin 函数)

**Step 1: 修改上传端点路径和权限**

将现有的 `/admin/upload` 改为 `/api/upload`，并更新依赖：

```python
@app.post("/api/upload")
async def upload_plugin(
    request: Request,
    file: UploadFile = File(...),
    _: bool = Depends(require_auth)  # 改为 require_auth
):
```

**Step 2: 修改保存逻辑支持 pending 状态**

在验证通过后，保存到 pending 目录：

```python
# Validate the ZIP file
is_valid, result = validate_skill_zip(temp_zip)

if not is_valid:
    return templates.TemplateResponse("admin_upload.html", {
        "request": request,
        "success": None,
        "error": f"Validation failed: {result.get('error', 'Unknown error')}"
    })

# Get current user
user_id = request.session.get("user_id")

# Save to pending directory with skill_id as filename
from database import create_skill_record

# Create database record first
skill_id = create_skill_record(
    skill_name=result['name'],
    version=result['version'],
    filename=file.filename,
    uploader_id=user_id,
    status='pending'
)

# Save to pending directory
pending_filename = f"{skill_id}_{file.filename}"
target_path = PENDING_DIR / pending_filename
shutil.copy(temp_zip, target_path)

return templates.TemplateResponse("admin_upload.html", {
    "request": request,
    "success": f"Skill uploaded successfully! Awaiting admin approval. (Skill ID: {skill_id})",
    "error": None
})
```

**Step 3: Commit changes**

```bash
git add main.py
git commit -m "feat: modify upload endpoint to support approval workflow"
```

---

### Task 2.3: 实现审批函数

**Files:**
- Modify: `main.py` (在 upload_plugin 函数之后)

**Step 1: 添加审批辅助函数**

```python
def approve_skill_file(skill_id: int) -> bool:
    """Approve a skill by moving it from pending to plugins directory.

    Args:
        skill_id: Skill ID from database

    Returns:
        True if successful, False otherwise
    """
    from database import get_skill_by_id

    skill = get_skill_by_id(skill_id)
    if not skill:
        return False

    # Find pending file
    pending_files = list(PENDING_DIR.glob(f"{skill_id}_*.zip"))
    if not pending_files:
        return False

    pending_file = pending_files[0]
    target_path = PLUGINS_DIR / skill["filename"]

    # Move file
    shutil.move(str(pending_file), str(target_path))
    return True


def reject_skill_file(skill_id: int) -> bool:
    """Reject a skill by deleting pending file.

    Args:
        skill_id: Skill ID from database

    Returns:
        True if successful, False otherwise
    """
    # Find and delete pending file
    pending_files = list(PENDING_DIR.glob(f"{skill_id}_*.zip"))
    if not pending_files:
        return False

    pending_file = pending_files[0]
    pending_file.unlink()
    return True
```

**Step 2: Commit changes**

```bash
git add main.py
git commit -m "feat: add approve/reject helper functions"
```

---

### Task 2.4: 添加审批 API 端点

**Files:**
- Modify: `main.py` (在 delete_plugin 函数之后)

**Step 1: 添加待审批列表端点**

```python
@app.get("/api/pending")
async def get_pending_skills_api(
    request: Request,
    _: bool = Depends(require_admin)
):
    """Get list of pending skills awaiting approval (admin only)."""
    from database import get_pending_skills

    pending = get_pending_skills()

    return {
        "pending": pending,
        "total": len(pending)
    }
```

**Step 2: 添加审批操作端点**

```python
@app.post("/api/review/{skill_id}")
async def review_skill(
    skill_id: int,
    request: Request,
    action: str = Form(...),
    comment: str = Form(""),
    _: bool = Depends(require_admin)
):
    """Review and approve/reject a pending skill (admin only).

    Args:
        skill_id: Skill ID to review
        action: "approve" or "reject"
        comment: Optional review comment

    Returns:
        JSON response
    """
    from database import get_skill_by_id, update_skill_status

    # Verify skill exists and is pending
    skill = get_skill_by_id(skill_id)
    if not skill or skill["status"] != "pending":
        raise HTTPException(404, "Skill not found or already reviewed")

    reviewer_id = request.session.get("user_id")

    if action == "approve":
        # Move file to plugins directory
        if not approve_skill_file(skill_id):
            raise HTTPException(500, "Failed to approve skill")

        # Update database
        update_skill_status(skill_id, "approved", reviewer_id, comment)

        return {"success": True, "message": "Skill approved successfully"}

    elif action == "reject":
        # Delete pending file
        reject_skill_file(skill_id)

        # Update database
        update_skill_status(skill_id, "rejected", reviewer_id, comment)

        return {"success": True, "message": "Skill rejected"}

    else:
        raise HTTPException(400, "Invalid action. Use 'approve' or 'reject'")
```

**Step 3: 添加用户上传历史端点**

```python
@app.get("/api/user/uploads")
async def get_user_uploads_api(
    request: Request,
    _: bool = Depends(require_auth)
):
    """Get current user's upload history."""
    from database import get_user_uploads

    user_id = request.session.get("user_id")
    uploads = get_user_uploads(user_id)

    return {
        "uploads": uploads,
        "total": len(uploads)
    }
```

**Step 4: Commit changes**

```bash
git add main.py
git commit -m "feat: add skill review API endpoints"
```

---

## Phase 3: 下载审计

### Task 3.1: 修改下载端点记录用户

**Files:**
- Modify: `main.py:491-558` (download_plugin 函数)

**Step 1: 添加登录检查**

在函数开头添加认证检查：

```python
@app.get("/plugins/{filename}")
async def download_plugin(filename: str, request: Request, raw: bool = False):
    """Download plugin ZIP file (requires login)."""
    # Check authentication
    if "user_id" not in request.session:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )

    file_path = PLUGINS_DIR / filename
    # ... rest of function
```

**Step 2: 修改 record_download 调用**

更新下载记录调用，传入 user_id：

```python
# Record download
try:
    record_download(
        skill_name=skill_name,
        version=version,
        filename=filename,
        user_id=request.session.get("user_id"),  # 新增
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
except Exception as e:
    print(f"Failed to record download: {e}")
```

**Step 3: Commit changes**

```bash
git add main.py
git commit -m "feat: require authentication for downloads and track user"
```

---

### Task 3.2: 添加用户下载历史 API

**Files:**
- Modify: `main.py` (在 download_plugin 函数之后)

**Step 1: 添加下载历史端点**

```python
@app.get("/api/user/downloads")
async def get_user_downloads_api(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _: bool = Depends(require_auth)
):
    """Get current user's download history."""
    from database import get_user_downloads

    user_id = request.session.get("user_id")
    offset = (page - 1) * per_page

    result = get_user_downloads(
        user_id=user_id,
        limit=per_page,
        offset=offset
    )

    return {
        "downloads": result["downloads"],
        "total": result["total"],
        "page": page,
        "per_page": per_page,
        "total_pages": (result["total"] + per_page - 1) // per_page
    }
```

**Step 2: Commit changes**

```bash
git add main.py
git commit -m "feat: add user download history API"
```

---

## Phase 4: 前端界面

### Task 4.1: 创建新的登录页面

**Files:**
- Modify: `templates/login.html` (完全替换现有内容)

**Step 1: 创建用户登录页面**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Skill Registry</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 400px;
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
            color: #333;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: 500;
        }
        input {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        .btn-login {
            width: 100%;
            padding: 12px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            font-weight: 500;
        }
        .btn-login:hover {
            background: #5568d3;
        }
        .error {
            background: #fee;
            color: #c33;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>Skill Registry Login</h1>

        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}

        <form method="post" action="/api/login">
            <div class="form-group">
                <label for="employee_id">工号 (Employee ID)</label>
                <input
                    type="text"
                    id="employee_id"
                    name="employee_id"
                    placeholder="例如: w00545471"
                    required
                    pattern="[a-z][0-9]{8}"
                    title="格式: 字母 + 8位数字"
                >
            </div>

            <div class="form-group">
                <label for="api_key">API KEY</label>
                <input
                    type="password"
                    id="api_key"
                    name="api_key"
                    placeholder="输入您的 API KEY"
                    required
                >
            </div>

            <button type="submit" class="btn-login">登录</button>
        </form>
    </div>
</body>
</html>
```

**Step 2: 添加登录页面路由**

在 `main.py` 中添加：

```python
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    """Display login page."""
    # If already logged in, redirect to home
    if "user_id" in request.session:
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error
    })
```

**Step 3: 修改登录 API 成功后重定向**

更新 `/api/login` 端点，成功后重定向：

```python
@app.post("/api/login")
async def login_api(request: Request, employee_id: str = Form(...), api_key: str = Form(...)):
    from database import get_user_by_credentials, update_last_login

    user = get_user_by_credentials(employee_id, api_key)

    if not user:
        return RedirectResponse(
            url="/login?error=" + "Invalid credentials",
            status_code=302
        )

    request.session["user_id"] = user["id"]
    request.session["employee_id"] = user["employee_id"]
    request.session["role"] = user["role"]

    update_last_login(user["id"])

    return RedirectResponse(url="/", status_code=302)
```

**Step 4: Commit changes**

```bash
git add templates/login.html main.py
git commit -m "feat: add user login page"
```

---

### Task 4.2: 修改首页导航栏

**Files:**
- Modify: `templates/index.html` (修改导航栏部分)

**Step 1: 在 index.html 顶部添加登录检查和导航栏**

在 `<body>` 标签后添加：

```html
<nav class="navbar">
    <div class="nav-container">
        <div class="nav-brand">
            <a href="/">Skill Registry</a>
        </div>
        <div class="nav-menu">
            {% if request.session.get("user_id") %}
                <span class="welcome">欢迎, {{ request.session.get("employee_id") }}</span>
                <a href="/upload" class="nav-link">上传</a>
                {% if request.session.get("role") == "admin" %}
                <a href="/admin" class="nav-link">管理后台</a>
                {% endif %}
                <a href="/logout" class="nav-link">退出</a>
            {% else %}
                <a href="/login" class="nav-link btn-login">登录</a>
            {% endif %}
        </div>
    </div>
</nav>

<style>
.navbar {
    background: #2d3748;
    padding: 0 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.nav-container {
    max-width: 1200px;
    margin: 0 auto;
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 60px;
}
.nav-brand a {
    color: white;
    text-decoration: none;
    font-size: 20px;
    font-weight: bold;
}
.nav-menu {
    display: flex;
    gap: 20px;
    align-items: center;
}
.welcome {
    color: white;
    margin-right: 20px;
}
.nav-link {
    color: white;
    text-decoration: none;
    padding: 8px 16px;
    border-radius: 5px;
    transition: background 0.2s;
}
.nav-link:hover {
    background: rgba(255,255,255,0.1);
}
.btn-login {
    background: #667eea;
}
.btn-login:hover {
    background: #5568d3;
}
</style>
```

**Step 2: 修改 Skill 卡片的下载按钮**

未登录时，下载按钮应该显示"登录后下载"：

```html
{% if request.session.get("user_id") %}
<a href="/plugins/{{ plugin.latest_version.filename }}" class="btn-download">下载</a>
{% else %}
<a href="/login" class="btn-download disabled">登录后下载</a>
{% endif %}
```

**Step 3: Commit changes**

```bash
git add templates/index.html
git commit -m "feat: add user authentication to navigation bar"
```

---

### Task 4.3: 创建用户上传页面

**Files:**
- Create: `templates/upload.html`

**Step 1: 创建上传页面模板**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>上传 Skill - Skill Registry</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <nav class="navbar">
        <!-- 复用导航栏代码 -->
    </nav>

    <div class="container">
        <h1>上传 Skill</h1>

        {% if success %}
        <div class="alert alert-success">{{ success }}</div>
        {% endif %}

        {% if error %}
        <div class="alert alert-error">{{ error }}</div>
        {% endif %}

        <div class="upload-form">
            <form method="post" action="/api/upload" enctype="multipart/form-data">
                <div class="form-group">
                    <label>选择 ZIP 文件</label>
                    <input type="file" name="file" accept=".zip" required>
                </div>

                <button type="submit" class="btn-primary">上传</button>
            </form>
        </div>

        <h2>我的上传</h2>
        <div id="uploads-list" class="uploads-list">
            <p>加载中...</p>
        </div>
    </div>

    <script>
        // Load user's upload history
        fetch('/api/user/uploads')
            .then(r => r.json())
            .then(data => {
                const container = document.getElementById('uploads-list');
                if (data.uploads.length === 0) {
                    container.innerHTML = '<p>暂无上传记录</p>';
                    return;
                }

                container.innerHTML = data.uploads.map(u => `
                    <div class="upload-item">
                        <div class="upload-name">${u.skill_name} v${u.version}</div>
                        <div class="upload-status status-${u.status}">
                            ${u.status === 'approved' ? '已批准' :
                              u.status === 'rejected' ? '已拒绝' : '待审批'}
                        </div>
                        <div class="upload-time">${new Date(u.uploaded_at).toLocaleString()}</div>
                    </div>
                `).join('');
            });
    </script>
</body>
</html>
```

**Step 2: 添加上传页面路由**

```python
@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, _: bool = Depends(require_auth)):
    """Display upload page."""
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "success": None,
        "error": None
    })
```

**Step 3: Commit changes**

```bash
git add templates/upload.html main.py
git commit -m "feat: add user upload page"
```

---

### Task 4.4: 创建管理后台

**Files:**
- Create: `templates/admin.html`

**Step 1: 创建管理后台页面**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>管理后台 - Skill Registry</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: sans-serif; background: #f5f5f5; }
        .navbar { background: #2d3748; padding: 15px 20px; }
        .container { max-width: 1200px; margin: 30px auto; padding: 20px; }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; }
        .tab {
            padding: 10px 20px;
            background: white;
            cursor: pointer;
            border: 1px solid #ddd;
        }
        .tab.active { background: #667eea; color: white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        table { width: 100%; background: white; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        .status-pending { color: orange; }
        .status-approved { color: green; }
        .status-rejected { color: red; }
    </style>
</head>
<body>
    <nav class="navbar">
        <a href="/" style="color: white;">返回首页</a>
    </nav>

    <div class="container">
        <h1>管理后台</h1>

        <div class="tabs">
            <div class="tab active" data-tab="pending">待审批 ({{ pending_count }})</div>
            <div class="tab" data-tab="stats">统计</div>
        </div>

        <div id="tab-pending" class="tab-content active">
            <table id="pending-table">
                <thead>
                    <tr>
                        <th>Skill 名称</th>
                        <th>版本</th>
                        <th>上传者</th>
                        <th>上传时间</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td colspan="5">加载中...</td></tr>
                </tbody>
            </table>
        </div>

        <div id="tab-stats" class="tab-content">
            <h2>统计数据</h2>
            <div id="stats-content">加载中...</div>
        </div>
    </div>

    <script>
        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
            });
        });

        // Load pending skills
        fetch('/api/pending')
            .then(r => r.json())
            .then(data => {
                const tbody = document.querySelector('#pending-table tbody');
                if (data.pending.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5">暂无待审批项目</td></tr>';
                    return;
                }

                tbody.innerHTML = data.pending.map(p => `
                    <tr>
                        <td>${p.skill_name}</td>
                        <td>${p.version}</td>
                        <td>${p.uploader_employee_id}</td>
                        <td>${new Date(p.uploaded_at).toLocaleString()}</td>
                        <td>
                            <button onclick="review(${p.id}, 'approve')">批准</button>
                            <button onclick="review(${p.id}, 'reject')">拒绝</button>
                        </td>
                    </tr>
                `).join('');
            });

        function review(skillId, action) {
            const comment = prompt(`请输入${action === 'approve' ? '批准' : '拒绝'}意见（可选）:`);

            const formData = new FormData();
            formData.append('action', action);
            formData.append('comment', comment || '');

            fetch(`/api/review/${skillId}`, {
                method: 'POST',
                body: formData
            })
            .then(r => r.json())
            .then(data => {
                alert(data.message);
                location.reload();
            });
        }
    </script>
</body>
</html>
```

**Step 2: 添加管理后台路由**

```python
@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, _: bool = Depends(require_admin)):
    """Display admin dashboard."""
    from database import get_pending_skills

    pending = get_pending_skills()

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "pending_count": len(pending)
    })
```

**Step 3: Commit changes**

```bash
git add templates/admin.html main.py
git commit -m "feat: add admin dashboard page"
```

---

## Phase 5: 统计与测试

### Task 5.1: 添加管理员统计 API

**Files:**
- Modify: `main.py` (在 admin_page 之后)

**Step 1: 添加统计 API 端点**

```python
@app.get("/api/admin/stats")
async def admin_stats_api(
    request: Request,
    _: bool = Depends(require_admin)
):
    """Get admin dashboard statistics."""
    from database import (
        get_connection,
        get_download_stats,
        get_stats_with_author,
        scan_plugins
    )

    with get_connection() as conn:
        # Total users
        users_count = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()["count"]

        # Pending skills
        pending_count = conn.execute("SELECT COUNT(*) as count FROM skills WHERE status = 'pending'").fetchone()["count"]

        # Approved skills
        approved_count = conn.execute("SELECT COUNT(*) as count FROM skills WHERE status = 'approved'").fetchone()["count"]

        # Today's downloads
        today_downloads = conn.execute("""
            SELECT COUNT(*) as count FROM downloads
            WHERE date(downloaded_at) = date('now')
        """).fetchone()["count"]

        # Top skills
        top_skills = conn.execute("""
            SELECT skill_name, COUNT(*) as downloads
            FROM downloads
            GROUP BY skill_name
            ORDER BY downloads DESC
            LIMIT 10
        """).fetchall()

        # Top users
        top_users = conn.execute("""
            SELECT u.employee_id, COUNT(d.id) as downloads
            FROM users u
            LEFT JOIN downloads d ON u.id = d.user_id
            GROUP BY u.id
            HAVING downloads > 0
            ORDER BY downloads DESC
            LIMIT 10
        """).fetchall()

    return {
        "summary": {
            "total_users": users_count,
            "pending_skills": pending_count,
            "approved_skills": approved_count,
            "today_downloads": today_downloads
        },
        "top_skills": [dict(s) for s in top_skills],
        "top_users": [dict(u) for u in top_users]
    }
```

**Step 2: Commit changes**

```bash
git add main.py
git commit -m "feat: add admin statistics API"
```

---

### Task 5.2: 创建端到端测试脚本

**Files:**
- Create: `tests/test_user_management.py`

**Step 1: 创建测试文件**

```python
#!/usr/bin/env python3
"""
End-to-end tests for user management system.
"""

import pytest
import requests
import tempfile
import zipfile
from pathlib import Path

BASE_URL = "http://localhost:28000"

def create_test_skill():
    """Create a minimal valid skill ZIP for testing."""
    temp = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)

    with zipfile.ZipFile(temp.name, 'w') as zf:
        # SKILL.md with required fields
        skill_md = """---
name: test-skill
description: Test skill for user management
metadata:
  version: 1.0.0
  author: w00000001
---

# Test Skill

This is a test skill.
"""
        zf.writestr('test-skill/SKILL.md', skill_md)

    return Path(temp.name)

def test_login_success():
    """Test successful login."""
    session = requests.Session()

    response = session.post(
        f"{BASE_URL}/api/login",
        data={
            "employee_id": "w00000001",
            "api_key": "sk-test-admin-key-1"
        },
        allow_redirects=False
    )

    assert response.status_code in [200, 302]

def test_login_failure():
    """Test login with invalid credentials."""
    session = requests.Session()

    response = session.post(
        f"{BASE_URL}/api/login",
        data={
            "employee_id": "w00000001",
            "api_key": "wrong-key"
        },
        allow_redirects=False
    )

    # Should redirect back to login with error
    assert response.status_code == 302

def test_upload_requires_auth():
    """Test that upload requires authentication."""
    response = requests.get(f"{BASE_URL}/upload")

    # Should redirect to login
    assert response.status_code == 302
    assert "/login" in response.headers.get('Location', '')

def test_admin_requires_admin_role():
    """Test that admin page requires admin role."""
    session = requests.Session()

    # Login as regular user
    session.post(
        f"{BASE_URL}/api/login",
        data={
            "employee_id": "w00000002",
            "api_key": "sk-test-user-key-1"
        }
    )

    # Try to access admin page
    response = session.get(f"{BASE_URL}/admin", allow_redirects=False)

    # Should get 403
    assert response.status_code == 403

def test_upload_and_approval_flow():
    """Test complete upload and approval workflow."""
    session = requests.Session()

    # Login as regular user
    session.post(
        f"{BASE_URL}/api/login",
        data={
            "employee_id": "w00000002",
            "api_key": "sk-test-user-key-1"
        }
    )

    # Create test skill
    skill_zip = create_test_skill()

    # Upload skill
    with open(skill_zip, 'rb') as f:
        response = session.post(
            f"{BASE_URL}/api/upload",
            files={"file": ("test-skill.zip", f, "application/zip")}
        )

    assert response.status_code == 200

    # Clean up
    skill_zip.unlink()

    # Login as admin
    admin_session = requests.Session()
    admin_session.post(
        f"{BASE_URL}/api/login",
        data={
            "employee_id": "w00000001",
            "api_key": "sk-test-admin-key-1"
        }
    )

    # Get pending skills
    response = admin_session.get(f"{BASE_URL}/api/pending")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] > 0

    # Approve the skill
    skill_id = data["pending"][0]["id"]
    response = admin_session.post(
        f"{BASE_URL}/api/review/{skill_id}",
        data={"action": "approve", "comment": "Test approval"}
    )

    assert response.status_code == 200

if __name__ == "__main__":
    print("Running user management tests...")
    print("Make sure the server is running on http://localhost:28000")
    print()

    pytest.main([__file__, "-v"])
```

**Step 2: Commit changes**

```bash
git add tests/test_user_management.py
git commit -m "test: add end-to-end tests for user management"
```

---

### Task 5.3: 更新文档

**Files:**
- Modify: `README.md`

**Step 1: 添加用户管理部分到 README**

在 README.md 中添加新章节：

```markdown
## 用户管理

### 用户角色

系统支持两种用户角色：

- **管理员**：可以审批 Skills、删除 Skills、查看统计数据
- **普通用户**：可以上传和下载已批准的 Skills

### 登录

使用工号和 API KEY 登录系统：

- 工号格式：字母 + 8位数字（例如：w00545471）
- API KEY：由 LiteLLM 分发的密钥

### 上传流程

1. 登录后访问"上传"页面
2. 选择 Skill ZIP 文件上传
3. Skill 状态为"待审批"
4. 管理员审批通过后，Skill 才对其他用户可见

### 审批流程

管理员在"管理后台"查看待审批的 Skills：
- **批准**：Skill 移至 plugins 目录，所有用户可下载
- **拒绝**：删除上传文件，记录拒绝原因

### 初始化用户

运行初始化脚本添加测试用户：

```bash
python scripts/init_users.py
```

默认测试账号：
- 管理员：w00000001 / sk-test-admin-key-1
- 用户1：w00000002 / sk-test-user-key-1
- 用户2：w00000003 / sk-test-user-key-2
```

**Step 2: Commit changes**

```bash
git add README.md
git commit -m "docs: add user management documentation"
```

---

### Task 5.4: 运行完整测试

**Step 1: 启动服务器**

```bash
python main.py
```

**Step 2: 在另一个终端运行测试**

```bash
pytest tests/test_user_management.py -v
```

Expected output:
```
tests/test_user_management.py::test_login_success PASSED
tests/test_user_management.py::test_login_failure PASSED
tests/test_user_management.py::test_upload_requires_auth PASSED
tests/test_user_management.py::test_admin_requires_admin_role PASSED
tests/test_user_management.py::test_upload_and_approval_flow PASSED
```

**Step 3: 手动测试流程**

1. 访问 http://localhost:28000
2. 点击"登录"按钮
3. 使用测试账号登录
4. 尝试上传 Skill
5. 切换到管理员账号
6. 在管理后台审批 Skill
7. 返回首页下载已批准的 Skill

**Step 4: 创建最终 commit**

```bash
git add .
git commit -m "feat: complete user management system implementation"
```

---

## 完成检查清单

在标记任务完成前，确保：

- [ ] 所有数据库表已创建并包含正确的索引
- [ ] 用户可以登录和登出
- [ ] 普通用户可以上传 Skills（pending 状态）
- [ ] 管理员可以审批/拒绝 Skills
- [ ] 只有已批准的 Skills 可以被下载
- [ ] 下载记录包含用户 ID
- [ ] 用户可以查看自己的上传和下载历史
- [ ] 管理员可以访问统计面板
- [ ] 所有测试通过
- [ ] 文档已更新

---

## 故障排查

### 数据库问题

```bash
# 查看数据库内容
sqlite3 data/registry.db "SELECT * FROM users;"
sqlite3 data/registry.db "SELECT * FROM skills;"
sqlite3 data/registry.db "SELECT * FROM downloads;"
```

### Session 问题

检查 .env 中的 SECRET_KEY 是否设置：
```bash
echo "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')" >> .env
```

### 权限问题

确保 data/ 和 data/pending/ 目录可写：
```bash
chmod -R 755 data/
```
