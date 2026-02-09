# 用户管理、技能自管理和审核通知系统设计

**项目**: Claude Code Skill Registry 功能优化
**日期**: 2025-02-09
**状态**: 设计阶段
**优先级**: 高

---

## 概述

本次优化包含三个核心模块的升级，旨在提升管理效率和用户体验：

1. **用户管理系统** - 管理员对用户的完整 CRUD 操作
2. **用户技能自管理** - 用户管理自己上传的技能（下架/上架/版本管理）
3. **审核通知系统** - 修复审核 Bug 并实现站内消息通知

---

## 第一部分：用户管理系统

### 1.1 功能需求

**管理员用户管理功能包括：**

- **用户列表页面**
  - 展示所有用户（支持分页，默认每页 20 条）
  - 显示字段：工号、角色、创建时间、最后登录、技能数量、状态
  - 支持按工号搜索、按角色筛选
  - 操作列：编辑、删除、重置 API Key

- **新增用户**
  - 表单字段：工号（必填）、角色（必填）
  - 系统自动生成 32 位随机 API Key
  - 创建成功后显示 API Key 供复制（仅一次显示机会）

- **编辑用户**
  - 可修改：角色
  - 不可修改：工号（主键）
  - 额外操作：重置 API Key（生成新的）

- **删除用户**
  - 软删除：标记用户为"已禁用"状态
  - 检查用户是否有关联技能，有则提示不允许删除
  - 管理员可以重新启用已删除用户

### 1.2 数据库设计

```sql
-- users 表新增字段
ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'; -- active/disabled
ALTER TABLE users ADD COLUMN skills_count INTEGER DEFAULT 0; -- 技能数量统计

-- 创建索引
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_employee_id ON users(employee_id);
```

### 1.3 API 接口设计

**获取用户列表**
```
GET /api/admin/users
Query Parameters:
  - page: int (default: 1)
  - per_page: int (default: 20, max: 100)
  - search: string (可选，按工号搜索)
  - role: string (可选，按角色筛选)
  - status: string (可选，按状态筛选)

Response:
{
  "success": true,
  "data": [
    {
      "id": 1,
      "employee_id": "123456",
      "role": "user",
      "status": "active",
      "skills_count": 5,
      "created_at": "2025-01-01T10:00:00",
      "last_login": "2025-02-09T10:30:00"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

**创建用户**
```
POST /api/admin/users
Body:
{
  "employee_id": "123456",
  "role": "user"
}

Response:
{
  "success": true,
  "data": {
    "id": 1,
    "employee_id": "123456",
    "role": "user",
    "api_key": "generated-32-char-key",
    "status": "active",
    "created_at": "2025-02-09T10:30:00"
  },
  "message": "API Key 仅显示一次，请立即复制保存"
}
```

**更新用户**
```
PUT /api/admin/users/{id}
Body:
{
  "role": "admin"
}

Response:
{
  "success": true,
  "data": {
    "id": 1,
    "employee_id": "123456",
    "role": "admin",
    "status": "active",
    "updated_at": "2025-02-09T10:35:00"
  }
}
```

**删除/禁用用户**
```
DELETE /api/admin/users/{id}
Response:
{
  "success": true,
  "message": "用户已禁用"
}

