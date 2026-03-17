"""
Prometheus metrics for Gitea push operations.

This module provides Prometheus metrics for monitoring:
- Push attempts and success/failure rates
- Push operation duration
- Queue length by status
- Last successful push timestamp

Requires: pip install prometheus_client
"""

import logging
import time
from typing import Optional
from datetime import datetime

try:
    from prometheus_client import Counter, Histogram, Gauge, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logging.warning("prometheus_client not installed. Metrics will be disabled.")

logger = logging.getLogger(__name__)


class GiteaPushMetrics:
    """Prometheus metrics collector for Gitea push operations."""

    def __init__(self, enabled: bool = True):
        """Initialize metrics collector.

        Args:
            enabled: Whether to enable metrics collection
        """
        self.enabled = enabled and PROMETHEUS_AVAILABLE

        if not self.enabled:
            logger.info("Prometheus metrics disabled")
            return

        # Push attempt counter
        self.push_attempts = Counter(
            'gitea_push_attempts_total',
            'Total number of push attempts',
            ['status', 'skill_name']
        )

        # Push duration histogram
        self.push_duration = Histogram(
            'gitea_push_duration_seconds',
            'Time taken to complete push operations',
            ['skill_name'],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 300.0]
        )

        # Queue length gauge
        self.queue_length = Gauge(
            'gitea_queue_length',
            'Number of tasks in queue by status',
            ['status']
        )

        # Last push success timestamp
        self.last_push_success = Gauge(
            'gitea_last_push_success_timestamp',
            'Unix timestamp of last successful push'
        )

        # Active workers gauge
        self.active_workers = Gauge(
            'gitea_active_workers',
            'Number of active worker processes'
        )

        # Task reservation gauge
        self.reserved_tasks = Gauge(
            'gitea_reserved_tasks',
            'Number of currently reserved tasks'
        )

        logger.info("Prometheus metrics initialized")

    def record_push_attempt(self, status: str, skill_name: str):
        """Record a push attempt.

        Args:
            status: Status of the push ('success', 'failed', 'retry')
            skill_name: Name of the skill being pushed
        """
        if not self.enabled:
            return

        self.push_attempts.labels(status=status, skill_name=skill_name).inc()
        logger.debug(f"Recorded push attempt: {status} for {skill_name}")

    def record_push_duration(self, skill_name: str, duration_seconds: float):
        """Record the duration of a push operation.

        Args:
            skill_name: Name of the skill being pushed
            duration_seconds: Time taken in seconds
        """
        if not self.enabled:
            return

        self.push_duration.labels(skill_name=skill_name).observe(duration_seconds)
        logger.debug(f"Recorded push duration: {duration_seconds:.2f}s for {skill_name}")

    def record_push_success(self):
        """Update the last successful push timestamp."""
        if not self.enabled:
            return

        self.last_push_success.set(time.time())
        logger.debug("Updated last push success timestamp")

    def update_queue_length(self, status: str, count: int):
        """Update the queue length for a specific status.

        Args:
            status: Task status ('pending', 'pushing', 'success', 'failed')
            count: Number of tasks with this status
        """
        if not self.enabled:
            return

        self.queue_length.labels(status=status).set(count)
        logger.debug(f"Updated queue length: {status}={count}")

    def update_queue_lengths(self, counts: dict):
        """Update queue lengths for all statuses.

        Args:
            counts: Dictionary mapping status to count
        """
        if not self.enabled:
            return

        for status, count in counts.items():
            self.update_queue_length(status, count)

    def set_active_workers(self, count: int):
        """Set the number of active workers.

        Args:
            count: Number of active worker processes
        """
        if not self.enabled:
            return

        self.active_workers.set(count)
        logger.debug(f"Updated active workers: {count}")

    def set_reserved_tasks(self, count: int):
        """Set the number of currently reserved tasks.

        Args:
            count: Number of reserved tasks
        """
        if not self.enabled:
            return

        self.reserved_tasks.set(count)
        logger.debug(f"Updated reserved tasks: {count}")

    def start_metrics_server(self, port: int = 8000):
        """Start the Prometheus metrics HTTP server.

        Args:
            port: Port to listen on (default: 8000)
        """
        if not self.enabled:
            logger.warning("Cannot start metrics server: metrics disabled")
            return

        try:
            start_http_server(port)
            logger.info(f"Prometheus metrics server started on port {port}")
            logger.info(f"Metrics available at http://localhost:{port}/metrics")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")


# Global metrics instance
_metrics: Optional[GiteaPushMetrics] = None


def init_metrics(enabled: bool = True, port: Optional[int] = None) -> GiteaPushMetrics:
    """Initialize the global metrics collector.

    Args:
        enabled: Whether to enable metrics collection
        port: Optional port to start metrics server on

    Returns:
        GiteaPushMetrics instance
    """
    global _metrics
    _metrics = GiteaPushMetrics(enabled=enabled)

    if port is not None:
        _metrics.start_metrics_server(port=port)

    return _metrics


def get_metrics() -> Optional[GiteaPushMetrics]:
    """Get the global metrics instance.

    Returns:
        GiteaPushMetrics instance or None if not initialized
    """
    return _metrics


class PushOperationTimer:
    """Context manager for timing push operations.

    Usage:
        with PushOperationTimer(skill_name) as timer:
            result = push_skill(...)
        timer.record_success()  # or timer.record_failure()
    """

    def __init__(self, skill_name: str, metrics: Optional[GiteaPushMetrics] = None):
        """Initialize timer.

        Args:
            skill_name: Name of the skill being pushed
            metrics: Optional metrics instance (uses global if not provided)
        """
        self.skill_name = skill_name
        self.metrics = metrics or get_metrics()
        self.start_time = None
        self.duration = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            self.duration = time.time() - self.start_time

    def record_success(self):
        """Record a successful push."""
        if self.metrics and self.duration is not None:
            self.metrics.record_push_attempt('success', self.skill_name)
            self.metrics.record_push_duration(self.skill_name, self.duration)
            self.metrics.record_push_success()

    def record_failure(self, fatal: bool = False):
        """Record a failed push.

        Args:
            fatal: Whether the failure is fatal (non-retryable)
        """
        if self.metrics and self.duration is not None:
            status = 'failed_fatal' if fatal else 'failed_retry'
            self.metrics.record_push_attempt(status, self.skill_name)
            self.metrics.record_push_duration(self.skill_name, self.duration)

    def record_retry(self):
        """Record a retry attempt."""
        if self.metrics and self.duration is not None:
            self.metrics.record_push_attempt('retry', self.skill_name)
