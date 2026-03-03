import pytest
from fastapi import Header, HTTPException
from api.v1.dependencies import verify_api_key_header, get_rate_limit

def test_verify_valid_api_key():
    """测试验证有效的 API Key"""
    # 先创建一个测试 API Key
    from database import create_api_key
    api_key_record = create_api_key(user_id=1, name="Test")
    api_key = api_key_record['api_key']

    # 验证应该成功
    result = verify_api_key_header(x_api_key=api_key)
    assert result['user_id'] == 1

def test_verify_invalid_api_key():
    """测试验证无效的 API Key"""
    with pytest.raises(HTTPException) as exc:
        verify_api_key_header(x_api_key="sk_invalid")
    assert exc.value.status_code == 401

def test_verify_missing_api_key():
    """测试缺少 API Key"""
    with pytest.raises(HTTPException) as exc:
        verify_api_key_header(x_api_key=None)
    assert exc.value.status_code == 401

def test_rate_limit():
    """测试速率限制"""
    from database import create_api_key
    api_key_record = create_api_key(user_id=1, name="Rate Limit Test")

    limit = get_rate_limit(api_key_record['api_key'])
    assert limit == 100  # 默认值