Error Response (用户有技能):
{
  "success": false,
  "error": "USER_HAS_SKILLS",
  "message": "该用户有 5 个技能，无法删除",
  "skills_count": 5
}
```

**重置 API Key**
```
POST /api/admin/users/{id}/reset-key
Response:
{
  "success": true,
  "data": {
    "api_key": "new-32-char-key"
  },
  "message": "新 API Key 已生成，旧 Key 立即失效"
}
```

### 1.4 界面设计

**用户管理页面布局：**
```
┌─────────────────────────────────────────────────────┐
│  用户管理                            [+ 新增用户]   │
├─────────────────────────────────────────────────────┤
│  搜索: [_______]  角色: [全部 ▼]       [查询]      │
├─────────────────────────────────────────────────────┤
│  工号    │ 角色   │ 技能数 │ 最后登录  │ 操作      │
│  123456  │ 用户   │ 5      │ 2月9日    │ [编辑]    │
│          │        │        │           │ [删除]    │
│  654321  │ 管理员 │ 0      │ 2月8日    │ [编辑]    │
│          │        │        │           │ [重置密钥]│
└─────────────────────────────────────────────────────┘
│              共 150 条   [1] [2] [3] ...             │
```

**新增用户对话框：**
```
┌─────────────────────────────┐
│  新增用户                   │
├─────────────────────────────┤
│  工号: [_______________]     │
│                             │
│  角色: [用户 ▼]             │
│        - 管理员              │
│        - 用户                │
│                             │
│        [取消]      [创建]    │
└─────────────────────────────┘

创建成功后显示：
┌─────────────────────────────┐
│  用户创建成功               │
├─────────────────────────────┤
│  API Key:                   │
│  [xxxxxxxxxxxxxxxxxxxxxxx]   │
│                             │
│  [复制到剪贴板]  [关闭]      │
│                             │
│  ⚠️ 请立即保存，关闭后无法再次查看 │
└─────────────────────────────┘
```

---

## 第二部分：用户技能自管理

### 2.1 功能需求

**用户专属的"我的技能"管理功能：**

- **我的技能页面**
  - 路由：`/my-skills`
  - 展示当前用户上传的所有技能（包括所有版本）
  - 显示字段：技能名称、版本、状态、创建时间、下载次数、审核状态
  - 支持按状态筛选：全部/已发布/已下架/待审核/已拒绝

- **下架功能**
  - 操作：点击"下架"按钮
  - 逻辑：将 `skills` 表的 `is_active` 字段设为 `false`
  - 效果：技能不再出现在首页和市场索引中
  - 数据保留：所有版本数据保留，可重新上架

- **重新上架功能**
  - 操作：对已下架的技能点击"重新上架"
  - 逻辑：将 `is_active` 设为 `true`
  - 无需重新审核：已审核通过的技能可直接上架

- **版本管理**
  - 展示技能的所有版本，按时间倒序
  - 支持设置"默认版本"（下载时优先使用）
  - 每个版本显示：版本号、上传时间、下载次数、状态

### 2.2 数据库设计

```sql
-- skills 表新增字段
ALTER TABLE skills ADD COLUMN is_active BOOLEAN DEFAULT true; -- 是否上架
ALTER TABLE skills ADD COLUMN is_default_version BOOLEAN DEFAULT false; -- 是否默认版本

-- 创建索引
CREATE INDEX idx_skills_is_active ON skills(is_active);
CREATE INDEX idx_skills_uploader_active ON skills(uploader_id, is_active);
```

### 2.3 API 接口设计

**获取我的技能列表**
```
GET /api/my-skills
Query Parameters:
  - status: string (可选，all/active/unlisted/pending/rejected)
  - page: int (default: 1)
  - per_page: int (default: 20)

Response:
{
  "success": true,
  "data": [
    {
      "id": 1,
      "skill_name": "code-reviewer",
      "version": "1.0.0",
      "is_active": true,
      "is_default_version": true,
      "status": "approved",
      "uploaded_at": "2025-02-09T10:30:00",
      "download_count": 150,
      "versions": [
        {"version": "1.0.0", "is_default": true, "downloads": 150},
        {"version": "1.1.0", "is_default": false, "downloads": 30}
      ]
    }
  ],
  "pagination": {...}
}
```

**下架技能**
```
POST /api/my-skills/{id}/unlist
Response:
{
  "success": true,
  "message": "技能已下架"
}
```

**重新上架技能**
```
POST /api/my-skills/{id}/publish
Response:
{
  "success": true,
  "message": "技能已重新上架"
}
```

**设置默认版本**
```
POST /api/my-skills/{id}/set-default
Body:
{
  "version": "1.1.0"
}

