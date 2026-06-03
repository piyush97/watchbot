"""WatchBot — Unified homelab + social media monitoring plugin for Hermes Agent.

This plugin wires monitors for:
  - Proxmox LXC containers (SSH-based watchdog)
  - Home Assistant sensors (local API)
  - X/Twitter timeline + keyword search
  - Blog/RSS feeds (blogwatcher-cli + feedparser)
  - System health (disk, CPU, memory, temperature)
  - Docker containers (Unix socket API)

Tools, CLI commands, hooks, and a web dashboard are provided.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from watchbot.core import load_config
from watchbot.monitors import system as system_mon

logger = logging.getLogger(__name__)

__all__ = [
    "register_tools",
    "register_cli",
    "on_session_end",
    "post_tool_call",
]


# ── Tool handlers ─────────────────────────────────────────────

def _handle_status(**kwargs) -> Dict[str, Any]:
    from watchbot.tools.dashboard import get_dashboard_data
    cfg = load_config()
    return get_dashboard_data(cfg)


def _handle_alert(**kwargs) -> Dict[str, Any]:
    from watchbot.tools.alerts import (
        acknowledge_alert_tool,
        get_alerts_tool,
        resolve_alert_tool,
        trigger_alert_tool,
    )
    action = kwargs.get("action", "list")

    if action == "list":
        return get_alerts_tool(
            source=kwargs.get("source"),
            severity=kwargs.get("severity"),
        )
    elif action == "ack":
        return acknowledge_alert_tool(kwargs.get("alert_id", 0))
    elif action == "resolve":
        return resolve_alert_tool(kwargs.get("alert_id", 0))
    elif action == "trigger":
        return trigger_alert_tool(
            source=kwargs.get("source", "manual"),
            severity=kwargs.get("severity", "info"),
            title=kwargs.get("title", "Manual alert"),
            message=kwargs.get("message"),
        )
    return {"error": f"Unknown action: {action}"}


def _handle_query(**kwargs) -> Dict[str, Any]:
    from watchbot.tools.queries import query_monitor_tool
    return query_monitor_tool(kwargs.get("monitor", ""))


def _handle_dashboard(**kwargs) -> Dict[str, Any]:
    return _handle_status(**kwargs)


# ── Tool schemas ───────────────────────────────────────────────

WATCHBOT_STATUS_SCHEMA: Dict[str, Any] = {
    "name": "watchbot_status",
    "description": "Get WatchBot status across all monitors. Returns aggregated health data for Proxmox, Home Assistant, system, Docker, X/Twitter, and blogs.",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

WATCHBOT_ALERT_SCHEMA: Dict[str, Any] = {
    "name": "watchbot_alert",
    "description": "Manage WatchBot alerts. Use 'list' to see active alerts, 'ack' to dismiss, 'resolve' to mark resolved, or 'trigger' to create one manually.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "ack", "resolve", "trigger"],
                "description": "Alert action",
            },
            "alert_id": {
                "type": "integer",
                "description": "Alert ID (for ack/resolve)",
            },
            "source": {
                "type": "string",
                "description": "Alert source (for trigger, e.g. 'homelab')",
            },
            "severity": {
                "type": "string",
                "enum": ["info", "warning", "error", "critical"],
                "description": "Alert severity (for trigger)",
            },
            "title": {
                "type": "string",
                "description": "Alert title (for trigger)",
            },
            "message": {
                "type": "string",
                "description": "Alert message (for trigger)",
            },
        },
        "required": ["action"],
    },
}

WATCHBOT_QUERY_SCHEMA: Dict[str, Any] = {
    "name": "watchbot_query",
    "description": "Query a specific WatchBot monitor for detailed data. Monitors: homelab, home_assistant, twitter, blogs, system, docker.",
    "parameters": {
        "type": "object",
        "properties": {
            "monitor": {
                "type": "string",
                "enum": ["homelab", "home_assistant", "twitter", "blogs", "system", "docker"],
                "description": "Monitor to query",
            },
        },
        "required": ["monitor"],
    },
}

WATCHBOT_DASHBOARD_SCHEMA: Dict[str, Any] = {
    "name": "watchbot_dashboard",
    "description": "Get dashboard-ready aggregated data from all monitors. Returns a structured dict with health status per monitor.",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

_TOOLS = (
    ("watchbot_status",    WATCHBOT_STATUS_SCHEMA,    _handle_status,    "👁️"),
    ("watchbot_alert",     WATCHBOT_ALERT_SCHEMA,     _handle_alert,     "🚨"),
    ("watchbot_query",     WATCHBOT_QUERY_SCHEMA,     _handle_query,     "🔍"),
    ("watchbot_dashboard", WATCHBOT_DASHBOARD_SCHEMA, _handle_dashboard, "📊"),
)


def register_tools() -> tuple:
    """Called by Hermes plugin loader to discover provided tools."""
    return _TOOLS


def register_cli(subparser) -> None:
    """Called by Hermes plugin loader to register CLI commands."""
    from watchbot.cli.commands import register_cli as _reg
    _reg(subparser)


# ── Hooks ──────────────────────────────────────────────────────

def on_session_end(**kwargs) -> None:
    """Runs at session end — logs a summary of monitor states."""
    try:
        cfg = load_config()
        from watchbot.core.state import save_snapshot
        from watchbot.tools.dashboard import get_dashboard_data
        data = get_dashboard_data(cfg)
        save_snapshot("watchbot_session_end", data)
        if data.get("health") in ("warning", "critical"):
            logger.info("WatchBot end-of-session health: %s", data["health"])
    except Exception as e:
        logger.debug("WatchBot on_session_end hook: %s", e)


def post_tool_call(result: Dict[str, Any], **kwargs) -> None:
    """Runs after each tool call — lightweight health check."""
    try:
        # Only run periodic health check (not on every tool call)
        import random
        if random.random() > 0.05:  # ~5% sampling
            return

        cfg = load_config()
        health = system_mon.check_all(cfg)
        if health.get("cpu", {}).get("used_pct", 0) > 95:
            logger.warning("WatchBot: CPU spike detected (%.1f%%)",
                          health["cpu"]["used_pct"])
    except Exception as e:
        logger.debug("WatchBot post_tool_call hook: %s", e)
