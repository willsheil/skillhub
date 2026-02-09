# 日志系统使用指南

## 概述

本系统实现了企业级的结构化日志解决方案，支持：
- JSON 格式的结构化日志
- 日志轮转和归档
- 操作审计日志
- 性能监控和追踪
- 敏感信息自动脱敏

## 日志文件结构

```
logs/
├── application.log      # 主应用日志（JSON格式）
├── error.log           # 错误日志（JSON格式）
├── audit.log           # 审计日志（JSON格式）
└── application.log.1   # 轮转备份文件
```

## 日志级别

| 级别 | 用途 | 示例 |
|------|------|------|
| DEBUG | 详细调试信息 | 函数调用参数、中间变量 |
| INFO | 一般信息 | 操作成功、状态变更 |
| WARNING | 警告信息 | 重试操作、配置问题 |
| ERROR | 错误信息 | 操作失败、异常捕获 |
| CRITICAL | 严重错误 | 系统无法继续运行 |

## 使用方法

### 1. 基础日志记录

```python
import logging
from logging_config import setup_logging

# 初始化日志系统
logger = setup_logging(level="INFO")

# 基础日志
logger.info("用户登录成功")
logger.warning("磁盘空间不足")
logger.error("数据库连接失败", exc_info=True)
```

### 2. 结构化日志（添加上下文）

```python
# 添加额外上下文信息
logger.info(
    "技能上传成功",
    extra={
        "skill_name": "code-reviewer",
        "version": "1.0.0",
        "user_id": 123,
        "file_size": 15000
    }
)
```

**输出示例**:
```json
{
  "timestamp": "2025-02-09T10:30:00.123Z",
  "level": "INFO",
  "logger": "main",
  "message": "技能上传成功",
  "context": {
    "skill_name": "code-reviewer",
    "version": "1.0.0",
    "user_id": 123,
    "file_size": 15000
  }
}
```

### 3. 审计日志

审计日志用于记录关键操作，用于合规和安全审计。

```python
from logging_config import audit_log

# 用户登录
audit_log(
    logger,
    action="user_login",
    user_id=123,
    ip_address="192.168.1.1",
    result="success"
)

# 技能审核
audit_log(
    logger,
    action="skill_approve",
    user_id=1,
    skill_id=456,
    ip_address="192.168.1.100",
    result="approved",
    comment="审核通过"
)

# 技能下载
audit_log(
    logger,
    action="skill_download",
    user_id=123,
    skill_name="code-reviewer",
    version="1.0.0",
    ip_address="192.168.1.1"
)
```

**审计操作类型**:
- `user_login` - 用户登录
- `user_logout` - 用户登出
- `skill_upload` - 技能上传
- `skill_download` - 技能下载
- `skill_approve` - 技能批准
- `skill_reject` - 技能拒绝
- `admin_access` - 管理员访问
- `config_change` - 配置变更
- `gitea_push` - Gitea 推送
- `gitea_push_failed` - Gitea 推送失败
- `user_create` - 用户创建
- `user_delete` - 用户删除

### 4. 性能追踪

#### 方法 1：使用上下文管理器

```python
from logging_config import PerformanceTracker

# 追踪操作性能
with PerformanceTracker(
    logger,
    operation="database_query",
    threshold_ms=1000,  # 超过1秒记录为警告
    query="SELECT * FROM skills"
):
    # 执行数据库查询
    result = db.execute("SELECT * FROM skills")
```

#### 方法 2：使用装饰器

```python
from logging_config import log_performance

@log_performance(logger, "push_to_gitea")
def push_skill(skill_zip, skill_name, version):
    # 推送技能到 Gitea
    ...

# 调用函数会自动记录性能
push_skill(zip_path, "my-skill", "1.0.0")
```