Response:
{
  "success": true,
  "message": "默认版本已更新"
}
```

**获取技能的所有版本**
```
GET /api/my-skills/{skill_name}/versions
Response:
{
  "success": true,
  "data": [
    {
      "id": 1,
      "version": "1.0.0",
      "is_active": true,
      "is_default": true,
      "uploaded_at": "2025-02-01T10:00:00",
      "download_count": 150
    },
    {
      "id": 2,
      "version": "1.1.0",
      "is_active": true,
      "is_default": false,
      "uploaded_at": "2025-02-09T10:00:00",
      "download_count": 30
    }
  ]
}
```

### 2.4 界面设计

**我的技能页面布局：**
```
┌─────────────────────────────────────────────────────┐
│  我的技能                            [上传新技能]   │
├─────────────────────────────────────────────────────┤
│  筛选: [全部 ▼]    搜索: [_______________]         │
├─────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────┐  │
│  │ code-reviewer                     [已发布]   │  │
│  │ 版本: 1.0.0 (默认)  │ 上传: 2月9日          │  │
│  │ 下载: 150次         │ 审核: 已通过           │  │
│  │ [查看版本] [下架] [重新上传]               │  │
│  └─────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────┐  │
│  │ test-helper                       [已下架]   │  │
│  │ 版本: 2.0.0        │ 上传: 2月8日          │  │
│  │ 下载: 0次           │ 审核: 已通过           │  │
│  │ [查看版本] [重新上架] [重新上传]           │  │
│  └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**版本管理对话框：**
```
┌─────────────────────────────┐
│  code-reviewer 版本管理     │
├─────────────────────────────┤
│  版本   │ 状态   │ 默认 │ 操作│
│  1.0.0  │ 已发布 │ ✓   │ [设] │
│  1.1.0  │ 已发布 │     │ [设] │
│  2.0.0  │ 已下架 │     │ [设] │
│                             │
│         [关闭]              │
└─────────────────────────────┘
```

### 2.5 数据流

**下架技能流程：**
```
用户                           skills表              文件系统
 │                               │                      │
 │  1. 点击"下架"                │                      │
 │  ──────────────────────────► │                      │
 │                               │ 2. UPDATE skills      │
 │                               │    SET is_active=0    │
 │                               │    WHERE id=?         │
 │  3. 返回成功                  │                      │
 │  ◄────────────────────────── │                      │
 │                               │                      │
 │                               │    文件保留，不删除    │
```

**版本管理数据结构：**
```
skills 表数据示例：
┌────┬───────────────┬────────┬───────────┬─────────────┐
│ id │ skill_name    │ version│ is_active  │ is_default  │
├────┼───────────────┼────────┼───────────┼─────────────┤
│ 1  │ code-reviewer │ 1.0.0  │ true       │ true        │  ← 默认版本
│ 2  │ code-reviewer │ 1.1.0  │ true       │ false       │
│ 3  │ code-reviewer │ 2.0.0  │ false      │ false       │  ← 已下架
└────┴───────────────┴────────┴───────────┴─────────────┘

下载时优先使用 is_default=true 的版本
```

---

## 第三部分：审核通知系统

### 3.1 Bug 修复

**问题定位：**
错误 "Failed to approve skill 2" 来自 `gitea_integration.py` 的 `approve_skill_file` 函数

**根本原因：**
- 函数使用 `shutil.move` 移动文件
- 当目标路径已存在同名文件时，移动操作失败
- 缺少文件存在检查和预清理逻辑

