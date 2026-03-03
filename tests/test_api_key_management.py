import pytest
from database import (
    create_api_key,
    verify_api_key,
    get_api_key_info,
    deactivate_api_key,
    init_external_api_tables,
    get_connection
)

@pytest.fixture(autouse=True)
def setup_test_data():
    """设置测试数据"""
    init_external_api_tables()
    # 清理测试数据
    with get_connection() as conn:
        conn.execute("DELETE FROM external_api_keys WHERE name LIKE 'Test%'")
        conn.execute("DELETE FROM external_api_keys WHERE name LIKE 'Verify%'")
        conn.execute("DELETE FROM external_api_keys WHERE name LIKE 'Inactive%'")
        conn.execute("DELETE FROM external_api_keys WHERE name LIKE 'Info%'")
        conn.commit()
    yield
    # 清理
    with get_connection() as conn:
        conn.execute("DELETE FROM external_api_keys WHERE name LIKE 'Test%'")
        conn.execute("DELETE FROM external_api_keys WHERE name LIKE 'Verify%'")
        conn.execute("DELETE FROM external_api_keys WHERE name LIKE 'Inactive%'")
        conn.execute("DELETE FROM external_api_keys WHERE name LIKE 'Info%'")
        conn.commit()

def test_create_api_key():
    """测试创建 API Key"""
    # 假设用户 ID 1 存在
    api_key = create_api_key(user_id=1, name="Test Key")
    assert api_key is not None
    assert len(api_key['api_key']) == 46  # sk_ + 43位字符 (token_urlsafe(32))
    assert api_key['api_key'].startswith("sk_")

def test_verify_api_key_valid():
    """测试验证有效的 API Key"""
    api_key = create_api_key(user_id=1, name="Verify Test")
    info = verify_api_key(api_key['api_key'])
    assert info is not None
    assert info['user_id'] == 1
    assert info['is_active'] == 1

def test_verify_api_key_invalid():
    """测试验证无效的 API Key"""
    info = verify_api_key("sk_invalid123")
    assert info is None

def test_verify_api_key_inactive():
    """测试验证已停用的 API Key"""
    api_key_record = create_api_key(user_id=1, name="Inactive Test")
    deactivate_api_key(api_key_record['id'])
    info = verify_api_key(api_key_record['api_key'])
    assert info is None

def test_get_api_key_info():
    """测试获取 API Key 信息"""
    api_key = create_api_key(user_id=1, name="Info Test")
    info = get_api_key_info(api_key['api_key'])
    assert info['name'] == "Info Test"
    assert info['rate_limit'] == 100
