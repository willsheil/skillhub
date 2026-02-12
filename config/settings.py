"""
Configuration settings for Claude Code Skill Registry.

This module contains all configuration constants and logging setup.
"""

import logging
import logging.handlers
import json
import os
import re
import sys
import time
from contextvars import ContextVar
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Dict, Optional


# ============================================================================
# Directory Paths
# ============================================================================

PLUGINS_DIR = Path(os.getenv("PLUGINS_DIR", "./plugins"))
PLUGINS_DIR.mkdir(exist_ok=True)

DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)

PENDING_DIR = DATA_DIR / "pending"
PENDING_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Admin Credentials
# ============================================================================

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # 默认密码，生产环境应修改


# ============================================================================
# Security
# ============================================================================

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")


# ============================================================================
# Logging Configuration
# ============================================================================

# Context variable for request tracing
request_id_var: ContextVar[str] = ContextVar('request_id', default='')


class SensitiveDataFilter(logging.Filter):
    """Filter to mask sensitive data in log messages.

    Masks patterns like:
    - API keys
    - Tokens
    - Passwords
    - Employee IDs (partial)
    """

    SENSITIVE_PATTERNS = [
        ('api_key', r'(api_key[\'":\s]+)[\w-]+', r'\g<1>***'),
        ('token', r'(token[\'":\s]+)[\w-]+', r'\g<1>***'),
        ('password', r'(password[\'":\s]+)[\w-]+', r'\g<1>***'),
        ('authorization', r'(authorization[\'":\s]+)[\w-]+', r'\g<1>***'),
        ('employee_id', r'(employee_id[\'":\s]+)\d{2}(\d{4})', r'\g<1>***\g<2>'),
    ]

    def __init__(self):
        super().__init__()
        self.patterns = [(name, re.compile(pattern, re.IGNORECASE), repl)
                        for name, pattern, repl in self.SENSITIVE_PATTERNS]

    def filter(self, record):
        """Mask sensitive data in log record."""
        if isinstance(record.msg, str):
            for name, pattern, repl in self.patterns:
                record.msg = pattern.sub(repl, record.msg)

        # Also filter in extra fields
        for key, value in record.__dict__.items():
            if isinstance(value, str) and key not in ('name', 'msg', 'funcName', 'pathname'):
                # Apply patterns to the value
                for name, pattern, repl in self.patterns:
                    record.__dict__[key] = pattern.sub(repl, value)
                    value = record.__dict__[key]  # Update for next pattern

                # Special handling for known sensitive fields
                # If the value itself looks like a sensitive pattern, mask it
                if key == 'employee_id' and len(value) == 6 and value.isdigit():
                    record.__dict__[key] = f"***{value[-4:]}"
                elif key in ('api_key', 'token', 'password', 'authorization'):
                    if value and not value.startswith('***'):
                        record.__dict__[key] = '***'

        return True


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter.

    Output format:
    {
        "timestamp": "2025-02-09T10:30:00.123Z",
        "level": "INFO",
        "logger": "gitea_client",
        "message": "Push successful",
        "request_id": "abc123",
        "context": {
            "skill_name": "my-skill",
            "version": "1.0.0"
        },
        "performance": {
            "duration_ms": 1234
        }
    }
    """

    def __init__(self):
        super().__init__()
        self.converter = time.gmtime

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Extract base fields
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add request ID if available
        request_id = request_id_var.get(None)
        if request_id:
            log_data["request_id"] = request_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }

        # Add extra fields as context
        for key, value in record.__dict__.items():
            if key not in {'name', 'msg', 'args', 'levelname', 'levelno',
                          'pathname', 'filename', 'module', 'exc_info',
                          'exc_text', 'stack_info', 'lineno', 'funcName',
                          'created', 'msecs', 'relativeCreated', 'thread',
                          'threadName', 'processName', 'process', 'message',
                          'asctime', 'asctime'}:
                if not key.startswith('_'):
                    log_data.setdefault("context", {})[key] = value

        return json.dumps(log_data, ensure_ascii=False)


class AuditHandler(logging.Handler):
    """Custom handler for audit logging.

    Writes audit logs to a separate file for compliance and security.
    """

    AUDIT_ACTIONS = {
        'user_login', 'user_logout', 'skill_upload', 'skill_download',
        'skill_approve', 'skill_reject', 'admin_access', 'config_change',
        'gitea_push', 'gitea_push_failed', 'user_create', 'user_delete'
    }

    def __init__(self, filename: str):
        super().__init__()
        self.filename = Path(filename)
        self.filename.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, record: logging.LogRecord):
        """Write audit log entry."""
        try:
            # Only log audit actions
            if getattr(record, 'action', None) not in self.AUDIT_ACTIONS:
                return

            audit_data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "action": getattr(record, 'action', 'unknown'),
                "user": getattr(record, 'user_id', 'system'),
                "ip_address": getattr(record, 'ip_address', '-'),
                "user_agent": getattr(record, 'user_agent', '-'),
                "result": getattr(record, 'result', 'success'),
                "details": {
                    k: v for k, v in record.__dict__.items()
                    if k not in {'name', 'msg', 'args', 'levelname', 'created',
                               'msecs', 'relativeCreated', 'thread', 'process',
                               'processName', 'message', 'exc_info', 'exc_text'}
                }
            }

            with open(self.filename, 'a', encoding='utf-8') as f:
                f.write(json.dumps(audit_data, ensure_ascii=False) + '\n')

        except Exception:
            self.handleError(record)


class PerformanceTracker:
    """Track performance metrics for operations.

    Usage:
        with PerformanceTracker(logger, "operation_name", context={"key": "value"}):
            # do work
            pass
    """

    def __init__(self, logger: logging.Logger, operation: str,
                 threshold_ms: int = 1000, **context):
        self.logger = logger
        self.operation = operation
        self.threshold_ms = threshold_ms
        self.context = context
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000

        # Add performance data to context
        perf_context = {
            **self.context,
            "performance": {
                "operation": self.operation,
                "duration_ms": round(duration_ms, 2),
                "slow": duration_ms > self.threshold_ms
            }
        }

        # Log warning if operation is slow
        if duration_ms > self.threshold_ms:
            self.logger.warning(
                f"Slow operation: {self.operation} took {duration_ms:.2f}ms",
                extra=perf_context
            )
        elif exc_type is None:
            self.logger.debug(
                f"Operation completed: {self.operation}",
                extra=perf_context
            )


def setup_logging(
    level: str = os.getenv("LOG_LEVEL", "INFO"),
    log_dir: str = "./logs",
    enable_json: bool = True,
    enable_console: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """Setup application logging with handlers.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files
        enable_json: Enable JSON structured logging
        enable_console: Enable console output
        max_bytes: Max size per log file before rotation
        backup_count: Number of backup files to keep

    Returns:
        Root logger instance
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Sensitive data filter
    sensitive_filter = SensitiveDataFilter()

    # JSON file handler for structured logs
    if enable_json:
        json_handler = logging.handlers.RotatingFileHandler(
            log_path / "application.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        json_handler.setFormatter(StructuredFormatter())
        json_handler.addFilter(sensitive_filter)
        root_logger.addHandler(json_handler)

    # Error log file
    error_handler = logging.handlers.RotatingFileHandler(
        log_path / "error.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(StructuredFormatter())
    error_handler.addFilter(sensitive_filter)
    root_logger.addHandler(error_handler)

    # Audit log handler
    audit_handler = AuditHandler(log_path / "audit.log")
    audit_handler.setLevel(logging.INFO)
    root_logger.addHandler(audit_handler)

    # Console handler (human readable for development)
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(sensitive_filter)
        root_logger.addHandler(console_handler)

    return root_logger


def audit_log(logger: logging.Logger, action: str, **kwargs):
    """Log an audit event.

    Args:
        logger: Logger instance
        action: Action type (user_login, skill_upload, etc.)
        **kwargs: Additional context (user_id, ip_address, etc.)
    """
    logger.info(
        f"Audit: {action}",
        extra={
            "action": action,
            **kwargs
        }
    )


def log_performance(logger: logging.Logger, operation: str, **context):
    """Decorator to log function performance.

    Usage:
        @log_performance(logger, "database_query")
        def query_data():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                logger.debug(
                    f"Performance: {operation} completed in {duration_ms:.2f}ms",
                    extra={
                        "operation": operation,
                        "duration_ms": duration_ms,
                        **context
                    }
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"Performance: {operation} failed after {duration_ms:.2f}ms",
                    extra={
                        "operation": operation,
                        "duration_ms": duration_ms,
                        "error": str(e),
                        **context
                    },
                    exc_info=True
                )
                raise
        return wrapper
    return decorator
