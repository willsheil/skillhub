"""
Logging configuration for SkillHub application.

Provides structured logging with JSON format, log rotation, audit logging,
performance tracking, and sensitive data masking.
"""

import logging
import logging.handlers
import json
import sys
import os
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from contextvars import ContextVar
from functools import wraps


# Context variable for request tracing
request_id_var: ContextVar[str] = ContextVar('request_id', default='')


class SensitiveDataFilter(logging.Filter):
    """Filter to mask sensitive data in log messages."""

    SENSITIVE_PATTERNS = [
        ('api_key', r'(api_key[=:]\s*)[\w-]+', r'\g<1>***'),
        ('token', r'(token[=:]\s*)[\w-]+', r'\g<1>***'),
        ('password', r'(password[=:]\s*)[\w-]+', r'\g<1>***'),
        ('authorization', r'(authorization[=:]\s*)[\w-]+', r'\g<1>***'),
    ]

    def __init__(self, enabled: bool = True):
        super().__init__()
        self.enabled = enabled
        if enabled:
            self.patterns = [
                (name, re.compile(pattern, re.IGNORECASE), repl)
                for name, pattern, repl in self.SENSITIVE_PATTERNS
            ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Mask sensitive data in log record."""
        if self.enabled and isinstance(record.msg, str):
            for name, pattern, repl in self.patterns:
                record.msg = pattern.sub(repl, record.msg)
        return True


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter."""

    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request ID if available
        req_id = request_id_var.get()
        if req_id:
            log_data["request_id"] = req_id

        # Add extra fields
        if self.include_extra:
            for key, value in record.__dict__.items():
                if key not in ('name', 'msg', 'args', 'created', 'filename',
                              'funcName', 'levelname', 'levelno', 'lineno',
                              'module', 'msecs', 'message', 'pathname', 'process',
                              'processName', 'relativeCreated', 'thread', 'threadName',
                              'exc_info', 'exc_text', 'stack_info'):
                    if not callable(value):
                        log_data[key] = value

        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class PlainFormatter(logging.Formatter):
    """Plain text formatter with timestamps."""

    def __init__(self):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def setup_logging(
    level: str = "INFO",
    log_dir: str = "./logs",
    enable_json: bool = True,
    enable_console: bool = True,
    mask_sensitive: bool = True,
) -> None:
    """Setup logging configuration.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files
        enable_json: Enable JSON structured logging to file
        enable_console: Enable console logging
        mask_sensitive: Enable sensitive data masking in logs
    """
    # Check environment variable to override
    mask_sensitive = os.getenv("LOG_MASK_SENSITIVE", str(mask_sensitive)).lower() == "true"
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        console_handler.setFormatter(PlainFormatter())
        console_handler.addFilter(SensitiveDataFilter(mask_sensitive))
        root_logger.addHandler(console_handler)

    # File handler with rotation
    if enable_json:
        file_handler = logging.handlers.RotatingFileHandler(
            log_path / "skillhub.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(StructuredFormatter())
        file_handler.addFilter(SensitiveDataFilter(mask_sensitive))
        root_logger.addHandler(file_handler)

    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        log_path / "error.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(StructuredFormatter())
    error_handler.addFilter(SensitiveDataFilter(mask_sensitive))
    root_logger.addHandler(error_handler)


def audit_log(action: str, user: Optional[str] = None, details: Optional[Dict] = None) -> None:
    """Log an audit event.

    Args:
        action: Action being audited
        user: User performing action
        details: Additional details
    """
    logger = logging.getLogger("skillhub.audit")
    log_data = {
        "action": action,
        "user": user,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    if details:
        log_data["details"] = details

    logger.info(json.dumps(log_data))


class PerformanceTracker:
    """Context manager for tracking operation performance."""

    def __init__(self, operation: str, logger_name: str = "skillhub.performance"):
        self.operation = operation
        self.logger = logging.getLogger(logger_name)
        self.start_time = 0.0
        self.end_time = 0.0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration_ms = (self.end_time - self.start_time) * 1000

        log_data = {
            "operation": self.operation,
            "duration_ms": round(duration_ms, 2),
            "status": "success" if exc_type is None else "error"
        }

        if exc_type:
            log_data["error"] = str(exc_val)

        self.logger.info(json.dumps(log_data))

    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        return (self.end_time - self.start_time) * 1000
