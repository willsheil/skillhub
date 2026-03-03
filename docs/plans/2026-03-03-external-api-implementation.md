# 外部平台 API 接口实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为其他平台提供 RESTful API 接口，支持技能列表查询（分类/分页/搜索）、技能详情获取、ZIP 压缩包下载，使用 API Key 认证。

**架构:** 独立 API 模块 `api/v1/`，通过 FastAPI 依赖注入实现认证，复用现有数据库查询逻辑，新增 API Key 和审计日志表。

**Tech Stack:** FastAPI, Pydantic, PyMySQL, Redis（可选，用于速率限制）, pytest

---

## 前置准备

### Task 0: 创建 API 模块目录结构

**Files:**
- Create: `api/__init__.py`
- Create: `api/v1/__init__.py`
- Create: `api/v1/routes.py`
- Create: `api/v1/schemas.py`
- Create: `api/v1/services.py`
- Create: `api/v1/dependencies.py`
- Create: `api/docs/external_api.md`

**Step 1: 创建目录结构**

```bash
mkdir -p api/v1 api/docs
```

**Step 2: 创建初始化文件**

```bash
# api/__init__.py
touch api/__init__.py

# api/v1/__init__.py
touch api/v1/__init__.py
```

**Step 3: 创建空文件（后续填充）**

```bash
touch api/v1/routes.py
touch api/v1/schemas.py
touch api/v1/services.py
touch api/v1/dependencies.py
touch api/docs/external_api.md
```

**Step 4: 提交**

```bash
git add api/
git commit -m "feat: 创建外部 API 模块目录结构"
```

---

## 数据库变更

### Task 1: 创建 API Key 数据库表

**Files:**
- Modify: `database.py` (添加表创建函数)
- Test: `tests/test_api_database.py`

**Step 1: 编写测试 - 验证表创建**

```python
# tests/test_api_database.py
import pytest
from database import get_connection, init_external_api_tables

def test_external_api_keys_table_exists():
    """测试 external_api_keys 表是否存在"""
    init_external_api_tables()
    with get_connection() as conn:
        result = conn.execute("""
            SELECT COUNT(*) as count FROM information_schema.tables
            WHERE table_name = 'external_api_keys'
        """).fetchone()
        assert result['count'] == 1

def test_api_call_logs_table_exists():
    """测试 api_call_logs 表是否存在"""
    init_external_api_tables()
    with get_connection() as conn:
        result = conn.execute("""
            SELECT COUNT(*) as count FROM information_schema.tables
            WHERE table_name = 'api_call_logs'
        """).fetchone()
        assert result['count'] == 1
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/test_api_database.py -v
```

Expected: FAIL - `init_external_api_tables` 函数不存在

**Step 3: 实现表创建函数**

```python
# database.py - 在文件末尾添加

def init_external_api_tables():
    """初始化外部 API 相关的数据库表"""
    with get_connection() as conn:
        # 创建 external_api_keys 表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS external_api_keys (
                id INT PRIMARY KEY AUTO_INCREMENT,
                user_id INT NOT NULL,
                api_key VARCHAR(64) UNIQUE NOT NULL,
                name VARCHAR(100),
                is_active TINYINT(1) DEFAULT 1,
                rate_limit INT DEFAULT 100,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                INDEX idx_api_key (api_key),
                INDEX idx_user_id (user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # 创建 api_call_logs 表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_call_logs (
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
                INDEX idx_api_key_time (api_key_id, created_at),
                INDEX idx_endpoint (endpoint)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()
```

**Step 4: 运行测试验证通过**

```bash
pytest tests/test_api_database.py -v
```

Expected: PASS

**Step 5: 提交**

```bash
git add database.py tests/test_api_database.py
git commit -m "feat: 添加外部 API 数据库表"
```

---

### Task 2: 实现 API Key 管理函数

**Files:**
- Modify: `database.py`
- Test: `tests/test_api_key_management.py`

**Step 1: 编写测试 - API Key 创建和验证**

