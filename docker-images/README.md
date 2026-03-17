# Docker 离线部署指南

## 1. 构建镜像（在有网络的环境）

### Windows WSL Ubuntu-24.04
```bash
# 进入项目目录
cd /mnt/d/work/20260312/skillhub

# 运行构建脚本
chmod +x build-docker.sh
./build-docker.sh
```

脚本会自动：
- 安装 Docker（如果未安装）
- 构建 SkillHub 镜像
- 拉取 Gitea 和 MySQL 镜像
- 导出为 `.tar.gz` 文件

## 2. 导出的镜像文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `skillhub-app.tar.gz` | ~200MB | SkillHub 主应用 |
| `gitea.tar.gz` | ~150MB | Gitea Git 服务 |
| `mysql.tar.gz` | ~500MB | MySQL 8.0 数据库 |

## 3. 在目标环境部署

### 3.1 导入镜像
```bash
# 创建镜像目录
mkdir -p docker-images
cd docker-images

# 导入镜像
docker load < skillhub-app.tar.gz
docker load < gitea.tar.gz
docker load < mysql.tar.gz

# 验证镜像
docker images
```

### 3.2 配置环境变量
```bash
# 复制环境变量模板
cp .env.docker.example .env

# 编辑配置（修改密码等）
vi .env
```

### 3.3 启动服务
```bash
# 启动所有服务
docker compose up -d

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f
```

### 3.4 访问服务
- **SkillHub**: http://localhost:28000
- **Gitea**: http://localhost:3000
- **MySQL**: localhost:3306

## 4. 初始配置

### 4.1 Gitea 初始化
首次访问 http://localhost:3000 需要完成 Gitea 初始化配置：
1. 数据库选择 MySQL
2. 主机: mysql:3306
3. 用户名: root
4. 密码: root
5. 数据库名: gitea

### 4.2 创建 Gitea Token
1. 登录 Gitea
2. 进入 设置 → 应用 → 管理访问令牌
3. 生成新令牌
4. 更新 `.env` 中的 `GITEA_TOKEN`

### 4.3 SkillHub 登录
- 管理员: `admin001` / 密码: `admin_key_001`

## 5. 常用命令

```bash
# 停止服务
docker compose down

# 重启服务
docker compose restart

# 查看日志
docker compose logs -f skillhub

# 备份数据
docker compose exec mysql mysqldump -u root -proot skills123 > backup.sql

# 更新应用
docker compose build skillhub
docker compose up -d skillhub
```

## 6. 目录结构

```
skillhub/
├── docker-compose.yml      # Docker 编排文件
├── Dockerfile              # 应用镜像构建
├── .env.docker.example     # 环境变量模板
├── build-docker.sh         # 构建脚本
├── docker-images/          # 导出的镜像文件
│   ├── skillhub-app.tar.gz
│   ├── gitea.tar.gz
│   └── mysql.tar.gz
├── init/
│   └── 01-init.sql         # 数据库初始化
├── plugins/                # 技能存储
├── data/                   # 应用数据
└── logs/                   # 日志文件
```
