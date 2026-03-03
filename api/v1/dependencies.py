from fastapi import Header, HTTPException, status
from typing import Optional
from database import verify_api_key, get_api_key_info

# 速率限制内存存储（生产环境建议使用 Redis）
_rate_limit_store = {}

def verify_api_key_header(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> dict:
    """验证 API Key 依赖注入

    Raises:
        HTTPException: 401 如果 API Key 无效

    Returns:
        API Key 信息字典
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key is required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    api_key_info = verify_api_key(x_api_key)
    if not api_key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key_info

def get_rate_limit(api_key: str) -> int:
    """获取 API Key 的速率限制

    Returns:
        每分钟允许的请求数
    """
    info = get_api_key_info(api_key)
    if info:
        return info.get('rate_limit', 100)
    return 100

def check_rate_limit(api_key: str, rate_limit: int) -> bool:
    """检查速率限制

    Args:
        api_key: API Key 字符串
        rate_limit: 每分钟请求数限制

    Returns:
        True 如果未超限，False 如果超限
    """
    import time
    current_time = int(time.time())

    if api_key not in _rate_limit_store:
        _rate_limit_store[api_key] = []
        return True

    # 移除超过 60 秒的记录
    _rate_limit_store[api_key] = [
        t for t in _rate_limit_store[api_key]
        if current_time - t < 60
    ]

    # 检查请求数
    if len(_rate_limit_store[api_key]) >= rate_limit:
        return False

    _rate_limit_store[api_key].append(current_time)
    return True