**性能日志示例**:
```json
{
  "timestamp": "2025-02-09T10:30:00.123Z",
  "level": "WARNING",
  "logger": "main",
  "message": "Slow operation: database_query took 1234.56ms",
  "context": {
    "performance": {
      "operation": "database_query",
      "duration_ms": 1234.56,
      "slow": true
    },
    "query": "SELECT * FROM skills"
  }
}
```

### 5. 请求追踪

为请求分配唯一 ID，便于追踪整个请求链路：

```python
import uuid
from logging_config import request_id_var

# 在请求开始时设置 request_id
request_id = str(uuid.uuid4())
request_id_var.set(request_id)

# 该请求的所有日志会自动包含 request_id
logger.info("处理请求开始", extra={"endpoint": "/api/upload"})
# ... 执行操作 ...
logger.info("处理请求完成", extra={"endpoint": "/api/upload", "status": "success"})
```

### 6. 异常追踪

```python
try:
    # 可能出错的代码
    result = risky_operation()
except Exception as e:
    logger.error(
        "操作失败",
        extra={
            "operation": "risky_operation",
            "error_type": type(e).__name__,
            "error_message": str(e)
        },
        exc_info=True  # 包含完整的堆栈跟踪
    )
```

## 敏感信息脱敏

系统会自动脱敏以下敏感信息：

| 敏感信息 | 脱敏示例 |
|---------|---------|
| API Key | `api_key=abc123` → `api_key=***` |
| Token | `token=xyz789` → `token=***` |
| Password | `password=secret` → `password=***` |
| Employee ID | `employee_id=123456` → `employee_id=***456` |

## 日志配置

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| LOG_LEVEL | 日志级别 | INFO |
| LOG_DIR | 日志目录 | ./logs |
| LOG_JSON_ENABLED | 启用JSON日志 | true |
| LOG_CONSOLE_ENABLED | 启用控制台输出 | true |
| LOG_MAX_BYTES | 单文件最大字节数 | 10485760 (10MB) |
| LOG_BACKUP_COUNT | 备份文件数量 | 5 |

### 配置示例

```bash
# .env 文件
LOG_LEVEL=DEBUG
LOG_DIR=/var/log/skill-registry
LOG_MAX_BYTES=52428800  # 50MB
LOG_BACKUP_COUNT=10
```

### Python 配置

```python
from logging_config import setup_logging

logger = setup_logging(
    level="DEBUG",
    log_dir="./logs",
    enable_json=True,
    enable_console=True,
    max_bytes=50 * 1024 * 1024,  # 50MB
    backup_count=10
)
```

## 日志查询和分析

### 使用 jq 查询 JSON 日志

```bash
# 查看所有错误日志
cat logs/application.log | jq 'select(.level == "ERROR")'

# 查看特定用户的操作
cat logs/application.log | jq 'select(.context.user_id == 123)'

# 查看慢操作（超过1秒）
cat logs/application.log | jq 'select(.context.performance.duration_ms > 1000)'

# 统计错误类型
cat logs/error.log | jq -r '.exception.type' | sort | uniq -c
```

### 使用 grep 查询

```bash
# 查找特定关键词
grep "skill_upload" logs/application.log

# 查找特定时间范围
grep "2025-02-09T1[0-2]:" logs/application.log

# 查找特定用户
grep '"user_id": 123' logs/application.log
```

### 日志分析工具

#### ELK Stack (Elasticsearch, Logstash, Kibana)
```bash
# Filebeat 配置示例
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /path/to/logs/application.log
  json.keys_under_root: true
  json.add_error_key: true

output.elasticsearch:
  hosts: ["localhost:9200"]
```

#### Grafana Loki
```bash
# Promtail 配置示例
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

scrape_configs:
- job_name: skill-registry
  static_configs:
  - targets:
      - localhost
    labels:
      job: skill-registry
      __path__: /path/to/logs/*.log
```

## 性能优化

### 1. 异步日志

对于高性能场景，可以使用异步日志处理：

