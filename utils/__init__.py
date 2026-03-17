"""
Utils module - Utility functions for SkillHub.

Provides:
- Logging configuration
- File operations
- Skill file parsing
- ZIP file handling
"""

from .logging_config import setup_logging, audit_log, PerformanceTracker
from .file_utils import (
    ensure_directory,
    safe_remove,
    get_file_size,
    list_files,
)
from .skill_parser import SkillMetadata, parse_skill_metadata
from .zip_utils import (
    create_skill_zip,
    extract_skill_zip,
    validate_skill_zip,
)

__all__ = [
    # Logging
    "setup_logging",
    "audit_log",
    "PerformanceTracker",
    # File utils
    "ensure_directory",
    "safe_remove",
    "get_file_size",
    "list_files",
    # Skill parser
    "SkillMetadata",
    "parse_skill_metadata",
    # ZIP utils
    "create_skill_zip",
    "extract_skill_zip",
    "validate_skill_zip",
]
