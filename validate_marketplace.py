import json
from pathlib import Path

def validate_marketplace(file_path):
    """验证 marketplace.json 是否符合规范"""

    print(f"验证 {file_path}...\n")

    # 1. 检查文件是否存在
    if not Path(file_path).exists():
        print("[FAIL] File not found")
        return False

    # 2. 验证 JSON 语法
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            marketplace = json.load(f)
        print("[PASS] JSON syntax valid")
    except json.JSONDecodeError as e:
        print(f"[FAIL] JSON syntax error: {e}")
        return False

    # 3. 验证必需字段
    required_fields = ['name', 'owner', 'plugins']
    missing_fields = [f for f in required_fields if f not in marketplace]

    if missing_fields:
        print(f"[FAIL] Missing required fields: {', '.join(missing_fields)}")
        return False
    print("[PASS] Required fields present")

    # 4. 验证 name 字段
    if not isinstance(marketplace['name'], str) or ' ' in marketplace['name']:
        print("[FAIL] name must be kebab-case string without spaces")
        return False
    print(f"[PASS] Marketplace name: {marketplace['name']}")

    # 5. 验证 owner 字段
    if not isinstance(marketplace['owner'], dict):
        print("[FAIL] owner must be an object")
        return False

    if 'name' not in marketplace['owner']:
        print("[FAIL] owner.name is required")
        return False
    print(f"[PASS] Owner: {marketplace['owner']['name']}")

    # 6. 验证 plugins 数组
    if not isinstance(marketplace['plugins'], list):
        print("[FAIL] plugins must be an array")
        return False

    if len(marketplace['plugins']) == 0:
        print("[WARN] plugins array is empty")
    else:
        print(f"[PASS] Plugin count: {len(marketplace['plugins'])}")

    # 7. 验证每个插件
    plugin_names = set()
    for i, plugin in enumerate(marketplace['plugins']):
        print(f"\nChecking plugin #{i+1}: {plugin.get('name', 'unknown')}")

        # 必需字段
        if 'name' not in plugin:
            print(f"  [FAIL] Missing 'name' field")
            return False

        if 'source' not in plugin:
            print(f"  [FAIL] Missing 'source' field")
            return False

        # 检查重复名称
        if plugin['name'] in plugin_names:
            print(f"  [FAIL] Duplicate plugin name: {plugin['name']}")
            return False
        plugin_names.add(plugin['name'])

        # 验证 source 字段
        source = plugin['source']
        if isinstance(source, str):
            if source.startswith('..'):
                print(f"  [FAIL] source cannot contain path traversal (..)")
                return False
        elif isinstance(source, dict):
            if 'source' not in source:
                print(f"  [FAIL] source object must contain 'source' field")
                return False

        print(f"  [OK] {plugin['name']} -> {plugin['source']}")

    # 8. 可选元数据
    if 'metadata' in marketplace:
        metadata = marketplace['metadata']
        print(f"\n[PASS] Metadata present:")
        if 'description' in metadata:
            print(f"   Description: {metadata['description']}")
        if 'version' in metadata:
            print(f"   Version: {metadata['version']}")

    return True

if __name__ == '__main__':
    result = validate_marketplace('marketplace.json')
    print(f"\n{'='*50}")
    if result:
        print("[PASS] Validation passed! marketplace.json is valid")
    else:
        print("[FAIL] Validation failed, please fix the issues above")
