#!/usr/bin/env python3
"""Generate 100+ test skills with different categories"""

import os
import zipfile
import yaml
import random

CATEGORIES = ['opensource', 'icsl', 'huawei', 'productivity', 'development', 'security', 'automation']

SKILL_TEMPLATES = [
    {"name": "pdf-processor", "desc": "PDF文档处理工具，支持读取、编辑、转换"},
    {"name": "image-resizer", "desc": "图片批量调整大小和格式转换"},
    {"name": "data-exporter", "desc": "数据导出工具，支持多种格式"},
    {"name": "code-formatter", "desc": "代码格式化工具，支持多语言"},
    {"name": "api-tester", "desc": "API测试工具，支持REST和GraphQL"},
    {"name": "db-backup", "desc": "数据库备份和恢复工具"},
    {"name": "log-analyzer", "desc": "日志分析工具，支持多种日志格式"},
    {"name": "metrics-collector", "desc": "系统指标收集工具"},
    {"name": "notifier", "desc": "多渠道通知工具"},
    {"name": "scheduler", "desc": "任务调度工具"},
    {"name": "cache-manager", "desc": "缓存管理工具"},
    {"name": "auth-helper", "desc": "认证助手，支持多平台登录"},
    {"name": "file-sync", "desc": "文件同步工具"},
    {"name": "report-generator", "desc": "报告生成器"},
    {"name": "validator", "desc": "数据验证工具"},
]

# Authors (ICSL自研和华为自研需要)
ICSL_AUTHORS = ['w00000001', 'w00000002', 'w00000003', 'w12345678', 'emp001']
HUAWEI_AUTHORS = ['hw00001', 'hw00002', 'hw12345', 'hw99999']
OPENSOURCE_AUTHORS = ['community', 'open-source-team', 'contributor']

def create_skill_zip(skill_name, version, category, author, output_dir):
    """Create a skill ZIP file"""
    skill_dir = os.path.join(output_dir, skill_name)
    os.makedirs(skill_dir, exist_ok=True)

    # Create SKILL.md
    skill_md = f"""---
name: {skill_name}
description: {random.choice(SKILL_TEMPLATES).get('desc', '技能描述')} - 版本 {version}
metadata:
  version: {version}
  author: {author}
  tags: {category},utility,tool
  category: {category}
license: MIT
compatibility: Claude Code 1.0+
allowed-tools: bash, grep, read, write
---

# {skill_name}

This is a skill for {category}.

## Features

- Feature 1
- Feature 2
- Feature 3

## Usage

Use this skill to automate your workflow.
"""

    with open(os.path.join(skill_dir, 'SKILL.md'), 'w', encoding='utf-8') as f:
        f.write(skill_md)

    # Create a simple script
    script_content = f"""#!/usr/bin/env python3
# {skill_name} v{version}
print("{skill_name} executed!")
"""

    with open(os.path.join(skill_dir, 'run.py'), 'w', encoding='utf-8') as f:
        f.write(script_content)

    # Create ZIP
    zip_name = f"{skill_name}-{version}.zip"
    zip_path = os.path.join(output_dir, zip_name)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(os.path.join(skill_dir, 'SKILL.md'), 'SKILL.md')
        zf.write(os.path.join(skill_dir, 'run.py'), 'run.py')

    # Clean up temp dir
    import shutil
    shutil.rmtree(skill_dir)

    return zip_path

def main():
    output_dir = "./data/test_skills"
    os.makedirs(output_dir, exist_ok=True)

    skills_created = 0

    # Create skills for each category
    for category in CATEGORIES:
        # Determine author based on category
        if category == 'icsl':
            author = random.choice(ICSL_AUTHORS)
        elif category == 'huawei':
            author = random.choice(HUAWEI_AUTHORS)
        else:
            author = random.choice(OPENSOURCE_AUTHORS)

        # Create 15-20 skills per category
        num_skills = random.randint(15, 20)

        for i in range(num_skills):
            skill_name = f"{category}-{(i+1):03d}"
            version = f"1.0.{i}"

            try:
                zip_path = create_skill_zip(skill_name, version, category, author, output_dir)
                print(f"Created: {zip_path}")
                skills_created += 1
            except Exception as e:
                print(f"Error creating {skill_name}: {e}")

    print(f"\nTotal skills created: {skills_created}")
    print(f"ZIP files location: {output_dir}")

if __name__ == "__main__":
    main()
