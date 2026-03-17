"""
API services - Business logic layer.

Provides service classes that encapsulate business logic and interact with repositories.
"""

import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from db.repositories import (
    UserRepository,
    SkillRepository,
    DownloadRepository,
    NotificationRepository,
)
from db.models import User, Skill
from core.constants import SkillStatus, SourceType, NotificationType
from core.config import get_settings
from utils.skill_parser import parse_skill_metadata
from utils.zip_utils import validate_skill_zip

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service."""

    @staticmethod
    def authenticate(employee_id: str, api_key: str) -> Optional[User]:
        """Authenticate user with credentials.

        Args:
            employee_id: Employee ID
            api_key: API key

        Returns:
            User object if authenticated, None otherwise
        """
        user = UserRepository.get_by_credentials(employee_id, api_key)
        if user and user.is_active():
            UserRepository.update_last_login(user.id)
        return user

    @staticmethod
    def create_user(employee_id: str, api_key: str, role: str = "user") -> User:
        """Create a new user.

        Args:
            employee_id: Employee ID
            api_key: API key (plain text)
            role: User role

        Returns:
            Created User object
        """
        return UserRepository.create(employee_id, api_key, role)

    @staticmethod
    def reset_api_key(user_id: int) -> str:
        """Reset user's API key.

        Args:
            user_id: User ID

        Returns:
            New API key (plain text)
        """
        return UserRepository.reset_api_key(user_id)


class SkillService:
    """Skill management service."""

    @staticmethod
    def search(
        source_type: Optional[str] = None,
        keyword: Optional[str] = None,
        tags: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Search skills.

        Args:
            source_type: Filter by source type
            keyword: Search keyword
            tags: Filter by tags
            page: Page number
            page_size: Page size

        Returns:
            Dict with items and pagination
        """
        skills, total = SkillRepository.search(
            source_type=source_type,
            keyword=keyword,
            tags=tags,
            page=page,
            page_size=page_size,
        )

        return {
            "items": [s.to_dict() for s in skills],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size
            }
        }

    @staticmethod
    def get_by_id(skill_id: int) -> Optional[Skill]:
        """Get skill by ID.

        Args:
            skill_id: Skill ID

        Returns:
            Skill object or None
        """
        return SkillRepository.get_by_id(skill_id)

    @staticmethod
    def get_by_name(skill_name: str, version: Optional[str] = None) -> Optional[Skill]:
        """Get skill by name.

        Args:
            skill_name: Skill name
            version: Optional version

        Returns:
            Skill object or None
        """
        return SkillRepository.get_by_name(skill_name, version)

    @staticmethod
    def get_my_skills(user_id: int) -> List[Dict[str, Any]]:
        """Get skills for a user.

        Args:
            user_id: User ID

        Returns:
            List of user's skills grouped by name
        """
        skills = SkillRepository.get_by_uploader(user_id)

        # Group by skill name
        grouped = {}
        for skill in skills:
            if skill.skill_name not in grouped:
                grouped[skill.skill_name] = {
                    "skill_name": skill.skill_name,
                    "description": skill.description,
                    "versions": []
                }
            grouped[skill.skill_name]["versions"].append({
                "id": skill.id,
                "version": skill.version,
                "status": skill.status,
                "is_default": skill.is_default_version,
                "is_active": skill.is_active,
            })

        return list(grouped.values())

    @staticmethod
    def set_default_version(skill_id: int) -> bool:
        """Set skill as default version.

        Args:
            skill_id: Skill ID

        Returns:
            True if successful
        """
        return SkillRepository.set_default_version(skill_id)

    @staticmethod
    def unlist(skill_id: int) -> bool:
        """Unlist a skill.

        Args:
            skill_id: Skill ID

        Returns:
            True if successful
        """
        return SkillRepository.update_active_status(skill_id, False)

    @staticmethod
    def delete(skill_id: int) -> bool:
        """Delete a skill.

        Args:
            skill_id: Skill ID

        Returns:
            True if successful
        """
        return SkillRepository.delete(skill_id)


