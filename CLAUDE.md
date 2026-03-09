# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 工作规则

1. **称呼规则**: 每次回复前必须使用"Boss"作为称呼
2. **决策确认**: 遇到不确定的代码设计问题时，必须先询问 Boss，不得直接行动
3. **代码兼容性**: 不能写兼容性代码，除非 Boss 主动要求
4. **语言规则**: 用中文回答
5. **系统信息**: Windows系统，不要使用linux命令

---

## Python 项目开发规范

### 代码风格规范

1. **遵循 PEP 8**：严格遵守 Python 官方代码风格指南
2. **命名规范**：
   - 变量/函数：snake_case（小写字母+下划线）
   - 类名：PascalCase（首字母大写）
   - 常量：UPPER_SNAKE_CASE（全大写+下划线）
   - 私有成员：前缀单下划线 `_private`
   - 避免使用单字母变量名（除循环计数器 i, j, k）
3. **导入顺序**：
   - 顺序：标准库 → 第三方库 → 本地模块
   - 每组之间空一行
   - 避免通配符导入 `from module import *`
4. **代码复杂度**：
   - 单个函数不超过 50 行
   - 圈复杂度不超过 10
   - 嵌套层级不超过 4 层

### 类型注解规范

1. **必须使用类型提示**：所有函数参数和返回值应有类型注解
2. **使用 typing 模块**：
   - 优先使用 `list[str]` 而非 `List[str]`（Python 3.9+）
   - 使用 `Optional[T]` 表示可空类型
   - 使用 `Union[T1, T2]` 表示联合类型
3. **避免使用 `Any`**：除非必要，否则不使用 `typing.Any`

### 错误处理规范

1. **明确异常类型**：捕获具体的异常类型，避免裸 `except:`
2. **异常处理结构**：
   ```python
   try:
       result = risky_operation()
   except SpecificError as e:
       logger.error(f"操作失败: {e}")
       raise  # 或处理并返回
   finally:
       cleanup()
   ```
3. **资源管理**：使用上下文管理器 `with` 管理资源
4. **禁止静默失败**：不使用空的 except 块

### 测试规范

1. **使用 pytest**：作为测试框架
2. **测试文件命名**：`test_*.py`
3. **测试函数命名**：`test_<功能>_<场景>`
4. **测试结构**：AAA 模式（Arrange-Act-Assert）
5. **测试覆盖**：
   - 单元测试覆盖率 ≥ 80%
   - 关键业务逻辑覆盖率 ≥ 90%
6. **测试隔离**：每个测试独立，不依赖执行顺序

### 文档规范

1. **docstring 格式**：使用 Google 风格
   ```python
   def calculate_total(items: list[Item]) -> float:
       """计算项目总价。

       Args:
           items: 项目列表，每个项目包含价格和数量。

       Returns:
           所有项目的总价。

       Raises:
           ValueError: 如果项目列表为空。
       """
   ```
2. **注释规范**：
   - 解释"为什么"而非"是什么"
   - 复杂逻辑必须添加注释
   - 保持注释与代码同步

### 安全规范

1. **SQL 注入防护**：使用参数化查询，不拼接 SQL
2. **敏感信息**：使用环境变量，不硬编码
3. **输入验证**：在系统边界验证用户输入

### 日志规范

1. **使用 logging 模块**：不使用 print
2. **日志级别**：DEBUG < INFO < WARNING < ERROR < CRITICAL
3. **日志格式**：包含时间、级别、模块、消息

---

## Project Overview

SkillHub is an enterprise-level Claude Code skill plugin registry system. It manages skill plugins through a web interface, provides approval workflows for user uploads, integrates with Gitea for version control, and serves a marketplace-compatible API for Claude Code clients.

**Key characteristics:**
- Python FastAPI application with MySQL 8.0 backend
- Session-based authentication (employee_id + api_key)
- Two user roles: `admin` (full access) and `user` (upload + manage own skills)
- Skills stored as ZIP files with SKILL.md metadata (YAML frontmatter format)
- Three-tier skill storage: `plugins/{org}/{collection}/{skill-name}/`
- Supports multi-source classification: `opensource`, `icsl`, `huawei`
- Async Gitea push service with concurrent workers and row-level locking

## Common Commands

### Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (auto-reload)
uvicorn main:app --reload --port 8000

# Run with explicit host/port
python main.py  # Uses configured port from env, default 8000

# Initialize database and create admin user
python -c "from database import init_db, create_user; init_db(); create_user('admin001', 'your_key', 'admin')"
```

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_skill_management.py

# Run with markers (see pytest.ini)
pytest -m unit              # Fast isolated tests
pytest -m integration       # Database-required tests
pytest -m gitea             # Gitea integration tests
pytest -m "not slow"        # Skip slow tests

# Run single test
pytest tests/test_skill_management.py::test_default_version_setting -v
```

### Docker Deployment

```bash
# Build and start all services (MySQL + app)
docker-compose up -d

# View logs
docker-compose logs -f registry

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose up -d --build
```

