# Claude Code Skill Registry API 接口文档

## 目录

- [概述](#概述)
- [认证机制](#认证机制)
- [通用规范](#通用规范)
- [公开接口](#公开接口)
- [认证接口](#认证接口)
- [用户接口](#用户接口)
- [管理员接口](#管理员接口)
- [错误码](#错误码)
- [数据模型](#数据模型)

---

## 概述

### 基础信息

- **Base URL**: `http://your-domain:8000`
- **API 版本**: v1.0.0
- **数据格式**: JSON
- **字符编码**: UTF-8
- **认证方式**: Session Cookie

### 接口分类

| 类别 | 说明 | 权限要求 |
|------|------|----------|
| 公开接口 | 无需认证即可访问 | 无 |
| 认证接口 | 用户登录/登出 | 无 |
| 用户接口 | 普通用户功能 | 用户认证 |
| 管理员接口 | 管理员专属功能 | 管理员认证 |

---

## 认证机制

### Session 认证

系统使用 Session Cookie 进行用户认证：

1. **登录流程**
   - 调用 `POST /api/login` 接口
   - 提交工号 (`employee_id`) 和 API Key (`api_key`)
   - 服务器验证成功后创建 Session
   - 客户端自动保存 Session Cookie

2. **认证要求**
   - 所有需要认证的接口必须在请求头中携带 Session Cookie
   - 未认证的请求将返回 `401 Unauthorized`

3. **会话过期**
   - 默认会话有效期：24 小时
   - 过期后需要重新登录

### 权限控制

| 角色 | 权限范围 |
|------|----------|
| **user** | 上传技能、下载已批准技能、查看个人统计 |
| **admin** | 所有用户权限 + 审核技能、查看系统统计、管理用户、删除技能 |

---

## 通用规范

### 请求格式

```http
POST /api/endpoint HTTP/1.1
Host: your-domain:8000
Content-Type: application/json
Cookie: session=xxx

{
  "key": "value"
}
```

### 响应格式

**成功响应**:
```json
{
  "success": true,
  "data": {...}
}
```

**错误响应**:
```json
{
  "detail": "Error message"
}
```

### 分页参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码，默认 1 |
| per_page | integer | 否 | 每页数量，默认 20，最大 100 |

### 时间格式

所有时间字段使用 ISO 8601 格式：
```
2025-02-09T10:30:00
```

---

## 公开接口

### 1. 健康检查

检查服务运行状态。

**接口**: `GET /api/health`

**权限**: 无需认证

**请求参数**: 无

**响应示例**:
```json
{
  "status": "healthy",
  "timestamp": "2025-02-09T10:30:00",
  "version": "1.0.0",
  "service": "Skill Registry"
}
```

**状态码**:
- `200 OK` - 服务正常
- `503 Service Unavailable` - 服务异常

---

### 2. 市场索引

获取 Claude Code 市场索引文件，用于客户端自动发现技能。

**接口**: `GET /marketplace.json`

**权限**: 无需认证

**请求参数**: 无

**响应示例**:
```json
{
  "name": "private-registry",
  "owner": {
    "name": "Internal Registry",
    "email": "admin@company.local"
  },
  "metadata": {
    "version": "1.0.0",
    "description": "Internal Claude Code Skill Registry",
    "updated_at": "2025-02-09T10:30:00"
  },
  "plugins": [
    {
      "name": "code-reviewer",
      "version": "1.0.0",
      "description": "智能代码审查助手",
      "author": {"name": "张三"},
      "download_url": "http://localhost:8000/plugins/code-reviewer-1.0.0.zip",
      "size_kb": 15.2
    }
  ]
}
```

---

### 3. 技能列表

获取所有可用技能列表，支持分页。

**接口**: `GET /api/skills`

**权限**: 无需认证

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码，默认 1 |
| per_page | integer | 否 | 每页数量，默认 1000 |

**响应示例**:
```json
{
  "data": [
    {
      "name": "code-reviewer",
      "metadata": {
        "name": "code-reviewer",
        "version": "1.0.0",
        "description": "智能代码审查助手",
        "license": "MIT",
        "compatibility": "Claude Code 1.0+",
        "metadata": {
          "author": "w00545471",
          "version": "1.0.0"
        }
      },
      "versions": [
        {
          "version": "1.0.0",
          "filename": "code-reviewer-1.0.0.zip",
          "size": 15564,
          "updated_at": "2025-02-09T10:30:00"
        }
      ],
      "latest_version": "1.0.0"
    }
  ],
  "total": 100,
  "page": 1,
  "per_page": 1000,
  "total_pages": 1
}
```

---

### 4. 统计排行

获取技能下载排行统计。

**接口**: `GET /api/stats/top`

**权限**: 无需认证

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| start_date | string | 否 | 开始日期 (YYYY-MM-DD) |
| end_date | string | 否 | 结束日期 (YYYY-MM-DD) |

**响应示例**:
```json
{
  "period": {
    "start_date": "2025-02-01",
    "end_date": "2025-02-09"
  },
  "total_downloads": 1500,
  "rankings": [
    {
      "rank": 1,
      "skill_name": "code-reviewer",
      "downloads": 500,
      "author": "张三"
    },
    {
      "rank": 2,
      "skill_name": "security-scanner",
      "downloads": 380,
      "author": "李四"
    }
  ]
}
```

---

### 5. 导出统计

导出下载统计数据为 Excel 文件。

**接口**: `GET /api/stats/export`

**权限**: 无需认证

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| start_date | string | 否 | 开始日期 (YYYY-MM-DD) |
| end_date | string | 否 | 结束日期 (YYYY-MM-DD) |

**响应**:
- Content-Type: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- 文件名: `download_stats_{start}_to_{end}.xlsx`

---

## 认证接口

### 1. 用户登录

使用工号和 API Key 登录系统。

**接口**: `POST /api/login`

**权限**: 无需认证

**请求参数** (Form Data):

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| employee_id | string | 是 | 工号 |
| api_key | string | 是 | API 密钥 |

**请求示例**:
```http
POST /api/login HTTP/1.1
Content-Type: application/x-www-form-urlencoded

employee_id=123456&api_key=your-api-key
```

**响应**:
- 成功: 重定向到 `/` (HTTP 302)
- 失败: 重定向到 `/login?error=invalid` (HTTP 302)

---

### 2. 获取当前用户

获取当前登录用户的信息。

**接口**: `GET /api/me`

**权限**: 需要认证

**响应示例**:
```json
{
  "id": 1,
  "employee_id": "123456",
  "role": "user",
  "created_at": "2025-01-01T10:00:00",
  "last_login": "2025-02-09T10:30:00"
}
```

**错误响应**:
```json
{
  "detail": "Not authenticated"
}
```
状态码: `401 Unauthorized`

---

### 3. 用户登出

退出登录并清除 Session。

**接口**: `GET /logout`

**权限**: 无需认证（但会清除当前 Session）

**响应**: 重定向到 `/` (HTTP 302)

---

## 用户接口

### 1. 上传技能

上传新的技能插件文件。

**接口**: `POST /api/upload`

**权限**: 需要认证

**请求参数** (Multipart Form Data):

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | 技能 ZIP 文件 |

**请求示例**:
```http
POST /api/upload HTTP/1.1
Content-Type: multipart/form-data

file: skill.zip
```

**技能 ZIP 要求**:

1. **文件结构**:
```
skill-name/
├── SKILL.md          # 必需：技能元数据
└── prompt.md         # 必需：技能提示词
```

2. **SKILL.md 格式**:
```markdown
---
name: skill-name
description: 技能描述（1-1024字符）
metadata:
  version: "1.0.0"
  author: w00545471
license: MIT
compatibility: Claude Code 1.0+
---
技能详细说明...
```

3. **命名规范**:
   - 技能名称：1-64 字符，只能包含小写字母、数字和连字符
   - 不能以连字符开头或结尾
   - 不能包含连续连字符
   - 作者格式：小写字母 + 8 位数字（如 w00545471）

**响应** (HTML):
- 成功: 显示成功消息，2 秒后自动跳转
- 失败: 显示错误信息

**可能错误**:
- `400 Bad Request` - 文件格式不正确
- `409 Conflict` - 技能版本已存在
- `401 Unauthorized` - 未认证
- `500 Internal Server Error` - 服务器错误

---

### 2. 下载技能

下载指定技能的 ZIP 文件。

**接口**: `GET /plugins/{filename}`

**权限**: 需要认证

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| filename | string | ZIP 文件名 |

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| raw | boolean | 否 | true=返回原始ZIP，false=返回带安装脚本的ZIP（默认） |

**响应**:
- Content-Type: `application/zip`
- 自动包含安装脚本 (install.bat, install.sh)

---

### 3. 批量下载

批量下载多个技能并打包。

**接口**: `POST /api/batch-download`

**权限**: 需要认证

**请求体** (JSON):
```json
{
  "filenames": [
    "skill1-1.0.0.zip",
    "skill2-2.0.0.zip"
  ]
}
```

**响应**:
- Content-Type: `application/zip`
- 文件名: `skills-batch-{timestamp}.zip`
- 包含所有技能及批量安装脚本

---

### 4. 下载历史

获取当前用户的下载历史记录。

**接口**: `GET /api/user/downloads`

**权限**: 需要认证

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码，默认 1 |
| per_page | integer | 否 | 每页数量，默认 20 |

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "skill_name": "code-reviewer",
      "version": "1.0.0",
      "filename": "code-reviewer-1.0.0.zip",
      "download_time": "2025-02-09T10:30:00"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 50,
    "total_pages": 3
  }
}
```

---

### 5. 上传历史

获取当前用户的上传历史记录。

**接口**: `GET /api/user/uploads`

**权限**: 需要认证

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "skill_name": "my-skill",
      "version": "1.0.0",
      "status": "approved",
      "uploaded_at": "2025-02-09T10:30:00",
      "reviewed_at": "2025-02-09T11:00:00",
      "review_comment": "很好！"
    }
  ],
  "count": 10
}
```

---

### 6. 技能详情

获取技能的详细信息和 SKILL.md 内容。

**接口**: `GET /api/skill/{skill_name}/content`

**权限**: 需要认证

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| skill_name | string | 技能名称 |

**响应示例**:
```json
{
  "content": "---\nname: my-skill\ndescription: ...\n---\n\n技能说明..."
}
```

---

## 管理员接口

### 1. 待审核列表

获取所有待审核的技能列表。

**接口**: `GET /api/pending`

**权限**: 管理员

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "skill_name": "new-skill",
      "version": "1.0.0",
      "filename": "new-skill-1.0.0.zip",
      "uploader_id": 5,
      "employee_id": "654321",
      "uploaded_at": "2025-02-09T10:30:00",
      "status": "pending"
    }
  ],
  "count": 15
}
```

---

### 2. 审核技能

批准或拒绝待审核的技能。

**接口**: `POST /api/review/{skill_id}`

**权限**: 管理员

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| skill_id | integer | 技能 ID |

**请求体** (JSON):
```json
{
  "action": "approve",
  "comment": "审核意见"
}
```

**参数说明**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| action | string | 是 | "approve" 或 "reject" |
| comment | string | 否 | 审核意见（拒绝时建议填写） |

**批准响应示例**:
```json
{
  "success": true,
  "message": "Skill new-skill@1.0.0 approved",
  "skill_id": 1,
  "push_task_id": 123
}
```

**拒绝响应示例**:
```json
{
  "success": true,
  "message": "Skill new-skill@1.0.0 rejected",
  "skill_id": 1
}
```

**错误响应**:
- `400 Bad Request` - 技能状态不是 pending
- `404 Not Found` - 技能不存在

---

### 3. 管理员统计

获取系统综合统计数据。

**接口**: `GET /api/admin/stats`

**权限**: 管理员

**响应示例**:
```json
{
  "success": true,
  "data": {
    "total_users": 150,
    "pending_skills": 15,
    "approved_skills": 250,
    "today_downloads": 50,
    "top_skills": [
      {
        "skill_name": "code-reviewer",
        "downloads": 500
      }
    ],
    "top_users": [
      {
        "employee_id": "123456",
        "downloads": 150
      }
    ]
  }
}
```

---

### 4. Gitea 任务列表

获取 Gitea 推送任务列表。

**接口**: `GET /api/admin/gitea-tasks`

**权限**: 管理员

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 否 | 状态筛选 (pending/pushing/success/failed) |
| limit | integer | 否 | 返回数量，默认 50，最大 200 |

**响应示例**:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "skill_id": 10,
      "status": "success",
      "created_at": "2025-02-09T10:30:00",
      "updated_at": "2025-02-09T10:31:00",
      "skill_name": "my-skill",
      "uploader_id": 5,
      "uploader_name": "123456"
    }
  ],
  "count": 50
}
```

---

### 5. 批量上传

管理员批量上传技能文件。

**接口**: `POST /admin/upload-batch`

**权限**: 管理员

**请求参数** (Multipart Form Data):

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| files | file[] | 是 | 多个技能 ZIP 文件 |

**响应** (HTML):
- 显示每个文件的上传结果

---

### 6. 删除技能

删除指定的技能文件。

**接口**: `DELETE /admin/plugins/{filename}`

**权限**: 管理员

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| filename | string | ZIP 文件名 |

**响应示例**:
```json
{
  "success": true,
  "message": "Deleted skill-1.0.0.zip"
}
```

**错误响应**:
- `404 Not Found` - 文件不存在

---

## 错误码

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 OK | 请求成功 |
| 302 Found | 重定向 |
| 400 Bad Request | 请求参数错误 |
| 401 Unauthorized | 未认证 |
| 403 Forbidden | 无权限 |
| 404 Not Found | 资源不存在 |
| 409 Conflict | 资源冲突（如版本已存在） |
| 500 Internal Server Error | 服务器错误 |
| 503 Service Unavailable | 服务不可用 |

### 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

### 常见错误场景

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `Not authenticated` | 未登录或 Session 过期 | 重新登录 |
| `Admin access required` | 需要管理员权限 | 使用管理员账号登录 |
| `Only ZIP files are allowed` | 文件格式错误 | 上传 ZIP 格式文件 |
| `Invalid ZIP file` | ZIP 文件损坏 | 重新打包技能文件 |
| `Missing SKILL.md in ZIP` | 缺少必需文件 | 添加 SKILL.md 文件 |
| `Invalid skill name: ...` | 技能名称不符合规范 | 修改技能名称 |
| `Skill already exists` | 技能版本已存在 | 使用新版本号 |
| `Plugin not found` | 技能不存在 | 检查技能名称 |

---

## 数据模型

### User (用户)

```typescript
{
  id: number;                    // 用户 ID
  employee_id: string;           // 工号
  role: "user" | "admin";        // 角色
  created_at: string;            // 创建时间 (ISO 8601)
  last_login: string;            // 最后登录时间 (ISO 8601)
}
```

### Skill (技能)

```typescript
{
  id: number;                    // 技能 ID
  skill_name: string;            // 技能名称
  version: string;               // 版本号
  filename: string;              // 文件名
  uploader_id: number;           // 上传者 ID
  status: "pending" | "approved" | "rejected";  // 状态
  uploaded_at: string;           // 上传时间 (ISO 8601)
  reviewed_at?: string;          // 审核时间 (ISO 8601)
  reviewer_id?: number;          // 审核者 ID
  review_comment?: string;       // 审核意见
}
```

### SkillMetadata (技能元数据)

```typescript
{
  name: string;                  // 技能名称 (1-64 字符)
  description: string;           // 描述 (1-1024 字符)
  version: string;               // 版本号 (如 "1.0.0")
  license?: string;              // 许可证
  compatibility?: string;        // 兼容性说明 (1-500 字符)
  metadata: {
    author: string;              // 作者 (小写字母+8位数字)
    version: string;             // 版本号
    [key: string]: any;          // 其他自定义字段
  };
  allowed_tools?: string;        // 允许的工具列表
}
```

### Download (下载记录)

```typescript
{
  id: number;                    // 记录 ID
  skill_name: string;            // 技能名称
  version: string;               // 版本号
  filename: string;              // 文件名
  download_time: string;         // 下载时间 (ISO 8601)
  user_id?: number;              // 用户 ID（可为空）
  ip_address?: string;           // IP 地址
  user_agent?: string;           // User Agent
}
```

### GiteaPushTask (Gitea 推送任务)

```typescript
{
  id: number;                    // 任务 ID
  skill_id: number;              // 技能 ID
  status: "pending" | "pushing" | "success" | "failed";  // 状态
  created_at: string;            // 创建时间 (ISO 8601)
  updated_at: string;            // 更新时间 (ISO 8601)
  error_message?: string;        // 错误信息
  retry_count: number;           // 重试次数
}
```

---

## 附录

### 技能命名规范

**规则**:
- 长度：1-64 字符
- 字符：小写字母、数字、连字符（-）
- 不能以连字符开头或结尾
- 不能包含连续连字符

**示例**:
- ✅ `code-reviewer`
- ✅ `test-helper`
- ✅ `semgrep-rule-creator`
- ❌ `Code-Reviewer`（包含大写）
- ❌ `-code-reviewer`（以连字符开头）
- ❌ `code--reviewer`（连续连字符）

### 版本号规范

推荐使用语义化版本号：`主版本.次版本.修订版本`

**示例**:
- `1.0.0` - 初始版本
- `1.1.0` - 新增功能
- `1.1.1` - 修复 bug
- `2.0.0` - 重大更新

### 作者标识规范

格式：小写字母 + 8 位数字

**示例**:
- ✅ `w00545471`
- ✅ `a12345678`
- ❌ `W00545471`（包含大写）
- ❌ `w545471`（数字不足）

### 状态流转

```
上传 → pending (待审核)
       ↓
    审核中
       ↓
    ┌───┴───┐
    ↓       ↓
approved  rejected
(已批准)  (已拒绝)
```

---

## 更新日志

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0.0 | 2025-02-09 | 初始版本 |

---

## 技术支持

如有问题，请联系：
- 技术支持邮箱: support@your-domain.com
- 问题反馈: http://github.com/your-repo/issues
