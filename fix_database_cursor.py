#!/usr/bin/env python3
"""
Fix database.py for PyMySQL compatibility.

PyMySQL requires using cursor.execute() instead of conn.execute()
"""

import re
import logging
import os

# 导入日志配置
from logging_config import setup_logging

# 初始化日志系统
setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_dir="./logs",
    enable_json=True,
    enable_console=True
)

# 获取logger
logger = logging.getLogger(__name__)

# Read the file
with open('database.py', 'r', encoding='utf-8') as f:
    content = f.read()

logger.info("Fixing database.py for PyMySQL compatibility...")

# Fix conn.execute() calls to use cursor
# Pattern 1: with get_connection() as conn: ... conn.execute(...)
# We need to add cursor = conn.cursor() before execute calls

# This is a complex fix, let's create a new version
lines = content.split('\n')
output_lines = []
in_with_block = False
indent_level = 0
fixes_applied = 0

for i, line in enumerate(lines):
    # Check if we're entering a with get_connection() block
    if 'with get_connection() as conn:' in line:
        output_lines.append(line)
        in_with_block = True
        indent_level = len(line) - len(line.lstrip())
        continue

    # Check if we're exiting the with block
    if in_with_block and line.strip() and not line.strip().startswith('#'):
        current_indent = len(line) - len(line.lstrip())
        if current_indent <= indent_level and not line.strip().startswith('conn'):
            in_with_block = False

    # Replace conn.execute() with cursor.execute()
    if in_with_block and 'conn.execute(' in line:
        # Get the indentation
        indent = ' ' * (len(line) - len(line.lstrip()))

        # Extract the SQL and parameters
        match = re.match(r'(\s+)conn\.execute\((.*?)\)(.*)', line)
        if match:
            new_indent = match.group(1)
            execute_args = match.group(2)
            rest = match.group(3)

            # Add cursor = conn.cursor() if not already added
            if i > 0 and 'cursor = conn.cursor()' not in lines[i-1]:
                output_lines.append(f"{new_indent}cursor = conn.cursor()")
                fixes_applied += 1

            # Replace conn.execute with cursor.execute
            new_line = f"{new_indent}cursor.execute({execute_args}){rest}"
            output_lines.append(new_line)
            fixes_applied += 1
            continue

    output_lines.append(line)

# Write back
with open('database.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output_lines))

logger.info("database.py has been updated for PyMySQL compatibility", extra={"fixes_applied": fixes_applied})
logger.info("Please review the changes and test.")