**修复方案：**
```python
def approve_skill_file(skill_id: int) -> bool:
    """Approve a skill by moving it from pending to plugins directory.

    Args:
        skill_id: The ID of the skill to approve

    Returns:
        True if successful, False otherwise
    """
    from database import get_skill_by_id, update_skill_status
    import os

    # Get skill record
    skill = get_skill_by_id(skill_id)
    if not skill:
        logger.error(f"Skill {skill_id} not found")
        return False

    if skill["status"] != "pending":
        logger.warning(f"Skill {skill_id} is not in pending status: {skill['status']}")
        return False

    # Move file from pending to plugins
    pending_path = PENDING_DIR / skill["filename"]
    plugins_path = PLUGINS_DIR / skill["filename"]

    if not pending_path.exists():
        logger.error(f"Pending file not found: {pending_path}")
        return False

    try:
        # Fix: Check and remove existing file
        if plugins_path.exists():
            logger.info(f"Removing existing file: {plugins_path}")
            plugins_path.unlink()

        # Move file
        shutil.move(str(pending_path), str(plugins_path))

        # Update database status
        update_skill_status(skill_id, "approved")

        # Create notification for uploader
        from database import create_notification
        create_notification(
            user_id=skill["uploader_id"],
            type="review_success",
            title="您的技能已通过审核",
            content=f"技能 {skill['skill_name']} v{skill['version']} 已通过审核",
            related_skill_id=skill_id
        )

        logger.info(f"Successfully approved skill {skill_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to approve skill {skill_id}: {e}")
        return False
```

### 3.2 通知系统设计

**通知表设计：**
```sql
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,           -- 接收用户
    type TEXT NOT NULL,                 -- 类型：review_success/review_rejected
    title TEXT NOT NULL,                -- 标题
    content TEXT,                       -- 内容
    related_skill_id INTEGER,           -- 关联技能
    is_read BOOLEAN DEFAULT false,      -- 是否已读
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (related_skill_id) REFERENCES skills(id)
);

-- 创建索引
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read);
CREATE INDEX idx_notifications_created ON notifications(created_at DESC);
```

**通知触发时机：**
- **审核通过**：创建通知，标题"您的技能已通过审核"，内容包含技能名称和版本
- **审核拒绝**：创建通知，标题"您的技能未通过审核"，内容包含拒绝原因

### 3.3 API 接口设计

**获取通知列表**
```
GET /api/notifications
Query Parameters:
  - page: int (default: 1)
  - per_page: int (default: 10)

Response:
{
  "success": true,
  "data": [
    {
      "id": 1,
      "type": "review_success",
      "title": "您的技能已通过审核",
      "content": "技能 code-reviewer v1.0.0 已通过审核",
      "related_skill_id": 10,
      "is_read": false,
      "created_at": "2025-02-09T10:30:00"
    }
  ],
  "unread_count": 3,
  "pagination": {...}
}
```

**获取未读数量**
```
GET /api/notifications/unread-count
Response:
{
  "success": true,
  "count": 3
}
```

**标记为已读**
```
POST /api/notifications/{id}/read
Response:
{
  "success": true,
  "message": "已标记为已读"
}
```

**标记全部为已读**
```
POST /api/notifications/read-all
Response:
{
  "success": true,
  "message": "所有通知已标记为已读"
}
```

### 3.4 界面设计

**导航栏更新：**
```
┌──────────────────────────────────────────────────┐
│ [首页] [我的技能] [上传] [管理后台]   [🔔 3]   │
│                                              用户 ▼│
└──────────────────────────────────────────────────┘
```

**通知下拉面板：**
```
┌──────────────────────────────┐
│  通知 (3 条未读)    [全部已读]│
├──────────────────────────────┤
│  ● 您的技能已通过审核       │
│    code-reviewer v1.0.0     │
│    2分钟前                  │
├──────────────────────────────┤
│  ● 您的技能未通过审核       │
│    test-helper v2.0.0       │
│    原因：格式错误            │
│    1小时前                  │
├──────────────────────────────┤
│  ○ 系统公告                │
│    维护通知                │
│    昨天                     │
├──────────────────────────────┤
│          [查看全部通知]      │
└──────────────────────────────┘
```

### 3.5 审核通知流程

