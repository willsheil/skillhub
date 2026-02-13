"""
环境诊断脚本
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
    print(f"Python 路径: {sys.executable}")
    print(f"Python 可执行文件: {sys.executable}")

    # 检查当前目录
    import os
    cwd = os.getcwd()
    print(f"当前目录: {cwd}")

    # 检查 requirements.txt
    req_file = os.path.join(cwd, "requirements.txt")
    if os.path.exists(req_file):
        with open(req_file, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"\nrequirements.txt 存在:")
        print(content[:500] if len(content) > 500 else content)
    else:
        print("错误: 无法读取 requirements.txt")

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

    for package in installed_packages:
        try:
            __import__(package)
            version = __import__(package).__version__
            print(f"  ✓ {package} ({version})")
        except ImportError:
            print(f"  ✗ {package} (未安装)")

    # 检查 tortoise 导入
    print(f"\nTortoise ORM 检查:")
    try:
        import tortoise
        print(f"  ✓ tortoise 已安装")
        print(f"  tortoise 版本: {tortoise.__version__}")
    except ImportError:
        print(f"  ✗ tortoise 未安装")

    # 检查连接模块
    try:
        from tortoise import connections
        print(f"  ✓ connections 模块可用")
        except ImportError:
            print(f"  ✗ connections 模块不可用")

    # 检查 fastapi 集成
    try:
        from tortoise.contrib.fastapi import register_tortoise
        print(f"  ✓ register_tortoise 可用")
        except ImportError:
            print(f"  ✗ register_tortoise 不可用")

    print(f"\n" + "=" * 60)
    print("诊断完成！")
    print(f"\n如果 tortoise 导入正常，请重新运行: python main.py")
    print(f"\n如果仍有错误，请将以上输出发送给开发者")
