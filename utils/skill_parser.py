"""
Skill metadata parser for SKILL.md files.

Parses YAML frontmatter from skill markdown files to extract metadata.
"""

import re
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SkillMetadata:
    """Skill metadata parsed from SKILL.md."""
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)
    category: Optional[str] = None
    license: str = "MIT"
    compatibility: str = ""
    allowed_tools: List[str] = field(default_factory=list)
    raw_yaml: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "category": self.category,
            "license": self.license,
            "compatibility": self.compatibility,
            "allowed_tools": self.allowed_tools,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        import json
        return json.dumps(self.to_dict())


def parse_skill_metadata(content: str) -> SkillMetadata:
    """Parse SKILL.md content to extract metadata.

    Args:
        content: Raw content of SKILL.md file

    Returns:
        SkillMetadata object

    Example:
        >>> content = '''
        ... ---
        ... name: my-skill
        ... description: A test skill
        ... version: 1.0.0
        ... author: w00000001
        ... tags: test, demo
        ... ---
        ... '''
        >>> metadata = parse_skill_metadata(content)
        >>> print(metadata.name)
        my-skill
    """
    metadata = SkillMetadata()

    # Extract YAML frontmatter
    pattern = r'^---\s*\n(.*?)\n---\s*\n'
    match = re.match(pattern, content, re.DOTALL)

    if not match:
        logger.warning("No YAML frontmatter found in SKILL.md")
        return metadata

    yaml_content = match.group(1)
    metadata.raw_yaml = yaml_content

    try:
        data = yaml.safe_load(yaml_content)
        if not data:
            logger.warning("Empty YAML frontmatter")
            return metadata

        # Parse top-level fields
        metadata.name = data.get("name", "")
        metadata.description = data.get("description", "")

        # Parse metadata section
        meta = data.get("metadata", {})
        if isinstance(meta, dict):
            metadata.version = meta.get("version", "1.0.0")
            metadata.author = meta.get("author", "")
            metadata.tags = _parse_list(meta.get("tags"))
            metadata.category = meta.get("category")
            metadata.license = meta.get("license", "MIT")
            metadata.compatibility = meta.get("compatibility", "")
            metadata.allowed_tools = _parse_list(meta.get("allowed-tools"))
        else:
            # Backwards compatibility: fields at top level
            metadata.version = data.get("version", "1.0.0")
            metadata.author = data.get("author", "")
            metadata.tags = _parse_list(data.get("tags"))
            metadata.category = data.get("category")
            metadata.license = data.get("license", "MIT")
            metadata.compatibility = data.get("compatibility", "")
            metadata.allowed_tools = _parse_list(data.get("allowed-tools"))

    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML: {e}")

    return metadata


def _parse_list(value: Any) -> List[str]:
    """Parse value as list.

    Args:
        value: Value to parse (string, list, or None)

    Returns:
        List of strings
    """
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def read_skill_file(skill_dir: Path) -> Optional[SkillMetadata]:
    """Read and parse SKILL.md from a skill directory.

    Args:
        skill_dir: Path to skill directory

    Returns:
        SkillMetadata object or None if not found
    """
    skill_file = Path(skill_dir) / "SKILL.md"
    if not skill_file.exists():
        logger.warning(f"SKILL.md not found in {skill_dir}")
        return None

    try:
        content = skill_file.read_text(encoding="utf-8")
        return parse_skill_metadata(content)
    except Exception as e:
        logger.error(f"Failed to read SKILL.md: {e}")
        return None


def validate_skill_metadata(metadata: SkillMetadata) -> List[str]:
    """Validate skill metadata.

    Args:
        metadata: SkillMetadata to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    if not metadata.name:
        errors.append("name is required")
    elif not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$', metadata.name):
        errors.append("name must be lowercase alphanumeric with hyphens")

    if not metadata.version:
        errors.append("version is required")

    return errors
