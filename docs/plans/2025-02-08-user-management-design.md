# 用户管理系统 - 设计文档

## 概述

为 Skill Registry 添加完整的用户管理系统，支持基于工号和 API KEY 的登录认证、角色权限控制、Skill 审批流程以及下载审计功能。

## 需求

### 1. 用户登录
- 用户使用工号（格式：字母+8位数字，如 `w00545471`）+ API_KEY 登录
- 工号和 KEY 由管理员预先写入数据库
- 登录成功后建立会话，支持上传和下载 Skills

### 2. 角色权限
- **管理员**：可以审批 Skills、删除 Skills、查看统计数据
- **普通用户**：可以上传和下载已批准的 Skills

### 3. Skill 审批流程
- 普通用户上传的 Skills 状态为 `pending`（待审批）
- 管理员审批后状态变为 `approved` 或 `rejected`
- 只有 `approved` 状态的 Skills 才对其他用户可见和可下载

### 4. 审计日志
- 记录每次 Skill 下载的下载人（工号）和下载时间
- 记录 Skill 上传的上传人和上传时间
- 记录审批操作（审批人、审批时间、审批意见）

## 数据库设计

基于现有的 `registry.db`（SQLite），添加以下表：

### users 表

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT UNIQUE NOT NULL,  -- 工号，格式：字母+8位数字
    api_key TEXT NOT NULL,             -- LiteLLM API KEY
    role TEXT NOT NULL DEFAULT 'user', -- 'admin' 或 'user'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
)
```

**索引**：
```sql
CREATE INDEX idx_users_employee_id ON users(employee_id);
```

### skills 表

```sql
CREATE TABLE skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL,
    version TEXT NOT NULL,
    filename TEXT NOT NULL,
    uploader_id INTEGER NOT NULL,      -- 关联 users.id
    status TEXT DEFAULT 'pending',     -- 'pending', 'approved', 'rejected'
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,
    reviewer_id INTEGER,               -- 关联 users.id（管理员）
    review_comment TEXT,
    FOREIGN KEY (uploader_id) REFERENCES users(id),
    FOREIGN KEY (reviewer_id) REFERENCES users(id)
)
```

**索引**：
```sql
CREATE INDEX idx_skills_status ON skills(status);
CREATE INDEX idx_skills_uploader ON skills(uploader_id);
```

### downloads 表修改

在现有的 `downloads` 表添加字段：
```sql
ALTER TABLE downloads ADD COLUMN user_id INTEGER REFERENCES users(id);
```

### 初始化数据

管理员可以直接在数据库中插入初始用户：
```sql
INSERT INTO users (employee_id, api_key, role) VALUES
('w00000001', 'sk-admin-key-1', 'admin'),
('w00000002', 'sk-user-key-1', 'user'),
('w00000003', 'sk-user-key-2', 'user');
```

## 认证与授权系统

### 登录端点

**POST /api/login**

请求：
```json
{
  "employee_id": "w00545471",
  "api_key": "sk-..."
}
```

响应（成功）：
```json
{
  "success": true,
  "user": {
    "employee_id": "w00545471",
    "role": "user"
  }
}
```

响应（失败）：
```json
{
  "success": false,
  "error": "Invalid credentials"
}
```

### Session 管理

使用现有的 FastAPI SessionMiddleware：

```python
# 登录成功后
request.session["user_id"] = user.id
request.session["employee_id"] = user.employee_id
request.session["role"] = user.role

# 退出登录
request.session.clear()
```

### 权限装饰器

```python
def require_auth(request: Request):
    """要求用户登录"""
    if "user_id" not in request.session:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

def require_admin(request: Request):
    """要求管理员权限"""
    if request.session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return True
