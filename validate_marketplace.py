import json
from pathlib import Path
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


def validate_marketplace(file_path):
    """验证 marketplace.json 是否符合规范"""

    logger.info(f"Validating marketplace file", extra={"file_path": str(file_path)})

    # 1. 检查文件是否存在
    if not Path(file_path).exists():
        logger.error("[FAIL] File not found", extra={"file_path": str(file_path)})
        return False

    # 2. 验证 JSON 语法
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            marketplace = json.load(f)
        logger.info("[PASS] JSON syntax valid")
    except json.JSONDecodeError as e:
        logger.error(f"[FAIL] JSON syntax error", extra={"error": str(e)})
        return False

    # 3. 验证必需字段
    required_fields = ['name', 'owner', 'plugins']
    missing_fields = [f for f in required_fields if f not in marketplace]

    if missing_fields:
        logger.error(f"[FAIL] Missing required fields", extra={"missing_fields": missing_fields})
        return False
    logger.info("[PASS] Required fields present")

    # 4. 验证 name 字段
    if not isinstance(marketplace['name'], str) or ' ' in marketplace['name']:
        logger.error("[FAIL] name must be kebab-case string without spaces")
        return False
    logger.info(f"[PASS] Marketplace name: {marketplace['name']}", extra={"name": marketplace['name']})

    # 5. 验证 owner 字段
    if not isinstance(marketplace['owner'], dict):
        logger.error("[FAIL] owner must be an object")
        return False

    if 'name' not in marketplace['owner']:
        logger.error("[FAIL] owner.name is required")
        return False
    logger.info(f"[PASS] Owner: {marketplace['owner']['name']}", extra={"owner": marketplace['owner']['name']})

    # 6. 验证 plugins 数组
    if not isinstance(marketplace['plugins'], list):
        logger.error("[FAIL] plugins must be an array")
        return False

    if len(marketplace['plugins']) == 0:
        logger.warning("[WARN] plugins array is empty")
    else:
        logger.info(f"[PASS] Plugin count: {len(marketplace['plugins'])}", extra={"count": len(marketplace['plugins'])})

    # 7. 验证每个插件
    plugin_names = set()
    for i, plugin in enumerate(marketplace['plugins']):
        plugin_name = plugin.get('name', 'unknown')
        logger.info(f"Checking plugin #{i+1}", extra={"plugin_name": plugin_name})

        # 必需字段
        if 'name' not in plugin:
            logger.error(f"[FAIL] Missing 'name' field", extra={"plugin_index": i})
            return False

        if 'source' not in plugin:
            logger.error(f"[FAIL] Missing 'source' field", extra={"plugin_index": i, "plugin_name": plugin_name})
            return False

        # 检查重复名称
        if plugin['name'] in plugin_names:
            logger.error(f"[FAIL] Duplicate plugin name", extra={"plugin_name": plugin['name']})
            return False
        plugin_names.add(plugin['name'])

        # 验证 source 字段
        source = plugin['source']
        if isinstance(source, str):
            logger.debug(f"Plugin source is string", extra={"plugin_name": plugin_name, "source": source})
        elif isinstance(source, dict):
            if 'url' not in source:
                logger.error(f"[FAIL] source.url is required when source is object", extra={"plugin_name": plugin_name})
                return False
            logger.debug(f"Plugin source is object", extra={"plugin_name": plugin_name, "source_url": source['url']})
        else:
            logger.error(f"[FAIL] source must be string or object", extra={"plugin_name": plugin_name})
            return False

    logger.info("Marketplace validation completed successfully!", extra={
        "status": "success",
        "plugin_count": len(marketplace['plugins'])
    })
    return True


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        validate_marketplace(sys.argv[1])
    else:
        validate_marketplace("marketplace.json")