```
管理员                       skills表              notifications表      用户
 │                               │                      │             │
 │  1. 点击"批准"                │                      │             │
 │  ──────────────────────────► │                      │             │
 │                               │ 2. UPDATE status      │             │
 │                               │    = 'approved'       │             │
 │                               │ 3. INSERT notification │             │
 │                               │    (user_id, type,    │             │
 │                               │     title, content)   │             │
 │                               │                      │ 4. 登录系统   │
 │                               │                      │ ◄────────── │
 │                               │                      │ 5. 查询通知   │
 │                               │                      │ ──────────► │
 │                               │                      │ 6. 显示未读数 │
 │                               │                      │ ◄────────── │
 │                               │                      │ 7. 点击通知   │
 │                               │                      │ ──────────► │
 │                               │                      │ 8. 标记已读   │
 │                               │                      │ ◄────────── │
```

---

## 第四部分：错误处理和边界情况

### 4.1 用户管理模块

**边界情况处理：**

- **工号重复**：返回 409 Conflict，提示"该工号已存在"
- **删除有技能的用户**：返回 400 Bad Request，提示"该用户有 X 个技能，请先转移或删除技能"
- **重置 API Key**：需要二次确认"确定要重置吗？旧 Key 将立即失效"
- **编辑用户**：不允许修改自己的工号和角色（防止管理员锁死自己）

**错误示例：**
```json
// 工号已存在
{
  "success": false,
  "error": "EMPLOYEE_ID_EXISTS",
  "message": "工号 123456 已存在",
  "suggestion": "请检查工号是否输入正确"
}

// 不能删除有技能的用户
{
  "success": false,
  "error": "USER_HAS_SKILLS",
  "message": "该用户有 5 个技能，无法删除",
  "skills_count": 5,
  "suggestion": "请先转移这些技能到其他用户或删除技能"
}
```

### 4.2 技能管理模块

**边界情况处理：**

- **下架正在被下载的技能**：允许下架，已开始的下载继续完成
- **下架已集成到 Gitea 的技能**：只下架本地，不影响 Gitea 仓库
- **删除最后一个版本**：不允许删除，至少保留一个版本
- **重新上传同名版本**：检查版本是否已存在，存在则提示"该版本已存在，请使用新版本号"

**版本管理逻辑：**
```
上传技能时检查：
IF skill_name AND version 已存在 AND 上传者 = 当前用户 THEN
    提示"该版本已存在，是否覆盖？"
ELSE IF skill_name AND version 已存在 AND 上传者 ≠ 当前用户 THEN
    返回错误"该技能已被其他用户创建"
END IF
```

### 4.3 审核通知模块

**边界情况处理：**

- **重复审核**：检查状态，避免重复批准或拒绝
- **通知过多**：限制每个用户最多保留 100 条通知，超出的自动删除旧通知
- **离线用户**：通知存储在数据库，用户登录后加载

**通用错误格式：**
```json
{
  "success": false,
  "error": "ERROR_CODE",
  "message": "用户友好的错误描述",
  "details": {}
}
```

**常见错误码：**
- `UNAUTHORIZED` - 未登录
- `FORBIDDEN` - 无权限
- `NOT_FOUND` - 资源不存在
- `VALIDATION_ERROR` - 参数验证失败
- `DUPLICATE_ERROR` - 资源重复
- `OPERATION_NOT_ALLOWED` - 不允许的操作

---

## 第五部分：实施计划

### 5.1 开发任务分解

**阶段 1：用户管理（预计 1 天）**
- [ ] 数据库 schema 更新
- [ ] 后端 API 开发（5 个接口）
- [ ] 前端页面开发（用户列表、新增对话框）
- [ ] 单元测试和集成测试

**阶段 2：技能自管理（预计 1 天）**
- [ ] 数据库 schema 更新
- [ ] 后端 API 开发（5 个接口）
- [ ] 前端页面开发（我的技能、版本管理）
- [ ] 状态筛选和搜索功能
- [ ] 单元测试和集成测试

