"""WatchBot — Unified homelab + social media monitoring plugin for Hermes Agent.

Wires 6 monitors into 4 agent tools, CLI commands, lifecycle hooks,
and a web dashboard. Uses the official Hermes ``register(ctx)`` API.

Monitors:
  - Proxmox LXC containers (SSH-based watchdog, auto-restart critical)
  - Home Assistant sensors (local REST API)
  - X/Twitter timeline + keyword search (via xurl CLI)
  - Blog/RSS feeds (blogwatcher-cli + feedparser fallback)
  - System health (disk, CPU, memory, temperature via /proc)
  - Docker containers (Unix socket API)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from watchbot.core import load_config
from watchbot.monitors import system as system_mon

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool schemas — what the LLM reads to decide when to call each tool
# ---------------------------------------------------------------------------

WATCHBOT_STATUS_SCHEMA: Dict[str, Any] = {
    "name": "watchbot_status",
    "description": (
        "Get WatchBot status across all monitors. Returns aggregated health "
        "data for Proxmox LXCs, Home Assistant sensors, system resources "
        "(disk/CPU/mem), Docker containers, X/Twitter, and blog feeds."
    ),
    "parameters": {"type": "object", "properties": {}},
}

WATCHBOT_ALERT_SCHEMA: Dict[str, Any] = {
    "name": "watchbot_alert",
    "description": (
        "Manage WatchBot alerts. Use 'list' to see active alerts, "
        "'ack' to dismiss, 'resolve' to mark resolved, or 'trigger' "
        "to create one manually."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "ack", "resolve", "trigger"],
                "description": "Alert action to perform",
            },
            "alert_id": {
                "type": "integer",
                "description": "Alert ID (required for ack/resolve)",
            },
            "source": {
                "type": "string",
                "description": "Alert source name for trigger (e.g. 'homelab')",
            },
            "severity": {
                "type": "string",
                "enum": ["info", "warning", "error", "critical"],
                "description": "Alert severity for trigger",
            },
            "title": {
                "type": "string",
                "description": "Alert title for trigger",
            },
            "message": {
                "type": "string",
                "description": "Optional alert message body",
            },
        },
        "required": ["action"],
    },
}

WATCHBOT_QUERY_SCHEMA: Dict[str, Any] = {
    "name": "watchbot_query",
    "description": (
        "Query a specific WatchBot monitor for detailed data. "
        "Monitors: homelab, home_assistant, twitter, blogs, system, docker."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "monitor": {
                "type": "string",
                "enum": [
                    "homelab", "home_assistant", "twitter",
                    "blogs", "system", "docker",
                ],
                "description": "Monitor to query",
            },
        },
        "required": ["monitor"],
    },
}

WATCHBOT_DASHBOARD_SCHEMA: Dict[str, Any] = {
    "name": "watchbot_dashboard",
    "description": (
        "Get dashboard-ready aggregated data from all monitors. "
        "Returns a structured dict with per-monitor health status."
    ),
    "parameters": {"type": "object", "properties": {}},
}


# ---------------------------------------------------------------------------
# Tool handlers — the code that runs when the LLM calls each tool
# ---------------------------------------------------------------------------

def _handle_status(args: dict, **kwargs) -> str:
    """Aggregated status across all monitors."""
    from watchbot.tools.dashboard import get_dashboard_data
    cfg = load_config()
    data = get_dashboard_data(cfg)
    return __import__("json").dumps(data, default=str)


def _handle_alert(args: dict, **kwargs) -> str:
    """Alert management — list, acknowledge, resolve, trigger."""
    from watchbot.tools.alerts import (
        acknowledge_alert_tool,
        get_alerts_tool,
        resolve_alert_tool,
        trigger_alert_tool,
    )
    action = args.get("action", "list")

    if action == "list":
        data = get_alerts_tool(
            source=args.get("source"),
            severity=args.get("severity"),
        )
    elif action == "ack":
        data = acknowledge_alert_tool(args.get("alert_id", 0))
    elif action == "resolve":
        data = resolve_alert_tool(args.get("alert_id", 0))
    elif action == "trigger":
        data = trigger_alert_tool(
            source=args.get("source", "manual"),
            severity=args.get("severity", "info"),
            title=args.get("title", "Manual alert"),
            message=args.get("message"),
        )
    else:
        data = {"error": f"Unknown action: {action}"}

    return __import__("json").dumps(data, default=str)


def _handle_query(args: dict, **kwargs) -> str:
    """Query a specific monitor by name."""
    from watchbot.tools.queries import query_monitor_tool
    data = query_monitor_tool(args.get("monitor", ""))
    return __import__("json").dumps(data, default=str)


def _handle_dashboard(args: dict, **kwargs) -> str:
    """Dashboard data — same as status."""
    return _handle_status(args, **kwargs)


# ---------------------------------------------------------------------------
# CLI command handler
# ---------------------------------------------------------------------------

def _watchbot_cli_handler(args) -> None:
    """Dispatch ``hermes watchbot <subcommand>``."""
    from watchbot.cli.commands import run_command
    import sys
    sys.exit(run_command(args))


def _watchbot_cli_setup(subparser) -> None:
    """Build the argparse tree for ``hermes watchbot``."""
    from watchbot.cli.commands import register_cli
    register_cli(subparser)


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------

def _on_session_end(**kwargs) -> None:
    """Log a summary of monitor states when a session ends."""
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


def _on_post_tool_call(tool_name: str, **kwargs) -> None:
    """Lightweight health check after tool calls (~5% sampling)."""
    try:
        import random
        if random.random() > 0.05:
            return
        cfg = load_config()
        health = system_mon.check_all(cfg)
        if health.get("cpu", {}).get("used_pct", 0) > 95:
            logger.warning("WatchBot: CPU spike (%.1f%%)", health["cpu"]["used_pct"])
    except Exception as e:
        logger.debug("WatchBot post_tool_call hook: %s", e)


# ---------------------------------------------------------------------------
# Official Hermes plugin registration
# ---------------------------------------------------------------------------

def register(ctx):
    """Register tools, hooks, CLI commands, and bundled skills.

    Called exactly once by Hermes at plugin load time.
    """
    # ── Register tools ──────────────────────────────────────────
    ctx.register_tool(
        name="watchbot_status",
        toolset="watchbot",
        schema=WATCHBOT_STATUS_SCHEMA,
        handler=_handle_status,
    )
    ctx.register_tool(
        name="watchbot_alert",
        toolset="watchbot",
        schema=WATCHBOT_ALERT_SCHEMA,
        handler=_handle_alert,
    )
    ctx.register_tool(
        name="watchbot_query",
        toolset="watchbot",
        schema=WATCHBOT_QUERY_SCHEMA,
        handler=_handle_query,
    )
    ctx.register_tool(
        name="watchbot_dashboard",
        toolset="watchbot",
        schema=WATCHBOT_DASHBOARD_SCHEMA,
        handler=_handle_dashboard,
    )

    # ── Register hooks ──────────────────────────────────────────
    ctx.register_hook("on_session_end", _on_session_end)
    ctx.register_hook("post_tool_call", _on_post_tool_call)

    # ── Register CLI subcommand (hermes watchbot ...) ───────────
    ctx.register_cli_command(
        name="watchbot",
        help="Unified homelab + social media monitoring",
        setup_fn=_watchbot_cli_setup,
        handler_fn=_watchbot_cli_handler,
    )

    # ── Register bundled skill (plugin:watchbot) ────────────────
    plugin_dir = Path(__file__).resolve().parent
    # Check both drop-in plugin layout and pip package layout
    for candidate in (
        plugin_dir / "SKILL.md",                     # ~/.hermes/plugins/watchbot/SKILL.md
        plugin_dir.parent.parent / "SKILL.md",       # pip src/ layout
    ):
        if candidate.exists():
            ctx.register_skill("watchbot", candidate)
            break
