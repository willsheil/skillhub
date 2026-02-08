# 迁移到 SKILL.md 格式 - 设计文档

## 概述

将 Skill Registry 的元数据格式从 `package.json` 迁移到 `SKILL.md`（包含 YAML 前置内容）。

## 新的 Skill 文件夹结构

```
my-skill/
├── SKILL.md          # Required: instructions + metadata (YAML frontmatter + Markdown)
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation
└── assets/           # Optional: templates, resources
```

## SKILL.md 格式

每个 SKILL.md 必须包含 YAML 前置内容：

```yaml
---
name: skill-name
description: When to use this skill
author: w00545471
custom:
  category: security
  tags: [python, audit]
---

# Skill Instructions

Markdown content here...
```

### 必需字段

- `name`: 简短技能标识符（小写字母、数字、连字符）
- `description`: 技能描述，何时使用此技能
- `author`: 作者 ID（格式：1个字母 + 8位数字，如 w00545471）

### 可选字段

- `custom`: 自定义 JSON 对象，用于扩展功能

## 需要修改的组件

### 1. main.py 核心函数

#### `extract_metadata()` - 解析 SKILL.md
- 从 ZIP 中查找 `SKILL.md` 文件
- 解析 YAML 前置内容
- 返回标准化的元数据字典

#### `validate_skill_zip()` - 验证逻辑
- 检查 ZIP 中是否包含 `SKILL.md`
- 验证 YAML 必需字段（name, description, author）
- 验证 author 格式（字母 + 8位数字）

#### `save_skill_zip()` - 保存逻辑
- 从 SKILL.md 中提取 name 作为文件名
- 版本号从 YAML 中读取或默认为 "1.0.0"

### 2. 数据模型变更

旧格式 (package.json):
```json
{
  "name": "skill-name",
  "version": "1.0.0",
  "description": "Description",
  "author": {"name": "Author Name", "email": "email@example.com"}
}
```

新格式 (SKILL.md YAML):
```yaml
name: skill-name
description: Description
author: w00545471
custom:
  version: "1.0.0"
```

### 3. API 响应格式

保持 marketplace.json 格式不变，但内部从 SKILL.md 提取数据：

```json
{
  "name": "skill-name",
  "version": "1.0.0",
  "description": "Description",
  "author": {"id": "w00545471"}
}
```

### 4. 前端模板更新

- 更新插件卡片显示逻辑
- 支持新的 author 格式显示

## 实现步骤

1. **添加依赖**: PyYAML 用于解析 YAML
2. **创建 SKILL.md 解析器**: 提取 YAML 前置内容
3. **修改 extract_metadata()**: 从 package.json 改为 SKILL.md
4. **修改 validate_skill_zip()**: 验证 SKILL.md 存在性和必需字段
5. **修改 save_skill_zip()**: 使用 SKILL.md 中的 name 字段
6. **更新前端模板**: 显示新的元数据格式
7. **创建迁移脚本**: 将现有 package.json 转换为 SKILL.md
8. **测试验证**: 确保功能完整

## 回滚策略

- 保持现有插件 ZIP 不变
- 新格式仅影响新上传的插件
- 可选：创建转换脚本更新旧插件