```python
# tests/test_api_key_management.py
import pytest
from database import (
    create_api_key,
    verify_api_key,
    get_api_key_info,
    deactivate_api_key
)

def test_create_api_key():
    """测试创建 API Key"""
    # 假设用户 ID 1 存在
    api_key = create_api_key(user_id=1, name="Test Key")
    assert api_key is not None
    assert len(api_key) == 43  # sk_ + 40位字符
    assert api_key.startswith("sk_")

def test_verify_api_key_valid():
    """测试验证有效的 API Key"""
    api_key = create_api_key(user_id=1, name="Verify Test")
    info = verify_api_key(api_key)
    assert info is not None
    assert info['user_id'] == 1
    assert info['is_active'] == 1

def test_verify_api_key_invalid():
    """测试验证无效的 API Key"""
    info = verify_api_key("sk_invalid123")
    assert info is None

def test_verify_api_key_inactive():
    """测试验证已停用的 API Key"""
    api_key_record = create_api_key(user_id=1, name="Inactive Test")
    deactivate_api_key(api_key_record['id'])
    info = verify_api_key(api_key_record['api_key'])
    assert info is None

def test_get_api_key_info():
    """测试获取 API Key 信息"""
    api_key = create_api_key(user_id=1, name="Info Test")
    info = get_api_key_info(api_key)
    assert info['name'] == "Info Test"
    assert info['rate_limit'] == 100
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/test_api_key_management.py -v
```

Expected: FAIL - 函数不存在

**Step 3: 实现 API Key 管理函数**

```python
# database.py - 添加以下函数

import secrets
from datetime import datetime
from typing import Optional, Dict, Any

def create_api_key(user_id: int, name: str = None, rate_limit: int = 100) -> Optional[Dict[str, Any]]:
    """创建新的 API Key

    Args:
        user_id: 用户 ID
        name: API Key 名称/备注
        rate_limit: 速率限制（每分钟请求数）

    Returns:
        包含 API Key 信息的字典，失败返回 None
    """
    api_key = f"sk_{secrets.token_urlsafe(32)}"

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO external_api_keys (user_id, api_key, name, rate_limit)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, api_key, name, rate_limit)
            )
            conn.commit()

            return {
                'id': cursor.lastrowid,
                'api_key': api_key,
                'user_id': user_id,
                'name': name,
                'rate_limit': rate_limit,
                'is_active': 1
            }
    except Exception as e:
        logger.error(f"创建 API Key 失败: {e}")
        return None

def verify_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    """验证 API Key 并返回信息

    Args:
        api_key: API Key 字符串

    Returns:
        API Key 信息字典，无效返回 None
    """
    with get_connection() as conn:
        result = conn.execute(
            """
            SELECT id, user_id, api_key, name, is_active, rate_limit
            FROM external_api_keys
            WHERE api_key = %s AND is_active = 1
            """,
            (api_key,)
        ).fetchone()

        if result:
            # 更新最后使用时间
            conn.execute(
                "UPDATE external_api_keys SET last_used_at = NOW() WHERE id = %s",
                (result['id'],)
            )
            conn.commit()
            return dict(result)

        return None

def get_api_key_info(api_key: str) -> Optional[Dict[str, Any]]:
    """获取 API Key 详细信息"""
    with get_connection() as conn:
        result = conn.execute(
            """
            SELECT * FROM external_api_keys WHERE api_key = %s
            """,
            (api_key,)
        ).fetchone()

        return dict(result) if result else None

def deactivate_api_key(api_key_id: int) -> bool:
    """停用 API Key"""
    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE external_api_keys SET is_active = 0 WHERE id = %s",
                (api_key_id,)
            )
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"停用 API Key 失败: {e}")
        return False

def log_api_call(api_key_id: int, endpoint: str, method: str,
                 params: str = None, ip_address: str = None,
                 status_code: int = None, response_time_ms: int = None):
    """记录 API 调用日志"""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO api_call_logs
                (api_key_id, endpoint, method, params, ip_address, status_code, response_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (api_key_id, endpoint, method, params, ip_address, status_code, response_time_ms)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"记录 API 调用日志失败: {e}")
```

**Step 4: 运行测试验证通过**

```bash
pytest tests/test_api_key_management.py -v
```

Expected: PASS

**Step 5: 提交**

```bash
git add database.py tests/test_api_key_management.py
git commit -m "feat: 实现 API Key 管理函数"
```

---

## Pydantic Schema 定义

### Task 3: 定义请求和响应模型

**Files:**
- Create: `api/v1/schemas.py`
- Test: `tests/test_api_schemas.py`

**Step 1: 编写测试 - Schema 验证**

