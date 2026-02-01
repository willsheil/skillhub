# Claude Code Skill Registry

内网私有 Skill Registry，用于托管和分发 Claude Code 技能插件。

## 快速开始

### 方式 1: Docker Compose (推荐)

```bash
# 1. 启动服务
docker-compose up -d

# 2. 访问 http://localhost:8000
```

### 方式 2: 直接运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
python main.py

# 3. 访问 http://localhost:8000
```

## 导入已有的 Skill 包

将之前打包的 `skills-marketplace.zip` 导入 Registry：

```bash
# 导入到指定组织和集合
python import-skills.py marketplace.zip -o company-a -c security-tools

# 导入到默认组织和集合
python import-skills.py marketplace.zip
```

## 添加新插件

### 方法 1: 通过 Web 管理界面上传（推荐）

访问 `http://localhost:8000/admin/upload`，支持两种上传方式：

#### 上传 Skill 集（多个技能）

适用于包含多个技能的 ZIP 文件，系统会自动提取其中的每个技能。

- 填写 `organization`（组织）和 `collection`（集合）
- **留空** `name` 和 `version`
- 选择 ZIP 文件上传

示例 ZIP 结构：
```
skills-marketplace.zip
└── skills/
    └── plugins/
        ├── skill-a/
        │   └── .claude-plugin/plugin.json
        ├── skill-b/
        │   └── .claude-plugin/plugin.json
        └── skill-c/
            └── .claude-plugin/plugin.json
```

#### 上传单个 Skill

- 填写 `organization`（组织）和 `collection`（集合）
- **填写** `name`（技能名称）和 `version`（版本）
- 选择 ZIP 文件上传

### 方法 2: HTTP API 上传

**上传 Skill 集（自动提取）：**
```bash
curl -X POST http://localhost:8000/admin/upload \
  -F "organization=my-org" \
  -F "collection=my-collection" \
  -F "file=@skills-marketplace.zip"
```

**上传单个 Skill：**
```bash
curl -X POST http://localhost:8000/admin/upload \
  -F "organization=my-org" \
  -F "collection=my-collection" \
  -F "name=my-skill" \
  -F "version=1.0.0" \
  -F "file=@my-skill.zip"
```

### 方法 3: 直接复制文件

```bash
# 创建插件目录（三层结构）
mkdir -p plugins/my-org/my-collection/my-skill

# 复制 zip 包
cp my-skill-1.0.0.zip plugins/my-org/my-collection/my-skill/

# 无需重启，Registry 会自动检测
```

## 目录结构

```
registry/
├── main.py                 # FastAPI 应用
├── requirements.txt        # Python 依赖
├── Dockerfile             # Docker 构建
├── docker-compose.yml     # Docker Compose 配置
├── import-skills.py       # 导入工具
├── templates/
│   └── index.html         # 前端页面
├── static/                # 静态文件
└── plugins/               # 插件存储目录
    ├── default/              # 组织
    │   ├── default/          # Skill 集
    │   │   ├── auditing-python-security/
    │   │   │   ├── 1.0.0.zip
    │   │   │   └── 1.1.0.zip
    │   │   └── static-analysis/
    │   │       └── 1.0.0.zip
    │   └── security-suite/   # 另一个 Skill 集
    │       ├── semgrep-rule-creator/
    │       └── yara-authoring/
    └── company-a/            # 其他组织
        └── their-collection/
            └── their-skill/
                └── 1.0.0.zip
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 前端展示页面 |
| `/marketplace.json` | GET | Claude Code 市场索引 |
| `/plugins/{org}/{collection}/{name}/{version}.zip` | GET | 下载插件 |
| `/api/skills` | GET | API 获取技能列表 |
| `/api/collections` | GET | 列出所有 Skill 集 |
| `/api/collections/{org}/{collection}` | GET | 获取集合下的所有 skills |
| `/admin/upload` | POST | 上传新插件（支持 `organization` 和 `collection` 参数，默认：default） |
| `/admin/plugins/{org}/{collection}/{name}/{version}` | DELETE | 删除插件版本 |

## 安装 Skill

### 安装单个 Skill
```bash
/plugin install my-skill
```

### 安装整个 Skill 集
在 Web 界面中：
1. 找到目标 Skill 集
2. 点击"查看集合"按钮
3. 选择要安装的技能（或全选）
4. 点击"批量安装"

或通过 API 获取集合下的所有 skills：
```bash
curl http://localhost:8000/api/collections/company-a/security-tools
```

## 在 Claude Code 中使用

```bash
# 1. 添加私有 Registry
/plugins marketplace add http://192.168.1.100:8000/marketplace.json

