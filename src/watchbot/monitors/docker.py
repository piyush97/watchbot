"""Docker container health monitoring via Docker socket."""

from __future__ import annotations

import http.client
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from watchbot.core.alerts import dispatch_alert, render_alert_template
from watchbot.core.config import get_monitor_config
from watchbot.core.state import get_state, save_snapshot, set_state

logger = logging.getLogger(__name__)

MONITOR_NAME = "docker"


def _docker_get(socket_path: str, endpoint: str) -> Optional[Any]:
    """Make a GET request to the Docker socket."""
    try:
        conn = http.client.HTTPConnection("localhost")
        conn.sock = __import__("socket").socket(__import__("socket").AF_UNIX,
                                                 __import__("socket").SOCK_STREAM)
        conn.sock.connect(socket_path)
        conn.sock.settimeout(10)
        conn.request("GET", endpoint)
        resp = conn.getresponse()
        data = resp.read().decode()
        conn.close()
        return json.loads(data) if data else None
    except Exception as e:
        logger.debug("Docker socket error (%s): %s", endpoint, e)
        return None


def list_containers(socket_path: str = "/var/run/docker.sock",
                    all: bool = False) -> List[Dict]:
    """List Docker containers."""
    endpoint = "/v1.45/containers/json?all=true" if all else "/v1.45/containers/json"
    data = _docker_get(socket_path, endpoint)
    if not data:
        return []

    containers = []
    for c in data:
        names = c.get("Names", [])
        name = names[0].lstrip("/") if names else c.get("Id", "")[:12]
        state = c.get("State", "unknown")
        status = c.get("Status", "")
        restart_count = c.get("RestartCount", 0)

        containers.append({
            "id": c.get("Id", "")[:12],
            "name": name,
            "image": c.get("Image", ""),
            "state": state,
            "status": status,
            "running": state == "running",
            "restart_count": restart_count,
            "created": c.get("Created", 0),
        })

        # Alert on high restart counts
        if restart_count > 3:
            last_count = get_state(MONITOR_NAME, f"container_{name}_restarts")
            if last_count != restart_count:
                msg = render_alert_template("docker_restart",
                    name=name, restarts=restart_count,
                    timestamp=datetime.now(timezone.utc).strftime("%H:%M UTC"),
                )
                dispatch_alert(MONITOR_NAME, "warning",
                              f"Docker {name} restarted {restart_count}x", msg)
                set_state(MONITOR_NAME, f"container_{name}_restarts", restart_count)

    return containers


def get_container_stats(socket_path: str = "/var/run/docker.sock") -> Dict[str, Any]:
    """Get Docker stats (CPU, memory) for running containers."""
    containers = list_containers(socket_path, all=False)
    stats = {}

    for c in containers:
        if c["running"]:
            data = _docker_get(socket_path,
                              f"/v1.45/containers/{c['id']}/stats?stream=false")
            if data:
                try:
                    cpu_delta = data["cpu_stats"]["cpu_usage"]["total_usage"]
                    sys_delta = data["cpu_stats"]["system_cpu_usage"]
                    precpu_delta = data["precpu_stats"]["cpu_usage"]["total_usage"]
                    presys_delta = data["precpu_stats"]["system_cpu_usage"]
                    cpu_pct = ((cpu_delta - precpu_delta) / (sys_delta - presys_delta)) * 100 if (sys_delta - presys_delta) > 0 else 0
                    mem_usage = data["memory_stats"]["usage"]
                    mem_limit = data["memory_stats"]["limit"]
                    mem_pct = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0
                    stats[c["name"]] = {
                        "cpu_pct": round(cpu_pct, 1),
                        "mem_mb": round(mem_usage / (1024**2), 1),
                        "mem_pct": round(mem_pct, 1),
                    }
                except (KeyError, TypeError, ZeroDivisionError):
                    pass

    return stats


def get_docker_summary(cfg: Optional[Dict] = None) -> Dict[str, Any]:
    """Get a Docker monitoring summary."""
    config = cfg or get_monitor_config(MONITOR_NAME)
    socket_path = config.get("socket", "/var/run/docker.sock")

    if not config.get("enabled", True):
        return {"enabled": False, "message": "Docker monitoring disabled"}

    # Safety: validate socket path is an absolute path under allowed dirs
    resolved_socket = Path(socket_path).resolve()
    allowed_socket_dirs = (
        Path("/var/run"),
        Path("/run"),
    )
    if not any(str(resolved_socket).startswith(str(p)) for p in allowed_socket_dirs):
        logger.warning("Docker socket path outside allowed dirs: %s", socket_path)
        return {"enabled": False, "error": f"Invalid socket path: {socket_path}"}

    containers = list_containers(socket_path)
    stats = get_container_stats(socket_path)
    running = sum(1 for c in containers if c["running"])
    stopped = sum(1 for c in containers if not c["running"])

    save_snapshot(MONITOR_NAME, {
        "total": len(containers),
        "running": running,
        "stopped": stopped,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "enabled": True,
        "total": len(containers),
        "running": running,
        "stopped": stopped,
        "containers": [
            {"name": c["name"], "state": c["state"], "restarts": c["restart_count"]}
            for c in containers
        ],
        "stats": stats,
        "health": "ok" if running == len(containers) else "warning",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
