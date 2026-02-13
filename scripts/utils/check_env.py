"""
环境诊断脚本

检查当前的 Python 环境和依赖状态
"""

import sys
import subprocess


def run_command(cmd):
    """运行命令并返回输出"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True,
            encoding='utf-8'
        )
        return result.stdout
    except Exception as e:
        return f"错误: {e}"


def check_python():
    """检查 Python 环境"""
    print("=" * 60)
    print("Python 环境检查")
    print("=" * 60)

    # Python 版本
    version = sys.version_info
    print(f"Python 版本: {version.major}.{version.minor}.{version.micro}")
    print(f"Python 可执行文件: {sys.executable}")

    # Python 路径
    print(f"Python 路径: {sys.executable}")

    # Python 当前目录
    import os
    cwd = os.getcwd()
    print(f"当前目录: {cwd}")

    # 检查 requirements.txt
    req_file = os.path.join(cwd, "requirements.txt")
    if os.path.exists(req_file):
        with open(req_file, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"\nrequirements.txt 存在:")
        print(f"{content[:500]}")
    else:
        print("错误: requirements.txt 不存在")

    # 检查已安装的包
    installed_packages = [
        "fastapi",
        "uvicorn",
        "jinja2",
        "starlette",
        "pydantic",
        "pymysql",
        "tortoise-orm",
        "aerich",
        "python-dotenv",
        "itsdangerous",
        "requests",
        "openpyxl",
        "pyyaml",
        "pytest",
        "python-multipart",
        "fnmatch"
    ]

    print("\n已安装的包:")
    for package in installed_packages:
        try:
            __import__(package)
            version = __import__(package).__version__
            print(f"  ✓ {package} ({version})")
        except ImportError:
            print(f"  ✗ {package} (未安装)")

    # 检查 Tortoise ORM
    print("\nTortoise ORM 检查:")
    try:
        import tortoise
        print(f"  ✓ tortoise 已安装")
        print(f"  版本: {tortoise.__version__}")
    except ImportError:
        print(f"  ✗ tortoise 未安装")

    # 检查 Tortoise connections 模块
    try:
        from tortoise import connections
        print(f"  ✓ connections 模块可用")
    except ImportError:
        print(f"  ✗ connections 模块不可用")

    # 检查 fastapi-tortoise-crud
    try:
        from fastapi_tortoise
        print(f"  ✓ fastapi-tortoise-crud 已安装")
    except ImportError:
        print(f"  ✗ fastapi-tortoise-crud 未安装")

    # 检查 db_config.py 中的导入
    try:
        from core import db_config
        if os.path.exists("core/db_config.py"):
            with open("core/db_config.py", "r", encoding="utf-8") as f:
                content = f.read()
                if "from tortoise import connections" in content:
                    print(f"  ✓ db_config.py 已正确导入 connections")
                else:
                    print(f"  ✗ db_config.py 导入有问题")

    print("\n" + "=" * 60)
    print("诊断完成！")
    print("=" * 60)
    print("\n如果 Tortoise 导入正常，请重新运行: python main.py")
    print("\n如果仍有错误，请将完整输出发送给开发者")
    print("=" * 60)
