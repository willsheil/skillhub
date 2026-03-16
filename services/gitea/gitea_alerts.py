"""
Alert manager for Gitea push failures.

This module provides notification capabilities for push failures:
- Webhook notifications
- Email notifications (optional)
- Alert aggregation and throttling
- Severity-based alert routing

Configuration:
    GITEA_ALERT_WEBHOOK_URL: Webhook URL for alerts
    GITEA_ALERT_EMAIL_ENABLED: Enable email alerts (default: false)
    GITEA_ALERT_EMAIL_SMTP_HOST: SMTP server host
    GITEA_ALERT_EMAIL_SMTP_PORT: SMTP server port (default: 587)
    GITEA_ALERT_EMAIL_FROM: Sender email address
    GITEA_ALERT_EMAIL_TO: Comma-separated recipient list
    GITEA_ALERT_THROTTLE_MINUTES: Minimum minutes between alerts (default: 60)
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts."""
    PUSH_FAILED = "push_failed"
    PUSH_TIMEOUT = "push_timeout"
    AUTHENTICATION_ERROR = "authentication_error"
    NETWORK_ERROR = "network_error"
    DISK_FULL = "disk_full"
    WORKER_STALLED = "worker_stalled"


@dataclass
class Alert:
    """Alert data structure."""
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    task_id: Optional[int] = None
    skill_name: Optional[str] = None
    version: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "task_id": self.task_id,
            "skill_name": self.skill_name,
            "version": self.version,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


class AlertThrottler:
    """Throttle alerts to prevent spam."""

    def __init__(self, min_interval_minutes: int = 60):
        """Initialize throttler.

        Args:
            min_interval_minutes: Minimum minutes between similar alerts
        """
        self.min_interval = timedelta(minutes=min_interval_minutes)
        self.last_alerts: Dict[str, datetime] = {}

    def should_send(self, alert: Alert) -> bool:
        """Check if alert should be sent based on throttle rules.

        Args:
            alert: Alert to check

        Returns:
            True if alert should be sent
        """
        # Create throttle key based on alert type and task
        if alert.task_id:
            key = f"{alert.alert_type.value}:{alert.task_id}"
        else:
            key = alert.alert_type.value

        last_sent = self.last_alerts.get(key)
        if last_sent is None:
            return True

        # Check if enough time has passed
        return datetime.utcnow() - last_sent >= self.min_interval

    def record_sent(self, alert: Alert):
        """Record that an alert was sent.

        Args:
            alert: Alert that was sent
        """
        if alert.task_id:
            key = f"{alert.alert_type.value}:{alert.task_id}"
        else:
            key = alert.alert_type.value

        self.last_alerts[key] = datetime.utcnow()

    def cleanup_old_entries(self, older_than_hours: int = 24):
        """Clean up old entries from the throttle cache.

        Args:
            older_than_hours: Remove entries older than this many hours
        """
        cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
        self.last_alerts = {
            k: v for k, v in self.last_alerts.items()
            if v > cutoff
        }


