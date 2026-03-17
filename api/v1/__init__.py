"""
API v1 module - Version 1 of the API.

Provides services, schemas, and dependencies for the SkillHub API.
Routes have been moved to apps/ directory.
"""

from . import services, schemas, dependencies

__all__ = ["services", "schemas", "dependencies"]
