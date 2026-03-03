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
| page | int | 否 | 1 | 页码（>=1） |
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