### Database Operations

```bash
# Initialize database tables
python -c "from database import init_db; init_db()"

# Create test user (role: user or admin)
python -c "from database import create_user; create_user('emp12345678', 'api_key_here', 'user')"

# Check MySQL connection
python check_mysql.py
python verify_mysql.py
```

## Architecture

### Module Structure

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | ~3600 | FastAPI app, all API endpoints, plugin scanning, marketplace generation |
| `database.py` | ~2150 | All DB operations, connection pooling, user/skill/statistics CRUD |
| `gitea_client.py` | ~740 | Git operations wrapper (clone, add, commit, push) |
| `gitea_push_service_v2.py` | ~590 | Async push service with concurrent workers |
| `gitea_integration.py` | ~250 | Gitea webhook and integration endpoints |
| `gitea_metrics.py` | ~270 | Push task metrics and health monitoring |
| `gitea_alerts.py` | ~460 | Alerting for push failures |

### Request Flow

1. **User uploads skill** → `/api/upload` → Validates ZIP + SKILL.md → Saves to `data/pending/` → Status: `pending`
2. **Admin reviews** → `/api/review/{skill_id}` → If approved: moves to `plugins/`, status: `approved`
3. **Gitea push** → Background worker creates task in `gitea_push_tasks` → Workers reserve with `SELECT ... FOR UPDATE SKIP LOCKED` → Push to Gitea → Update status to `success`/`failed`
4. **Marketplace scan** → `scan_plugins()` reads `plugins/` → Returns only `approved` + `is_active=1` skills

### Database Schema Highlights

```sql
users: employee_id, api_key, role (admin/user), status, skills_count
skills: skill_name, version, filename, uploader_id, status (pending/approved/rejected),
       source_type (opensource/icsl/huawei), is_active, is_default_version, latest_push_task_id
downloads: skill_name, version, user_id, downloaded_at (for statistics)
gitea_push_tasks: skill_id, status (pending/reserved/pushing/success/failed/retry_pending),
                  retry_count, worker_id, commit_hash, error_message
notifications: user_id, type (approval/rejection/upload/system), is_read, related_skill_id
```

### Key Design Patterns

1. **Connection Wrapper**: PyMySQL doesn't support `conn.execute()`, so `ConnectionWrapper` wraps connections to provide this interface
2. **Plugin Storage**: Three-tier directory structure `plugins/{org}/{collection}/{skill}/` for multi-tenant isolation
3. **Default Version**: Each skill name can have multiple versions; one version has `is_default_version=1`
4. **Source Types**: Skills classified as `opensource`, `icsl`, or `huawei` for filtering
5. **Async Push**: Background workers process push tasks concurrently with row-level locking to prevent duplicate processing

## Configuration

### Environment Variables (.env)

```bash
# Admin credentials for web login
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-this-password
SECRET_KEY=your-random-secret-key

# Database (MySQL 8.0)
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=root
DB_DATABASE=skills

# Gitea integration (optional)
GITEA_REPO_URL=http://localhost:3000/owner/repo.git
GITEA_TOKEN=your_gitea_token
GITEA_PUSH_INTERVAL=30

# Storage
PLUGINS_DIR=./plugins
```

### Skill Format (SKILL.md)

```yaml
---
name: skill-name              # lowercase, hyphens, numbers only
description: Skill description
metadata:
  version: 1.0.0
  author: w00000001           # lowercase letter + 8 digits
  tags: tag1, tag2, tag3
  category: category-name
license: MIT
compatibility: Claude Code 1.0+
allowed-tools: bash, grep, read
---
```

## Important API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/login` | POST | Public | User login (employee_id + api_key) |
| `/api/upload` | POST | Login | Upload skill ZIP (creates pending skill) |
| `/api/pending` | GET | Admin | Get pending skills for review |
| `/api/review/{skill_id}` | POST | Admin | Approve or reject skill |
| `/api/my-skills` | GET | Login | Get current user's skills (grouped by name) |
| `/api/my-skills/{id}/set-default` | POST | Login | Set skill version as default |
| `/marketplace.json` | GET | Public | Claude Code marketplace index |
| `/plugins/{filename}` | GET | Public | Download skill ZIP |
| `/api/gitea/status` | GET | Admin | Push service status |
| `/stats` | GET | Login | Statistics page |

## Testing Notes

- Tests use `pytest` with auto-fixtures that set up/clean test database
- Test data is prefixed (e.g., `test-mgmt-`) to enable safe cleanup
- Use `create_test_skill_zip()` helper to generate valid skill ZIP files for testing
- Test database operations use `get_connection()` context manager
- Markers: `unit`, `integration`, `e2e`, `slow`, `gitea`

## Deployment Considerations

- Production uses MySQL 8.0 (not SQLite)
- Plugins directory is mounted as volume in Docker
- Gitea push service runs as background task, not in request handlers
- Session authentication requires secure SECRET_KEY in production
- File upload limit: 50MB (enforced in main.py)