**阶段 3：审核通知（预计 0.5 天）**
- [ ] Bug 修复（approve_skill_file 函数）
- [ ] 数据库 schema 更新（notifications 表）
- [ ] 后端 API 开发（4 个接口）
- [ ] 前端通知组件开发
- [ ] 导航栏更新
- [ ] 单元测试和集成测试

**阶段 4：测试和优化（预计 0.5 天）**
- [ ] 端到端测试
- [ ] 性能测试
- [ ] 安全测试
- [ ] Bug 修复

### 5.2 技术依赖

**新增依赖：**
- 无（使用现有技术栈）

**数据库变更：**
- users 表：新增 status, skills_count 字段
- skills 表：新增 is_active, is_default_version 字段
- 新增 notifications 表

### 5.3 兼容性

**向后兼容：**
- 所有新增字段都有默认值
- 旧数据自动兼容
- API 版本保持不变（仅新增接口）

**前端兼容：**
- 现有页面不受影响
- 导航栏新增链接（向下兼容）

---

## 第六部分：测试计划

### 6.1 用户管理功能测试

**单元测试用例：**
- ✓ 创建用户 - 正常流程
- ✓ 创建用户 - 工号重复（应失败）
- ✓ 创建用户 - 生成唯一 API Key
- ✓ 编辑用户 - 修改角色
- ✓ 编辑用户 - 尝试修改工号（应失败）
- ✓ 删除用户 - 正常流程
- ✓ 删除用户 - 用户有技能（应失败）
- ✓ 重置 API Key - 生成新 Key
- ✓ 用户列表 - 分页功能
- ✓ 用户列表 - 搜索功能

**集成测试：**
- ✓ 管理员创建用户后，用户可立即登录
- ✓ 禁用用户后无法登录
- ✓ 重新启用用户后可正常登录

### 6.2 技能管理功能测试

**单元测试用例：**
- ✓ 下架技能 - 正常流程
- ✓ 下架技能 - 再次下架（应提示已下架）
- ✓ 重新上架 - 正常流程
- ✓ 重新上架 - 未下架的技能（应提示）
- ✓ 版本列表 - 显示所有版本
- ✓ 设置默认版本 - 正常流程
- ✓ 上传同名版本 - 应拒绝或提示覆盖
- ✓ 删除最后一个版本 - 应拒绝

**界面测试：**
- ✓ 我的技能页面 - 只显示当前用户的技能
- ✓ 下架后技能不在首页显示
- ✓ 重新上架后技能重新出现
- ✓ 导航栏"我的技能"链接可访问

### 6.3 审核通知功能测试

**功能测试：**
- ✓ 审核通过 - 创建成功通知
- ✓ 审核拒绝 - 创建拒绝通知（含原因）
- ✓ 通知显示 - 未读红点和数量
- ✓ 点击通知 - 标记为已读
- ✓ 全部已读 - 一键标记所有通知
- ✓ Bug 修复 - 批准技能不再报错

**边界测试：**
- ✓ 重复审核同一技能 - 应拒绝
- ✓ 审核不存在的技能 - 应 404
- ✓ 通知超过 100 条 - 自动清理旧通知
- ✓ 通知列表分页 - 每页 10 条

### 6.4 端到端测试场景

**场景 1：完整的用户生命周期**
1. 管理员创建用户（工号 999999）
2. 新用户登录并上传技能
3. 管理员审核通过
4. 用户收到通知
5. 用户下架技能
6. 管理员禁用用户
7. 用户无法登录

**场景 2：技能版本管理**
1. 用户上传技能 v1.0.0
2. 审核通过并发布
3. 用户上传 v1.1.0
4. 审核通过
5. 用户查看版本列表（显示 2 个版本）
6. 用户下架 v1.0.0
7. 系统默认使用 v1.1.0

**场景 3：审核通知**
1. 用户上传 3 个技能
2. 管理员批准 1 个，拒绝 2 个
3. 用户登录看到 3 条通知
4. 用户点击查看通知内容
5. 通知标记为已读

