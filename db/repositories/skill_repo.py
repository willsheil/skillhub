"""
Skill repository - Database operations for skills.

Provides methods for skill CRUD operations, version management, and search.
"""

import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from db.connection import get_connection
from db.models import Skill
from core.constants import SkillStatus, SourceType

logger = logging.getLogger(__name__)


class SkillRepository:
    """Repository for skill database operations."""

    @staticmethod
    def get_by_id(skill_id: int) -> Optional[Skill]:
        """Get skill by ID.

        Args:
            skill_id: Skill ID

        Returns:
            Skill object if found, None otherwise
        """
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM skills WHERE id = %s",
                (skill_id,)
            )
            row = cursor.fetchone()
            if row:
                return Skill(**row)
            return None

    @staticmethod
    def get_by_name(skill_name: str, version: Optional[str] = None) -> Optional[Skill]:
        """Get skill by name and optional version.

        Args:
            skill_name: Skill name
            version: Optional version (returns default if not specified)

        Returns:
            Skill object if found, None otherwise
        """
        with get_connection() as conn:
            if version:
                cursor = conn.execute(
                    "SELECT * FROM skills WHERE skill_name = %s AND version = %s",
                    (skill_name, version)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM skills WHERE skill_name = %s AND is_default_version = 1",
                    (skill_name,)
                )
            row = cursor.fetchone()
            if row:
                return Skill(**row)
            return None

    @staticmethod
    def create(
        skill_name: str,
        version: str,
        filename: str,
        uploader_id: int,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        source_type: str = SourceType.OPENSOURCE.value,
    ) -> Skill:
        """Create a new skill.

        Args:
            skill_name: Skill name
            version: Version string
            filename: ZIP filename
            uploader_id: Uploader user ID
            description: Skill description
            metadata: Optional metadata dict
            source_type: Source type

        Returns:
            Created Skill object
        """
        metadata_json = json.dumps(metadata) if metadata else None
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO skills
                   (skill_name, version, filename, description, metadata, uploader_id, source_type)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (skill_name, version, filename, description, metadata_json, uploader_id, source_type)
            )
            conn.commit()

            # Get created skill
            cursor = conn.execute(
                "SELECT * FROM skills WHERE skill_name = %s AND version = %s",
                (skill_name, version)
            )
            row = cursor.fetchone()
            return Skill(**row)

    @staticmethod
    def update_status(
        skill_id: int,
        status: str,
        reviewer_id: Optional[int] = None,
        review_comment: Optional[str] = None,
    ) -> bool:
        """Update skill status.

        Args:
            skill_id: Skill ID
            status: New status
            reviewer_id: Admin user ID who reviewed
            review_comment: Optional review comment

        Returns:
            True if updated, False otherwise
        """
        with get_connection() as conn:
            if reviewer_id:
                conn.execute(
                    """UPDATE skills
                       SET status = %s, reviewed_at = %s, reviewer_id = %s, review_comment = %s
                       WHERE id = %s""",
                    (status, datetime.now(), reviewer_id, review_comment, skill_id)
                )
            else:
                conn.execute(
                    "UPDATE skills SET status = %s WHERE id = %s",
                    (status, skill_id)
                )
            conn.commit()
            return True

    @staticmethod
    def set_default_version(skill_id: int) -> bool:
        """Set a skill version as default.

        Args:
            skill_id: Skill ID to set as default

        Returns:
            True if updated
        """
        with get_connection() as conn:
            # First, get the skill to find its name
            cursor = conn.execute(
                "SELECT skill_name FROM skills WHERE id = %s",
                (skill_id,)
            )
            row = cursor.fetchone()
            if not row:
                return False

            skill_name = row['skill_name']

            # Clear default flag from all versions
            conn.execute(
                "UPDATE skills SET is_default_version = 0 WHERE skill_name = %s",
                (skill_name,)
            )

            # Set new default
            conn.execute(
                "UPDATE skills SET is_default_version = 1 WHERE id = %s",
                (skill_id,)
            )
            conn.commit()
            return True

    @staticmethod
    def get_versions(skill_name: str) -> List[Dict[str, Any]]:
        """Get all versions of a skill.

        Args:
            skill_name: Skill name

        Returns:
            List of version info dicts
        """
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, version, is_default_version, status, is_active, created_at
                   FROM skills WHERE skill_name = %s ORDER BY created_at DESC""",
                (skill_name,)
            )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_pending(uploader_id: Optional[int] = None, limit: int = 50, offset: int = 0) -> List[Skill]:
        """Get pending skills.

        Args:
            uploader_id: Optional filter by uploader
            limit: Max results
            offset: Result offset

        Returns:
            List of pending Skill objects
        """
        with get_connection() as conn:
            if uploader_id:
                cursor = conn.execute(
                    """SELECT * FROM skills WHERE status = %s AND uploader_id = %s
                       ORDER BY uploaded_at DESC LIMIT %s OFFSET %s""",
                    (SkillStatus.PENDING.value, uploader_id, limit, offset)
                )
            else:
                cursor = conn.execute(
                    """SELECT * FROM skills WHERE status = %s
                       ORDER BY uploaded_at DESC LIMIT %s OFFSET %s""",
                    (SkillStatus.PENDING.value, limit, offset)
                )
            return [Skill(**row) for row in cursor.fetchall()]

    @staticmethod
    def get_by_uploader(
        uploader_id: int,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Skill]:
        """Get skills by uploader.

        Args:
            uploader_id: Uploader user ID
            status: Optional status filter
            limit: Max results
            offset: Result offset

        Returns:
            List of Skill objects
        """
        with get_connection() as conn:
            if status:
                cursor = conn.execute(
                    """SELECT * FROM skills WHERE uploader_id = %s AND status = %s
                       ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                    (uploader_id, status, limit, offset)
                )
            else:
                cursor = conn.execute(
                    """SELECT * FROM skills WHERE uploader_id = %s
                       ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                    (uploader_id, limit, offset)
                )
            return [Skill(**row) for row in cursor.fetchall()]

    @staticmethod
    def search(
        source_type: Optional[str] = None,
        keyword: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: str = SkillStatus.APPROVED.value,
        is_active: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Skill], int]:
        """Search skills with filters.

        Args:
            source_type: Filter by source type
            keyword: Search keyword
            tags: Filter by tags
            status: Filter by status
            is_active: Filter by active status
            page: Page number
            page_size: Page size

        Returns:
            Tuple of (list of skills, total count)
        """
        conditions = ["status = %s", "is_active = %s"]
        params = [status, int(is_active)]

        if source_type and source_type != "all":
            conditions.append("source_type = %s")
            params.append(source_type)

        if keyword:
            conditions.append("(skill_name LIKE %s OR description LIKE %s)")
            keyword_pattern = f"%{keyword}%"
            params.extend([keyword_pattern, keyword_pattern])

        if tags:
            for tag in tags:
                conditions.append("metadata LIKE %s")
                params.append(f"%{tag}%")

        where_clause = " AND ".join(conditions)
        offset = (page - 1) * page_size

        with get_connection() as conn:
            # Get total count
            count_cursor = conn.execute(
                f"SELECT COUNT(*) as total FROM skills WHERE {where_clause}",
                params
            )
            total = count_cursor.fetchone()['total']

            # Get data
            params.extend([page_size, offset])
            cursor = conn.execute(
                f"""SELECT * FROM skills WHERE {where_clause}
                    ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                params
            )
            skills = [Skill(**row) for row in cursor.fetchall()]

        return skills, total

    @staticmethod
    def get_active_skills(limit: int = 100) -> List[Skill]:
        """Get all active approved skills.

        Args:
            limit: Max results

        Returns:
            List of active Skill objects
        """
        with get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM skills
                   WHERE status = %s AND is_active = 1
                   ORDER BY skill_name, created_at DESC""",
                (SkillStatus.APPROVED.value,)
            )
            return [Skill(**row) for row in cursor.fetchall()]

    @staticmethod
    def update_active_status(skill_id: int, is_active: bool) -> bool:
        """Update skill active status.

        Args:
            skill_id: Skill ID
            is_active: New active status

        Returns:
            True if updated
        """
        with get_connection() as conn:
            conn.execute(
                "UPDATE skills SET is_active = %s WHERE id = %s",
                (int(is_active), skill_id)
            )
            conn.commit()
            return True

    @staticmethod
    def update_source_type(skill_id: int, source_type: str) -> bool:
        """Update skill source type.

        Args:
            skill_id: Skill ID
            source_type: New source type

        Returns:
            True if updated
        """
        with get_connection() as conn:
            conn.execute(
                "UPDATE skills SET source_type = %s WHERE id = %s",
                (source_type, skill_id)
            )
            conn.commit()
            return True

    @staticmethod
    def delete(skill_id: int) -> bool:
        """Delete a skill.

        Args:
            skill_id: Skill ID

        Returns:
            True if deleted
        """
        with get_connection() as conn:
            conn.execute("DELETE FROM skills WHERE id = %s", (skill_id,))
            conn.commit()
            return True

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """Get skill statistics.

        Returns:
            Dict with counts by status and source type
        """
        with get_connection() as conn:
            # Count by status
            status_cursor = conn.execute(
                "SELECT status, COUNT(*) as count FROM skills GROUP BY status"
            )
            by_status = {row['status']: row['count'] for row in status_cursor.fetchall()}

            # Count by source type
            source_cursor = conn.execute(
                "SELECT source_type, COUNT(*) as count FROM skills GROUP BY source_type"
            )
            by_source = {row['source_type']: row['count'] for row in source_cursor.fetchall()}

            # Total
            total_cursor = conn.execute("SELECT COUNT(*) as count FROM skills")
            total = total_cursor.fetchone()['count']

            return {
                "total": total,
                "by_status": by_status,
                "by_source_type": by_source,
            }
