# Skills4sec 样式整合设计方案

## 项目概述

将 skills4sec 前端项目的样式系统整合到 ss (Skill Registry) 项目中，实现统一的现代 UI 风格。

## 需求确认

| 需求项 | 选择 |
|--------|------|
| 整合范围 | 全部页面 |
| 整合方式 | 参考样式重写 |
| 首页功能 | 完整复制 |
| 页面路由 | 保持后端路由 (FastAPI) |
| 数据加载 | 后端 API |
| 认证方式 | 重写登录页 |
| 配色方案 | 保持紫色主题 (#6366f1) |

## 设计方案

### 架构设计

```
ss-project/
├── static/
│   ├── css/
│   │   ├── skills4sec.css    # skills4sec 原始样式
│   │   └── custom.css        # 自定义覆盖样式
│   └── js/
│       ├── skills4sec.js     # 通用 JS 组件
│       └── pages/            # 页面特定 JS
│           ├── index.js
│           ├── detail.js
│           ├── login.js
│           └── admin.js
└── templates/
    ├── index.html             # 首页 - 完全重写
    ├── login.html             # 登录页 - 完全重写
    ├── skill_detail.html      # 详情页 - 完全重写
    ├── my_skills.html         # 用户中心 - 完全重写
    ├── admin.html             # 管理后台 - 完全重写
    └── ...
```

### 样式系统

使用 skills4sec 的 CSS 设计系统：
- CSS Variables 定义主题色
- 组件化 CSS 类
- 响应式设计 (移动端适配)

### 页面规划

1. **首页** (`/`)
   - Hero 区域：标题 + 副标题 + 搜索框
   - 分类筛选：pill 样式的分类按钮
   - 技能卡片网格：3-4 列响应式布局
   - 特性介绍：3 列特性卡片

2. **登录页** (`/login`)
   - 居中登录卡片
   - 紫色渐变背景
   - 表单验证

3. **技能详情页** (`/skill/{name}`)
   - 面包屑导航
   - 技能头部信息
   - 安装命令框
   - Markdown 内容渲染

4. **用户中心** (`/my-skills`)
   - 用户信息卡片
   - 我的技能列表
   - 上传按钮

5. **管理后台** (`/admin`)
   - 侧边栏导航
   - 待审核技能列表
   - 用户管理
   - API 密钥管理

### API 对接

保持现有 FastAPI 路由不变：
- `GET /api/skills` - 获取技能列表
- `GET /api/skills/{name}` - 获取技能详情
- `POST /api/login` - 用户登录
- `GET /marketplace.json` - 市场数据

## 实现顺序

1. 复制并整理 CSS 样式文件
2. 创建通用 JS 组件
3. 重写首页 (index.html)
4. 重写登录页 (login.html)
5. 重写详情页 (skill_detail.html)
6. 重写用户中心 (my_skills.html)
7. 重写管理后台 (admin.html)

## 预期效果

- 统一的紫色主题现代 UI
- 响应式布局支持移动端
- 平滑的过渡动画
- 保持所有现有功能