```python
# tests/test_api_schemas.py
from pydantic import ValidationError
import pytest
from api.v1.schemas import (
    SkillListResponse,
    SkillDetailResponse,
    SkillItem,
    PaginationInfo
)

def test_skill_item_schema():
    """测试 Skill Item Schema"""
    data = {
        "name": "test-skill",
        "description": "Test skill",
        "metadata": {
            "version": "1.0.0",
            "author": "w00000001",
            "tags": ["test"],
            "category": "test",
            "license": "MIT",
            "compatibility": "Claude Code 1.0+"
        },
        "source_type": "opensource",
        "default_version": "1.0.0",
        "versions": ["1.0.0"],
        "download_url": "/api/v1/skills/test-skill/download"
    }
    skill = SkillItem(**data)
    assert skill.name == "test-skill"
    assert skill.source_type == "opensource"

def test_skill_list_response_schema():
    """测试技能列表响应 Schema"""
    data = {
        "code": 200,
        "message": "success",
        "data": {
            "items": []
        },
        "pagination": {
            "page": 1,
            "page_size": 20,
            "total": 0,
            "total_pages": 0
        }
    }
    response = SkillListResponse(**data)
    assert response.code == 200
    assert response.pagination.page == 1

def test_pagination_validation():
    """测试分页参数验证"""
    from api.v1.schemas import SkillListQuery
    query = SkillListQuery(page=1, page_size=20)
    assert query.page == 1
    assert query.page_size == 20

def test_invalid_source_type():
    """测试无效的 source_type"""
    from api.v1.schemas import SkillListQuery
    with pytest.raises(ValidationError):
        SkillListQuery(source_type="invalid")
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/test_api_schemas.py -v
```

Expected: FAIL - schemas.py 文件为空

**Step 3: 实现 Schema 定义**

```python
# api/v1/schemas.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from enum import Enum

class SourceTypeEnum(str, Enum):
    """技能来源类型枚举"""
    opensource = "opensource"
    icsl = "icsl"
    huawei = "huawei"
    all = "all"

# ========== 嵌套模型 ==========

class SkillMetadata(BaseModel):
    """技能元数据"""
    version: str
    author: str
    tags: List[str] = []
    category: Optional[str] = None
    license: Optional[str] = None
    compatibility: Optional[str] = None

class SkillVersionInfo(BaseModel):
    """技能版本信息"""
    version: str
    filename: str
    is_default: bool
    download_url: str

class PaginationInfo(BaseModel):
    """分页信息"""
    page: int
    page_size: int
    total: int
    total_pages: int

# ========== 技能相关模型 ==========

class SkillItem(BaseModel):
    """技能列表项"""
    name: str
    description: str
    metadata: SkillMetadata
    source_type: str
    default_version: str
    versions: List[str]
    download_url: str

class SkillDetail(BaseModel):
    """技能详情"""
    name: str
    description: str
    metadata: SkillMetadata
    source_type: str
    versions: List[SkillVersionInfo]

# ========== 请求参数模型 ==========

class SkillListQuery(BaseModel):
    """技能列表查询参数"""
    source_type: SourceTypeEnum = SourceTypeEnum.all
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
    keyword: Optional[str] = Field(None, description="搜索关键词")
    tags: Optional[str] = Field(None, description="标签过滤，逗号分隔")

    class Config:
        extra = "forbid"

class SkillDownloadQuery(BaseModel):
    """技能下载查询参数"""
    version: Optional[str] = Field(None, description="指定版本，不指定则下载默认版本")

# ========== 响应模型 ==========

class ApiResponse(BaseModel):
    """统一 API 响应基类"""
    code: int
    message: str
    data: Any

class SkillListResponse(BaseModel):
    """技能列表响应"""
    code: int
    message: str
    data: Dict[str, List[SkillItem]]
    pagination: PaginationInfo

class SkillDetailResponse(BaseModel):
    """技能详情响应"""
    code: int
    message: str
    data: SkillDetail

class ErrorResponse(BaseModel):
    """错误响应"""
    code: int
    message: str
    data: None = None
```

**Step 4: 运行测试验证通过**

```bash
pytest tests/test_api_schemas.py -v
```

Expected: PASS

**Step 5: 提交**

```bash
git add api/v1/schemas.py tests/test_api_schemas.py
git commit -m "feat: 定义 API 请求和响应 Schema"
```

---

## 认证依赖

### Task 4: 实现 API Key 认证依赖

**Files:**
- Create: `api/v1/dependencies.py`
- Test: `tests/test_api_dependencies.py`

