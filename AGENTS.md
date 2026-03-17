# 工作规则

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
3. **代码格式化**：
   - 使用 black 进行自动格式化
   - 行长度限制：88 字符（black 默认）
   - 缩进：4 个空格，不使用 Tab
4. **导入顺序**：
   - 使用 isort 自动排序
   - 顺序：标准库 → 第三方库 → 本地模块
   - 每组之间空一行
   - 避免通配符导入 `from module import *`
5. **代码复杂度**：
   - 单个函数不超过 50 行
   - 圈复杂度不超过 10
   - 嵌套层级不超过 4 层

### 类型注解规范

1. **必须使用类型提示**：所有函数参数和返回值必须有类型注解
2. **类型注解位置**：
   ```python
   def process_data(items: list[str]) -> dict[str, int]:
       pass
   ```
3. **使用 typing 模块**：
   - 优先使用 `list[str]` 而非 `List[str]`（Python 3.9+）
   - 使用 `Optional[T]` 表示可空类型
   - 使用 `Union[T1, T2]` 表示联合类型
   - 使用 `Literal` 表示字面量类型
4. **避免使用 `Any`**：除非必要，否则不使用 `typing.Any`
5. **类型别名**：复杂类型定义别名提高可读性
   ```python
   from typing import TypedDict

   class UserData(TypedDict):
       name: str
       age: int
       email: str
   ```

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
3. **自定义异常**：继承 `Exception` 或 `RuntimeError`
   ```python
   class ValidationError(Exception):
       """数据验证错误"""
       pass
   ```
4. **异常信息**'：提供有意义的错误消息，包含上下文信息
5. **资源管理**：使用上下文管理器 `with` 管理资源
6. **禁止静默失败**：不使用空的 except 块

### 测试规范

1. **使用 pytest**：作为测试框架
2. **测试文件命名**：`test_*.py` 或 `*_test.py`
3. **测试函数命名**：`test_<功能>_<场景>`
4. **测试结构**：AAA 模式（Arrange-Act-Assert）
   ```python
   def test_user_creation_success():
       # Arrange
       user_data = {"name": "test", "email": "test@example.com"}
       
       # Act
       user = create_user(user_data)
       
       # Assert
       assert user.name == "test"
       assert user.email == "test@example.com"
   ```
5. **测试覆盖**：
   - 单元测试覆盖率 ≥ 80%
   - 关键业务逻辑覆盖率 ≥ 90%
6. **使用 fixture**：复用测试数据和设置
7. **测试隔离**：每个测试独立，不依赖执行顺序
8. **标记测试**：使用 pytest markers 分类测试
   ```python
   @pytest.mark.unit
   @pytest.mark.slow
   def test_complex_operation():
       pass
   ```

### 文档规范

1. **docstring 格式**：使用 Google 风格或 NumPy 风格
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
2. **模块文档**：每个模块文件顶部添加模块级 docstring
3. **类文档**：每个类添加类级 docstring 说明用途
4. **注释规范**：
   - 解释"为什么"而非"是什么"
   - 复杂逻辑必须添加注释
   - 保持注释与代码同步
5. **README 要求**：
   - 项目简介和功能说明
   - 安装和运行指南
   - 依赖列表（requirements.txt 或 pyproject.toml）
   - 使用示例
   - 贡献指南

### 其他规范

1. **依赖管理**：使用 requirements.txt 或 pyproject.toml
2. **虚拟环境**：使用 venv 或 conda 管理环境
3. **日志记录**：使用 logging 模块，不使用 print
4. **配置管理**：使用环境变量或配置文件，不硬编码
5. **安全性**：
   - 敏感信息使用环境变量
   - 输入验证和清理
   - SQL 注入防护（使用参数化查询）
6. **性能**：
   - 避免不必要的循环嵌套
   - 使用生成器处理大数据
   - 合理使用缓存