"""
ZIP utility functions for skill packages.

Provides functions for creating, extracting, and validating skill ZIP packages.
"""

import zipfile
import logging
from pathlib import Path
from typing import Optional, List, Tuple
import io

from utils.skill_parser import parse_skill_metadata, validate_skill_metadata

logger = logging.getLogger(__name__)

# Required files in a skill package
REQUIRED_FILES = ["SKILL.md"]
ALLOWED_EXTENSIONS = {".md", ".txt", ".py", ".json", ".yaml", ".yml", ".sh", ".bat"}


def validate_skill_zip(zip_path: Path) -> Tuple[bool, List[str]]:
    """Validate a skill ZIP package.

    Args:
        zip_path: Path to the ZIP file

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    if not zip_path.exists():
        errors.append(f"File not found: {zip_path}")
        return False, errors

    if not zipfile.is_zipfile(zip_path):
        errors.append("Not a valid ZIP file")
        return False, errors

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Check for required files
            file_list = zf.namelist()
            for required in REQUIRED_FILES:
                if required not in file_list:
                    errors.append(f"Missing required file: {required}")

            # Validate SKILL.md
            if "SKILL.md" in file_list:
                try:
                    skill_content = zf.read("SKILL.md").decode("utf-8")
                    metadata = parse_skill_metadata(skill_content)
                    validation_errors = validate_skill_metadata(metadata)
                    if validation_errors:
                        errors.extend([f"SKILL.md: {e}" for e in validation_errors])
                except Exception as e:
                    errors.append(f"Failed to parse SKILL.md: {e}")

            # Check for dangerous files
            for filename in file_list:
                if filename.startswith("/") or ".." in filename:
                    errors.append(f"Dangerous path in ZIP: {filename}")

    except zipfile.BadZipFile as e:
        errors.append(f"Corrupted ZIP file: {e}")
        return False, errors
    except Exception as e:
        errors.append(f"Validation error: {e}")
        return False, errors

    return len(errors) == 0, errors


def extract_skill_zip(zip_path: Path, dest_dir: Path) -> bool:
    """Extract a skill ZIP package.

    Args:
        zip_path: Path to the ZIP file
        dest_dir: Destination directory

    Returns:
        True if successful
    """
    try:
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(dest_dir)

        logger.info(f"Extracted {zip_path} to {dest_dir}")
        return True
    except Exception as e:
        logger.error(f"Failed to extract {zip_path}: {e}")
        return False


def create_skill_zip(source_dir: Path, output_path: Path) -> bool:
    """Create a skill ZIP package from a directory.

    Args:
        source_dir: Source directory containing skill files
        output_path: Output ZIP file path

    Returns:
        True if successful
    """
    try:
        source_dir = Path(source_dir)
        output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in source_dir.rglob('*'):
                if file_path.is_file():
                    # Get relative path
                    arcname = file_path.relative_to(source_dir)
                    zf.write(file_path, arcname)

        logger.info(f"Created ZIP: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create ZIP: {e}")
        return False


def get_skill_zip_info(zip_path: Path) -> Optional[dict]:
    """Get information about a skill ZIP package.

    Args:
        zip_path: Path to the ZIP file

    Returns:
        Dict with file info or None if error
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            info = {
                "files": zf.namelist(),
                "file_count": len(zf.namelist()),
                "size": zip_path.stat().st_size,
            }

            # Try to parse SKILL.md
            if "SKILL.md" in zf.namelist():
                try:
                    content = zf.read("SKILL.md").decode("utf-8")
                    metadata = parse_skill_metadata(content)
                    info["metadata"] = metadata.to_dict()
                except Exception:
                    pass

            return info
    except Exception as e:
        logger.error(f"Failed to get ZIP info: {e}")
        return None


def list_zip_contents(zip_path: Path) -> List[str]:
    """List contents of a ZIP file.

    Args:
        zip_path: Path to the ZIP file

    Returns:
        List of file names in the ZIP
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            return zf.namelist()
    except Exception:
        return []
