import json
import zipfile
from pathlib import Path
from datetime import datetime
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

PLUGINS_DIR = Path('plugins')


def extract_metadata(collection, plugin_name, zip_path):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                if name.endswith('.claude-plugin/plugin.json'):
                    content = zf.read(name)
                    metadata = json.loads(content)
                    metadata['collection'] = collection
                    return metadata
    except Exception as e:
        logger.debug(f"Failed to extract metadata", extra={
            "collection": collection,
            "plugin_name": plugin_name,
            "error": str(e)
        })
    return {
        'name': plugin_name,
        'collection': collection,
        'version': 'unknown',
        'description': 'No description available',
        'author': {'name': 'Unknown'}
    }

plugins = []

logger.info("Scanning plugins directory...")

for collection_dir in PLUGINS_DIR.iterdir():
    if not collection_dir.is_dir():
        continue

    # Skip hidden/temp directories
    if collection_dir.name.startswith('.') or collection_dir.name.startswith('_'):
        continue

    collection = collection_dir.name
    logger.debug(f"Processing collection", extra={"collection": collection})

    for plugin_dir in collection_dir.iterdir():
        if not plugin_dir.is_dir():
            continue

        versions = []
        for zip_file in sorted(plugin_dir.glob('*.zip')):
            version = zip_file.stem
            versions.append({
                'version': version,
                'filename': zip_file.name,
                'size': zip_file.stat().st_size,
                'updated_at': datetime.fromtimestamp(zip_file.stat().st_mtime).isoformat()
            })

        if not versions:
            continue

        latest_zip = plugin_dir / versions[-1]['filename']
        metadata = extract_metadata(collection, plugin_dir.name, latest_zip)

        plugins.append({
            'name': plugin_dir.name,
            'collection': collection,
            'metadata': metadata,
            'versions': versions,
            'latest_version': versions[-1]['version']
        })

plugins = sorted(plugins, key=lambda x: (x['collection'], x['name']))

logger.info(f"Found {len(plugins)} plugins across collections")

marketplace = {
    'name': 'private-registry',
    'owner': {
        'name': 'Internal Registry',
        'email': 'admin@company.local'
    },
    'metadata': {
        'version': '1.0.0',
        'description': 'Internal Claude Code Skill Registry',
        'updated_at': datetime.now().isoformat()
    },
    'plugins': []
}

base_url = '/plugins'

for plugin in plugins:
    meta = plugin['metadata']
    latest = plugin['versions'][-1]

    marketplace['plugins'].append({
        'name': meta.get('name', plugin['name']),
        'version': latest['version'],
        'description': meta.get('description', 'No description'),
        'author': meta.get('author', {'name': 'Unknown'}),
        'source': f"{base_url}/{plugin['collection']}/{plugin['name']}/{latest['filename']}"
    })

with open('marketplace.json', 'w', encoding='utf-8') as f:
    json.dump(marketplace, f, indent=2, ensure_ascii=False)

logger.info("Generated marketplace.json", extra={
    "plugin_count": len(marketplace['plugins']),
    "output_file": "marketplace.json"
})
