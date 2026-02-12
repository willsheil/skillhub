#!/bin/bash

# Claude Code Skill 一键安装脚本
# 支持 Linux 和 macOS

# 技能信息（由服务器动态替换）
SKILL_NAME="auditing-python-security-1.0.2"
SKILL_VERSION="1.0.2"
SKILL_DIR="auditing-python-security-1.0.2"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 打印带颜色的消息
print_success() { echo -e "${GREEN}[OK]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERR]${NC} $1"; }
print_info() { echo -e "${CYAN}$1${NC}"; }

# 显示标题
echo ""
print_info "========================================"
print_info "  Claude Code Skill 一键安装程序"
print_info "========================================"
echo ""
echo "技能名称: $SKILL_NAME"
echo "版本: $SKILL_VERSION"
echo ""

# ====================
# 步骤1: 检测 CLAUDE_SKILLS_PATH
# ====================
if [ -n "$CLAUDE_SKILLS_PATH" ]; then
    if [ -d "$CLAUDE_SKILLS_PATH" ]; then
        SKILLS_DIR="$CLAUDE_SKILLS_PATH"
        print_success "从环境变量 CLAUDE_SKILLS_PATH 检测到 Skills 目录"
        echo "    $SKILLS_DIR"
        goto_verify_and_install=true
    else
        print_warning "环境变量 CLAUDE_SKILLS_PATH 指向的路径不存在:"
        echo "    $CLAUDE_SKILLS_PATH"
        goto_verify_and_install=false
    fi
else
    goto_verify_and_install=false
fi

# ====================
# 步骤2: 检测默认路径
# ====================
if [ "$goto_verify_and_install" = false ]; then
    DEFAULT_PATH="$HOME/.claude/skills"
    if [ -d "$DEFAULT_PATH" ]; then
        SKILLS_DIR="$DEFAULT_PATH"
        print_success "从默认位置检测到 Skills 目录"
        echo "    $SKILLS_DIR"
        goto_verify_and_install=true
    fi
fi

# ====================
# 步骤3: 交互式输入
# ====================
if [ "$goto_verify_and_install" = false ]; then
    echo ""
    print_warning "未自动检测到 Claude Code Skills 目录"
    echo ""
    echo "常见位置:"
    echo "  - macOS/Linux: ~/.claude/skills/"
    echo "  - 自定义: 请指定您的 Claude Code 配置目录下的 skills 文件夹"
    echo ""

    while true; do
        read -rp "请输入 Skills 目录完整路径: " SKILLS_DIR

        # 展开 ~ 为实际路径
        SKILLS_DIR="${SKILLS_DIR/#\~/$HOME}"

        # 去除首尾空格
        SKILLS_DIR="$(echo "$SKILLS_DIR" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

        # 检查路径是否为空
        if [ -z "$SKILLS_DIR" ]; then
            print_error "路径不能为空"
            continue
        fi

        # 检查路径是否存在
        if [ ! -d "$SKILLS_DIR" ]; then
            print_warning "路径不存在: $SKILLS_DIR"
            read -rp "是否创建此目录? (Y/N) " create_choice
            if [[ $create_choice =~ ^[Yy]$ ]]; then
                if mkdir -p "$SKILLS_DIR"; then
                    print_success "已创建目录: $SKILLS_DIR"
                    break
                else
                    print_error "创建目录失败，请检查权限"
                    continue
                fi
            else
                continue
            fi
        fi

        # 验证目录结构
        parent_parent="$(dirname "$(dirname "$SKILLS_DIR")")"
        if [ ! -d "$parent_parent" ]; then
            print_warning "该路径可能不是标准的 Skills 目录"
            read -rp "是否继续使用此路径? (Y/N) " continue_choice
            if [[ ! $continue_choice =~ ^[Yy]$ ]]; then
                continue
            fi
        fi

        break
    done
fi

# ====================
# 验证并安装
# ====================
echo ""
print_info "目标安装路径: $SKILLS_DIR"
echo ""

# 确保目标路径存在
if [ ! -d "$SKILLS_DIR" ]; then
    print_error "目标路径不存在: $SKILLS_DIR"
    exit 1
fi