class AlertManager:
    """Manager for sending push failure alerts."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize alert manager.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or self._load_config()
        self.throttler = AlertThrottler(
            min_interval_minutes=int(os.getenv("GITEA_ALERT_THROTTLE_MINUTES", "60"))
        )
        self.alert_history: List[Alert] = []
        self.max_history = int(os.getenv("GITEA_ALERT_HISTORY_SIZE", "1000"))

        logger.info("AlertManager initialized")

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables.

        Returns:
            Configuration dictionary
        """
        return {
            "webhook_url": os.getenv("GITEA_ALERT_WEBHOOK_URL"),
            "email_enabled": os.getenv("GITEA_ALERT_EMAIL_ENABLED", "false").lower() == "true",
            "email_smtp_host": os.getenv("GITEA_ALERT_EMAIL_SMTP_HOST", "localhost"),
            "email_smtp_port": int(os.getenv("GITEA_ALERT_EMAIL_SMTP_PORT", "587")),
            "email_from": os.getenv("GITEA_ALERT_EMAIL_FROM", "noreply@gitea-push.local"),
            "email_to": os.getenv("GITEA_ALERT_EMAIL_TO", "").split(",") if os.getenv("GITEA_ALERT_EMAIL_TO") else [],
        }

    async def send_alert(self, alert: Alert) -> bool:
        """Send an alert through configured channels.

        Args:
            alert: Alert to send

        Returns:
            True if alert was sent successfully
        """
        # Check throttle
        if not self.throttler.should_send(alert):
            logger.debug(f"Alert throttled: {alert.alert_type.value} for task {alert.task_id}")
            return False

        # Add to history
        self._add_to_history(alert)

        # Send webhook
        webhook_success = False
        if self.config.get("webhook_url"):
            webhook_success = await self._send_webhook(alert)

        # Send email
        email_success = False
        if self.config.get("email_enabled"):
            email_success = await self._send_email(alert)

        # Record sent if any channel succeeded
        if webhook_success or email_success:
            self.throttler.record_sent(alert)
            return True

        return False

    async def _send_webhook(self, alert: Alert) -> bool:
        """Send alert via webhook.

        Args:
            alert: Alert to send

        Returns:
            True if webhook sent successfully
        """
        import aiohttp

        webhook_url = self.config.get("webhook_url")
        if not webhook_url:
            return False

        try:
            payload = {
                "timestamp": alert.timestamp.isoformat(),
                "severity": alert.severity.value,
                "type": alert.alert_type.value,
                "title": alert.title,
                "message": alert.message,
                "details": alert.to_dict()
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Webhook alert sent: {alert.title}")
                        return True
                    else:
                        logger.warning(f"Webhook returned status {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False

    async def _send_email(self, alert: Alert) -> bool:
        """Send alert via email.

        Args:
            alert: Alert to send

        Returns:
            True if email sent successfully
        """
        if not self.config.get("email_enabled"):
            return False

        recipients = self.config.get("email_to", [])
        if not recipients:
            logger.warning("Email alerts enabled but no recipients configured")
            return False

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"
            msg['From'] = self.config['email_from']
            msg['To'] = ", ".join(recipients)

            # Create HTML body
            html_body = self._format_email_html(alert)
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(self.config['email_smtp_host'], self.config['email_smtp_port']) as server:
                server.starttls()
                server.send_message(msg)

            logger.info(f"Email alert sent to {len(recipients)} recipients")
            return True

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False

    def _format_email_html(self, alert: Alert) -> str:
        """Format alert as HTML email.

        Args:
            alert: Alert to format

        Returns:
            HTML string
        """
        severity_colors = {
            AlertSeverity.INFO: "#3498db",
            AlertSeverity.WARNING: "#f39c12",
            AlertSeverity.ERROR: "#e74c3c",
            AlertSeverity.CRITICAL: "#8e44ad"
        }

        color = severity_colors.get(alert.severity, "#333333")

        html = f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background-color: {color}; color: white; padding: 20px; border-radius: 5px 5px 0 0;">
                    <h2 style="margin: 0;">{alert.title}</h2>
                    <p style="margin: 5px 0 0 0; opacity: 0.9;">Severity: {alert.severity.value.upper()}</p>
                </div>
                <div style="background-color: #f8f9fa; padding: 20px; border: 1px solid #dee2e6; border-radius: 0 0 5px 5px;">
                    <p><strong>Message:</strong> {alert.message}</p>
        """

        if alert.skill_name:
            html += f'<p><strong>Skill:</strong> {alert.skill_name}'
            if alert.version:
                html += f' (version {alert.version})'
            html += '</p>'

        if alert.task_id:
            html += f'<p><strong>Task ID:</strong> {alert.task_id}</p>'

        if alert.error_message:
            html += f'<p><strong>Error:</strong><br><code style="background-color: #e9ecef; padding: 2px 5px; border-radius: 3px;">{alert.error_message}</code></p>'

        if alert.retry_count is not None:
            html += f'<p><strong>Retry Count:</strong> {alert.retry_count}</p>'

        html += f"""
                    <p style="margin-top: 20px; font-size: 12px; color: #6c757d;">
                        Timestamp: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def _add_to_history(self, alert: Alert):
        """Add alert to history.

        Args:
            alert: Alert to add
        """
        self.alert_history.append(alert)

        # Trim history if needed
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent alert history.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of alert dictionaries
        """
        recent = self.alert_history[-limit:]
        return [alert.to_dict() for alert in recent]

    def get_stats(self) -> Dict[str, Any]:
        """Get alert statistics.

        Returns:
            Statistics dictionary
        """
        if not self.alert_history:
            return {"total": 0, "by_severity": {}, "by_type": {}}

        by_severity = {}
        by_type = {}

        for alert in self.alert_history:
            # Count by severity
            sev = alert.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1

            # Count by type
            at = alert.alert_type.value
            by_type[at] = by_type.get(at, 0) + 1

        return {
            "total": len(self.alert_history),
            "by_severity": by_severity,
            "by_type": by_type
        }


async def send_failure_alert(task: Dict[str, Any], error: str, alert_manager: AlertManager):
    """Send a push failure alert.

    Args:
        task: Task dictionary from database
        error: Error message
        alert_manager: AlertManager instance
    """
    alert = Alert(
        alert_type=AlertType.PUSH_FAILED,
        severity=AlertSeverity.ERROR,
        title=f"Gitea Push Failed: {task.get('skill_name', 'Unknown')}",
        message=f"Failed to push skill {task.get('skill_name', 'Unknown')} to Gitea repository",
        task_id=task.get('id'),
        skill_name=task.get('skill_name'),
        version=task.get('version'),
        error_message=error,
        retry_count=task.get('retry_count', 0)
    )

    await alert_manager.send_alert(alert)


async def send_timeout_alert(task: Dict[str, Any], timeout_seconds: int, alert_manager: AlertManager):
    """Send a push timeout alert.

    Args:
        task: Task dictionary from database
        timeout_seconds: Timeout duration
        alert_manager: AlertManager instance
    """
    alert = Alert(
        alert_type=AlertType.PUSH_TIMEOUT,
        severity=AlertSeverity.WARNING,
        title=f"Gitea Push Timeout: {task.get('skill_name', 'Unknown')}",
        message=f"Push operation for skill {task.get('skill_name', 'Unknown')} timed out after {timeout_seconds} seconds",
        task_id=task.get('id'),
        skill_name=task.get('skill_name'),
        version=task.get('version'),
        metadata={"timeout_seconds": timeout_seconds}
    )

    await alert_manager.send_alert(alert)


async def send_authentication_error_alert(error: str, alert_manager: AlertManager):
    """Send an authentication error alert.

    Args:
        error: Error message
        alert_manager: AlertManager instance
    """
    alert = Alert(
        alert_type=AlertType.AUTHENTICATION_ERROR,
        severity=AlertSeverity.CRITICAL,
        title="Gitea Authentication Error",
        message=f"Failed to authenticate with Gitea: {error}",
        error_message=error
    )

    await alert_manager.send_alert(alert)