```python
import logging.handlers

# 使用队列处理器
queue_handler = logging.handlers.QueueHandler(logging.Queue())
listener = logging.handlers.QueueListener(queue_handler, *handlers)

logger.addHandler(queue_handler)
listener.start()
```

### 2. 日志级别调整

生产环境建议使用 INFO 级别：

```python
# 开发环境
logger = setup_logging(level="DEBUG")

# 生产环境
logger = setup_logging(level="INFO")
```

### 3. 减少日志量

```python
# 只在调试模式记录详细信息
if logger.isEnabledFor(logging.DEBUG):
    logger.debug("详细调试信息", extra={"large_data": big_object})

# 使用条件判断避免不必要的字符串格式化
logger.debug("用户数据: %s", user_data) if logger.debug else None
```

## 最佳实践

### 1. 日志消息规范

✅ **好的日志消息**:
- 清晰明确："用户登录成功"
- 包含上下文："技能上传失败: 文件大小超过限制"
- 使用过去式："已创建用户记录"

❌ **不好的日志消息**:
- 模糊不清："发生了错误"
- 缺少上下文："操作失败"
- 使用现在时："创建用户"

### 2. 适当的日志级别

```python
# DEBUG - 开发调试信息
logger.debug(f"SQL查询: {query}", extra={"query": query})

# INFO - 重要业务事件
logger.info(f"技能 {skill_name} 上传成功", extra={"skill_name": skill_name})

# WARNING - 可恢复的问题
logger.warning(f"重试第 {attempt} 次", extra={"attempt": attempt})

# ERROR - 需要关注的错误
logger.error("数据库连接失败", exc_info=True)

# CRITICAL - 系统无法继续
logger.critical("磁盘空间不足，无法写入文件")
```

### 3. 结构化数据使用

```python
# 推荐：使用 extra 参数添加结构化数据
logger.info(
    "用户操作",
    extra={
        "user_id": 123,
        "action": "upload",
        "resource_type": "skill",
        "resource_id": 456,
        "ip_address": "192.168.1.1"
    }
)

# 不推荐：将所有信息放在消息字符串中
logger.info(f"用户 123 执行了 upload 操作，资源类型是 skill，资源 ID 是 456")
```

### 4. 异常处理

```python
try:
    operation()
except Exception as e:
    # 记录完整的异常信息
    logger.error(
        "操作失败",
        extra={"operation": "operation", "error": str(e)},
        exc_info=True  # 包含堆栈跟踪
    )
```

## 监控和告警

### 1. 关键指标监控

```python
# 定期检查日志中的错误率
def check_error_rate(log_file, window_minutes=5):
    """检查过去N分钟内的错误率"""
    # 实现错误率统计
    pass

# 设置告警阈值
if error_rate > 0.1:  # 10% 错误率
    send_alert("高错误率告警")
```

### 2. 慢查询监控

```python
# 监控超过阈值的操作
with PerformanceTracker(logger, "database_query", threshold_ms=1000):
    result = db.execute(query)
```

## 故障排查

### 问题：日志文件过大

**解决方案**:
1. 调整日志级别（从 DEBUG 改为 INFO）
2. 减小 `LOG_MAX_BYTES` 值
3. 减少 `LOG_BACKUP_COUNT` 值
4. 实施日志归档策略

### 问题：性能影响

**解决方案**:
1. 使用异步日志
2. 减少日志输出量
3. 避免在热循环中记录日志
4. 使用条件判断避免不必要的字符串格式化

### 问题：敏感信息泄露

**解决方案**:
1. 检查 `SensitiveDataFilter` 是否正常工作
2. 确保所有日志记录都使用该过滤器
3. 审计代码中直接记录敏感信息的地方

## 参考

- Python logging 模块文档: https://docs.python.org/3/library/logging.html
- JSON 日志标准: https://jsonlog.org/
- ELK Stack 官方文档: https://www.elastic.co/guide/