**Step 1: 编写测试 - 认证依赖**

```python
# tests/test_api_dependencies.py
import pytest
from fastapi import Header, HTTPException
from api.v1.dependencies import verify_api_key_header, get_rate_limit

def test_verify_valid_api_key():
    """测试验证有效的 API Key"""
    # 先创建一个测试 API Key
    from database import create_api_key
    api_key_record = create_api_key(user_id=1, name="Test")
    api_key = api_key_record['api_key']

    # 验证应该成功
    result = verify_api_key_header(x_api_key=api_key)
    assert result['user_id'] == 1

def test_verify_invalid_api_key():
    """测试验证无效的 API Key"""
    with pytest.raises(HTTPException) as exc:
        verify_api_key_header(x_api_key="sk_invalid")
    assert exc.value.status_code == 401

def test_verify_missing_api_key():
    """测试缺少 API Key"""
    with pytest.raises(HTTPException) as exc:
        verify_api_key_header(x_api_key=None)
    assert exc.value.status_code == 401

def test_rate_limit():
    """测试速率限制"""
    from database import create_api_key
    api_key_record = create_api_key(user_id=1, name="Rate Limit Test")

    limit = get_rate_limit(api_key_record['api_key'])
    assert limit == 100  # 默认值
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/test_api_dependencies.py -v
```

Expected: FAIL - dependencies.py 文件为空

**Step 3: 实现认证依赖**

```python
# api/v1/dependencies.py
from fastapi import Header, HTTPException, status
from typing import Optional
from database import verify_api_key, get_api_key_info

# 速率限制内存存储（生产环境建议使用 Redis）
_rate_limit_store = {}

def verify_api_key_header(x_api_key: str = Header(..., alias="X-API-Key")) -> dict:
    """验证 API Key 依赖注入

    Raises:
        HTTPException: 401 如果 API Key 无效

    Returns:
        API Key 信息字典
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key is required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    api_key_info = verify_api_key(x_api_key)
    if not api_key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key_info

def get_rate_limit(api_key: str) -> int:
    """获取 API Key 的速率限制

    Returns:
        每分钟允许的请求数
    """
    info = get_api_key_info(api_key)
    if info:
        return info.get('rate_limit', 100)
    return 100

def check_rate_limit(api_key: str, rate_limit: int) -> bool:
    """检查速率限制

    Args:
        api_key: API Key 字符串
        rate_limit: 每分钟请求数限制

    Returns:
        True 如果未超限，False 如果超限
    """
    import time
    current_time = int(time.time())

    if api_key not in _rate_limit_store:
        _rate_limit_store[api_key] = []
        return True

    # 移除超过 60 秒的记录
    _rate_limit_store[api_key] = [
        t for t in _rate_limit_store[api_key]
        if current_time - t < 60
    ]

    # 检查请求数
    if len(_rate_limit_store[api_key]) >= rate_limit:
        return False

    _rate_limit_store[api_key].append(current_time)
    return True
```

**Step 4: 运行测试验证通过**

```bash
pytest tests/test_api_dependencies.py -v
```

Expected: PASS

**Step 5: 提交**

```bash
git add api/v1/dependencies.py tests/test_api_dependencies.py
git commit -m "feat: 实现 API Key 认证依赖"
```

---

## 业务逻辑层

### Task 5: 实现技能列表查询服务

**Files:**
- Create: `api/v1/services.py`
- Test: `tests/test_api_services.py`

**Step 1: 编写测试 - 技能列表查询**

```python
# tests/test_api_services.py
import pytest
from api.v1.services import get_skills_list, get_skill_detail
from database import init_db, get_connection

@pytest.fixture(autouse=True)
def setup_test_data():
    """设置测试数据"""
    init_external_api_tables()
    # 清理测试数据
    with get_connection() as conn:
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-api-%'")
        conn.commit()
    yield
    # 清理
    with get_connection() as conn:
        conn.execute("DELETE FROM skills WHERE skill_name LIKE 'test-api-%'")
        conn.commit()

def test_get_skills_list_basic():
    """测试基本列表查询"""
    result = get_skills_list(
        source_type="all",
        page=1,
        page_size=20
    )
    assert "items" in result
    assert "pagination" in result
    assert result["pagination"]["page"] == 1

def test_get_skills_list_with_filter():
    """测试带过滤条件的查询"""
    result = get_skills_list(
        source_type="opensource",
        page=1,
        page_size=20
    )
    # 验证所有返回的技能都是 opensource 类型
    for item in result["items"]:
        assert item["source_type"] == "opensource"

def test_get_skills_list_with_search():
    """测试关键词搜索"""
    result = get_skills_list(
        source_type="all",
        page=1,
        page_size=20,
        keyword="security"
    )
    # 验证返回的技能名称或描述包含关键词
    for item in result["items"]:
        keyword_in_name = "security" in item["name"].lower()
        keyword_in_desc = "security" in item["description"].lower()
        assert keyword_in_name or keyword_in_desc
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/test_api_services.py -v
```

