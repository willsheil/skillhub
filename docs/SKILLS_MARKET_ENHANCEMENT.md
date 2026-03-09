# 技能市场功能增强文档

## 概述

本次更新为 SkillHub 技能市场添加了 5 个核心功能增强，提升用户体验和技能管理能力。

---

## 一、技能搜索增强（高级版）

### 1.1 功能说明

- **全文搜索**：支持技能名称、描述、标签、作者的全文搜索
- **搜索建议**：输入时自动显示匹配的技能名称建议
- **搜索历史**：记录用户搜索历史，方便快速访问
- **结果高亮**：搜索结果中高亮显示匹配关键词

### 1.2 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/search` | GET | 高级搜索 |
| `/api/search/suggestions` | GET | 获取搜索建议 |
| `/api/search/history` | GET | 获取搜索历史 |
| `/api/search/history` | DELETE | 清空搜索历史 |

### 1.3 使用示例

```bash
# 搜索技能
curl "http://localhost:8000/api/search?q=git&category=devops"

# 获取搜索建议
curl "http://localhost:8000/api/search/suggestions?q=gi"

# 获取搜索历史（需登录）
curl -b "session=xxx" "http://localhost:8000/api/search/history"
```

### 1.4 数据库表

```sql
-- 搜索历史表
CREATE TABLE search_history (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    query VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_created (user_id, created_at DESC)
);
```

---

## 二、技能评分系统

### 2.1 功能说明

- **1-5 星评分**：用户可对技能进行 1-5 星评分
- **简短评论**：支持发表 500 字以内的评论
- **评分统计**：显示平均分、评分分布、评论数

### 2.2 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/skills/{id}/rating` | POST | 提交评分 |
| `/api/skills/{id}/rating` | GET | 获取评分统计 |
| `/api/skills/{id}/comments` | GET | 获取评论列表 |
| `/api/skills/{id}/comments` | POST | 发表评论 |
| `/api/skills/{id}/comments/{comment_id}` | DELETE | 删除评论 |

### 2.3 使用示例

```bash
# 提交评分
curl -X POST -H "Content-Type: application/json" \
  -d '{"rating": 5}' \
  -b "session=xxx" \
  "http://localhost:8000/api/skills/1/rating"

# 发表评论
curl -X POST -H "Content-Type: application/json" \
  -d '{"content": "非常好用的技能！"}' \
  -b "session=xxx" \
  "http://localhost:8000/api/skills/1/comments"

# 获取评论列表
curl "http://localhost:8000/api/skills/1/comments?page=1&per_page=20"
```

### 2.4 数据库表

```sql
-- 评分表
CREATE TABLE skill_ratings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    skill_id INT NOT NULL,
    user_id INT NOT NULL,
    rating TINYINT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uk_skill_user (skill_id, user_id)
);

-- 评论表
CREATE TABLE skill_comments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    skill_id INT NOT NULL,
    user_id INT NOT NULL,
    content VARCHAR(500) NOT NULL,
    rating_id INT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted TINYINT(1) DEFAULT 0,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (rating_id) REFERENCES skill_ratings(id) ON DELETE SET NULL
);
```

---

## 三、技能详情页增强

### 3.1 功能说明

- **SKILL.md 预览**：渲染 Markdown 格式的技能说明
- **使用示例**：展示技能使用示例代码
- **截图预览**：显示技能截图（如有）
- **相关技能推荐**：基于分类和标签推荐相关技能

### 3.2 前端组件

详情页包含以下新增组件：

1. **RatingComponent** - 评分组件（`/static/js/rating.js`）
2. **CommentComponent** - 评论组件（`/static/js/rating.js`）
3. **相关技能推荐** - 自动加载相关技能

### 3.3 skills 表新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `rating_average` | DECIMAL(2,1) | 平均评分 |
| `rating_count` | INT | 评分数量 |
| `comment_count` | INT | 评论数量 |
| `view_count` | INT | 浏览次数 |
| `screenshots` | TEXT | 截图 URL 列表（JSON） |
| `usage_example` | TEXT | 使用示例 |

---

## 四、安装命令生成

### 4.1 功能说明

在技能详情页自动生成一键安装命令，用户可复制使用：

```bash
# Claude Code 插件安装
/plugin install skill-name@marketplace

# npx 安装
npx skills add owner/skill-name
```

### 4.2 前端实现

在 `skill_detail.html` 中，安装命令自动生成并支持一键复制：

```html
<div class="install-command">
    <code>/plugin install {{skill_name}}@{{marketplace_url}}</code>
    <button onclick="copyToClipboard()">复制</button>
</div>
```

---

## 五、技能分类体系

### 5.1 功能说明

- **固定分类**：6 个预定义分类
- **分类筛选**：按分类过滤技能列表
- **分类统计**：显示各分类下的技能数量

### 5.2 预定义分类

| 分类 | Slug | 图标 |
|------|------|------|
| 前端开发 | `frontend` | `code` |
| 后端开发 | `backend` | `server` |
| DevOps | `devops` | `git-branch` |
| 安全 | `security` | `shield` |
| 数据工程 | `data` | `database` |
| 通用工具 | `general` | `tool` |

### 5.3 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/categories` | GET | 获取所有分类 |
| `/api/categories/{slug}/skills` | GET | 获取分类下的技能列表 |

### 5.4 使用示例

```bash
# 获取所有分类
curl "http://localhost:8000/api/categories"

# 获取 DevOps 分类下的技能
curl "http://localhost:8000/api/categories/devops/skills?page=1&per_page=20"
```

### 5.5 数据库表

```sql
-- 分类表
CREATE TABLE categories (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL UNIQUE,
    slug VARCHAR(50) NOT NULL UNIQUE,
    icon VARCHAR(50),
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_slug (slug),
    INDEX idx_sort (sort_order)
);

-- skills 表新增分类字段
ALTER TABLE skills ADD COLUMN category_id INT DEFAULT NULL;
```

---

## 前端文件结构

```
static/js/
├── search.js      # 搜索建议、搜索历史组件
├── rating.js      # 评分、评论组件
└── skill-management.js  # 现有技能管理

templates/
├── index.html     # 首页（搜索增强、分类筛选）
└── skill_detail.html  # 详情页（评分、评论、安装命令、相关推荐）
```

---

## 数据库迁移

所有迁移在 `init_db()` 中自动执行，无需手动操作。

新增迁移函数：
- `migrate_add_rating_comment_system()` - 评分评论系统
- `migrate_add_search_features()` - 搜索功能
- `migrate_add_category_system()` - 分类系统

---

## 测试

```bash
# 运行 API 测试
pytest tests/test_api_routes.py tests/test_api_services.py -v

# 运行数据库测试
pytest tests/test_api_database.py -v
```

---

## 更新日志

### v1.1.0 (2026-03-06)

**新增功能：**
- 技能搜索增强（高级版）
- 技能评分系统（评分+评论）
- 技能详情页增强（完整版）
- 安装命令生成
- 技能分类体系

**数据库变更：**
- 新增 `skill_ratings` 表
- 新增 `skill_comments` 表
- 新增 `search_history` 表
- 新增 `categories` 表
- `skills` 表新增字段：`rating_average`, `rating_count`, `comment_count`, `view_count`, `screenshots`, `usage_example`, `category_id`
