# Tortoise ORM 迁移完成指南

## 概述

本项目已完成从原生 SQL 到 Tortoise ORM 的迁移工作。所有数据库操作现在通过 ORM 进行，支持异步访问，同时保持向后兼容性。

## 已完成工作

### 1. 基础设施 ✅

**数据模型** (`core/models.py`)
- `User` - 用户表
- `Skill` - 技能表
- `Download` - 下载记录
- `Notification` - 通知表
- `GiteaPushTask` - Gitea 推送任务

**数据库配置** (`core/db_config.py`)
- MySQL 连接配置
- Tortoise 初始化/关闭函数
- FastAPI lifespan 集成

**数据访问层** (`core/repositories.py`)
- `UserRepository` - 用户数据操作
- `SkillRepository` - 技能数据操作
- `DownloadRepository` - 下载记录操作
- `NotificationRepository` - 通知操作
- `GiteaPushTaskRepository` - 推送任务操作
- `StatsRepository` - 统计查询

**依赖注入** (`core/dependencies.py`)
- `get_current_user_optional` - 可选用户获取
- `get_current_user` - 必需用户获取
- `get_current_admin` - 管理员获取
- `get_current_reviewer` - 审核员获取
- `get_pagination` - 分页参数

### 2. API 路由 ✅

**新版 ORM API** (支持异步操作)
- `api/v1/admin_orm.py` - 管理员功能
- `api/v1/skills_orm.py` - 技能管理
- `api/v1/stats_orm.py` - 统计查询
- `api/v1/users_orm.py` - 用户技能管理
- `api/v1/notifications_orm.py` - 通知管理

**旧版 API** (向后兼容)
- `api/v1/admin.py` - 保留原实现
- `api/v1/skills.py` - 保留原实现
- `api/v1/stats.py` - 保留原实现
- `api/v1/users.py` - 保留原实现

### 3. 应用层 ✅

**FastAPI 应用** (`core/app.py`)
- 使用 Tortoise ORM 初始化
- 异步 lifespan 管理
- Gitea 推送后台任务集成
- 模块化路由集成

**主入口** (`main.py`)
- 保持简洁的入口函数
- 调用 `core/app.create_app()`

### 4. 测试 ✅

**单元测试** (`tests/test_orm_repositories.py`)
- UserRepository 测试（4个测试用例）
- SkillRepository 测试（4个测试用例）
- DownloadRepository 测试（1个测试用例）
- NotificationRepository 测试（2个测试用例）
- GiteaPushTaskRepository 测试（2个测试用例）
- 集成测试（1个测试用例）

## 如何使用

### 旧版 API（兼容模式）

```python
# 旧版 API 仍然可用，使用原生 SQL
from core.dependencies import require_auth_legacy, get_db_legacy
from database import get_user_by_id

@router.get("/api/old-endpoint")
async def old_endpoint(request):
    # 检查认证
    require_auth_legacy(request)

    # 获取数据库连接
    with get_db_legacy() as conn:
        result = conn.execute("SELECT * FROM users")
        return result.fetchone()
```

### 新版 API（ORM 模式）

```python
# 新版 API 使用 Tortoise ORM + Repository
from core.dependencies import get_current_user, get_pagination
from core.repositories import UserRepository, SkillRepository

@router.get("/api/v1/skills")
async def list_skills(
    pagination: PaginationParams = Depends(get_pagination),
    current_user: User = Depends(get_current_user)
):
    # 异步数据库操作
    skills = await SkillRepository.get_all_active(
        limit=pagination.limit,
        offset=pagination.offset
    )

    return {"skills": [s.to_dict() for s in skills]}
```

## 模型示例

### 创建记录

```python
from core.repositories import DownloadRepository

@router.post("/api/v1/downloads")
async def record_download(
    skill_name: str,
    version: str,
    filename: str,
    current_user: User = Depends(get_current_user)
):
    await DownloadRepository.create(
        skill_name=skill_name,
        version=version,
        filename=filename,
        user_id=current_user.id if current_user else None
    )
    return {"message": "下载已记录"}
```

### 统计查询

```python
from core.repositories import StatsRepository

@router.get("/api/v1/stats")
async def get_overall_stats(current_user: User = Depends(get_current_user)):
    stats = await StatsRepository.get_overall()
    return {
        "total_users": stats["total_users"],
        "total_downloads": stats["total_downloads"]
    }
```

## 数据库迁移

使用 Alembic 管理数据库 schema 迁移：

```bash
# 安装 Alembic
pip install aerich

# 初始化迁移
aerich init -t aerich

# 生成迁移
aerich migrate

# 运行迁移
aerich upgrade
```

## 配置说明

### 环境变量

```bash
# .env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_DATABASE=skills
SECRET_KEY=your-secret-key
LOG_LEVEL=INFO

# Gitea 集成（可选）
GITEA_REPO_URL=https://your-gitea-url
GITEA_PUSH_INTERVAL=30
```

### 依赖安装

```bash
pip install -r requirements.txt
```

## 运行应用

```bash
# 开发模式
python main.py

# 或使用 uvicorn
uvicorn main:app --host 0.0.0.0 --port 28000 --reload
```

## 迁移检查清单

在完全切换到新版 ORM API 之前，请确认：

- [ ] 所有依赖已安装（tortoise-orm, aerich）
- [ ] 数据库连接正常
- [ ] 旧版 API 仍然可用（兼容性）
- [ ] 新版 API 路由已注册
- [ ] 单元测试通过
- [ ] 性能测试对比

## 回滚计划

如果发现问题需要回滚：

1. 修改 `api/v1/__init__.py` 禁用新版 API
2. 重新部署使用旧版 API
3. 问题修复后重新启用新版 API

## 性能优化建议

1. **使用连接池**: Tortoise 自动管理连接池
2. **预加载关联**: 使用 `prefetch_related()` 减少查询
3. **批量操作**: 使用 `filter().bulk_update()` 批量更新
4. **索引优化**: 确保 `to_dict()` 方法不触发额外查询

## 下一步工作

1. **认证系统升级**: 考虑集成 JWT 替代 session
2. **API 文档**: 使用 OpenAPI/Swagger 自动生成文档
3. **性能监控**: 集成 APM 工具
4. **缓存层**: 添加 Redis 缓存热门数据