Expected: FAIL - services.py 文件为空

**Step 3: 实现技能列表查询服务**

```python
# api/v1/services.py
from typing import Dict, List, Any, Optional
from database import get_connection
import logging

logger = logging.getLogger("skillhub.api.services")

def get_skills_list(
    source_type: str = "all",
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    tags: Optional[str] = None
) -> Dict[str, Any]:
    """获取技能列表

    Args:
        source_type: 来源类型过滤
        page: 页码
        page_size: 每页数量
        keyword: 搜索关键词
        tags: 标签过滤

    Returns:
        包含 items 和 pagination 的字典
    """
    offset = (page - 1) * page_size

    # 构建查询条件
    where_conditions = ["status = 'approved'", "is_active = 1"]
    params = []

    if source_type != "all":
        where_conditions.append("source_type = %s")
        params.append(source_type)

    if keyword:
        where_conditions.append("(skill_name LIKE %s OR description LIKE %s)")
        keyword_pattern = f"%{keyword}%"
        params.extend([keyword_pattern, keyword_pattern])

    if tags:
        tag_list = [t.strip() for t in tags.split(',')]
        # 简化实现：在 metadata 中搜索标签
        for tag in tag_list:
            where_conditions.append("metadata LIKE %s")
            params.append(f"%{tag}%")

    where_clause = " AND ".join(where_conditions)

    # 查询总数
    with get_connection() as conn:
        count_result = conn.execute(
            f"SELECT COUNT(*) as total FROM skills WHERE {where_clause}",
            params
        ).fetchone()
        total = count_result['total']

        # 查询数据
        query = f"""
            SELECT id, skill_name, description, metadata, source_type,
                   version, filename, is_default_version
            FROM skills
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([page_size, offset])

        rows = conn.execute(query, params).fetchall()

    # 处理结果
    items = []
    for row in rows:
        # 解析 metadata (JSON 格式)
        import json
        try:
            metadata = json.loads(row['metadata']) if row['metadata'] else {}
        except:
            metadata = {}

        # 获取所有版本
        versions = _get_skill_versions(row['skill_name'])

        items.append({
            "name": row['skill_name'],
            "description": row['description'] or "",
            "metadata": metadata,
            "source_type": row['source_type'],
            "default_version": row['version'],
            "versions": versions,
            "download_url": f"/api/v1/skills/{row['skill_name']}/download"
        })

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages
        }
    }

def _get_skill_versions(skill_name: str) -> List[str]:
    """获取技能的所有版本"""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT version FROM skills
            WHERE skill_name = %s AND status = 'approved' AND is_active = 1
            ORDER BY version DESC
            """,
            (skill_name,)
        ).fetchall()
        return [row['version'] for row in rows]

def get_skill_detail(skill_name: str) -> Optional[Dict[str, Any]]:
    """获取技能详情

    Args:
        skill_name: 技能名称

    Returns:
        技能详情字典，不存在返回 None
    """
    with get_connection() as conn:
        # 获取默认版本信息
        row = conn.execute(
            """
            SELECT id, skill_name, description, metadata, source_type,
                   version, filename, is_default_version
            FROM skills
            WHERE skill_name = %s AND status = 'approved' AND is_active = 1
            ORDER BY is_default_version DESC, version DESC
            LIMIT 1
            """,
            (skill_name,)
        ).fetchone()

        if not row:
            return None

        # 解析 metadata
        import json
        try:
            metadata = json.loads(row['metadata']) if row['metadata'] else {}
        except:
            metadata = {}

        # 获取所有版本详情
        versions = _get_skill_version_details(skill_name)

        return {
            "name": row['skill_name'],
            "description": row['description'] or "",
            "metadata": metadata,
            "source_type": row['source_type'],
            "versions": versions
        }

def _get_skill_version_details(skill_name: str) -> List[Dict[str, Any]]:
    """获取技能的所有版本详情"""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT version, filename, is_default_version
            FROM skills
            WHERE skill_name = %s AND status = 'approved' AND is_active = 1
            ORDER BY version DESC
            """,
            (skill_name,)
        ).fetchall()

        return [
            {
                "version": row['version'],
                "filename": row['filename'],
                "is_default": bool(row['is_default_version']),
                "download_url": f"/api/v1/skills/{skill_name}/download?version={row['version']}"
            }
            for row in rows
        ]

def get_skill_download_path(skill_name: str, version: Optional[str] = None) -> Optional[str]:
    """获取技能下载文件路径

    Args:
        skill_name: 技能名称
        version: 版本号，None 表示默认版本

    Returns:
        文件路径，不存在返回 None
    """
    with get_connection() as conn:
        if version:
            row = conn.execute(
                """
                SELECT filename FROM skills
                WHERE skill_name = %s AND version = %s
                AND status = 'approved' AND is_active = 1
                LIMIT 1
                """,
                (skill_name, version)
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT filename FROM skills
                WHERE skill_name = %s AND is_default_version = 1
                AND status = 'approved' AND is_active = 1
                LIMIT 1
                """,
                (skill_name,)
            ).fetchone()

        if row:
            from pathlib import Path
            plugins_dir = Path(__file__).parent.parent.parent / "plugins"
            return str(plugins_dir / row['filename'])

        return None
```

