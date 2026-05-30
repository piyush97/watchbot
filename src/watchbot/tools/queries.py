"""Agent-facing tools for querying specific monitors."""

from __future__ import annotations

from typing import Any, Dict, Optional

from watchbot.core.config import load_config
from watchbot.monitors import (
    blogwatcher,
    docker,
    homelab,
    home_assistant,
    system,
    x_twitter,
)


def query_monitor_tool(monitor: str, action: str = "summary",
                       **kwargs) -> Dict[str, Any]:
    """Tool handler: query a specific monitor for detailed data.

    Args:
        monitor: One of 'homelab', 'home_assistant', 'twitter', 'blogs',
                 'system', 'docker'
        action: 'summary' (default), 'detailed', or 'raw'
    """
    cfg = load_config()

    handlers = {
        "homelab": lambda: homelab.get_lxc_summary(cfg),
        "home_assistant": lambda: home_assistant.get_ha_summary(cfg),
        "twitter": lambda: x_twitter.get_twitter_summary(cfg),
        "blogs": lambda: blogwatcher.get_blog_summary(cfg),
        "system": lambda: system.get_system_summary(cfg),
        "docker": lambda: docker.get_docker_summary(cfg),
    }

    handler = handlers.get(monitor)
    if not handler:
        return {
            "error": f"Unknown monitor: {monitor}. Available: {', '.join(handlers.keys())}"
        }

    try:
        data = handler()
        return data
    except Exception as e:
        return {"error": str(e), "monitor": monitor}
