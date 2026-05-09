"""Configuration loading for WatchBot — YAML-based with deep-merge defaults."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

try:
    from hermes_constants import get_hermes_home
except ImportError:
    def get_hermes_home() -> Path:
        return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


DEFAULT_CONFIG_PATH = get_hermes_home() / "watchbot.yaml"


WATCHER_DEFAULTS: Dict[str, Any] = {
    "homelab": {
        "host": "192.168.0.2",
        "user": "root",
        "port": 22,
        "key_path": str(Path.home() / ".ssh" / "id_ed25519"),
        "critical": [100, 105, 106, 107, 103, 104, 111],
        "optional": [101, 108, 109, 110, 115, 117, 128],
        "check_interval_seconds": 600,
    },
    "home_assistant": {
        "url": "http://192.168.0.244:8123",
        "token_env": "HA_TOKEN",
        "sensors": [
            "sensor.my_ecobee_current_temperature",
        ],
        "check_interval_seconds": 300,
    },
    "twitter": {
        "enabled": False,
        "check_interval_minutes": 15,
        "keywords": [],
    },
    "blogs": {
        "enabled": True,
        "check_interval_hours": 6,
        "feeds": [
            "https://blog.nousresearch.com/feed",
            "https://news.ycombinator.com/rss",
        ],
    },
    "system": {
        "disk_threshold_pct": 85,
        "mem_threshold_pct": 90,
        "cpu_threshold_pct": 95,
        "check_interval_seconds": 120,
    },
    "docker": {
        "enabled": True,
        "socket": "/var/run/docker.sock",
        "check_interval_seconds": 300,
    },
    "alerts": {
        "telegram": {
            "enabled": True,
            "chat_id": 642899617,
        },
        "email": {
            "enabled": False,
        },
    },
}


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load WatchBot config, merging user overrides on top of defaults.

    If the config file doesn't exist, a default is written to disk
    so the user can edit it.
    """
    cfg_path = path or DEFAULT_CONFIG_PATH
    cfg = dict(WATCHER_DEFAULTS)

    if cfg_path.exists():
        try:
            with open(cfg_path) as f:
                user_cfg = yaml.safe_load(f) or {}
            watchbot_cfg = user_cfg.get("watchbot", user_cfg)
            _deep_merge(cfg, watchbot_cfg)
        except (yaml.YAMLError, OSError) as e:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to load config from %s: %s", cfg_path, e
            )
    else:
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(cfg_path, "w") as f:
                yaml.dump({"watchbot": cfg}, f, default_flow_style=False,
                         allow_unicode=True, width=120)
        except OSError:
            pass

    return cfg


def _deep_merge(base: Dict, override: Dict) -> None:
    """Recursively merge *override* into *base*."""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


def get_monitor_config(name: str, cfg: Optional[Dict] = None) -> Dict:
    """Get config for a specific monitor."""
    if cfg is None:
        cfg = load_config()
    return cfg.get(name, {})
