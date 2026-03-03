# 外部平台 API 接口设计文档

**日期**: 2026-03-03
**版本**: v1.0
**状态**: 设计已批准

## 1. 概述

为其他平台服务提供 API 接口，支持技能市场数据查询和技能包下载。

### 1.1 核心功能

1. **技能市场接口列表** - 支持分类过滤、分页、模糊搜索
2. **技能压缩包下载** - 提供直接的下载接口
3. **API 文档** - Swagger UI + Markdown 双重文档

### 1.2 技术选型

- **框架**: FastAPI
- **认证**: API Key (Header: X-API-Key)
- **文档**: Swagger UI + Markdown
- **数据库**: MySQL 8.0

## 2. API 架构设计

### 2.1 目录结构

```
skillhub/
├── api/
│   ├── __init__.py
│   ├── v1/
│   │   ├── __init__.py
│   │   ├── routes.py          # API 路由定义
│   │   ├── schemas.py         # 请求/响应模型（Pydantic）
│   │   ├── services.py        # 业务逻辑层
│   │   └── dependencies.py    # 依赖注入（API Key 认证）
│   └── docs/
│       └── external_api.md    # Markdown 文档
├── main.py                    # 注册 API 路由
```

### 2.2 核心 API 端点

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/api/v1/skills` | 技能列表（分类、分页、搜索） |
| GET | `/api/v1/skills/{skill_name}` | 技能详情 |
| GET | `/api/v1/skills/{skill_name}/download` | 下载 ZIP 压缩包 |
| GET | `/api/v1/docs` | Swagger UI 文档 |

## 3. 统一响应结构

### 3.1 成功响应

```json
{
    "code": 200,
    "message": "success",
    "data": {
        "items": [...]
    },
    "pagination": {
        "page": 1,
        "page_size": 20,
        "total": 100,
        "total_pages": 5
    }
}
```

### 3.2 错误响应

```json
{
    "code": 400,
    "message": "Invalid parameter",
    "data": null
}
```

### 3.3 错误码规范

| Code | 说明 |
|------|------|
| 200 | 成功 |
| 400 | 参数错误 |
| 401 | API Key 无效 |
| 403 | 无权限访问 |
| 404 | 资源不存在 |
| 429 | 请求过于频繁 |
| 500 | 服务器错误 |

## 4. 接口详细设计

### 4.1 获取技能列表

**端点**: `GET /api/v1/skills`

**认证**: 需要 API Key

**查询参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `source_type` | string | 否 | all | 分类：opensource/icsl/huawei/all |
| `page` | int | 否 | 1 | 页码（≥1） |
| `page_size` | int | 否 | 20 | 每页数量（1-100） |
| `keyword` | string | 否 | - | 搜索关键词（名称+描述） |
| `tags` | string | 否 | - | 标签过滤，逗号分隔 |

**响应示例**:
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "items": [
            {
                "name": "auditing-python-security",
                "description": "Python 安全审计工具",
                "metadata": {
                    "version": "1.0.0",
                    "author": "w00000001",
                    "tags": ["security", "python"],
                    "category": "security",
                    "license": "MIT",
                    "compatibility": "Claude Code 1.0+"
                },
                "source_type": "opensource",
                "default_version": "1.0.0",
                "versions": ["1.0.0", "1.1.0"],
                "download_url": "/api/v1/skills/auditing-python-security/download"
            }
        ]
    },
    "pagination": {
        "page": 1,
        "page_size": 20,
        "total": 45,
        "total_pages": 3
    }
}
```

### 4.2 获取技能详情

**端点**: `GET /api/v1/skills/{skill_name}`

**认证**: 需要 API Key

**路径参数**:
- `skill_name`: 技能名称