**Step 4: 运行测试验证通过**

```bash
pytest tests/test_api_services.py -v
```

Expected: PASS

**Step 5: 提交**

```bash
git add api/v1/services.py tests/test_api_services.py
git commit -m "feat: 实现技能查询服务层"
```

---

## API 路由

### Task 6: 实现技能列表和详情路由

**Files:**
- Create: `api/v1/routes.py`
- Modify: `main.py` (注册路由)
- Test: `tests/test_api_routes.py`

**Step 1: 编写测试 - API 端点**

```python
# tests/test_api_routes.py
import pytest
from fastapi.testclient import TestClient
from main import app
from database import create_api_key

client = TestClient(app)

@pytest.fixture
def api_key():
    """创建测试 API Key"""
    result = create_api_key(user_id=1, name="Route Test")
    return result['api_key']

def test_get_skills_list_no_auth():
    """测试无认证访问"""
    response = client.get("/api/v1/skills")
    assert response.status_code == 401

def test_get_skills_list_with_auth(api_key):
    """测试有效认证访问"""
    headers = {"X-API-Key": api_key}
    response = client.get("/api/v1/skills", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "items" in data["data"]

def test_get_skills_list_with_filter(api_key):
    """测试带过滤条件"""
    headers = {"X-API-Key": api_key}
    response = client.get(
        "/api/v1/skills?source_type=opensource&page=1&page_size=10",
        headers=headers
    )
    assert response.status_code == 200

def test_get_skill_detail(api_key):
    """测试获取技能详情"""
    headers = {"X-API-Key": api_key}
    # 假设存在这个技能
    response = client.get("/api/v1/skills/auditing-python-security", headers=headers)
    # 可能返回 404 或 200
    assert response.status_code in [200, 404]
```

**Step 2: 运行测试验证失败**

```bash
pytest tests/test_api_routes.py -v
```

Expected: FAIL - routes.py 为空，路由未注册

**Step 3: 实现路由定义**

