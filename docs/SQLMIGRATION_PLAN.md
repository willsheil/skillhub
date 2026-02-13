# ORM 迁移方案

## 当前状态分析

### 技术栈
- **框架**: FastAPI
- **数据库**: MySQL
- **当前数据访问**: 原生 SQL + PyMySQL

### 数据库表结构
| 表名 | 用途 | 主要字段 |
|--------|--------|----------|
| `users` | 用户管理 | id, employee_id, api_key, role, status, skills_count |
| `skills` | 技能管理 | id, skill_name, version, uploader_id, status, source_type, is_active |
| `downloads` | 下载记录 | id, skill_name, version, filename, user_id, downloaded_at |
| `notifications` | 用户通知 | id, user_id, type, title, content, is_read |
| `gitea_push_tasks` | Gitea推送任务 | id, skill_id, skill_name, status |

### 当前问题
1. **SQL 注入风险**: 虽然使用了参数化查询，但字符串拼接仍存在风险
2. **代码重复**: 大量重复的 SQL 模板代码
3. **类型安全缺失**: 返回 Dict[str, Any]，缺少类型检查
4. **维护困难**: SQL 散布在代码中，难以重构和优化
5. **缺少迁移工具**: 数据库 schema 变更需要手动管理

---

## ORM 方案对比

### 方案1: SQLModel (推荐)
**优势**:
- FastAPI 作者开发，原生支持
- 基于 Pydantic，与 FastAPI 无缝集成
- 基于 SQLAlchemy，成熟稳定
- 自动生成 JSON Schema
- 编辑器自动补全优秀

**劣势**:
- 相对较新，社区较小
- 异步支持需要额外配置

```python
from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    employee_id: str = Field(index=True, unique=True)
    api_key: str
    role: str = Field(default="user")
    status: str = Field(default="active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### 方案2: SQLAlchemy 2.0 + Async
**优势**:
- 最成熟的 Python ORM
- 强大的查询能力
- 优秀的异步支持
- 社区资源丰富

**劣势**:
- 与 Pydantic 需要额外转换层
- 配置相对复杂

```python
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[str] = mapped_column(String(20), unique=True)
    api_key: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")
```

### 方案3: Tortoise ORM
**优势**:
- 原生异步
- 类似 Django ORM，学习曲线低
- 与 FastAPI 集成良好

**劣势**:
- 社区较小
- 不如 SQLAlchemy 成熟

```python
from tortoise import fields
from tortoise.models import Model

class User(Model):
    id = fields.IntField(pk=True)
    employee_id = fields.CharField(max_length=20, unique=True)
    api_key = fields.CharField(max_length=255)
    role = fields.CharField(max_length=20, default="user")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"
```

---

## 推荐方案: SQLModel

### 为什么选择 SQLModel？

1. **FastAPI 生态**: 同一作者，设计理念一致
2. **Pydantic 集成**: 自动类型转换和验证
3. **代码简洁**: 一个模型定义即可用于 DB 和 API
4. **易于迁移**: 渐进式迁移，新旧代码可共存

---

## 迁移步骤

### Phase 1: 准备阶段 (1-2天)
**目标**: 搭建基础设施，新旧代码共存

```bash
# 安装依赖
pip install sqlmodel sqlalchemy[asyncio] aiomysql

# 创建新目录结构
core/
├── __init__.py
├── database.py        # 保留旧代码
├── models.py          # 新: SQLModel 定义
├── database_new.py    # 新: 数据库连接
└── dependencies.py    # 依赖注入
```

### Phase 2: 模型定义 (2-3天)
**目标**: 定义所有表的 SQLModel

```python
# core/models.py
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship, Text
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    admin = "admin"
    user = "user"
    reviewer = "reviewer"

class UserStatus(str, Enum):
    active = "active"
    disabled = "disabled"

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    employee_id: str = Field(max_length=20, unique=True, index=True)
    api_key: str = Field(max_length=255)
    role: UserRole = Field(default=UserRole.user)
    status: UserStatus = Field(default=UserStatus.active)
    skills_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None

    # 关系
    uploaded_skills: List["Skill"] = Relationship(back_populates="uploader")

class SkillSource(str, Enum):
    opensource = "opensource"
    icsl = "icsl"
    huawei = "huawei"

class SkillStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    unlisted = "unlisted"

class Skill(SQLModel, table=True):
    __tablename__ = "skills"

    id: Optional[int] = Field(default=None, primary_key=True)
    skill_name: str = Field(max_length=255, index=True)
    version: str = Field(max_length=50)
    filename: str = Field(max_length=255)
    uploader_id: int = Field(foreign_key="users.id")
    status: SkillStatus = Field(default=SkillStatus.pending)
    source_type: SkillSource = Field(default=SkillSource.opensource)
    is_active: bool = Field(default=True, index=True)
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
    reviewer_id: Optional[int] = Field(default=None, foreign_key="users.id")
    review_comment: Optional[str] = None
    default_version: bool = Field(default=False)

    uploader: Optional[User] = Relationship(back_populates="uploaded_skills")

# ... 其他模型类似定义
```

### Phase 3: 数据库访问层 (3-4天)
**目标**: 创建 Repository 模式的数据访问层

```python
# core/repositories/user_repository.py
from typing import Optional, List
from sqlmodel import Session, select
from core.models import User

class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_credentials(self, employee_id: str, api_key: str) -> Optional[User]:
        statement = select(User).where(
            User.employee_id == employee_id,
            User.api_key == api_key
        )
        return self.session.exec(statement).first()

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.session.get(User, user_id)

    def create(self, employee_id: str, api_key: str, role: str = "user") -> User:
        user = User(employee_id=employee_id, api_key=api_key, role=role)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def update_last_login(self, user_id: int) -> None:
        user = self.session.get(User, user_id)
        if user:
            from datetime import datetime
            user.last_login = datetime.utcnow()
            self.session.add(user)
            self.session.commit()

# ... 其他 repository 类
```

### Phase 4: API 路由迁移 (5-7天)
**目标**: 逐步迁移 API 路由到新 ORM

**优先级**:
1. 用户管理 API (相对独立，风险低)
2. 技能管理 API
3. 统计 API
4. 通知 API

**策略**: 每个路由迁移后进行测试

### Phase 5: 依赖注入 (2-3天)
**目标**: 统一数据库会话管理

```python
# core/dependencies.py
from typing import Generator
from sqlmodel import Session
from core.database_new import engine

def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

# API 中使用
from fastapi import Depends
from core.dependencies import get_db
from core.repositories.user_repository import UserRepository

@router.get("/api/users/me")
async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    repo = UserRepository(db)
    return repo.get_by_id(token.user_id)
```

### Phase 6: 测试和验证 (3-4天)
**目标**: 完整测试覆盖

1. 单元测试 (每个 Repository)
2. 集成测试 (API 端到端)
3. 性能测试 (对比新旧实现)
4. 数据一致性测试

### Phase 7: 清理 (1-2天)
**目标**: 移除旧代码

1. 确认所有功能正常
2. 删除 `core/database.py` 中的旧函数
3. 删除 `core/database_new.py`
4. 更新所有导入

---

## 风险和注意事项

### 数据兼容性
- 保持表结构不变，只修改访问层
- 使用 Alembic 管理数据库迁移

### 性能考虑
- ORM 有性能开销，需要测试
- 复杂查询可能需要原生 SQL
- 使用 `select_in_load()` 优化关系查询

### 回滚计划
- 新旧代码通过特性开关控制
- 发现问题可立即切换回旧实现
- 保留旧代码直到稳定运行 1 个月

---

## 时间估算

| 阶段 | 时间 | 依赖 |
|--------|------|------|
| Phase 1: 准备 | 1-2天 | - |
| Phase 2: 模型定义 | 2-3天 | Phase 1 |
| Phase 3: 数据访问层 | 3-4天 | Phase 2 |
| Phase 4: API迁移 | 5-7天 | Phase 3 |
| Phase 5: 依赖注入 | 2-3天 | Phase 4 |
| Phase 6: 测试验证 | 3-4天 | Phase 5 |
| Phase 7: 清理 | 1-2天 | Phase 6 |
| **总计** | **17-25天** | |

---

## 下一步行动

1. **团队评审**: 讨论 ORM 方案选择
2. **创建分支**: `feature/orm-migration`
3. **安装依赖**: 添加 SQLModel 到 requirements.txt
4. **开始 Phase 1**: 搭建基础结构
