# Skills4sec 样式整合实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 skills4sec 前端项目的现代 UI 样式系统完整整合到 ss 项目中，改造全部页面保持统一的紫色主题风格。

**Architecture:** 复制 skills4sec 的 CSS 样式系统到 ss 项目的 static 目录，重写所有 HTML 模板使用新样式，保持后端路由和数据加载方式不变。

**Tech Stack:** HTML, CSS (CSS Variables), JavaScript, FastAPI, Jinja2

---

## 实施顺序

### 任务 1: 准备样式文件

**Files:**
- Create: `static/css/skills4sec.css` - 从 skills4sec 项目复制
- Create: `static/css/custom.css` - 自定义覆盖样式
- Create: `static/js/skills4sec.js` - 通用 JS 组件

**Step 1: 复制 CSS 样式文件**

从 `G:\lol\skills4sec-main\skills4sec-main\docs\assets\style.css` 复制完整内容到 `static/css/skills4sec.css`

**Step 2: 创建自定义样式覆盖文件**

创建 `static/css/custom.css`，内容：
```css
/* 自定义覆盖样式 - 适配 ss 项目 */
:root {
  /* 保留紫色主题，添加项目特定变量 */
  --project-name: "Skill Registry";
}

/* 覆盖技能卡片的下载统计样式 */
.skill-stats {
  display: flex;
  gap: 1rem;
  font-size: 0.75rem;
  color: var(--muted-foreground);
}
```

**Step 3: 创建通用 JS 组件**

创建 `static/js/skills4sec.js`，包含：
- 移动端菜单切换
- 搜索框交互
- 卡片悬停效果
- Toast 通知
- 复制命令功能

**Step 4: 提交**

```bash
git add static/css/ static/js/
git commit -m "feat: 添加 skills4sec 样式系统基础文件"
```

---

### 任务 2: 重写首页 (index.html)

**Files:**
- Modify: `templates/index.html` - 完全重写

**Step 1: 备份现有 index.html**

先读取现有内容备份

**Step 2: 重写首页模板**

使用 skills4sec 样式重写首页，包含：
- 固定顶部导航 (参考 skills4sec nav 样式)
- Hero 区域：标题 + 副标题 + 搜索框
- 分类筛选 pill 按钮
- 技能卡片网格 (响应式 1-2-3 列)
- 特性介绍区域
- 页脚

关键代码结构：
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ registry_name }}</title>
  <link rel="stylesheet" href="/static/css/skills4sec.css">
  <link rel="stylesheet" href="/static/css/custom.css">
</head>
<body>
  <!-- 导航 -->
  <nav class="nav">
    <div class="max-w-7xl px-container">
      <div class="nav-inner">
        <a class="nav-logo" href="/">
          <svg>...</svg>
          <span>SkillHub</span>
        </a>
        <div class="nav-links">
          <a class="nav-link active" href="/">首页</a>
          <a class="nav-link" href="/browse">浏览技能</a>
          <a class="nav-link" href="/upload">提交技能</a>
        </div>
        <div class="nav-right">
          {% if session.get('user_id') %}
            <a href="/my-skills">我的技能</a>
            <a href="/admin">管理</a>
            <a href="/logout">退出</a>
          {% else %}
            <a href="/login">登录</a>
          {% endif %}
        </div>
      </div>
    </div>
  </nav>

  <!-- Hero 区域 -->
  <section class="hero">
    <div class="hero-gradient"></div>
    <div class="hero-content">
      <h1>发现 <span class="gradient-text">AI 技能</span></h1>
      <p>企业级 Claude Code 技能插件市场</p>
      <!-- 搜索框 -->
      <div class="search-box">
        <svg>...</svg>
        <input type="text" id="skill-search" placeholder="搜索技能...">
      </div>
      <!-- 分类筛选 -->
      <div class="category-pills">
        <button class="pill active" data-category="all">全部</button>
        <button class="pill" data-category="productivity">效率</button>
        <button class="pill" data-category="development">开发</button>
        <button class="pill" data-category="security">安全</button>
      </div>
    </div>
  </section>

  <!-- 技能列表 -->
  <section class="section">
    <div class="max-w-7xl px-container">
      <div class="section-header">
        <div>
          <h2>热门技能</h2>
          <p>发现最受欢迎的 AI 技能</p>
        </div>
      </div>
      <div class="skills-grid" id="skills-grid">
        <!-- 技能卡片由 JS 动态渲染或后端渲染 -->
      </div>
    </div>
  </section>

  <!-- 页脚 -->
  <footer class="footer">
    ...
  </footer>

  <script src="/static/js/skills4sec.js"></script>
