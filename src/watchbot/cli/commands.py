"""CLI commands for WatchBot — ``hermes watchbot <command>``."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict

from watchbot.core.config import load_config
from watchbot.core.state import get_active_alerts
from watchbot.monitors import (
    blogwatcher,
    docker,
    homelab,
    home_assistant,
    system,
    x_twitter,
)
from watchbot.tools.dashboard import get_dashboard_data

logger = logging.getLogger(__name__)


def register_cli(subparser: argparse.ArgumentParser) -> None:
    """Register ``hermes watchbot`` subcommands."""
    subs = subparser.add_subparsers(dest="watchbot_command")

    subs.add_parser("status", help="Overall WatchBot status across all monitors")
    subs.add_parser("health", help="System health snapshot (disk, CPU, memory)")
    subs.add_parser("lxc", help="Proxmox LXC container status")
    subs.add_parser("ha", help="Home Assistant sensor values")
    subs.add_parser("twitter", help="X/Twitter timeline and keyword matches")
    subs.add_parser("blogs", help="Blog/RSS feed latest posts")
    subs.add_parser("docker", help="Docker container status")
    subs.add_parser("alerts", help="Active alerts")
    subs.add_parser("dashboard", help="Start the dashboard web server")
    subs.add_parser("setup", help="Initial setup wizard")

    # Status command with optional format
    status_p = subs.add_parser("status", help="Formatted status")
    status_p.add_argument("--json", action="store_true", help="Output as JSON")
    status_p.add_argument("--monitor", default=None, help="Filter to one monitor")


def run_command(args: argparse.Namespace) -> int:
    """Dispatch CLI commands."""
    cfg = load_config()
    cmd = getattr(args, "watchbot_command", None) or "status"

    if cmd == "status":
        data = get_dashboard_data(cfg)
        if getattr(args, "json", False) or "JSON" in os.environ.get("WATCHBOT_OUTPUT", ""):
            print(json.dumps(data, indent=2, default=str))
        else:
            _print_status(data)
        return 0

    handlers = {
        "health": lambda: _print_health(system.get_system_summary(cfg)),
        "lxc": lambda: _print_lxc(homelab.get_lxc_summary(cfg)),
        "ha": lambda: _print_ha(home_assistant.get_ha_summary(cfg)),
        "twitter": lambda: _print_twitter(x_twitter.get_twitter_summary(cfg)),
        "blogs": lambda: _print_blogs(blogwatcher.get_blog_summary(cfg)),
        "docker": lambda: _print_docker(docker.get_docker_summary(cfg)),
        "alerts": lambda: _print_alerts(get_active_alerts()),
        "setup": lambda: _run_setup(cfg),
        "dashboard": lambda: _run_dashboard(cfg),
    }

    handler = handlers.get(cmd)
    if handler:
        handler()
        return 0

    print(f"Unknown command: {cmd}")
    return 1


def _print_status(data: Dict[str, Any]) -> None:
    """Print a formatted status overview."""
    print("═" * 50)
    print("  WatchBot — System Status")
    print("═" * 50)

    health_emoji = {"ok": "✅", "warning": "⚠️", "critical": "🔥", "unknown": "❓"}
    emoji = health_emoji.get(data.get("health", "unknown"), "❓")
    print(f"\n  Overall Health: {emoji}  {data['health'].upper()}")
    print(f"  Timestamp: {data.get('timestamp', '?')[:19]}")

    for name, monitor in data.get("monitors", {}).items():
        if isinstance(monitor, dict):
            mhealth = monitor.get("health", "?")
            emoji = health_emoji.get(mhealth, "❓")
            print(f"\n  {emoji}  {name}")
            for key, val in monitor.items():
                if key not in ("health", "timestamp", "error") and not isinstance(val, (dict, list)):
                    print(f"       {key}: {val}")
        elif isinstance(monitor, str):
            print(f"\n  ❌  {name}: {monitor}")


def _print_health(data: Dict[str, Any]) -> None:
    print("\n── System Health ──\n")
    for comp in ("disk", "memory", "cpu"):
        info = data.get(comp, {})
        if "used_pct" in info:
            bar = "█" * int(info["used_pct"] / 5) + "░" * (20 - int(info["used_pct"] / 5))
            print(f"  {comp.upper():8s}  {info['used_pct']:5.1f}%  {bar}")
    if data.get("temperature"):
        print(f"  TEMP      {data['temperature']}°C")
    print()


def _print_lxc(data: Dict[str, Any]) -> None:
    print(f"\n── Proxmox LXCs ({data.get('running', 0)}/{data.get('total', 0)} running) ──\n")
    for c in data.get("critical_down", []):
        print(f"  🔥 CRITICAL: LXC {c['vmid']} ({c.get('name', '?')}) is DOWN")
    for c in data.get("optional_down", []):
        print(f"  ⚠️  OPTIONAL: LXC {c['vmid']} ({c.get('name', '?')}) is DOWN")
    if not data.get("critical_down") and not data.get("optional_down"):
        print("  ✅ All containers running")


def _print_ha(data: Dict[str, Any]) -> None:
    print("\n── Home Assistant Sensors ──\n")
    for name, val in data.get("sensors", {}).items():
        print(f"  {name:40s} {val}")


def _print_twitter(data: Dict[str, Any]) -> None:
    print(f"\n── X/Twitter ──\n")
    print(f"  Enabled: {data.get('enabled', False)}")
    print(f"  Timeline tweets: {data.get('timeline_tweets', 0)}")
    print(f"  Keyword matches: {data.get('keyword_matches', 0)}")


def _print_blogs(data: Dict[str, Any]) -> None:
    print(f"\n── Blog/RSS Feeds ──\n")
    print(f"  Enabled: {data.get('enabled', True)}")
    print(f"  New posts: {data.get('new_posts', 0)}")
    for post in data.get("latest_posts", []):
        print(f"  📰 {post.get('title', '?')}")
        print(f"     {post.get('url', '')}")


def _print_docker(data: Dict[str, Any]) -> None:
    print(f"\n── Docker ({data.get('running', 0)}/{data.get('total', 0)} running) ──\n")
    for c in data.get("containers", []):
        icon = "✅" if c.get("state") == "running" else "⏹️"
        name = c.get("name", "?")
        restarts = c.get("restarts", 0)
        restart_tag = f" (restarts: {restarts})" if restarts > 0 else ""
        print(f"  {icon}  {name:30s} {c.get('state', '?')}{restart_tag}")


def _print_alerts(alerts: list) -> None:
    from watchbot.core.alerts import build_alert_summary
    print(f"\n{build_alert_summary()}\n")


def _run_setup(cfg: Dict) -> None:
    """Run the initial setup wizard."""
    print("\n═══ WatchBot Setup ═══\n")
    print("This will configure WatchBot for your environment.\n")

    # Check SSH access to Proxmox
    host = cfg.get("homelab", {}).get("host", "192.168.0.2")
    key = cfg.get("homelab", {}).get("key_path", "~/.ssh/id_ed25519")
    print(f"  [1/4] Proxmox host: {host}")
    print(f"        SSH key: {os.path.expanduser(key)}")
    if os.path.exists(os.path.expanduser(key)):
        print(f"        ✅ SSH key found")
    else:
        print(f"        ❌ SSH key not found at {key}")

    # Check Home Assistant
    ha_url = cfg.get("home_assistant", {}).get("url", "http://192.168.0.244:8123")
    ha_token = os.environ.get(cfg.get("home_assistant", {}).get("token_env", "HA_TOKEN"), "")
    print(f"\n  [2/4] Home Assistant: {ha_url}")
    print(f"        Token set: {'✅ Yes' if ha_token else '❌ No (set HA_TOKEN env var)'}")

    # Check X/Twitter
    tw_enabled = cfg.get("twitter", {}).get("enabled", False)
    print(f"\n  [3/4] X/Twitter monitoring: {'✅ Enabled' if tw_enabled else '⏹️  Disabled'}")
    if not tw_enabled:
        print("        Enable via watchbot.yaml: watchbot.twitter.enabled: true")

    # Check Docker socket
    docker_socket = cfg.get("docker", {}).get("socket", "/var/run/docker.sock")
    print(f"\n  [4/4] Docker socket: {docker_socket}")
    print(f"        {'✅ Accessible' if os.path.exists(docker_socket) else '❌ Not found'}")

    print("\n── Setup complete ──")
    print("Edit ~/.hermes/watchbot.yaml to customize monitors.")
    print("Run 'hermes watchbot status' to check everything.")


def _run_dashboard(cfg: Dict) -> None:
    """Start the web dashboard server."""
    try:
        from watchbot.web.dashboard import run_dashboard
    except ImportError:
        print("Dashboard requires: pip install watchbot[dashboard]")
        print("  Or: pip install flask plotly")
        return
    run_dashboard(cfg)
