"""
Skills business logic services.

This module contains business logic for skill management including
validation, metadata extraction, and file operations.
"""

import re
import shutil
import zipfile
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger("skillhub.skills")

# Import from app.core.database
from app.core.database import (
    get_connection,
    create_skill_record,
    get_pending_skills,
    get_skill_by_id,
    update_skill_status,
    get_user_uploads,
    get_skill_source_type,
    update_skill_active_status,
    get_skill_active_status,
    get_my_skills,
    set_default_skill_version,
    get_skill_versions,
    get_default_skill_version,
    get_all_default_skill_versions,
    get_skill_approval_status,
    delete_skill_version,
    batch_unlist_skills,
    batch_delete_skills,
    get_user_by_id,
    create_notification,
)

# Import constants from dependencies
from app.modules.skills.dependencies import PLUGINS_DIR, PENDING_DIR


def parse_skill_md(content: str) -> Tuple[Optional[dict], str]:
    """Parse SKILL.md content to extract YAML frontmatter and markdown body.

    Args:
        content: Raw SKILL.md content

    Returns:
        Tuple of (yaml_metadata_dict, markdown_body)
        If no YAML frontmatter found, returns (None, content)
    """
    # Pattern to match YAML frontmatter between --- markers
    # Use .+? instead of .*? to ensure we match at least one character
    # Remove ^ anchor since content might have leading whitespace
    pattern = r'---\s*\n(.+?)\n---\s*\n(.*)'
    match = re.match(pattern, content, re.DOTALL)

    if match:
        yaml_content = match.group(1)
        markdown_body = match.group(2).strip()
        try:
            metadata = yaml.safe_load(yaml_content)
            if not isinstance(metadata, dict):
                metadata = {}
            return metadata, markdown_body
        except yaml.YAMLError:
            return None, content

    return None, content