```

### 受保护的端点

| 端点 | 方法 | 权限要求 |
|------|------|----------|
| `/api/login` | POST | 公开 |
| `/api/logout` | POST | 登录用户 |
| `/api/upload` | POST | 登录用户 |
| `/api/upload-batch` | POST | 登录用户 |
| `/plugins/{filename}` | GET | 登录用户 |
| `/api/pending` | GET | 管理员 |
| `/api/review/{skill_id}` | POST | 管理员 |
| `/admin/plugins/{filename}` | DELETE | 管理员 |
| `/api/admin/stats` | GET | 管理员 |
| `/api/user/uploads` | GET | 登录用户 |
| `/api/user/downloads` | GET | 登录用户 |

## Skill 上传与审批流程

### 上传流程

1. **用户上传 Skill**：`POST /api/upload`
   - 验证用户已登录
   - 验证 ZIP 文件格式（现有的 `validate_skill_zip()`）
   - 保存到临时位置：`data/pending/{skill_id}.zip`
   - 在 skills 表创建记录，状态设为 `pending`
   - 返回上传成功提示

2. **上传响应**：
```json
{
  "success": true,
  "message": "Skill uploaded successfully, awaiting admin approval",
  "skill_id": 123
}
```

### 审批流程

**管理员审批**：`POST /api/review/{skill_id}`

请求：
```json
{
  "action": "approve",  // 或 "reject"
  "comment": "审核意见（可选）"
}
```

审批通过：
- 将 ZIP 从 `data/pending/` 移到 `plugins/` 目录
- 更新 skills 表：`status = 'approved'`
- 记录审批人（`reviewer_id`）和审批时间（`reviewed_at`）

审批拒绝：
- 删除 `data/pending/{skill_id}.zip` 临时文件
- 更新 skills 表：`status = 'rejected'`
- 记录拒绝原因（`review_comment`）

### 核心函数修改

```python
def save_skill_zip(
    temp_zip: Path,
    metadata: dict,
    uploader_id: int,
    status: str = "pending"
) -> int:
    """保存 skill ZIP 到临时位置并创建数据库记录。

    Returns:
        skill_id
    """
    # 保存到 data/pending/
    # 插入 skills 表
    # 返回 skill_id

def approve_skill(skill_id: int, reviewer_id: int) -> bool:
    """批准 skill，移动文件到 plugins 目录。"""
    # 更新 skills 表
    # 移动文件
    # 返回成功/失败

def reject_skill(skill_id: int, reviewer_id: int, comment: str) -> bool:
    """拒绝 skill，删除临时文件。"""
    # 更新 skills 表
    # 删除文件
    # 返回成功/失败
```

## 下载审计与统计

### 下载记录增强

修改 `record_download()` 函数：
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

### 下载端点修改

`GET /plugins/{filename}`：
- 检查用户是否登录（`require_auth`）
- 从 session 获取 `user_id`
- 调用 `record_download()` 时传入 `user_id`

### 新增统计 API

**1. 用户下载历史**：`GET /api/user/downloads`

查询参数：
- `page`: 页码（默认 1）
- `per_page`: 每页数量（默认 20）

响应：
```json
{
  "downloads": [
    {
      "skill_name": "auditing-python-security",
      "version": "1.0.0",
      "downloaded_at": "2025-02-08T10:30:00"
    }
  ],
  "total": 10,
  "page": 1,
  "per_page": 20
}
```

**2. 用户上传历史**：`GET /api/user/uploads`

响应：
```json
{
  "uploads": [
    {
      "skill_id": 123,
      "skill_name": "my-skill",
      "version": "1.0.0",
      "status": "approved",
      "uploaded_at": "2025-02-08T09:00:00",
      "review_comment": null
    }
  ],
  "total": 5
}
```

**3. 管理员统计面板**：`GET /api/admin/stats`

响应：
```json
{
  "summary": {
    "total_users": 25,
    "pending_skills": 3,
    "approved_skills": 50,
    "today_downloads": 15
  },
  "top_skills": [
    {"skill_name": "skill-a", "downloads": 120},
    {"skill_name": "skill-b", "downloads": 95}
  ],
  "top_users": [
    {"employee_id": "w00000001", "downloads": 45},
    {"employee_id": "w00000002", "downloads": 32}
  ]
}
```

**4. 待审批列表**：`GET /api/pending`

响应：
```json
{
  "pending": [
    {
      "skill_id": 123,
      "skill_name": "new-skill",
      "version": "1.0.0",
      "uploader": "w00545471",
      "uploaded_at": "2025-02-08T09:00:00"
    }
  ],
  "total": 3
}
```

## 前端界面修改

### 登录页面

**路由**：`GET/POST /login`

替代现有的 `/admin/login`，表单包含：
- 工号输入框（格式验证：字母+8位数字）
- API KEY 输入框（密码类型）
- 登录按钮

### 首页导航栏

- **未登录**：显示"登录"按钮
- **已登录**：显示"欢迎，{工号}" + "我的上传" + "退出"
- **管理员**：额外显示"管理后台"链接

### 主要页面

#### 1. Skill 列表页（`/`）

- 显示所有 `approved` 状态的 Skills
- 未登录：只显示 Skill 信息
- 已登录：显示下载按钮
- 点击下载：复制安装命令到剪贴板

#### 2. 上传页面（`/upload`）

- 所有登录用户可访问
- 上传表单（复用现有的上传界面）
- 上传成功后显示：
  - "等待管理员审批"提示
  - 用户上传历史表格（含状态）

#### 3. 管理后台（`/admin`）

仅管理员可访问，包含以下标签页：

**待审批**：
- 列出所有 `pending` 状态的 Skills
- 每行显示：Skill 名称、版本、上传人、上传时间
- 操作按钮：
  - "批准"：通过审批
  - "拒绝"：弹出对话框输入拒绝原因

**用户管理**（只读，初期）：
- 用户列表表格
- 显示：工号、角色、创建时间、最后登录
- 不支持编辑（初期通过数据库直接管理）

**统计面板**：
- 汇总数据卡片
- 下载排行榜（按 Skill）
- 活跃用户排行榜
- 审批趋势图（可选）

#### 4. 个人中心（`/profile`）

- 我的上传：显示用户上传的 Skills 及状态
- 我的下载：显示用户的下载历史
- 修改密码（未来功能）

### 退出登录

**GET /logout**
- 清除 session
- 重定向到登录页

## 会话流程

```
用户访问首页
    ↓
