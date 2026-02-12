"""
Configuration module for Claude Code Skill Registry.

This module provides centralized configuration management including:
- Application settings and constants
- Logging configuration
- Environment-based configuration
"""

from .settings import (
    # Directory paths
    PLUGINS_DIR,
    DATA_DIR,
    PENDING_DIR,

    # Admin credentials
    ADMIN_USERNAME,
    ADMIN_PASSWORD,

    # Security
    SECRET_KEY,

    # Logging setup
    setup_logging,
    audit_log,
    PerformanceTracker,
)

__all__ = [
    "PLUGINS_DIR",
    "DATA_DIR",
    "PENDING_DIR",
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD",
    "SECRET_KEY",
    "setup_logging",
    "audit_log",
    "PerformanceTracker",
]
