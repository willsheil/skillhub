# SKILL.md 格式迁移指南

## 概述

Claude Code Skill Registry 已按照 [Agent Skills Specification](https://agentskills.io/specification) 从 `package.json` 格式迁移到 `SKILL.md` 格式。

## 新的 Skill 格式

### 文件夹结构

```
skill-name/
├── SKILL.md          # 必需: 技能说明 + 元数据
├── scripts/          # 可选: 可执行代码
├── references/       # 可选: 参考文档
└── assets/           # 可选: 模板、资源文件
```

### SKILL.md 格式

每个 SKILL.md 文件必须以 YAML 前置内容开头，后跟 Markdown 说明：

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

### YAML 前置内容字段

#### 必需字段

| 字段 | 约束条件 |
|------|----------|
| `name` | 1-64字符，仅限小写字母、数字和连字符，不能以连字符开头或结尾，不能包含连续连字符(`--`) |
| `description` | 1-1024字符，非空，描述技能功能和何时使用 |

#### 可选字段

| 字段 | 约束条件 |
|------|----------|
| `license` | 许可证名称或引用 |
| `compatibility` | 1-500字符，环境要求（目标产品、系统包、网络访问等） |
| `metadata` | 任意键值映射，用于额外元数据（如 author, version） |
| `allowed-tools` | 空格分隔的预批准工具列表（实验性） |

### Name 字段格式

有效的 name 示例：
```yaml
name: pdf-processing
name: data-analysis
name: code-review
```

无效的 name 示例：
```yaml
name: PDF-Processing    # 不允许大写字母
name: -pdf              # 不能以连字符开头
name: pdf--processing   # 不能包含连续连字符
```

### Description 字段

良好的 description 示例：
```yaml
description: Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when working with PDF documents or when the user mentions PDFs, forms, or document extraction.
```

不佳的 description 示例：
```yaml
description: Helps with PDFs.
```

### Metadata 字段

`metadata` 用于存储额外的元数据，推荐包含：
- `author`: 作者信息（任意字符串）
- `version`: 版本号（如 "1.0.0"）

示例：
```yaml
metadata:
  author: w00545471
  version: "1.0.0"
  category: security
```

## 迁移现有技能

### 自动迁移

运行迁移脚本将现有 `package.json` 格式的技能转换为 `SKILL.md` 格式：

```bash
python migrate-to-skillmd.py
```

此脚本会：
1. 扫描 `plugins/` 目录中的所有 ZIP 文件
2. 提取 `package.json`
3. 生成 `SKILL.md`（带 YAML 前置内容）
4. 移除 `package.json`
5. 重新打包 ZIP

迁移后的 skill name 会自动转换为符合规范的格式（小写、替换非法字符等）。

### 手动迁移

如需手动迁移，请按以下步骤操作：

1. **解压 ZIP 文件**
   ```bash
   unzip skill-name-1.0.0.zip -d skill-name
   ```

2. **创建 SKILL.md**

   根据 `package.json` 内容创建 `SKILL.md`：

   ```yaml
   ---
   name: skill-name
   description: Skill description from package.json
   license: Unknown
   metadata:
     author: Author Name
     version: "1.0.0"
   ---

   # Skill Name

   Skill instructions...
   ```

3. **删除 package.json**
   ```bash
   rm skill-name/package.json
   ```

4. **重新打包**
   ```bash
   zip -r skill-name-1.0.0.zip skill-name/
   ```

## 创建新技能

### 步骤 1: 创建文件夹结构

```bash
mkdir my-skill
cd my-skill
mkdir -p scripts references assets
```

### 步骤 2: 创建 SKILL.md

```bash
cat > SKILL.md << 'EOF'
---
name: my-skill
description: Description of what this skill does and when to use it
license: Apache-2.0
metadata:
  author: your-name
  version: "1.0.0"
---

# My Skill

Detailed instructions for using this skill...
EOF
```

### 步骤 3: 打包

```bash
zip -r my-skill-1.0.0.zip my-skill/
```

### 步骤 4: 上传

通过 Web 界面上传到 Registry。

## 向后兼容性

- **读取**: Registry 可以同时读取新旧格式的技能（优先尝试 SKILL.md，失败时回退到 package.json）
- **写入**: 新上传的技能必须使用 SKILL.md 格式
- **验证**: 上传时强制验证 SKILL.md 格式，包括 name 和 description 的约束

## API 变更

### marketplace.json

`marketplace.json` 端点返回的格式与 Agent Skills 规范一致：

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

## 常见问题

### Q: 为什么需要迁移？

A: SKILL.md 格式提供了：
- 更好的可读性（Markdown 格式）
- 更简洁的元数据定义（YAML）
- 支持更丰富的说明文档
- 与 Agent Skills 官方规范保持一致

### Q: 迁移会丢失数据吗？

A: 不会。迁移脚本会保留所有元数据，只是转换格式。skill name 可能会根据规范进行调整（转换为小写、替换非法字符等）。

### Q: 可以同时使用新旧格式吗？

A: 可以。Registry 可以同时处理两种格式，但建议尽快迁移到新的 SKILL.md 格式。

### Q: 如何验证 SKILL.md 格式正确？

A: 使用以下命令测试：

```bash
python -c "
import yaml
with open('SKILL.md', 'r') as f:
    content = f.read()
    # Parse YAML frontmatter
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 2:
            metadata = yaml.safe_load(parts[1])
            print('Name:', metadata.get('name'))
            print('Description:', metadata.get('description'))
            print('Metadata:', metadata.get('metadata'))
"
```

## 技术细节

### 解析逻辑

Registry 使用以下优先级解析技能元数据：

1. 查找 `SKILL.md` 文件
2. 解析 YAML 前置内容
3. 验证必需字段（name, description）
4. 验证 name 格式（小写、数字、连字符，无连续连字符）
5. 验证 description 长度（1-1024字符）
6. 如果失败，回退到 `package.json`（向后兼容）

### Name 格式验证

正则表达式模式：`^[a-z0-9]+(-[a-z0-9]+)*$`

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

## 参考

- [Agent Skills Specification](https://agentskills.io/specification)
- 示例技能: `docs/example-skill/SKILL.md`
