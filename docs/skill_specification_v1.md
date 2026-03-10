# Skills 技术规范 v1.0

> 本文档定义了  Skills 的技术标准和开发规范

## 1. 概述

### 1.1 什么是 Skill111

Skill 是 Claude Code 的能力扩展插件，通过声明式的配置文件和提示词，为 Claude Code 提供特定领域的专业能力。

### 1.2 核心特性

- **声明式定义**: 使用 YAML 格式的 SKILL.md 文件定义技能
- **工具绑定**: 可以绑定特定的工具集，限制 AI 的操作范围
- **提示词工程**: 内置专业的提示词模板，引导 AI 高质量输出
- **版本管理**: 支持语义化版本号，便于管理和更新

---

## 2. 目录结构

### 2.1 标准结构

```
skill-name/
├── SKILL.md              # 必需：技能定义文件
├── README.md             # 可选：详细说明文档
├── examples/             # 可选：示例文件
│   ├── example1.md
│   └── example2.md
├── templates/            # 可选：模板文件
│   └── template.tmpl
└── rules/                # 可选：规则文件
    └── rule1.md
```

### 2.2 文件说明

| 文件/目录 | 必需 | 说明 |
|-----------|------|------|
| `SKILL.md` | ✅ | 技能定义文件，包含元数据和提示词 |
| `README.md` | ❌ | 详细的使用说明和文档 |
| `examples/` | ❌ | 示例文件目录 |
| `templates/` | ❌ | 模板文件目录 |
| `rules/` | ❌ | 规则和约束文件目录 |

---

## 3. SKILL.md 规范

### 3.1 基本格式

SKILL.md 使用 YAML Frontmatter 格式：

```markdown
---
name: skill-name
description: 技能描述
metadata:
  version: 1.0.0
  author: w00000001
  tags: tag1, tag2, tag3
  category: category-name
license: MIT
compatibility: Claude Code 1.0+
allowed-tools: bash, grep, read, write
---

# 技能提示词内容

这里是技能的具体提示词内容...
```

### 3.2 元数据字段

#### 必需字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `name` | string | 技能名称，仅限小写字母、数字、连字符 | `python-analyzer` |
| `description` | string | 技能描述，不超过 200 字符 | `分析 Python 代码质量` |
| `metadata.version` | string | 语义化版本号 | `1.0.0` |
| `metadata.author` | string | 作者工号（字母+8位数字） | `w00000001` |

#### 可选字段

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `metadata.tags` | string | 逗号分隔的标签列表 | 空 |
| `metadata.category` | string | 分类名称 | `general` |
| `license` | string | 许可证类型 | `MIT` |
| `compatibility` | string | 兼容性说明 | `Claude Code 1.0+` |
| `allowed-tools` | string | 允许使用的工具列表 | 全部工具 |

### 3.3 命名规范

#### 技能名称规范

- ✅ 允许：小写字母、数字、连字符
- ❌ 禁止：空格、特殊字符、大写字母、中文
- 📏 长度：3-50 个字符

```
# 正确示例
python-analyzer
code-review-2024
api-doc-generator

# 错误示例
Python Analyzer    # 包含空格
code_review        # 使用下划线
API-Generator      # 包含大写字母
代码分析器          # 包含中文
```

#### 版本号规范

采用语义化版本号（SemVer）：`MAJOR.MINOR.PATCH`

- **MAJOR**: 不兼容的 API 变更
- **MINOR**: 向后兼容的功能新增
- **PATCH**: 向后兼容的问题修复

---

## 4. 提示词编写规范

### 4.1 结构建议

```markdown
# 技能标题

## 触发条件
描述何时应该使用此技能

## 使用步骤
1. 第一步
2. 第二步
3. 第三步

## 输出格式
描述期望的输出格式

## 注意事项
- 注意点1
- 注意点2

## 示例
提供具体的使用示例
```

### 4.2 最佳实践

1. **明确性**: 提示词应该清晰明确，避免歧义
2. **结构化**: 使用标题、列表等结构化内容
3. **示例丰富**: 提供足够的示例帮助理解
4. **约束清晰**: 明确说明边界和限制条件

### 4.3 工具限制

通过 `allowed-tools` 限制 AI 可使用的工具：

```yaml
allowed-tools: bash, grep, read, write, edit
```

常用工具列表：
- `bash` - 执行 shell 命令
- `read` - 读取文件
- `write` - 写入文件
- `edit` - 编辑文件
- `grep` - 搜索文件内容
- `glob` - 搜索文件名

---

## 5. 打包规范

### 5.1 ZIP 包要求

- 必须包含 `SKILL.md` 文件
- 文件大小不超过 50MB
- 使用 UTF-8 编码
- 不包含敏感信息（密钥、密码等）

### 5.2 命名约定

```
skill-name-v1.0.0.zip
```

格式：`{skill-name}-v{version}.zip`

### 5.3 目录层级

ZIP 包解压后应直接包含技能文件，不要有多层嵌套：

```
# 正确结构
skill-name-v1.0.0.zip
└── SKILL.md
└── README.md

# 错误结构（多层嵌套）
skill-name-v1.0.0.zip
└── skill-name/
    └── SKILL.md
```

---

## 6. 分类体系

### 6.1 预定义分类

| 分类 | 标识 | 说明 |
|------|------|------|
| 通用工具 | `general` | 通用辅助工具 |
| 代码分析 | `code-analysis` | 代码质量、静态分析 |
| 文档生成 | `documentation` | 文档、注释生成 |
| 测试辅助 | `testing` | 测试用例生成、覆盖率 |
| API 开发 | `api` | API 设计、文档、测试 |
| DevOps | `devops` | 部署、运维、监控 |
| 数据处理 | `data` | 数据分析、转换、ETL |
| 安全审计 | `security` | 代码审计、漏洞检测 |

### 6.2 标签建议

推荐使用以下标签类别：
- 语言标签：`python`, `javascript`, `java`, `go`
- 框架标签：`django`, `react`, `spring`
- 功能标签：`review`, `refactor`, `test`, `document`

---

## 7. 示例模板

### 7.1 完整示例

```markdown
---
name: code-reviewer
description: 自动化代码审查助手，提供代码质量建议和最佳实践检查
metadata:
  version: 1.0.0
  author: w00000001
  tags: review, quality, best-practices
  category: code-analysis
license: MIT
compatibility: Claude Code 1.0+
allowed-tools: read, grep
---

# Code Reviewer

你是一位专业的代码审查专家，负责对代码进行全面的质量审查。

## 触发条件

当用户请求代码审查或使用 `/review` 命令时触发。

## 审查维度

### 1. 代码质量
- 代码可读性
- 命名规范
- 注释完整性

### 2. 潜在问题
- 空指针风险
- 资源泄漏
- 异常处理

### 3. 性能考量
- 算法复杂度
- 内存使用
- 潜在瓶颈

### 4. 安全检查
- 输入验证
- SQL 注入
- XSS 风险

## 输出格式

### 审查摘要
- 文件数量：X
- 问题等级：严重/警告/建议
- 总体评分：X/10

### 问题列表
| 行号 | 等级 | 问题描述 | 修改建议 |
|------|------|----------|----------|
| 42 | 警告 | ... | ... |

## 注意事项

- 保持客观、专业的态度
- 提供可操作的建议
- 优先关注安全和性能问题
```

---

## 8. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0.0 | 2024-01-01 | 初始版本发布 |

---

## 9. 联系方式

如有问题或建议，请联系技能管理团队。
