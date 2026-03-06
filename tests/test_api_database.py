import pytest
from database import get_connection, init_external_api_tables

def test_external_api_keys_table_exists():
    """测试 external_api_keys 表是否存在"""
    init_external_api_tables()
    with get_connection() as conn:
        result = conn.execute("""
            SELECT COUNT(*) as count FROM information_schema.tables
            WHERE table_name = 'external_api_keys' AND table_schema = DATABASE()
        """).fetchone()
        assert result['count'] == 1

def test_api_call_logs_table_exists():
    """测试 api_call_logs 表是否存在"""
    init_external_api_tables()
    with get_connection() as conn:
        result = conn.execute("""
            SELECT COUNT(*) as count FROM information_schema.tables
            WHERE table_name = 'api_call_logs' AND table_schema = DATABASE()
        """).fetchone()
        assert result['count'] == 1