def extract_metadata_from_skill_md(zip_path: Path) -> Optional[dict]:
    """Extract metadata from SKILL.md inside zip.

    The ZIP should have structure:
        skill-name/
        └── SKILL.md

    Args:
        zip_path: Path to the skill ZIP file

    Returns:
        Metadata dict or None if parsing fails
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()

            # Find SKILL.md (may be in root or subdirectory)
            skill_md_paths = [name for name in namelist
                             if name.endswith('SKILL.md') or name == 'SKILL.md']

            if not skill_md_paths:
                return None

            # Use the first SKILL.md found
            skill_md_path = skill_md_paths[0]
            content = zf.read(skill_md_path).decode('utf-8')

            metadata, _ = parse_skill_md(content)
            return metadata

    except Exception as e:
        logger.warning(f"Failed to extract metadata from {zip_path}: {e}", extra={"zip_path": str(zip_path)})
        return None


def validate_skill_name(name: str) -> Tuple[bool, str]:
    """Validate skill name according to specification.

    Requirements:
    - Must be 1-64 characters
    - May only contain lowercase letters, numbers, and hyphens
    - Must not start or end with '-'
    - Must not contain consecutive hyphens ('--')

    Args:
        name: The skill name to validate

    Returns:
        (is_valid, error_message)
    """
    if not name or not isinstance(name, str):
        return False, "Name is required"

    if len(name) < 1 or len(name) > 64:
        return False, "Name must be 1-64 characters"

    if not re.match(r'^[a-z0-9-]+$', name):
        return False, "Name may only contain lowercase letters, numbers, and hyphens"

    if name.startswith('-') or name.endswith('-'):
        return False, "Name must not start or end with hyphen"

    if '--' in name:
        return False, "Name must not contain consecutive hyphens"

    return True, ""


def validate_skill_zip(zip_path: Path) -> Tuple[bool, Dict[str, Any]]:
    """Validate a skill ZIP file according to Agent Skills specification.

    The ZIP should have structure:
        skill-name/
        ├── SKILL.md          # Required
        ├── scripts/          # Optional
        ├── references/       # Optional
        └── assets/           # Optional

    SKILL.md must contain YAML frontmatter with required fields:
        - name: skill identifier (max 64 chars, lowercase letters/numbers/hyphens only)
        - description: what skill does (max 1024 chars)
        - metadata.version: version string (e.g., "1.0.0")
        - metadata.author: author identifier (format: lowercase letter + 8 digits, e.g., "w00545471")

    Optional fields:
        - license: license name or reference
        - compatibility: environment requirements (max 500 chars)
        - metadata: arbitrary key-value mapping (other custom fields)
        - allowed-tools: space-delimited list of pre-approved tools

    Args:
        zip_path: Path to the skill ZIP file

    Returns:
        (is_valid, metadata or error_info)
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()

            # Find SKILL.md (may be in root or subdirectory)
            skill_md_paths = [name for name in namelist
                             if name.endswith('SKILL.md') or name == 'SKILL.md']

            if not skill_md_paths:
                return False, {"error": "Missing SKILL.md in ZIP"}

            # Read and parse SKILL.md
            skill_md_path = skill_md_paths[0]
            content = zf.read(skill_md_path).decode('utf-8')
            metadata, _ = parse_skill_md(content)

            if metadata is None:
                return False, {"error": "Invalid YAML frontmatter in SKILL.md"}

            # Validate required fields
            if "name" not in metadata:
                return False, {"error": "Missing required field 'name' in SKILL.md YAML frontmatter"}
            if "description" not in metadata:
                return False, {"error": "Missing required field 'description' in SKILL.md YAML frontmatter"}

            # Validate name format
            is_name_valid, name_error = validate_skill_name(metadata["name"])
            if not is_name_valid:
                return False, {"error": f"Invalid skill name: {name_error}"}

            # Validate description length (max 1024 chars)
            description = metadata["description"]
            if not isinstance(description, str) or len(description) == 0 or len(description) > 1024:
                return False, {"error": "Description must be 1-1024 characters"}

            # Validate optional fields if present
            # compatibility: max 500 chars
            if "compatibility" in metadata:
                compat = metadata["compatibility"]
                if not isinstance(compat, str) or len(compat) == 0 or len(compat) > 500:
                    return False, {"error": "Compatibility must be 1-500 characters if provided"}

            # Extract and validate metadata fields (version and author are required)
            skill_metadata = metadata.get("metadata", {})
            if not isinstance(skill_metadata, dict):
                return False, {"error": "Metadata must be a key-value mapping"}

            # Validate version is required in metadata
            version = skill_metadata.get("version")
            if not version:
                return False, {"error": "Missing required field 'metadata.version' in SKILL.md"}
            if not isinstance(version, str) or len(version) == 0:
                return False, {"error": "Metadata.version must be a non-empty string"}

            # Validate author is required in metadata
            author = skill_metadata.get("author")
            if not author:
                return False, {"error": "Missing required field 'metadata.author' in SKILL.md"}
            if not isinstance(author, str) or len(author) == 0:
                return False, {"error": "Metadata.author must be a non-empty string"}

            # Validate author format: lowercase letter followed by 8 digits (e.g., w00545471)
            if not re.match(r'^[a-z]\d{8}$', author):
                return False, {"error": "Invalid author format. Must be a lowercase letter followed by 8 digits (e.g., w00545471)"}

            # Normalize metadata for return (matching API format)
            normalized_metadata = {
                "name": metadata["name"],
                "description": metadata["description"],
                "version": version,
                "license": metadata.get("license"),
                "compatibility": metadata.get("compatibility"),
                "metadata": skill_metadata,
                "allowed_tools": metadata.get("allowed-tools")
            }

            return True, normalized_metadata

    except zipfile.BadZipFile:
        return False, {"error": "Invalid ZIP file"}
    except yaml.YAMLError as e:
        return False, {"error": f"Invalid YAML in SKILL.md: {str(e)}"}
    except Exception as e:
        return False, {"error": str(e)}


