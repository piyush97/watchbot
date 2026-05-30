"""Agent-facing tools for querying monitor data."""

from __future__ import annotations

from typing import Any, Dict

from watchbot.monitors import (
    blogwatcher,
    docker,
    homelab,
    home_assistant,
    system,
    x_twitter,
)


def get_dashboard_data(cfg: Dict) -> Dict[str, Any]:
    """Get aggregated dashboard data from all enabled monitors."""
    dashboard = {
        "timestamp": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "monitors": {},
    }

    # Proxmox LXC
    try:
        dashboard["monitors"]["homelab"] = homelab.get_lxc_summary(cfg)
    except Exception as e:
        dashboard["monitors"]["homelab"] = {"error": str(e)}

    # Home Assistant
    try:
        dashboard["monitors"]["home_assistant"] = home_assistant.get_ha_summary(cfg)
    except Exception as e:
        dashboard["monitors"]["home_assistant"] = {"error": str(e)}

    # System health
    try:
        dashboard["monitors"]["system"] = system.get_system_summary(cfg)
    except Exception as e:
        dashboard["monitors"]["system"] = {"error": str(e)}

    # Docker
    try:
        dashboard["monitors"]["docker"] = docker.get_docker_summary(cfg)
    except Exception as e:
        dashboard["monitors"]["docker"] = {"error": str(e)}

    # X/Twitter
    if cfg.get("twitter", {}).get("enabled", False):
        try:
            dashboard["monitors"]["twitter"] = x_twitter.get_twitter_summary(cfg)
        except Exception as e:
            dashboard["monitors"]["twitter"] = {"error": str(e)}

    # Blogs
    if cfg.get("blogs", {}).get("enabled", True):
        try:
            dashboard["monitors"]["blogs"] = blogwatcher.get_blog_summary(cfg)
        except Exception as e:
            dashboard["monitors"]["blogs"] = {"error": str(e)}

    # Aggregate health
    healths = [m.get("health", "unknown") for m in dashboard["monitors"].values()
               if isinstance(m, dict)]
    dashboard["health"] = (
        "critical" if "critical" in healths else
        "warning" if "warning" in healths else
        "ok" if healths else "unknown"
    )

    return dashboard
