#!/bin/bash
# SkillHub Docker 离线镜像构建脚本
# 在 WSL Ubuntu-24.04 中运行

set -e

echo "=========================================="
echo "SkillHub Docker 离线镜像构建脚本"
echo "=========================================="

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "[1/5] 安装 Docker..."
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker $USER
    echo "Docker 安装完成！"
    echo "请运行: newgrp docker 或重新登录WSL"
    echo "然后重新运行此脚本"
    exit 0
fi

# 启动 Docker 服务
echo "[2/5] 启动 Docker 服务..."
sudo service docker start || true

# 进入项目目录
PROJECT_DIR="/mnt/d/work/20260312/skillhub"
cd "$PROJECT_DIR"

echo "[3/5] 构建 SkillHub 镜像..."
docker build -t skillhub-app:latest .

echo "[4/5] 拉取 Gitea 和 MySQL 镜像..."
docker pull gitea/gitea:latest
docker pull mysql:8.0

echo "[5/5] 导出镜像到文件..."
mkdir -p docker-images

echo "导出 skillhub-app..."
docker save skillhub-app:latest | gzip > docker-images/skillhub-app.tar.gz

echo "导出 gitea..."
docker save gitea/gitea:latest | gzip > docker-images/gitea.tar.gz

echo "导出 mysql..."
docker save mysql:8.0 | gzip > docker-images/mysql.tar.gz

echo ""
echo "=========================================="
echo "构建完成！镜像文件位于:"
echo "  ${PROJECT_DIR}/docker-images/"
echo ""
echo "文件列表:"
ls -lh docker-images/
echo ""
echo "=========================================="
echo "在其他环境导入镜像命令:"
echo "  docker load < skillhub-app.tar.gz"
echo "  docker load < gitea.tar.gz"
echo "  docker load < mysql.tar.gz"
echo ""
echo "然后运行:"
echo "  docker compose up -d"
echo "=========================================="