# 2. 查看可用插件
/plugin menu

# 3. 安装插件（支持完整路径）
/plugin install ICSL/Base/auditing-python-security
```

## 防火墙配置

建议通过防火墙限制访问：

```bash
# 只允许特定 IP 段访问
iptables -A INPUT -p tcp --dport 8000 -s 192.168.0.0/16 -j ACCEPT
iptables -A INPUT -p tcp --dport 8000 -j DROP
```

## 备份

定期备份 `plugins/` 目录即可：

```bash
# 备份
tar czf registry-backup-$(date +%Y%m%d).tar.gz plugins/

# 恢复
tar xzf registry-backup-20240201.tar.gz
```

## 迁移现有插件

如果已有旧结构的插件（无组织层级），使用迁移脚本：

```bash
python migrate-to-org.py
```

此脚本会将 `plugins/{skill}/` 移动到 `plugins/default/{skill}/`。

## 配置 Registry

Registry 使用 `.env` 文件进行配置。复制 `.env.example` 为 `.env` 并修改：

```bash
cp .env.example .env
```

### 配置项说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `ADMIN_USERNAME` | 管理员用户名 | `admin` |
| `ADMIN_PASSWORD` | 管理员密码 | `admin123` |
| `SECRET_KEY` | Session 密钥（生产环境必须修改） | `your-secret-key-change-this` |
| `PLUGINS_DIR` | 插件存储目录 | `./plugins` |

### 示例配置

```bash
# .env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password
SECRET_KEY=your-random-secret-key-here
PLUGINS_DIR=./plugins
```

**安全提示**：生产环境请务必修改默认密码和密钥！

## 安装 Skill

### 安装整个 Skill Set（技能集）

**方式 1：通过 Web 界面**
1. 访问 Registry 首页 `http://localhost:8000`
2. 找到目标 Skill 集（如 `ICSL / Base`）
3. 点击"查看集合"按钮
4. 在弹窗中选择要安装的技能（勾选复选框）
5. 点击"安装选中技能"按钮
6. 安装命令会自动复制到剪贴板，粘贴到 Claude Code 执行

**方式 2：通过 API 获取并安装**

```bash
# 获取集合下的所有 skills
curl http://localhost:8000/api/collections/ICSL/Base

# 安装集合中的所有 skills（手动逐个安装）
/plugin install ICSL/Base/ask-questions-if-underspecified
/plugin install ICSL/Base/audit-context-building
/plugin install ICSL/Base/auditing-python-security
```

### 指定安装某个 Skill

**方式 1：通过 Web 界面**
1. 在 Registry 首页找到目标 Skill
2. 点击该行右侧的"安装"按钮
3. 安装命令会自动复制到剪贴板
4. 粘贴到 Claude Code 执行

**方式 2：命令行安装**

安装语法：`/plugin install {organization}/{collection}/{skill-name}`

```bash
# 安装指定组织和集合下的某个 skill
/plugin install ICSL/Base/ask-questions-if-underspecified

# 安装默认组织和集合下的 skill
/plugin install my-skill
```

**从特定 Registry 安装：**
```bash
# 1. 添加 Registry
/plugins marketplace add http://localhost:8000/marketplace.json

# 2. 查看可用技能
/plugin menu

# 3. 安装指定技能（完整路径）
/plugin install ICSL/Base/auditing-python-security
```

## 管理员功能

### 通过 Web 界面上传

1. 访问 `http://localhost:8000/admin/login`
2. 使用 `.env` 中配置的账号密码登录
3. 选择上传类型：
   - **Skill 集**：包含多个技能的 ZIP 文件（自动提取）
   - **单个 Skill**：单个技能的 ZIP 文件（需填写名称和版本）
4. 填写组织和集合名称
5. 选择 ZIP 文件并上传

### 上传类型说明

| 上传类型 | 填写 Name/Version | 处理方式 |
|----------|-------------------|----------|
| Skill 集（多个技能） | 留空 | 自动提取 ZIP 中的每个技能 |
| 单个 Skill | 必填 | 使用填写的名称和版本 |

## 注意事项

1. **认证**: 管理后台使用用户名/密码认证，密码配置在 `.env` 文件中
2. **自动发现**: 上传 ZIP 后无需重启，页面会自动刷新
3. **版本管理**: 支持同一插件的多个版本，最新版会标记
4. **Skill 集**: 上传包含多个技能的 ZIP 时，系统会自动提取每个技能的元数据