### 6.5 性能测试

- ✓ 用户列表加载 - 1000 用户 < 500ms
- ✓ 我的技术列表 - 100 个技能 < 300ms
- ✓ 通知列表加载 - 100 条通知 < 200ms
- ✓ 下架/上架操作 - < 100ms
- ✓ 创建用户 - < 200ms

### 6.6 安全测试

- ✓ 普通用户无法访问用户管理页面
- ✓ 普通用户无法下架他人技能
- ✓ 管理员无法删除自己（防止锁死）
- ✓ API Key 生成足够随机（32 字符）
- ✓ 审核操作记录审计日志

---

## 第七部分：验收标准

### 7.1 功能验收

**用户管理：**
- ✓ 管理员可以创建用户（输入工号+角色，系统生成 API Key）
- ✓ 管理员可以编辑用户角色
- ✓ 管理员可以删除/禁用用户
- ✓ 管理员可以重置用户的 API Key
- ✓ 用户列表支持搜索和分页

**技能自管理：**
- ✓ 用户可以在"我的技能"页面查看所有上传的技能
- ✓ 用户可以下架自己上传的技能
- ✓ 用户可以重新上架已下架的技能
- ✓ 用户可以查看技能的所有版本
- ✓ 用户可以设置默认版本

**审核通知：**
- ✓ 审核功能不再报错
- ✓ 用户登录后可以看到审核结果通知
- ✓ 导航栏显示未读通知数量
- ✓ 点击通知可以标记为已读

### 7.2 性能验收

- 所有页面加载时间 < 1 秒
- API 响应时间 < 200ms
- 支持 1000+ 用户和 1000+ 技能

### 7.3 安全验收

- 所有操作有权限检查
- 敏感操作记录审计日志
- API Key 安全生成和存储

---

## 附录

### A. 数据库 Migration 脚本

```python
# migration_add_user_management.py
def upgrade():
    """Add user management features"""
    # Add status and skills_count to users table
    conn.execute("""
        ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'
    """)
    conn.execute("""
        ALTER TABLE users ADD COLUMN skills_count INTEGER DEFAULT 0
    """)

    # Add is_active and is_default_version to skills table
    conn.execute("""
        ALTER TABLE skills ADD COLUMN is_active BOOLEAN DEFAULT true
    """)
    conn.execute("""
        ALTER TABLE skills ADD COLUMN is_default_version BOOLEAN DEFAULT false
    """)

    # Create notifications table
    conn.execute("""
        CREATE TABLE notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            related_skill_id INTEGER,
            is_read BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (related_skill_id) REFERENCES skills(id)
        )
    """)

    # Create indexes
    conn.execute("CREATE INDEX idx_users_status ON users(status)")
    conn.execute("CREATE INDEX idx_skills_is_active ON skills(is_active)")
    conn.execute("CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read)")
    conn.commit()

def downgrade():
    """Revert changes"""
    conn.execute("DROP TABLE notifications")
    conn.execute("ALTER TABLE skills DROP COLUMN is_default_version")
    conn.execute("ALTER TABLE skills DROP COLUMN is_active")
    conn.execute("ALTER TABLE users DROP COLUMN skills_count")
    conn.execute("ALTER TABLE users DROP COLUMN status")
    conn.commit()
```

### B. API 密钥生成函数

```python
import secrets
import string

def generate_api_key(length=32):
    """Generate a secure random API key."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))
```

### C. 通知创建函数

```python
def create_notification(user_id: int, type: str, title: str,
                        content: str, related_skill_id: int = None):
    """Create a notification for a user."""
    from database import get_connection

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO notifications (user_id, type, title, content, related_skill_id)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, type, title, content, related_skill_id))
        conn.commit()
```

---

**文档版本**: 1.0.0
**最后更新**: 2025-02-09
**作者**: Claude Sonnet
**状态**: 待评审
