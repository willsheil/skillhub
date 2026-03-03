from pydantic import ValidationError
import pytest
from api.v1.schemas import (
    SkillListResponse,
    SkillDetailResponse,
    SkillItem,
    PaginationInfo
)

def test_skill_item_schema():
    """测试 Skill Item Schema"""
    data = {
        "name": "test-skill",
        "description": "Test skill",
        "metadata": {
            "version": "1.0.0",
            "author": "w00000001",
            "tags": ["test"],
            "category": "test",
            "license": "MIT",
            "compatibility": "Claude Code 1.0+"
        },
        "source_type": "opensource",
        "default_version": "1.0.0",
        "versions": ["1.0.0"],
        "download_url": "/api/v1/skills/test-skill/download"
    }
    skill = SkillItem(**data)
    assert skill.name == "test-skill"
    assert skill.source_type == "opensource"

def test_skill_list_response_schema():
    """测试技能列表响应 Schema"""
    data = {
        "code": 200,
        "message": "success",
        "data": {
            "items": []
        },
        "pagination": {
            "page": 1,
            "page_size": 20,
            "total": 0,
            "total_pages": 0
        }
    }
    response = SkillListResponse(**data)
    assert response.code == 200
    assert response.pagination.page == 1

def test_pagination_validation():
    """测试分页参数验证"""
    from api.v1.schemas import SkillListQuery
    query = SkillListQuery(page=1, page_size=20)
    assert query.page == 1
    assert query.page_size == 20

def test_invalid_source_type():
    """测试无效的 source_type"""
    from api.v1.schemas import SkillListQuery
    with pytest.raises(ValidationError):
        SkillListQuery(source_type="invalid")
