"""Home Assistant sensor monitoring — temperature, device states, areas."""

from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from watchbot.core.alerts import dispatch_alert, render_alert_template
from watchbot.core.config import get_monitor_config
from watchbot.core.state import save_snapshot

logger = logging.getLogger(__name__)

MONITOR_NAME = "home_assistant"


def _ha_request(url: str, token: str, endpoint: str,
                timeout: int = 10) -> Optional[Dict]:
    """Make a GET request to the Home Assistant API."""
    full_url = f"{url.rstrip('/')}/api/{endpoint.lstrip('/')}"
    req = urllib.request.Request(full_url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.HTTPError, urllib.error.URLError, OSError,
            json.JSONDecodeError) as e:
        logger.warning("HA API error (%s): %s", endpoint, e)
        return None


def get_sensor_states(cfg: Optional[Dict] = None) -> List[Dict]:
    """Fetch sensor states from Home Assistant.

    Returns a list of {entity_id, state, attributes, friendly_name}.
    """
    config = cfg or get_monitor_config(MONITOR_NAME)
    url = config.get("url", "http://192.168.0.244:8123")
    token_env = config.get("token_env", "HA_TOKEN")
    token = os.environ.get(token_env, "")
    sensor_ids = config.get("sensors", [])

    if not token:
        logger.warning("HA token not set (env: %s)", token_env)
        return []

    results = []
    for entity_id in sensor_ids:
        data = _ha_request(url, token, f"states/{entity_id}")
        if data and isinstance(data, dict):
            attrs = data.get("attributes", {})
            results.append({
                "entity_id": data.get("entity_id", entity_id),
                "state": data.get("state"),
                "unit": attrs.get("unit_of_measurement", ""),
                "friendly_name": attrs.get("friendly_name", entity_id),
                "last_changed": data.get("last_changed"),
            })
        else:
            results.append({
                "entity_id": entity_id,
                "state": None,
                "error": "No data returned",
            })

    return results


def list_entities(domain: Optional[str] = None,
                  cfg: Optional[Dict] = None) -> List[Dict]:
    """List all entities, optionally filtered by domain."""
    config = cfg or get_monitor_config(MONITOR_NAME)
    url = config.get("url", "http://192.168.0.244:8123")
    token_env = config.get("token_env", "HA_TOKEN")
    token = os.environ.get(token_env, "")

    if not token:
        return []

    data = _ha_request(url, token, "states")
    if not data:
        return []

    entities = []
    for entity in data if isinstance(data, list) else []:
        entity_id = entity.get("entity_id", "")
        if domain and not entity_id.startswith(f"{domain}."):
            continue
        entities.append({
            "entity_id": entity_id,
            "state": entity.get("state"),
            "friendly_name": entity.get("attributes", {}).get("friendly_name", ""),
        })

    return entities


def get_ha_summary(cfg: Optional[Dict] = None) -> Dict[str, Any]:
    """Get a Home Assistant summary for dashboard."""
    sensors = get_sensor_states(cfg)
    sensor_data = {}
    for s in sensors:
        name = s.get("friendly_name", s["entity_id"])
        state = s.get("state")
        unit = s.get("unit", "")
        sensor_data[name] = f"{state}{unit}" if state else "unknown"

    # Save snapshot
    save_snapshot(MONITOR_NAME, {
        "sensor_count": len(sensors),
        "sensors": {s["entity_id"]: s.get("state") for s in sensors},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "sensors": sensor_data,
        "count": len(sensors),
        "healthy": all(s.get("state") is not None for s in sensors),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
