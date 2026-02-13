"""
Core infrastructure module for the application.

This module provides:
- Configuration management
- Database configuration and models
- Dependency injection
- Middleware components
- Logging configuration
"""

from app.core.config import settings
from app.core.database.config import DB_CONFIG, get_connection, init_db
from app.core.database.models import (
    create_skill_record,
    get_pending_skills,
    get_skill_by_id,
    update_skill_status,
    get_user_by_credentials,
    get_user_by_id,
    update_last_login,
    record_download,
    get_download_stats,
    get_stats_with_author,
    get_user_uploads,
    get_total_users_count,
    get_skills_count_by_status,
    get_today_downloads_count,
    get_top_skills_by_downloads,
    get_top_users_by_downloads,
    get_skill_source_type,
    create_notification,
    update_skill_active_status,
    get_skill_active_status,
    get_my_skills,
    set_default_skill_version,
    get_skill_versions,
    get_user_notifications,
    get_unread_notifications_count,
    mark_notification_read,
    mark_all_notifications_read,
    cleanup_old_notifications,
    get_users_list,
    create_user,
    update_user_role,
    disable_user,
    enable_user,
    delete_user,
    reset_user_api_key,
    get_user_skills_count,
    get_default_skill_version,
    get_all_default_skill_versions,
    get_skill_approval_status,
    delete_skill_version,
    batch_unlist_skills,
    batch_delete_skills,
)
from app.core.dependencies.auth import (
    get_current_user,
    get_current_user_from_session,
    require_admin,
    require_admin_or_author,
)
from app.core.middleware.session import SessionMiddleware
from app.core.logging.config import (
    setup_logging,
    audit_log,
    PerformanceTracker,
    request_id_var,
)

__all__ = [
    # Config
    "settings",
    # Database
    "DB_CONFIG",
    "get_connection",
    "init_db",
    # Database models
    "create_skill_record",
    "get_pending_skills",
    "get_skill_by_id",
    "update_skill_status",
    "get_user_by_credentials",
    "get_user_by_id",
    "update_last_login",
    "record_download",
    "get_download_stats",
    "get_stats_with_author",
    "get_user_uploads",
    "get_total_users_count",
    "get_skills_count_by_status",
    "get_today_downloads_count",
    "get_top_skills_by_downloads",
    "get_top_users_by_downloads",
    "get_skill_source_type",
    "create_notification",
    "update_skill_active_status",
    "get_skill_active_status",
    "get_my_skills",
    "set_default_skill_version",
    "get_skill_versions",
    "get_user_notifications",
    "get_unread_notifications_count",
    "mark_notification_read",
    "mark_all_notifications_read",
    "cleanup_old_notifications",
    "get_users_list",
    "create_user",
    "update_user_role",
    "disable_user",
    "enable_user",
    "delete_user",
    "reset_user_api_key",
    "get_user_skills_count",
    "get_default_skill_version",
    "get_all_default_skill_versions",
    "get_skill_approval_status",
    "delete_skill_version",
    "batch_unlist_skills",
    "batch_delete_skills",
    # Dependencies
    "get_current_user",
    "get_current_user_from_session",
    "require_admin",
    "require_admin_or_author",
    # Middleware
    "SessionMiddleware",
    # Logging
    "setup_logging",
    "audit_log",
    "PerformanceTracker",
    "request_id_var",
]