**响应示例**:
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "name": "auditing-python-security",
        "description": "Python 安全审计工具",
        "metadata": {
            "version": "1.0.0",
            "author": "w00000001",
            "tags": ["security", "python"],
            "category": "security",
            "license": "MIT",
            "compatibility": "Claude Code 1.0+"
        },
        "source_type": "opensource",
        "versions": [
            {
                "version": "1.0.0",
                "filename": "auditing-python-security-1.0.0.zip",
                "is_default": true,
                "download_url": "/api/v1/skills/auditing-python-security/download?version=1.0.0"
            },
            {
                "version": "1.1.0",
                "filename": "auditing-python-security-1.1.0.zip",
                "is_default": false,
                "download_url": "/api/v1/skills/auditing-python-security/download?version=1.1.0"
            }
        ]
    }
}
```

### 4.3 下载技能压缩包

**端点**: `GET /api/v1/skills/{skill_name}/download`

**认证**: 需要 API Key

**路径参数**:
- `skill_name`: 技能名称

**查询参数**:
- `version` (可选): 指定版本，默认下载默认版本

**响应**: 二进制 ZIP 文件

## 5. 认证与安全

### 5.1 API Key 认证

**请求头**:
```http
X-API-Key: sk_abc123def456...
```

**数据库存储**: 新增 `external_api_keys` 表

```sql
CREATE TABLE external_api_keys (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    api_key VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(100),
    is_active TINYINT(1) DEFAULT 1,
    rate_limit INT DEFAULT 100,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### 5.2 安全机制

| 机制 | 实现方式 |
|------|----------|
| 速率限制 | 每个 API Key 每分钟最多 100 次请求（可配置） |
| IP 白名单 | 可配置允许访问的 IP 段 |
| 日志审计 | 记录所有 API 调用 |
| CORS | 允许跨域访问，可配置白名单 |

### 5.3 审计日志

**新增表**: `api_call_logs`

```sql
CREATE TABLE api_call_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    api_key_id INT NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    params TEXT,
    ip_address VARCHAR(45),
    status_code INT,
    response_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (api_key_id) REFERENCES external_api_keys(id),
    INDEX idx_api_key_time (api_key_id, created_at)
);
```

## 6. 数据库变更

### 6.1 新增表汇总

| 表名 | 用途 |
|------|------|
| `external_api_keys` | 存储 API Key |
| `api_call_logs` | API 调用审计日志 |

### 6.2 现有表复用

- `users` - 关联 API Key 所属用户
- `skills` - 技能数据源
- `downloads` - 记录下载统计

## 7. 实现细节

### 7.1 核心查询逻辑

复用现有 `scan_plugins()` 函数，增加以下过滤条件：
- `status = 'approved'`
- `is_active = 1`
- `source_type` 匹配（如果指定）
- `keyword` 模糊匹配 `name` 或 `description`
- 支持分页（LIMIT + OFFSET）

### 7.2 速率限制实现

使用内存缓存（优先 Redis，回退到 dict）：
- 滑动窗口算法
- 记录每个 API Key 的请求时间戳
- 计算 1 分钟内请求数
- 超限返回 429 错误

### 7.3 FastAPI 依赖注入

```python
# api/v1/dependencies.py
async def verify_api_key(x_api_key: str = Header(...)):
    """验证 API Key 并返回用户信息"""
    async def get_current_api_key(
        x_api_key: str = Header(..., alias="X-API-Key")
    ):
        # 查询数据库验证
        # 检查速率限制
        # 返回 API Key 信息
        pass
    return get_current_api_key
```

## 8. 文档

### 8.1 Swagger UI

FastAPI 自动生成，访问 `/api/v1/docs`：
- 自动展示所有端点、参数、响应格式
- 支持在线测试
- 自动生成 OpenAPI JSON

### 8.2 Markdown 文档

**文件**: `api/docs/external_api.md`

包含以下章节：
1. 概述
2. 认证（如何获取和管理 API Key）
3. 接口列表
4. 错误码说明
5. 调用示例（cURL / Python / JavaScript）

## 9. 测试策略

| 测试类型 | 覆盖范围 | 文件位置 |
|----------|----------|----------|
| 单元测试 | services.py 业务逻辑 | `tests/test_api_services.py` |
| 集成测试 | API 端点完整流程 | `tests/test_api_integration.py` |
| 认证测试 | API Key 验证、速率限制 | `tests/test_api_auth.py` |
| 性能测试 | 并发请求、分页性能 | `tests/test_api_performance.py` |

## 10. 部署注意事项

1. API Key 密钥生成使用 `secrets.token_urlsafe(32)`
2. 生产环境启用 HTTPS
3. 配置 CORS 白名单
4. 监控 API 调用日志
5. 定期清理审计日志（保留 90 天）

## 11. 后续扩展

- [ ] API Key 管理后台界面
- [ ] WebSocket 推送技能更新通知
- [ ] API 使用统计dashboard
- [ ] v2 版本支持更复杂的查询条件
