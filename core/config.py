"""
Configuration management for SkillHub application.

Provides centralized configuration using environment variables with sensible defaults.
"""

import os
from pathlib import Path
from typing import Optional


class Settings:
    """Application settings loaded from environment variables.

    All settings can be overridden via environment variables or .env file.

    Attributes:
        # App settings
        APP_NAME: Application name
        APP_VERSION: Application version
        DEBUG: Enable debug mode
        SECRET_KEY: Session secret key

        # Admin credentials
        ADMIN_USERNAME: Admin username for web login
        ADMIN_PASSWORD: Admin password for web login

        # Database settings
        DB_HOST: MySQL host
        DB_PORT: MySQL port
        DB_USER: MySQL username
        DB_PASSWORD: MySQL password
        DB_DATABASE: Database name

        # Storage settings
        PLUGINS_DIR: Directory for storing skill plugins
        PENDING_DIR: Directory for pending uploads

        # Gitea integration
        GITEA_REPO_URL: Gitea repository URL
        GITEA_TOKEN: Gitea access token
        GITEA_PUSH_INTERVAL: Push interval in seconds

        # Logging
        LOG_LEVEL: Logging level
        LOG_DIR: Directory for log files
    """

    def __init__(self):
        # Load dotenv
        from dotenv import load_dotenv
        load_dotenv()

        # App settings
        self.APP_NAME = os.getenv("APP_NAME", "SkillHub")
        self.APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
        self.DEBUG = os.getenv("DEBUG", "false").lower() == "true"
        self.SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")

        # Admin credentials
        self.ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
        self.ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

        # Database settings
        self.DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
        self.DB_PORT = int(os.getenv("DB_PORT", "3306"))
        self.DB_USER = os.getenv("DB_USER", "root")
        self.DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
        self.DB_DATABASE = os.getenv("DB_DATABASE", "skills")

        # Storage settings
        self.PLUGINS_DIR = Path(os.getenv("PLUGINS_DIR", "./plugins"))
        self.PENDING_DIR = Path(os.getenv("PENDING_DIR", "./data/pending"))

        # Gitea integration
        self.GITEA_REPO_URL = os.getenv("GITEA_REPO_URL")
        self.GITEA_TOKEN = os.getenv("GITEA_TOKEN")
        self.GITEA_PUSH_INTERVAL = int(os.getenv("GITEA_PUSH_INTERVAL", "30"))

        # Git configuration
        self.GIT_USER_NAME = os.getenv("GIT_USER_NAME", "Skill Registry")
        self.GIT_USER_EMAIL = os.getenv("GIT_USER_EMAIL", "registry@local")

        # Logging
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_DIR = Path(os.getenv("LOG_DIR", "./logs"))
        self.LOG_JSON = os.getenv("LOG_JSON", "true").lower() == "true"
        self.LOG_CONSOLE = os.getenv("LOG_CONSOLE", "true").lower() == "true"

        # API settings
        self.API_V1_PREFIX = os.getenv("API_V1_PREFIX", "/api/v1")
        self.MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(50 * 1024 * 1024)))

        # Rate limiting
        self.RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        self.DEFAULT_RATE_LIMIT = int(os.getenv("DEFAULT_RATE_LIMIT", "100"))

        # Ensure directories exist
        self.PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        self.PENDING_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def db_url(self) -> str:
        """Get database URL for SQLAlchemy."""
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_DATABASE}"

    @property
    def db_config(self) -> dict:
        """Get database config for PyMySQL."""
        return {
            'host': self.DB_HOST,
            'port': self.DB_PORT,
            'user': self.DB_USER,
            'password': self.DB_PASSWORD,
            'database': self.DB_DATABASE,
            'charset': 'utf8mb4',
        }

    @property
    def is_gitea_enabled(self) -> bool:
        """Check if Gitea integration is enabled."""
        return bool(self.GITEA_REPO_URL)

    @property
    def MAX_UPLOAD_SIZE_BYTES(self) -> int:
        """Get max upload size in bytes."""
        return self.MAX_UPLOAD_SIZE


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance.

    This function implements singleton pattern to ensure consistent
    configuration across the application.

    Returns:
        Settings: The global settings instance

    Example:
        >>> settings = get_settings()
        >>> print(settings.APP_NAME)
        SkillHub
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> Settings:
    """Reset and recreate the settings instance.

    Useful for testing or when configuration changes at runtime.

    Returns:
        Settings: New settings instance
    """
    global _settings
    _settings = Settings()
    return _settings
