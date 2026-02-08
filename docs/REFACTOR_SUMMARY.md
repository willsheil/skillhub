# Skill Registry 重构总结

## 重构目标

按照 [Agent Skills Specification](https://agentskills.io/specification) 将 Skill Registry 的元数据格式从 `package.json` 迁移到 `SKILL.md`（包含 YAML 前置内容）。

## 主要变更

### 1. 新的 Skill 格式

#### 文件夹结构
```
skill-name/
├── SKILL.md          # 必需: 技能说明 + 元数据
├── scripts/          # 可选: 可执行代码
├── references/       # 可选: 参考文档
└── assets/           # 可选: 模板、资源文件
```

#### SKILL.md 格式
```yaml
---
name: skill-name
description: A description of what this skill does and when to use it.
license: Apache-2.0
metadata:
  author: example-org
  version: "1.0"
---

# Skill Instructions

Markdown content here...
```

### 2. YAML 前置内容字段

#### 必需字段
| 字段 | 约束条件 |
|------|----------|
| `name` | 1-64字符，仅限小写字母、数字和连字符，不能以连字符开头或结尾，不能包含连续连字符(`--`) |
| `description` | 1-1024字符，非空，描述技能功能和何时使用 |

#### 可选字段
| 字段 | 约束条件 |
|------|----------|
| `license` | 许可证名称或引用 |
| `compatibility` | 1-500字符，环境要求 |
| `metadata` | 任意键值映射（可包含 author, version 等） |
| `allowed-tools` | 空格分隔的预批准工具列表（实验性） |

### 3. 代码变更

#### main.py
- **新增依赖**: `pyyaml` 用于解析 YAML
- **新增函数**:
  - `parse_skill_md()`: 解析 SKILL.md 的 YAML 前置内容
  - `extract_metadata_from_skill_md()`: 从 ZIP 中提取 SKILL.md 元数据
  - `validate_skill_name()`: 验证 skill name 格式（小写、数字、连字符，无连续连字符）

- **修改函数**:
  - `extract_metadata()`: 优先从 SKILL.md 提取，失败时回退到 package.json
  - `validate_skill_zip()`: 验证 SKILL.md 存在性和必需字段，验证 name 和 description 约束
  - `save_skill_zip()`: 使用 SKILL.md 中的 name 字段

#### 前端模板
- `index.html`: 更新 author 显示逻辑，从 `metadata.metadata.author` 读取
- `admin_upload.html`: 更新上传要求说明，符合 Agent Skills 规范

### 4. 新增文件

| 文件 | 说明 |
|------|------|
| `migrate-to-skillmd.py` | 迁移脚本，将现有 package.json 格式转换为 SKILL.md |
| `test_skill_format.py` | 测试脚本，验证新格式功能 |
| `docs/SKILL_FORMAT_MIGRATION.md` | 详细的迁移指南 |
| `docs/example-skill/SKILL.md` | 示例 SKILL.md 文件 |
| `docs/REFACTOR_SUMMARY.md` | 本文档 |

### 5. 修改的文件

| 文件 | 变更 |
|------|------|
| `requirements.txt` | 添加 `pyyaml` 依赖 |
| `main.py` | 核心逻辑重构，支持 Agent Skills 规范 |
| `templates/index.html` | 更新 author 显示逻辑 |
| `templates/admin_upload.html` | 更新上传要求说明 |

## 向后兼容性

- **读取**: Registry 可以同时读取新旧格式的技能
  - 优先尝试 SKILL.md
  - 失败时回退到 package.json
- **写入**: 新上传的技能必须使用 SKILL.md 格式
- **验证**: 上传时强制验证 SKILL.md 格式，包括 name 和 description 约束

## 迁移步骤

### 1. 安装新依赖

```bash
pip install -r requirements.txt
```

### 2. 迁移现有技能

```bash
python migrate-to-skillmd.py
```

此脚本会：
- 扫描 `plugins/` 目录中的所有 ZIP 文件
- 读取 `package.json`
- 生成 `SKILL.md`（带 YAML 前置内容）
- 移除 `package.json`
- 重新打包 ZIP

迁移过程中，skill name 会自动转换为符合规范的格式（小写、替换非法字符等）。

### 3. 验证迁移

启动服务并验证：
```bash
python main.py
```

访问 `http://localhost:28000/marketplace.json` 检查是否正确解析。

## Name 格式规范

Agent Skills 规范对 name 字段有严格要求：

- 1-64字符
- 仅限小写字母、数字和连字符
- 不能以连字符开头或结尾
- 不能包含连续连字符(`--`)

有效示例：
- `pdf-processing`
- `data-analysis`
- `code-review`
- `api-v2-client`

无效示例：
- `PDF-Processing`（大写字母）
- `-pdf`（以连字符开头）
- `pdf--processing`（连续连字符）
- `pdf_processing`（下划线）

## API 响应格式

`marketplace.json` 返回的格式与 Agent Skills 规范一致：

```json
{
  "name": "skill-name",
  "version": "1.0.0",
  "description": "Description",
  "license": "Apache-2.0",
  "compatibility": null,
  "metadata": {
    "author": "example-org",
    "version": "1.0"
  }
}
```

Author 信息现在位于 `metadata.author` 字段。

## 测试

运行测试脚本验证功能：

```bash
python test_skill_format.py
```

测试内容包括：
- Skill name 格式验证
- SKILL.md 解析
- ZIP 文件验证
- 向后兼容性

## 注意事项

1. **必需字段**: SKILL.md 必须包含 `name` 和 `description`
2. **Name 格式**: 必须严格遵循 Agent Skills 规范
3. **Description 长度**: 必须在 1-1024 字符之间
4. **Version**: 从 `metadata.version` 获取，默认为 `1.0.0`
5. **Author**: 现在位于 `metadata.author`，任意字符串格式
6. **文件位置**: SKILL.md 可以在 ZIP 根目录或子目录中

## 参考

- [Agent Skills Specification](https://agentskills.io/specification)
- `docs/SKILL_FORMAT_MIGRATION.md`
- `docs/example-skill/SKILL.md`