# 检查目标是否已存在
TARGET_PATH="$SKILLS_DIR/$SKILL_DIR"
if [ -d "$TARGET_PATH" ]; then
    echo ""
    print_warning "检测到同名技能已存在: $SKILL_DIR"
    echo ""
    echo "请选择操作:"
    echo "  [1] 覆盖安装 (删除旧版本)"
    echo "  [2] 跳过安装 (保留旧版本)"
    echo "  [3] 备份并安装 (旧版本重命名为 .backup)"
    echo ""

    while true; do
        read -rp "请选择 (1/2/3): " choice
        case $choice in
            1)
                # 覆盖
                if rm -rf "$TARGET_PATH"; then
                    print_success "已删除旧版本"
                    break
                else
                    print_error "删除旧版本失败，请检查权限"
                    exit 1
                fi
                ;;
            2)
                # 跳过
                print_warning "已跳过安装"
                echo ""
                print_info "========================================"
                print_info "  安装已跳过"
                print_info "========================================"
                echo ""
                echo "现有技能保持不变"
                echo ""
                exit 0
                ;;
            3)
                # 备份
                BACKUP_NAME="${SKILL_DIR}.backup.$(date +%Y%m%d-%H%M%S)"
                if mv "$TARGET_PATH" "$SKILLS_DIR/$BACKUP_NAME"; then
                    print_success "已备份旧版本为: $BACKUP_NAME"
                    break
                else
                    print_error "备份失败，请检查权限"
                    exit 1
                fi
                ;;
            *)
                print_error "无效选择，请输入 1、2 或 3"
                ;;
        esac
    done
fi

# ====================
# 执行安装
# ====================
echo ""
print_info "正在安装..."

# 查找实际的技能目录
# 技能目录可能是脚本所在目录的子目录，或者脚本本身就在技能目录中
if [ -d "$SCRIPT_DIR/$SKILL_DIR" ]; then
    # 技能目录在当前目录下
    SOURCE_DIR="$SCRIPT_DIR/$SKILL_DIR"
elif [ -f "$SCRIPT_DIR/package.json" ]; then
    # 脚本在技能目录中
    SOURCE_DIR="$SCRIPT_DIR"
else
    # 查找包含 package.json 的目录
    SOURCE_DIR=""
    for dir in "$SCRIPT_DIR"/*/; do
        if [ -f "$dir/package.json" ]; then
            SOURCE_DIR="$dir"
            break
        fi
    done
fi

if [ -z "$SOURCE_DIR" ] || [ ! -d "$SOURCE_DIR" ]; then
    print_error "找不到技能目录或 package.json"
    print_info "脚本应在技能包根目录或与技能目录同级"
    exit 1
fi

# 复制到目标位置
if [ "$SOURCE_DIR" = "$SCRIPT_DIR" ]; then
    # 需要创建目标目录并复制
    mkdir -p "$TARGET_PATH"
    cp -R "$SOURCE_DIR"/* "$TARGET_PATH/" 2>/dev/null || true
    # 排除安装脚本
    rm -f "$TARGET_PATH/install.sh" "$TARGET_PATH/install.bat" "$TARGET_PATH/README.txt" 2>/dev/null || true
else
    # 直接复制技能目录
    cp -R "$SOURCE_DIR" "$TARGET_PATH"
fi

# 验证安装
if [ -f "$TARGET_PATH/package.json" ]; then
    print_success "技能安装成功!"
    echo "    位置: $TARGET_PATH"
else
    print_error "安装失败，未找到 package.json"
    exit 1
fi

# ====================
# 成功退出
# ====================
echo ""
print_info "========================================"
print_info "  安装完成!"
print_info "========================================"
echo ""
print_success "技能 '$SKILL_NAME' 已成功安装"
echo ""
echo "请执行以下操作以使用新技能:"
echo "  1. 重启 Claude Code"
echo "  2. 或在 Claude Code 中刷新 Skills"
echo ""
echo "安装路径: $TARGET_PATH"
echo ""

# 可选：设置环境变量提示
if [ -z "$CLAUDE_SKILLS_PATH" ]; then
    echo "提示: 可以设置环境变量以避免下次手动输入路径"
    echo "    export CLAUDE_SKILLS_PATH=\"$SKILLS_DIR\""
    echo ""
fi

read -rp "按 Enter 键退出..."
exit 0
