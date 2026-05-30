"""Agent-facing tools for alert management."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from watchbot.core.alerts import build_alert_summary, dispatch_alert
from watchbot.core.state import dismiss_alert, get_active_alerts, resolve_alert


def get_alerts_tool(source: Optional[str] = None,
                    severity: Optional[str] = None,
                    limit: int = 20) -> Dict[str, Any]:
    """Tool handler: get active alerts with optional filters."""
    alerts = get_active_alerts(source=source, severity=severity)
    return {
        "count": len(alerts),
        "alerts": alerts[:limit],
        "summary": build_alert_summary(limit),
    }


def acknowledge_alert_tool(alert_id: int) -> Dict[str, Any]:
    """Tool handler: dismiss an alert."""
    success = dismiss_alert(alert_id)
    return {"success": success, "alert_id": alert_id}


def resolve_alert_tool(alert_id: int) -> Dict[str, Any]:
    """Tool handler: mark an alert as resolved."""
    success = resolve_alert(alert_id)
    return {"success": success, "alert_id": alert_id}


def trigger_alert_tool(source: str, severity: str, title: str,
                       message: Optional[str] = None) -> Dict[str, Any]:
    """Tool handler: manually trigger an alert."""
    alert_id = dispatch_alert(source, severity, title, message, force=True)
    return {"alert_id": alert_id, "success": alert_id is not None}