class UploadService:
    """Skill upload service."""

    @staticmethod
    def process_upload(
        file_content: bytes,
        filename: str,
        uploader_id: int,
    ) -> Dict[str, Any]:
        """Process uploaded skill ZIP.

        Args:
            file_content: ZIP file content
            filename: Original filename
            uploader_id: Uploader user ID

        Returns:
            Dict with upload result

        Raises:
            ValueError: If validation fails
        """
        settings = get_settings()

        # Validate file size
        if len(file_content) > settings.MAX_UPLOAD_SIZE_BYTES:
            raise ValueError(f"File too large. Max size: {settings.MAX_UPLOAD_SIZE_MB}MB")

        # Validate file extension
        if not filename.endswith('.zip'):
            raise ValueError("Only ZIP files are allowed")

        # Save to temp file for validation
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = Path(tmp.name)

        try:
            # Validate ZIP
            is_valid, errors = validate_skill_zip(tmp_path)
            if not is_valid:
                raise ValueError(f"Invalid skill package: {'; '.join(errors)}")

            # Parse metadata
            # (Would need to extract and parse SKILL.md here)

            # Save to pending directory
            pending_dir = settings.PENDING_DIR
            pending_dir.mkdir(parents=True, exist_ok=True)

            dest_path = pending_dir / filename

            # Copy file
            import shutil
            shutil.copy(tmp_path, dest_path)

            # TODO: Create database record

            return {
                "success": True,
                "filename": filename,
                "status": "pending"
            }

        finally:
            # Clean up temp file
            tmp_path.unlink(missing_ok=True)


class ReviewService:
    """Skill review service."""

    @staticmethod
    def approve(skill_id: int, reviewer_id: int, comment: Optional[str] = None) -> bool:
        """Approve a skill.

        Args:
            skill_id: Skill ID
            reviewer_id: Admin user ID
            comment: Optional review comment

        Returns:
            True if successful
        """
        skill = SkillRepository.get_by_id(skill_id)
        if not skill:
            return False

        # Update skill status
        SkillRepository.update_status(
            skill_id,
            SkillStatus.APPROVED.value,
            reviewer_id=reviewer_id,
            review_comment=comment
        )

        # Create notification
        NotificationRepository.create(
            user_id=skill.uploader_id,
            notification_type=NotificationType.APPROVAL.value,
            title="Skill Approved",
            content=f"Your skill '{skill.skill_name}' has been approved.",
            related_skill_id=skill_id
        )

        return True

    @staticmethod
    def reject(skill_id: int, reviewer_id: int, comment: str) -> bool:
        """Reject a skill.

        Args:
            skill_id: Skill ID
            reviewer_id: Admin user ID
            comment: Review comment

        Returns:
            True if successful
        """
        skill = SkillRepository.get_by_id(skill_id)
        if not skill:
            return False

        # Update skill status
        SkillRepository.update_status(
            skill_id,
            SkillStatus.REJECTED.value,
            reviewer_id=reviewer_id,
            review_comment=comment
        )

        # Create notification
        NotificationRepository.create(
            user_id=skill.uploader_id,
            notification_type=NotificationType.REJECTION.value,
            title="Skill Rejected",
            content=f"Your skill '{skill.skill_name}' has been rejected. Reason: {comment}",
            related_skill_id=skill_id
        )

        return True


class NotificationService:
    """Notification service."""

    @staticmethod
    def get_user_notifications(user_id: int, limit: int = 50) -> List[Dict]:
        """Get user notifications.

        Args:
            user_id: User ID
            limit: Max results

        Returns:
            List of notifications
        """
        notifications = NotificationRepository.get_by_user(user_id, limit=limit)
        return [n.to_dict() for n in notifications]

    @staticmethod
    def get_unread_count(user_id: int) -> int:
        """Get unread notification count.

        Args:
            user_id: User ID

        Returns:
            Count of unread notifications
        """
        return NotificationRepository.get_unread_count(user_id)

    @staticmethod
    def mark_as_read(notification_id: int) -> bool:
        """Mark notification as read.

        Args:
            notification_id: Notification ID

        Returns:
            True if successful
        """
        return NotificationRepository.mark_as_read(notification_id)

    @staticmethod
    def mark_all_as_read(user_id: int) -> int:
        """Mark all notifications as read.

        Args:
            user_id: User ID

        Returns:
            Number of notifications marked
        """
        return NotificationRepository.mark_all_as_read(user_id)


class MarketService:
    """Marketplace service."""

    @staticmethod
    def generate_marketplace_json() -> Dict[str, Any]:
        """Generate marketplace.json content.

        Returns:
            Marketplace JSON structure
        """
        skills = SkillRepository.get_active_skills(limit=1000)

        items = []
        for skill in skills:
            import json
            metadata = json.loads(skill.metadata) if skill.metadata else {}

            items.append({
                "name": skill.skill_name,
                "description": skill.description,
                "metadata": metadata,
                "source_type": skill.source_type,
            })

        return {
            "version": "1.0",
            "skills": items
        }