def save_skill_zip(temp_zip: Path, metadata: Dict[str, Any]) -> Path:
    """Save a skill ZIP to plugins directory.

    Args:
        temp_zip: Path to temporary ZIP file
        metadata: Skill metadata from SKILL.md

    Returns:
        Path to the saved ZIP file
    """
    skill_name = metadata["name"]
    version = metadata.get("version", "1.0.0")
    target_filename = f"{skill_name}-{version}.zip"
    target_path = PLUGINS_DIR / target_filename

    # Copy file to target location
    shutil.copy(temp_zip, target_path)

    return target_path


def approve_skill_file(skill_id: int) -> bool:
    """Approve a skill by moving it from pending to plugins directory.

    Args:
        skill_id: The ID of skill to approve

    Returns:
        True if successful, False otherwise
    """
    # Get skill record
    skill = get_skill_by_id(skill_id)
    if not skill:
        return False

    if skill["status"] != "pending":
        return False

    # File paths
    pending_path = PENDING_DIR / skill["filename"]
    plugins_path = PLUGINS_DIR / skill["filename"]

    try:
        # Check if file is in pending directory
        if pending_path.exists():
            # Move file from pending to plugins
            # Remove existing file if it exists (prevents FileExistsError on re-approval)
            if plugins_path.exists():
                logger.info(f"Removing existing file: {plugins_path}")
                plugins_path.unlink()

            shutil.move(str(pending_path), str(plugins_path))
        elif not plugins_path.exists():
            # File not in pending and not in plugins - error
            logger.error(f"Skill file not found: {skill['filename']} (checked both pending and plugins directories)")
            return False
        else:
            # File already in plugins directory (possibly from old batch upload)
            logger.info(f"File already in plugins directory: {plugins_path}")

        # Update database status
        update_skill_status(skill_id, "approved")

        # Set is_active=1 on approval
        update_skill_active_status(skill_id, True)

        # Create notification for uploader
        uploader_id = skill.get("uploader_id")
        if uploader_id:
            content = f"您的技能 {skill['skill_name']} (版本 {skill['version']}) 已通过审核并上线。"
            create_notification(
                user_id=uploader_id,
                type="review_success",
                title="您的技能已通过审核",
                content=content,
                related_skill_id=skill_id
            )

        return True
    except Exception as e:
        logger.error(f"Failed to approve skill {skill_id}: {e}")
        return False


def reject_skill_file(skill_id: int, comment: Optional[str] = None) -> bool:
    """Reject a skill file.

    Args:
        skill_id: The ID of skill to reject
        comment: Optional rejection comment

    Returns:
        True if successful, False otherwise
    """
    skill = get_skill_by_id(skill_id)
    if not skill:
        return False

    if skill["status"] != "pending":
        return False

    try:
        # Update database status
        update_skill_status(skill_id, "rejected")

        # Create notification for uploader
        uploader_id = skill.get("uploader_id")
        if uploader_id:
            content = f"您的技能 {skill['skill_name']} (版本 {skill['version']}) 未通过审核。"
            if comment:
                content += f" 原因: {comment}"
            create_notification(
                user_id=uploader_id,
                type="review_rejected",
                title="您的技能未通过审核",
                content=content,
                related_skill_id=skill_id
            )

        return True
    except Exception as e:
        logger.error(f"Failed to reject skill {skill_id}: {e}")
        return False


