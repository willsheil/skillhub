# SkillHub 测试套件

本目录包含 SkillHub 项目的完整测试套件。

## 测试文件说明

### 核心测试文件

| 测试文件 | 测试内容 | 描述 |
|---------|----------|------|
| `test_user_management.py` | 用户管理 | 登录、权限、会话管理 |
| `test_approval_integration.py` | 审批流程 | 技能审核、Gitea推送任务创建 |
| `test_batch_operations.py` | 批量操作 | 批量下架、批量删除、外键约束 |
| `test_notifications.py` | 通知系统 | 审核通知、未读计数、标记已读 |
| `test_skill_management.py` | 技能管理 | 默认版本、来源分类、状态管理 |
| `test_gitea_client.py` | Gitea客户端 | Git操作封装 |
| `test_gitea_integration.py` | Gitea集成 | 推送任务管理 |
| `test_push_service.py` | 推送服务 | 后台推送逻辑 |
| `test_e2e_gitea_flow.py` | 端到端测试 | 完整的Gitea工作流 |

## 运行测试

### 前提条件

1. 安装测试依赖：
```bash
pip install -r requirements.txt
```

2. 确保数据库配置正确（测试会使用独立数据库或内存数据库）

### 运行所有测试

```bash
# 运行所有测试
pytest

# 带详细输出
pytest -v

# 带打印输出
pytest -v -s
```

### 运行特定测试文件

```bash
# 运行用户管理测试
pytest tests/test_user_management.py

# 运行批量操作测试
pytest tests/test_batch_operations.py

# 运行通知系统测试
pytest tests/test_notifications.py

# 运行技能管理测试
pytest tests/test_skill_management.py
```

### 运行特定测试用例

```bash
# 运行单个测试函数
pytest tests/test_batch_operations.py::test_batch_unlist_skills

# 运行带标记的测试
pytest -m "not slow"           # 跳过慢速测试
pytest -m "unit"              # 只运行单元测试
pytest -m "integration"        # 只运行集成测试
```

### 测试覆盖率

```bash
# 生成覆盖率报告
pytest --cov=. --cov-report=html --cov-report=term

# 查看HTML报告
open htmlcov/index.html
```

## 测试分类

### 单元测试 (Unit Tests)

- 测试单个函数和类
- 不依赖外部服务
- 快速执行
- 标记: `@pytest.mark.unit`

### 集成测试 (Integration Tests)

- 测试模块间交互
- 可能需要数据库
- 标记: `@pytest.mark.integration`

### 端到端测试 (E2E Tests)

- 测试完整工作流
- 可能需要运行中的服务器
- 标记: `@pytest.mark.e2e`

### Gitea集成测试

- 测试与Gitea的集成
- 需要Gitea服务器
- 标记: `@pytest.mark.gitea`

## 测试数据管理

### Fixtures

测试使用 pytest fixtures 来管理测试数据：

```python
@pytest.fixture(autouse=True)
def setup_database():
    """每个测试前自动清理数据库"""
    # 清理逻辑
    yield
    # 清理逻辑
```

### 测试数据命名规范

为避免冲突，测试数据使用特定前缀：
- 用户: `test-*-user` (如 `test-batch-user`)
- 技能: `test-*-skill` (如 `test-batch-skill-1`)

## 编写新测试

### 测试模板

```python
"""
Tests for [模块名称] in SkillHub.
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_connection, init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Setup test database before each test."""
    init_db()
    # 清理测试数据
    with get_connection() as conn:
        conn.execute("DELETE FROM ...")
        conn.commit()
    yield
    # 测试后清理
    with get_connection() as conn:
        conn.execute("DELETE FROM ...")
        conn.commit()


def test_[测试名称]():
    """测试描述."""
    # Arrange (准备)
    user_id = create_test_user()

    # Act (执行)
    response = client.post("/api/endpoint")

    # Assert (断言)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
```

### 测试命名规范

- 测试函数以 `test_` 开头
- 使用描述性名称：`test_batch_unlist_skills`
- 测试类以 `Test` 开头

## 持续集成

### GitHub Actions 示例

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run tests
        run: |
          pytest --cov=. --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## 故障排除

### 常见问题

**Q: 测试失败，提示数据库连接错误**

A: 检查 `.env` 文件中的数据库配置，确保测试数据库可用。

**Q: 某些测试被跳过**

A: 某些测试需要特定条件（如运行中的服务器），检查测试输出中的跳过原因。

**Q: 外键约束错误**

A: 确保测试正确清理相关数据，使用事务或正确的删除顺序。

## 贡献指南

1. 新功能应该包含对应的测试
2. 测试覆盖率应保持在 80% 以上
3. 遵循现有的测试命名和组织规范
4. 为复杂逻辑添加集成测试
5. 提交前运行完整测试套件

## 相关文档

- [技术架构文档](../docs/技术架构.md)
- [使用说明](../docs/使用说明.md)
- [API文档](../docs/apidoc.md)