```python
# api/v1/routes.py
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import FileResponse
from typing import Optional
import time

from .schemas import (
    SkillListResponse,
    SkillDetailResponse,
    SkillListQuery,
    SkillDownloadQuery,
    ErrorResponse
)
from .services import get_skills_list, get_skill_detail, get_skill_download_path
from .dependencies import verify_api_key_header, check_rate_limit

router = APIRouter(prefix="/api/v1", tags=["external-api"])

@router.get("/skills", response_model=SkillListResponse)
async def list_skills(
    query: SkillListQuery = Depends(),
    api_key_info: dict = Depends(verify_api_key_header)
):
    """获取技能列表

    支持分类过滤、分页、关键词搜索
    """
    # 检查速率限制
    if not check_rate_limit(api_key_info['api_key'], api_key_info['rate_limit']):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )

    start_time = time.time()

    # 查询数据
    result = get_skills_list(
        source_type=query.source_type.value,
        page=query.page,
        page_size=query.page_size,
        keyword=query.keyword,
        tags=query.tags
    )

    # 记录日志（异步，不阻塞响应）
    response_time = int((time.time() - start_time) * 1000)
    # TODO: 异步记录日志

    return SkillListResponse(
        code=200,
        message="success",
        data={"items": result["items"]},
        pagination=result["pagination"]
    )

@router.get("/skills/{skill_name}", response_model=SkillDetailResponse)
async def get_skill(
    skill_name: str,
    api_key_info: dict = Depends(verify_api_key_header)
):
    """获取技能详情"""
    if not check_rate_limit(api_key_info['api_key'], api_key_info['rate_limit']):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )

    detail = get_skill_detail(skill_name)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill '{skill_name}' not found"
        )

    return SkillDetailResponse(
        code=200,
        message="success",
        data=detail
    )

@router.get("/skills/{skill_name}/download")
async def download_skill(
    skill_name: str,
    query: SkillDownloadQuery = Depends(),
    api_key_info: dict = Depends(verify_api_key_header)
):
    """下载技能 ZIP 压缩包"""
    if not check_rate_limit(api_key_info['api_key'], api_key_info['rate_limit']):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )

    file_path = get_skill_download_path(skill_name, query.version)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill file not found"
        )

    from pathlib import Path
    filename = Path(file_path).name

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/zip"
    )
```

**Step 4: 在 main.py 中注册路由**

```python
# main.py - 在文件适当位置添加

from api.v1.routes import router as api_v1_router

# 在 app 创建之后注册路由
app.include_router(api_v1_router.router)
```

**Step 5: 运行测试验证通过**

```bash
pytest tests/test_api_routes.py -v
```

Expected: PASS

**Step 6: 提交**

```bash
git add api/v1/routes.py main.py tests/test_api_routes.py
git commit -m "feat: 实现技能列表和详情 API 路由"
```

---

### Task 7: 实现下载接口

**说明**: 下载接口已在 Task 6 的 routes.py 中实现，此任务仅补充测试。

**Files:**
- Test: `tests/test_api_download.py`

**Step 1: 编写下载测试**

```python
# tests/test_api_download.py
import pytest
from fastapi.testclient import TestClient
from main import app
from database import create_api_key

client = TestClient(app)

@pytest.fixture
def api_key():
    result = create_api_key(user_id=1, name="Download Test")
    return result['api_key']

def test_download_skill_no_auth():
    """测试无认证下载"""
    response = client.get("/api/v1/skills/test-skill/download")
    assert response.status_code == 401

def test_download_skill_with_auth(api_key):
    """测试有效认证下载"""
    headers = {"X-API-Key": api_key}
    response = client.get("/api/v1/skills/auditing-python-security/download", headers=headers)
    # 可能返回 404（技能不存在）或 200（存在）
    assert response.status_code in [200, 404]

def test_download_skill_with_version(api_key):
    """测试指定版本下载"""
    headers = {"X-API-Key": api_key}
    response = client.get(
        "/api/v1/skills/auditing-python-security/download?version=1.0.0",
        headers=headers
    )
    assert response.status_code in [200, 404]
```

**Step 2: 运行测试**

```bash
pytest tests/test_api_download.py -v
```

Expected: PASS

**Step 3: 提交**

```bash
git add tests/test_api_download.py
git commit -m "test: 添加下载接口测试"
```

---

## API 文档

### Task 8: 配置 Swagger UI 和编写 Markdown 文档

**Files:**
- Modify: `main.py` (配置 Swagger)
- Create: `api/docs/external_api.md`

**Step 1: 配置 FastAPI 的元数据和文档**

```python
# main.py - 在 app 创建时添加配置

app = FastAPI(
    title="SkillHub API",
    description="Claude Code 技能插件管理系统 API",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc"
)

# 配置 API Key 安全方案
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="SkillHub External API",
        version="1.0.0",
        routes=app.routes,
    )

    # 添加安全方案
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "请输入您的 API Key"
        }
    }

    # 全局应用安全方案
    for path in openapi_schema["paths"].values():
        for operation in path.values():
            operation["security"] = [{"ApiKeyAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

**Step 2: 编写 Markdown 文档**

```markdown
# SkillHub External API 文档

## 1. 概述

