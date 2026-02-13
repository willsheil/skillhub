"""
Application settings and configuration.

This module provides configuration management for the application,
loading settings from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Settings:
    """Application settings."""

    # Database settings
    db_host: str = os.getenv('DB_HOST', '127.0.0.1')
    db_port: int = int(os.getenv('DB_PORT', '3306'))
    db_user: str = os.getenv('DB_USER', 'root')
    db_password: str = os.getenv('DB_PASSWORD', 'root')
    db_database: str = os.getenv('DB_DATABASE', 'skills')

    # Application settings
    admin_username: str = os.getenv('ADMIN_USERNAME', 'admin')
    admin_password: str = os.getenv('ADMIN_PASSWORD', 'admin123')
    secret_key: str = os.getenv('SECRET_KEY', 'your-secret-key-change-this')

    # Directory settings
    plugins_dir: str = os.getenv('PLUGINS_DIR', './plugins')
    data_dir: str = os.getenv('DATA_DIR', './data')
    log_dir: str = os.getenv('LOG_DIR', './logs')

    # Logging settings
    log_level: str = os.getenv('LOG_LEVEL', 'INFO')
    log_json_enabled: bool = os.getenv('LOG_JSON', 'true').lower() == 'true'
    log_console_enabled: bool = os.getenv('LOG_CONSOLE', 'true').lower() == 'true'

    # Gitea integration settings
    gitea_repo_url: Optional[str] = os.getenv('GITEA_REPO_URL')
    gitea_push_interval: int = int(os.getenv('GITEA_PUSH_INTERVAL', '30'))
    gitea_token: Optional[str] = os.getenv('GITEA_TOKEN')
    gitea_branch: str = os.getenv('GITEA_BRANCH', 'main')

    # Marketplace settings
    marketplace_file: str = os.getenv('MARKETPLACE_FILE', './marketplace.json')


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance.

    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


__all__ = ["Settings", "get_settings"]