def scan_plugins() -> List[Dict[str, Any]]:
    """Get approved and active skills from database with metadata from ZIP files.

    This is optimized to only show skills that are both approved and active,
    avoiding need to scan all ZIP files repeatedly.

    Returns:
        List of skill dictionaries with metadata
    """
    result = []

    # Get all approved and active skills directly from database
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id, skill_name, version, filename, uploader_id, status,
                source_type, uploaded_at, reviewed_at, reviewer_id,
                review_comment, is_active, is_default_version
            FROM skills
            WHERE status = 'approved' AND is_active = 1
            ORDER BY skill_name, uploaded_at DESC
            """
        ).fetchall()

        # Group by skill_name to get only one entry per skill (the default version if exists)
        skills_by_name = {}
        for row in rows:
            skill_name = row["skill_name"]
            is_default = row["is_default_version"]

            # If we haven't added this skill yet, or this is default version
            if skill_name not in skills_by_name or is_default:
                skills_by_name[skill_name] = row
            # If current is not default and existing is not default, keep first one
            elif not skills_by_name[skill_name]["is_default_version"]:
                continue  # Keep existing one

        # Build result list with metadata from ZIP files
        for skill_name, row in skills_by_name.items():
            # Extract metadata from ZIP file
            metadata = extract_metadata_from_skill_zip(PLUGINS_DIR / row["filename"])
            if not metadata:
                # Fallback if ZIP file doesn't exist or is invalid
                metadata = {
                    "name": skill_name,
                    "description": f"{skill_name} - 技能描述",
                    "version": row["version"],
                    "license": None,
                    "compatibility": None,
                    "metadata": {"version": row["version"], "author": "未知"},
                    "allowed_tools": None
                }

            result.append({
                "name": skill_name,
                "metadata": metadata,
                "latest_version": row["version"],
                "source_type": row["source_type"] or "opensource",
                "uploaded_at": row["uploaded_at"].isoformat() if row["uploaded_at"] else None,
                "download_count": 0,  # TODO: Add download count if tracking
                "versions": [{
                    "version": row["version"],
                    "filename": row["filename"]
                }]
            })

    return result


def extract_metadata(zip_filename: str) -> Optional[Dict[str, Any]]:
    """Extract metadata from SKILL.md inside zip per Agent Skills specification.

    The ZIP should have structure:
        skill-name-1.0.0.zip
        └── skill-name/
            ├── SKILL.md
            ├── scripts/
            └── ...

    Args:
        zip_filename: Name of ZIP file (e.g., "skill-name-1.0.0.zip")

    Returns:
        Metadata dict or fallback info
    """
    zip_path = PLUGINS_DIR / zip_filename

    # Remove .zip extension to get skill name
    skill_name = zip_filename[:-4] if zip_filename.endswith('.zip') else zip_filename

    # Try to extract from SKILL.md
    metadata = extract_metadata_from_skill_md(zip_path)

    if metadata:
        # Extract version from metadata field (per Agent Skills spec)
        skill_metadata = metadata.get("metadata", {})
        if isinstance(skill_metadata, dict):
            spec_version = skill_metadata.get("version")
        else:
            spec_version = None
            skill_metadata = {}

        # Normalize metadata format per Agent Skills spec
        # Author is in metadata.author from SKILL.md
        author = skill_metadata.get("author") or metadata.get("author")
        normalized = {
            "name": metadata.get("name", skill_name),
            "version": spec_version if spec_version else "1.0.0",
            "description": metadata.get("description", "No description available"),
            "author": author,
            "license": metadata.get("license"),
            "compatibility": metadata.get("compatibility"),
            "metadata": {**skill_metadata, "author": author},
            "allowed_tools": metadata.get("allowed-tools")
        }
        return normalized

    # Fallback: try legacy package.json format for backward compatibility
    try:
        import json
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()

            for name in namelist:
                if name == 'package.json' or (name.endswith('/package.json')):
                    content = zf.read(name)
                    legacy_metadata = json.loads(content)
                    # Convert legacy format to Agent Skills format
                    legacy_author = legacy_metadata.get("author", {})
                    author_name = "Unknown"
                    if isinstance(legacy_author, dict):
                        author_name = legacy_author.get("name", "Unknown")
                    elif isinstance(legacy_author, str):
                        author_name = legacy_author

                    return {
                        "name": legacy_metadata.get("name", skill_name),
                        "version": legacy_metadata.get("version", "1.0.0"),
                        "description": legacy_metadata.get("description", "No description available"),
                        "license": None,
                        "compatibility": None,
                        "metadata": {
                            "author": author_name,
                            "version": legacy_metadata.get("version", "1.0.0")
                        },
                        "legacy": True
                    }
    except Exception:
        pass

    # Final fallback
    return {
        "name": skill_name,
        "version": "1.0.0",
        "description": "No description available",
        "license": None,
        "compatibility": None,
        "metadata": {"author": "未知"}
    }