SkillHub 外部 API 为其他平台提供技能市场数据查询和技能包下载服务。

### Base URL

```
http://your-domain:28000/api/v1
```

### 认证方式

所有 API 请求需要在 HTTP Header 中携带 API Key：

```http
X-API-Key: sk_your_api_key_here
```

## 2. 获取 API Key

请联系管理员获取 API Key。每个 API Key 有独立的速率限制。

## 3. 接口列表

### 3.1 获取技能列表

**端点**: `GET /api/v1/skills`

**参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| source_type | string | 否 | all | 分类：opensource/icsl/huawei/all |
| page | int | 否 | 1 | 页码（≥1） |
| page_size | int | 否 | 20 | 每页数量（1-100） |
| keyword | string | 否 | - | 搜索关键词（名称+描述） |
| tags | string | 否 | - | 标签过滤，逗号分隔 |

**请求示例**:

```bash
curl -H "X-API-Key: sk_your_key" \
  "http://localhost:28000/api/v1/skills?source_type=opensource&page=1&page_size=20"
```

**响应示例**:

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
        "total": 45,
        "total_pages": 3
    }
}
```

### 3.2 获取技能详情

**端点**: `GET /api/v1/skills/{skill_name}`

**请求示例**:

```bash
curl -H "X-API-Key: sk_your_key" \
  "http://localhost:28000/api/v1/skills/auditing-python-security"
```

### 3.3 下载技能压缩包

**端点**: `GET /api/v1/skills/{skill_name}/download`

**参数**:
- `version` (可选): 指定版本

**请求示例**:

```bash
curl -H "X-API-Key: sk_your_key" -o skill.zip \
  "http://localhost:28000/api/v1/skills/auditing-python-security/download"
```

## 4. 错误码

| Code | 说明 |
|------|------|
| 200 | 成功 |
| 400 | 参数错误 |
| 401 | API Key 无效 |
| 403 | 无权限访问 |
| 404 | 资源不存在 |
| 429 | 请求过于频繁 |
| 500 | 服务器错误 |

## 5. 调用示例

### Python

```python
import requests

headers = {"X-API-Key": "sk_your_key"}
response = requests.get(
    "http://localhost:28000/api/v1/skills",
    headers=headers,
    params={"source_type": "opensource", "page": 1}
)
data = response.json()
```

### JavaScript

```javascript
fetch('http://localhost:28000/api/v1/skills?source_type=opensource', {
    headers: {
        'X-API-Key': 'sk_your_key'
    }
})
.then(res => res.json())
.then(data => console.log(data));
```

## 6. 在线文档

访问 Swagger UI 进行交互式测试：`http://your-domain:28000/api/v1/docs`
```

**Step 3: 验证 Swagger 文档可访问**

```bash
# 启动服务
uvicorn main:app --reload

# 访问 http://localhost:8000/api/v1/docs
# 应该能看到 Swagger UI 界面
```

**Step 4: 提交**

```bash
git add main.py api/docs/external_api.md
git commit -m "feat: 配置 Swagger UI 和添加 API 文档"
```

---

## 收尾工作

### Task 9: 全量测试和清理

**Step 1: 运行所有测试**

```bash
pytest tests/ -v
```

确保所有测试通过。

**Step 2: 代码格式检查**

```bash
# 如果有 black
black api/ tests/

# 如果有 pylint/pylint
pylint api/v1/
```

**Step 3: 提交最终代码**

```bash
git add .
git commit -m "chore: 最终代码整理和测试通过"
```

---

## 实施完成检查清单

- [ ] 数据库表已创建（external_api_keys, api_call_logs）
- [ ] API Key 管理函数已实现并测试通过
- [ ] Pydantic Schema 已定义
- [ ] 认证依赖已实现
- [ ] 技能查询服务已实现
- [ ] API 路由已实现并注册
- [ ] Swagger UI 已配置
- [ ] Markdown 文档已编写
- [ ] 所有测试通过
- [ ] 代码已提交

---

## 预计工时

- Task 0: 目录结构 - 5 分钟
- Task 1-2: 数据库 - 30 分钟
- Task 3: Schema - 20 分钟
- Task 4: 认证 - 20 分钟
- Task 5: 服务层 - 40 分钟
- Task 6-7: 路由 - 30 分钟
- Task 8: 文档 - 20 分钟
- Task 9: 收尾 - 15 分钟

**总计**: 约 3 小时