点击"登录"
    ↓
输入工号 + API KEY
    ↓
验证 credentials
    ↓
├─ 成功 → 创建 session
│         ↓
│         ├─ 普通用户 → 浏览/下载/上传 Skills
│         └─ 管理员   → 额外可审批 Skills、查看统计
│
└─ 失败 → 显示错误信息
```

## 实施步骤

### Phase 1: 数据库与认证基础
1. 扩展 `database.py`：添加 users、skills 表
2. 创建初始化脚本：插入测试用户数据
3. 修改 `main.py`：添加登录/登出端点
4. 创建权限装饰器：`require_auth`、`require_admin`

### Phase 2: 上传与审批流程
1. 修改 `save_skill_zip()`：支持 pending 状态
2. 创建 `approve_skill()` 和 `reject_skill()` 函数
3. 添加 `/api/review/{skill_id}` 端点
4. 修改 `/api/upload`：需要登录，保存为 pending

### Phase 3: 下载审计
1. 修改 `downloads` 表：添加 user_id 字段
2. 修改 `record_download()`：记录 user_id
3. 修改 `/plugins/{filename}`：要求登录
4. 添加用户下载/上传历史 API

### Phase 4: 前端界面
1. 创建新的登录页面模板
2. 修改导航栏：显示登录状态
3. 创建上传页面（含上传历史）
4. 创建管理后台（待审批、统计面板）

### Phase 5: 统计与测试
1. 添加管理员统计 API
2. 创建统计页面模板
3. 端到端测试：完整流程验证
4. 编写测试数据和使用文档

## 安全考虑

1. **API KEY 存储**：
   - 使用哈希存储（如 bcrypt）
   - 数据库文件设置适当权限

2. **Session 安全**：
   - 使用强密钥（SECRET_KEY）
   - 设置合理的过期时间

3. **SQL 注入防护**：
   - 使用参数化查询（已实现）
   - 验证所有输入

4. **文件上传安全**：
   - 验证 ZIP 文件格式（已实现）
   - 限制文件大小
   - 沙箱环境解析 ZIP

5. **审计日志**：
   - 记录所有敏感操作
   - 定期备份日志

## 未来扩展

- 用户注册功能（自动验证 API KEY）
- 批量导入用户
- 用户权限细粒度控制
- 邮件通知（审批结果）
- Skill 版本管理
- 下载限流
- OAuth 集成
