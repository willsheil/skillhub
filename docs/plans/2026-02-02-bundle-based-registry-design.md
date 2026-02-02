# Bundle-Based Registry Design

## 目标

将 Registry 从三层结构（Organization → Collection → Skill）简化为两层结构（Skill Bundle → Skill），让组织用户通过类似 `/plugin marketplace add` 和 `/plugin install` 命令一键安装 Skill Bundle。

## 架构变更

### 目录结构

**旧结构（三层）：**
```
plugins/
├── {organization}/
│   ├── {collection}/
│   │   ├── {skill}/
│   │   │   ├── {version}.zip
```

**新结构（两层）：**
```
plugins/
├── {bundle}/
│   ├── {skill}/
│   │   ├── {version}.zip
│   └── .bundle-metadata.json (可选)
```

**示例：**
```
plugins/
├── security-tools/
│   ├── semgrep-rule-creator/
│   │   ├── 1.0.0.zip
│   │   └── 1.1.0.zip
│   ├── yara-authoring/
│   │   └── 1.0.0.zip
│   └── .bundle-metadata.json
└── productivity-boosters/
    └── git-workflow-helper/
        └── 2.0.0.zip
```

## API 端点变更

### 修改的端点

| 旧端点 | 新端点 | 变更说明 |
|--------|--------|----------|
| `/api/collections` | `/api/bundles` | 列出所有 bundles |
| `/api/collections/{org}/{collection}` | `/api/bundles/{bundle}` | 获取 bundle 下的所有 skills |
| `/plugins/{org}/{collection}/{name}/{version}.zip` | `/plugins/{bundle}/{name}/{version}.zip` | 下载端点（两参数） |
| `/admin/upload` | `/admin/upload` | 参数从 `organization/collection` 改为 `bundle` |

### 新增端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/bundles/{bundle}/skills` | GET | 列出 bundle 下所有 skill 详情 |
| `/api/search` | GET | 搜索 bundles 和 skills（按名称/描述） |

### 删除端点

- `/api/skills`
- `/api/collections`
- `/api/collections/{org}/{collection}`

## Marketplace.json 格式

**新格式：**
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
    "updated_at": "2025-02-02T10:00:00Z"
  },
  "plugins": [
    {
      "name": "auditing-python-security",
      "bundle": "security-tools",
      "version": "1.0.0",
      "description": "Security auditing for Python code",
      "author": {"name": "Security Team"},
      "source": "/plugins/security-tools/auditing-python-security/1.0.0.zip"
    }
  ]
}
```

**兼容性待验证：** 是否需要保留 `organization` 和 `collection` 字段，通过测试验证后再决定。

## 安装命令格式

| 操作 | 命令 |
|------|------|
| 安装整个 Bundle | `/plugin install security-tools` |
| 安装单个 Skill | `/plugin install security-tools/semgrep-rule-creator` |

无需 `--all` 参数，CLI 自动识别是 bundle 还是 skill。

## 前端界面变更

### 首页布局

**新布局（两层）：**
```
┌─────────────────────────────────────────┐
│ 🔍 [搜索框]                              │
├─────────────────────────────────────────┤
│ 📦 security-tools (Bundle)               │
│    • semgrep-rule-creator (v1.0.0) [安装] │
│    • yara-authoring (v1.0.0) [安装]       │
│    [安装整个Bundle]                      │
├─────────────────────────────────────────┤
│ 📦 productivity-boosters                 │
│    • git-workflow-helper (v2.0.0) [安装] │
│    [安装整个Bundle]                      │
└─────────────────────────────────────────┘
```

### 上传页面

**旧表单字段：**
- Organization
- Collection
- Name（可选）
- Version（可选）
- File

**新表单字段：**
- Bundle Name
- Name（可选）
- Version（可选）
- File

## 搜索功能

**搜索权重：**
- Bundle 名称匹配：+10 分
- Skill 名称匹配：+5 分
- 描述匹配：+2 分

按匹配分数排序返回结果。

## 数据处理

### 旧数据处理

不需要迁移脚本。管理员直接删除 `plugins/` 目录，重新上传新的 bundles。

**步骤：**
```bash
# 备份并删除
mv plugins plugins-old

# 通过 /admin/upload 重新上传
```

## 实施清单

### 后端修改 (main.py)

- [ ] 修改 `scan_plugins()` - 从三层遍历改为两层
- [ ] 修改 `marketplace_json()` - 更新 JSON 格式
- [ ] 修改 `download_plugin()` - 从三参数改为两参数
- [ ] 添加 `/api/bundles` 端点
- [ ] 添加 `/api/bundles/{bundle}` 端点
- [ ] 添加 `/api/search` 端点
- [ ] 修改 `/admin/upload` - organization/collection → bundle
- [ ] 修改 `delete_plugin()` - 从四参数改为三参数
- [ ] 删除 `/api/skills`, `/api/collections` 等端点

### 前端修改

- [ ] `templates/index.html` - 搜索框 + bundle 卡片布局
- [ ] `templates/admin_upload.html` - 表单字段更新

### 验证

- [ ] 创建 `validate_marketplace.py` 测试脚本
- [ ] 在 Claude Code 中验证新的 marketplace.json 格式
- [ ] 测试 `/plugin install` 命令（bundle 和 skill）
- [ ] 测试搜索功能

### 部署

- [ ] 备份现有 plugins 目录
- [ ] 清空 `plugins/`
- [ ] 重新上传 skill bundles
- [ ] 端到端测试

## 兼容性验证

**验证脚本：** `scripts/validate_marketplace.py`

生成测试用的 marketplace.json，验证 Claude Code 能否识别新格式。

**验证清单：**
- [ ] Claude Code 能识别新的 marketplace.json
- [ ] `/plugin menu` 能显示 skills
- [ ] `/plugin install test-bundle/test-skill` 成功
- [ ] `/plugin install test-bundle` 安装整个 bundle

验证通过后决定是否完全移除 `organization` 和 `collection` 字段。
