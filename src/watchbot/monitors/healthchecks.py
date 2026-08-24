"""Healthchecks.io cron-ping monitoring.

Fetches the project's checks via the Healthchecks.io Management API v3 and
alerts when a check is late (grace window open) or down (grace expired — a
missed deadline). Reuses the existing per-monitor module contract: a pure
``parse_status`` / ``evaluate_check`` core plus a ``get_healthchecks_summary``
fetch that dispatches deduplicated alerts.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from watchbot.core.alerts import dispatch_alert
from watchbot.core.config import get_monitor_config
from watchbot.core.state import get_state, save_snapshot, set_state

logger = logging.getLogger(__name__)

MONITOR_NAME = "healthchecks"

API_BASE = "https://healthchecks.io"

# Healthchecks.io Management API v3 check status values.
#   up     -> last ping arrived on time
#   grace  -> ping overdue but grace window still open (UI: "late")
#   down   -> grace expired; expected ping never arrived (missed deadline)
#   new    -> never received a ping
#   paused -> monitoring disabled
_STATUS_MAP: Dict[str, Tuple[str, str, str]] = {
    "up": ("ok", "info", "up"),
    "grace": ("warning", "warning", "late"),
    "down": ("critical", "critical", "down"),
    "new": ("warning", "warning", "never pinged"),
    "paused": ("paused", "info", "paused"),
}


def parse_status(status: str) -> Tuple[str, str, str]:
    """Map a Healthchecks.io API status to (health, severity, label)."""
    return _STATUS_MAP.get(str(status or ""), ("unknown", "info", "unknown"))


def evaluate_check(check: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Decide whether a check needs an alert.

    Returns an alert payload (severity/title/message) when the check is late
    (grace) or down (missed deadline), else ``None``. Pure — no I/O.
    """
    status = str(check.get("status", ""))
    if status not in ("grace", "down"):
        return None
    severity, label = parse_status(status)[1], parse_status(status)[2]
    name = check.get("name") or check.get("slug") or "unnamed check"
    return {
        "severity": severity,
        "title": f"Healthchecks {name}: {label}",
        "message": (
            f"Check '{name}' is {label}. "
            f"last_ping={check.get('last_ping') or 'never'}, "
            f"next_ping={check.get('next_ping') or 'unknown'}."
        ),
    }


def _fetch_checks(cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """GET /api/v3/checks/ with the project API key. Returns the parsed body."""
    config = cfg or get_monitor_config(MONITOR_NAME)
    if not config.get("enabled", True):
        return None
    base = str(config.get("api_base", API_BASE)).rstrip("/")
    api_key_env = config.get("api_key_env", "HEALTHCHECKS_API_KEY")
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        logger.warning("Healthchecks API key not set (env: %s)", api_key_env)
        return None

    req = urllib.request.Request(f"{base}/api/v3/checks/")
    req.add_header("X-Api-Key", api_key)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.HTTPError, urllib.error.URLError, OSError,
            json.JSONDecodeError) as e:
        logger.warning("Healthchecks API error: %s", e)
        return None


def get_healthchecks_summary(cfg: Optional[Dict] = None) -> Dict[str, Any]:
    """Fetch checks from Healthchecks.io and alert on late/down checks."""
    # cfg may be the full WatchBot config (from load_config) or this monitor's
    # own dict. Read the monitor sub-config via get_monitor_config, which
    # deep-merges defaults, so `enabled` is honoured either way.
    config = get_monitor_config(MONITOR_NAME, cfg)
    if not config.get("enabled", True):
        return {"enabled": False, "message": "Healthchecks monitoring disabled"}

    body = _fetch_checks(config)
    if body is None:
        return {"enabled": False, "error": "Could not reach Healthchecks.io API"}

    checks = body.get("checks", []) if isinstance(body, dict) else []
    summary = []
    severity_rank = {"ok": 0, "unknown": 1, "paused": 1, "warning": 2, "critical": 3}
    worst = "ok"

    for check in checks:
        name = check.get("name") or check.get("slug") or "unnamed"
        status = str(check.get("status"))
        health, severity, label = parse_status(status)
        entry = {
            "name": name,
            "slug": check.get("slug"),
            "status": status,
            "health": health,
            "label": label,
            "last_ping": check.get("last_ping"),
            "next_ping": check.get("next_ping"),
            "post_url": check.get("post_url"),
        }
        summary.append(entry)
        if severity_rank.get(health, 0) > severity_rank.get(worst, 0):
            worst = health

        alert = evaluate_check(check)
        key = check.get("slug") or name
        last_state = get_state(MONITOR_NAME, f"check_{key}_status")
        if last_state != status:
            # Persist every observed status (not just alerting ones), so a
            # recovered check's next failure re-alerts instead of being
            # suppressed by a stale `down`/`grace` from the previous incident.
            if alert:
                dispatch_alert(
                    MONITOR_NAME, alert["severity"], alert["title"], alert["message"]
                )
            set_state(MONITOR_NAME, f"check_{key}_status", status)

    timestamp = datetime.now(timezone.utc).isoformat()
    save_snapshot(MONITOR_NAME, {
        "total": len(checks),
        "checks": summary,
        "timestamp": timestamp,
    })

    return {
        "enabled": True,
        "total": len(checks),
        "checks": summary,
        "health": worst,
        "timestamp": timestamp,
    }
