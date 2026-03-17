"""
File utility functions for SkillHub.

Provides file operations including directory management, file removal, and listing.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def ensure_directory(path: Path) -> Path:
    """Ensure directory exists, create if not.

    Args:
        path: Directory path

    Returns:
        Path object for the directory
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_remove(path: Path) -> bool:
    """Safely remove a file or directory.

    Args:
        path: Path to remove

    Returns:
        True if removed, False if didn't exist
    """
    path = Path(path)
    if not path.exists():
        return False

    try:
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        return True
    except Exception as e:
        logger.error(f"Failed to remove {path}: {e}")
        return False


def get_file_size(path: Path) -> int:
    """Get file size in bytes.

    Args:
        path: File path

    Returns:
        File size in bytes, 0 if not found
    """
    try:
        return Path(path).stat().st_size
    except OSError:
        return 0


def list_files(directory: Path, pattern: str = "*", recursive: bool = False) -> List[Path]:
    """List files in a directory.

    Args:
        directory: Directory to list
        pattern: Glob pattern
        recursive: Whether to search recursively

    Returns:
        List of file paths
    """
    directory = Path(directory)
    if not directory.exists():
        return []

    if recursive:
        return list(directory.rglob(pattern))
    else:
        return list(directory.glob(pattern))


def copy_file(src: Path, dst: Path) -> bool:
    """Copy a file.

    Args:
        src: Source file path
        dst: Destination file path

    Returns:
        True if successful
    """
    try:
        dst_parent = Path(dst).parent
        dst_parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        logger.error(f"Failed to copy {src} to {dst}: {e}")
        return False


def move_file(src: Path, dst: Path) -> bool:
    """Move a file.

    Args:
        src: Source file path
        dst: Destination file path

    Returns:
        True if successful
    """
    try:
        dst_parent = Path(dst).parent
        dst_parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src, dst)
        return True
    except Exception as e:
        logger.error(f"Failed to move {src} to {dst}: {e}")
        return False


def get_directory_size(path: Path) -> int:
    """Get total size of directory in bytes.

    Args:
        path: Directory path

    Returns:
        Total size in bytes
    """
    total = 0
    for entry in Path(path).rglob('*'):
        if entry.is_file():
            try:
                total += entry.stat().st_size
            except OSError:
                pass
    return total
