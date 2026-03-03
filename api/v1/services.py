from typing import Dict, List, Any, Optional
from database import get_connection
import logging

logger = logging.getLogger("skillhub.api.services")

def get_skills_list(
    source_type: str = "all",
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    tags: Optional[str] = None
) -> Dict[str, Any]:
    """获取技能列表

    Args:
        source_type: 来源类型过滤
        page: 页码
        page_size: 每页数量
        keyword: 搜索关键词
        tags: 标签过滤

    Returns:
        包含 items 和 pagination 的字典
    """
    offset = (page - 1) * page_size

    # 构建查询条件
    where_conditions = ["status = 'approved'", "is_active = 1"]
    params = []

    if source_type != "all":
        where_conditions.append("source_type = %s")
        params.append(source_type)

    if keyword:
        where_conditions.append("(skill_name LIKE %s OR description LIKE %s)")
        keyword_pattern = f"%{keyword}%"
        params.extend([keyword_pattern, keyword_pattern])

    if tags:
        tag_list = [t.strip() for t in tags.split(',')]
        # 简化实现：在 metadata 中搜索标签
        for tag in tag_list:
            where_conditions.append("metadata LIKE %s")
            params.append(f"%{tag}%")

    where_clause = " AND ".join(where_conditions)

    # 查询总数
    with get_connection() as conn:
        count_result = conn.execute(
            f"SELECT COUNT(*) as total FROM skills WHERE {where_clause}",
            params
        ).fetchone()
        total = count_result['total']

        # 查询数据
        query = f"""
            SELECT id, skill_name, description, metadata, source_type,
                   version, filename, is_default_version
            FROM skills
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([page_size, offset])

        rows = conn.execute(query, params).fetchall()

    # 处理结果
    items = []
    for row in rows:
        # 解析 metadata (JSON 格式)
        import json
        try:
            metadata = json.loads(row['metadata']) if row['metadata'] else {}
        except:
            metadata = {}

        # 确保必需字段存在，提供默认值
        metadata = {
            "version": metadata.get("version", row['version']),
            "author": metadata.get("author", "Unknown"),
            "tags": metadata.get("tags", []),
            "category": metadata.get("category"),
            "license": metadata.get("license"),
            "compatibility": metadata.get("compatibility")
        }

        # 获取所有版本
        versions = _get_skill_versions(row['skill_name'])

        items.append({
            "name": row['skill_name'],
            "description": row['description'] or "",
            "metadata": metadata,
            "source_type": row['source_type'],
            "default_version": row['version'],
            "versions": versions,
            "download_url": f"/api/v1/skills/{row['skill_name']}/download"
        })

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages
        }
    }

def _get_skill_versions(skill_name: str) -> List[str]:
    """获取技能的所有版本"""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT version FROM skills
            WHERE skill_name = %s AND status = 'approved' AND is_active = 1
            ORDER BY version DESC
            """,
            (skill_name,)
        ).fetchall()
        return [row['version'] for row in rows]

def get_skill_detail(skill_name: str) -> Optional[Dict[str, Any]]:
    """获取技能详情

    Args:
        skill_name: 技能名称

    Returns:
        技能详情字典，不存在返回 None
    """
    with get_connection() as conn:
        # 获取默认版本信息
        row = conn.execute(
            """
            SELECT id, skill_name, description, metadata, source_type,
                   version, filename, is_default_version
            FROM skills
            WHERE skill_name = %s AND status = 'approved' AND is_active = 1
            ORDER BY is_default_version DESC, version DESC
            LIMIT 1
            """,
            (skill_name,)
        ).fetchone()

        if not row:
            return None

        # 解析 metadata
        import json
        try:
            metadata = json.loads(row['metadata']) if row['metadata'] else {}
        except:
            metadata = {}

        # 确保必需字段存在，提供默认值
        metadata = {
            "version": metadata.get("version", row['version']),
            "author": metadata.get("author", "Unknown"),
            "tags": metadata.get("tags", []),
            "category": metadata.get("category"),
            "license": metadata.get("license"),
            "compatibility": metadata.get("compatibility")
        }

        # 获取所有版本详情
        versions = _get_skill_version_details(skill_name)

        return {
            "name": row['skill_name'],
            "description": row['description'] or "",
            "metadata": metadata,
            "source_type": row['source_type'],
            "versions": versions
        }

def _get_skill_version_details(skill_name: str) -> List[Dict[str, Any]]:
    """获取技能的所有版本详情"""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT version, filename, is_default_version
            FROM skills
            WHERE skill_name = %s AND status = 'approved' AND is_active = 1
            ORDER BY version DESC
            """,
            (skill_name,)
        ).fetchall()

        return [
            {
                "version": row['version'],
                "filename": row['filename'],
                "is_default": bool(row['is_default_version']),
                "download_url": f"/api/v1/skills/{skill_name}/download?version={row['version']}"
            }
            for row in rows
        ]

def get_skill_download_path(skill_name: str, version: Optional[str] = None) -> Optional[str]:
    """获取技能下载文件路径

    Args:
        skill_name: 技能名称
        version: 版本号，None 表示默认版本

    Returns:
        文件路径，不存在返回 None
    """
    with get_connection() as conn:
        if version:
            row = conn.execute(
                """
                SELECT filename FROM skills
                WHERE skill_name = %s AND version = %s
                AND status = 'approved' AND is_active = 1
                LIMIT 1
                """,
                (skill_name, version)
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT filename FROM skills
                WHERE skill_name = %s AND is_default_version = 1
                AND status = 'approved' AND is_active = 1
                LIMIT 1
                """,
                (skill_name,)
            ).fetchone()

        if row:
            from pathlib import Path
            plugins_dir = Path(__file__).parent.parent.parent / "plugins"
            return str(plugins_dir / row['filename'])

        return None