</body>
</html>
```

**Step 3: 添加页面交互脚本**

在页面底部添加：
```html
<script>
// 搜索功能
document.getElementById('skill-search').addEventListener('input', debounce(searchSkills, 300));

// 分类筛选
document.querySelectorAll('.pill').forEach(pill => {
  pill.addEventListener('click', () => filterByCategory(pill.dataset.category));
});
</script>
```

**Step 4: 测试验证**

启动服务 `python main.py`，访问 http://localhost:28000/ 验证首页样式

**Step 5: 提交**

```bash
git add templates/index.html
git commit -m "feat: 重写首页使用 skills4sec 样式"
```

---

### 任务 3: 重写登录页 (login.html)

**Files:**
- Modify: `templates/login.html` - 完全重写

**Step 1: 重写登录页模板**

使用 skills4sec 样式重写登录页：
- 紫色渐变背景
- 居中登录卡片
- 表单验证
- 错误提示

**Step 2: 测试验证**

访问 http://localhost:28000/login 验证登录页样式

**Step 3: 提交**

```bash
git add templates/login.html
git commit -m "feat: 重写登录页使用 skills4sec 样式"
```

---

### 任务 4: 重写技能详情页 (skill_detail.html)

**Files:**
- Modify: `templates/skill_detail.html` - 完全重写

**Step 1: 重写详情页模板**

使用 skills4sec 样式重写详情页：
- 面包屑导航
- 技能头部信息卡片
- 安装命令框 (含复制功能)
- Markdown 内容渲染
- 相关技能推荐

**Step 2: 测试验证**

访问具体技能详情页验证样式

**Step 3: 提交**

```bash
git add templates/skill_detail.html
git commit -m "feat: 重写技能详情页使用 skills4sec 样式"
```

---

### 任务 5: 重写用户中心 (my_skills.html)

**Files:**
- Modify: `templates/my_skills.html` - 完全重写

**Step 1: 重写用户中心模板**

使用 skills4sec 样式重写：
- 用户信息卡片
- 我的技能列表 (表格/卡片)
- 上传新技能按钮
- 版本管理

**Step 2: 测试验证**

登录后访问 http://localhost:28000/my-skills 验证样式

**Step 3: 提交**

```bash
git add templates/my_skills.html
git commit -m "feat: 重写用户中心使用 skills4sec 样式"
```

---

### 任务 6: 重写管理后台 (admin.html)

**Files:**
- Modify: `templates/admin.html` - 完全重写
- Modify: `templates/admin_users.html`
- Modify: `templates/admin_api_keys.html`
- Modify: `templates/admin_upload.html`

**Step 1: 重写管理后台模板**

使用 skills4sec 样式重写：
- 侧边栏导航
- 待审核技能列表
- 用户管理表格
- API 密钥管理

**Step 2: 测试验证**

管理员登录后访问 http://localhost:28000/admin 验证样式

**Step 3: 提交**

```bash
git add templates/admin*.html
git commit -m "feat: 重写管理后台使用 skills4sec 样式"
```

---

### 任务 7: 完善其他页面

**Files:**
- Modify: `templates/upload.html` - 上传页
- Modify: `templates/stats.html` - 统计页

**Step 1: 重写上传页**

使用 skills4sec 样式重写上传页面

**Step 2: 重写统计页**

使用 skills4sec 样式重写统计页面

**Step 3: 测试验证**

访问各页面验证样式一致性

**Step 4: 提交**

```bash
git add templates/upload.html templates/stats.html
git commit -m "feat: 重写上传页和统计页使用 skills4sec 样式"
```

---

### 任务 8: 最终验证与调整

**Step 1: 全面测试**

测试所有页面：
- 首页 /
- 登录 /login
- 技能详情 /skill/{name}
- 用户中心 /my-skills
- 管理后台 /admin
- 上传页 /upload
- 统计页 /stats

**Step 2: 样式微调**

根据测试结果调整 custom.css 中的覆盖样式

**Step 3: 最终提交**

```bash
git add static/css/custom.css
git commit -m "feat: 完成 skills4sec 样式整合"
```

---

## 验证命令

```bash
# 启动服务
python main.py

# 验证各页面
# 1. 首页
curl -s http://localhost:28000/ | grep "skills4sec\|gradient-text"
# 2. 登录页
curl -s http://localhost:28000/login | grep "nav\|gradient"
# 3. 技能详情
curl -s http://localhost:28000/skill/test | grep "detail"
```

---

## 注意事项

1. 保持后端 API 路由不变
2. 保持 session 认证机制
3. 确保移动端响应式适配
4. 所有外部 CDN 资源需检查可访问性
5. 遵循 Jinja2 模板语法
