"""Proxmox LXC monitoring via SSH — watchdog for container health."""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from watchbot.core.alerts import dispatch_alert, render_alert_template
from watchbot.core.config import get_monitor_config
from watchbot.core.state import get_state, save_snapshot, set_state

logger = logging.getLogger(__name__)

MONITOR_NAME = "homelab"


def _ssh_cmd(host: str, user: str, port: int, key_path: str, cmd: str) -> str:
    """Build an SSH command string."""
    return (
        f"ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "
        f"-i {key_path} -p {port} {user}@{host} {cmd}"
    )


def _run_ssh(host: str, user: str, port: int, key_path: str, cmd: str,
             timeout: int = 15) -> Tuple[bool, str]:
    """Run a command via SSH and return (success, output)."""
    full_cmd = _ssh_cmd(host, user, port, key_path, cmd)
    try:
        result = subprocess.run(
            full_cmd, shell=True, capture_output=True, text=True,
            timeout=timeout
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "SSH timeout"
    except Exception as e:
        return False, str(e)


def check_lxc(cfg: Optional[Dict] = None) -> List[Dict]:
    """Check Proxmox LXC container status.

    Returns a list of container status dicts.
    """
    config = cfg or get_monitor_config(MONITOR_NAME)
    host = config.get("host", "192.168.0.2")
    user = config.get("user", "root")
    port = config.get("port", 22)
    key_path = config.get("key_path", str(Path.home() / ".ssh" / "id_ed25519"))
    critical_ids = set(config.get("critical", []))
    optional_ids = set(config.get("optional", []))

    success, output = _run_ssh(host, user, port, key_path, "pct list")
    if not success:
        logger.warning("Failed to connect to Proxmox host: %s", output)
        dispatch_alert(
            MONITOR_NAME, "error",
            "Proxmox SSH connection failed",
            f"Host {host}: {output[:200]}",
        )
        return []

    containers = []
    for line in output.strip().split("\n")[1:]:  # Skip header
        if not line.strip():
            continue
        parts = re.split(r"\s+", line.strip())
        if len(parts) < 4:
            continue
        try:
            vmid = int(parts[0])
        except ValueError:
            continue
        status = parts[1].lower()
        name = parts[2] if len(parts) > 2 else f"lxc-{vmid}"
        is_running = status == "running"
        is_critical = vmid in critical_ids
        is_optional = vmid in optional_ids

        containers.append({
            "vmid": vmid,
            "name": name,
            "status": status,
            "running": is_running,
            "critical": is_critical,
            "optional": is_optional,
        })

        # Alert on critical/optional containers that are down
        if not is_running and (is_critical or is_optional):
            last_state = get_state(MONITOR_NAME, f"lxc_{vmid}_running")
            if last_state is not False:  # Was running, now down
                severity = "critical" if is_critical else "warning"
                action = "auto-restart" if is_critical else "manual check needed"
                msg = render_alert_template("lxc_down",
                    vmid=vmid, name=name, severity=severity, action=action,
                    timestamp=datetime.now(timezone.utc).strftime("%H:%M UTC"),
                )
                dispatch_alert(MONITOR_NAME, severity, f"LXC {vmid} ({name}) down", msg)

            # Auto-restart critical containers
            if is_critical:
                _restart_lxc(host, user, port, key_path, vmid)

        # Alert on recovery
        if is_running and last_state is False:
            downtime = "unknown"
            msg = render_alert_template("lxc_recovered",
                vmid=vmid, name=name, downtime=downtime,
                timestamp=datetime.now(timezone.utc).strftime("%H:%M UTC"),
            )
            dispatch_alert(MONITOR_NAME, "info", f"LXC {vmid} ({name}) recovered", msg)

        set_state(MONITOR_NAME, f"lxc_{vmid}_running", is_running)

    # Save snapshot
    save_snapshot(MONITOR_NAME, {
        "total": len(containers),
        "running": sum(1 for c in containers if c["running"]),
        "critical_down": [c["vmid"] for c in containers
                         if c["critical"] and not c["running"]],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return containers


def _restart_lxc(host: str, user: str, port: int, key_path: str,
                 vmid: int) -> bool:
    """Attempt to restart a critical container."""
    logger.info("Auto-restarting LXC %d...", vmid)
    success, output = _run_ssh(host, user, port, key_path,
                               f"pct start {vmid}")
    if success:
        logger.info("LXC %d restart successful", vmid)
        dispatch_alert(
            MONITOR_NAME, "info",
            f"LXC {vmid} auto-restarted",
            f"Container {vmid} was down and has been restarted successfully.",
        )
    else:
        logger.error("LXC %d restart failed: %s", vmid, output)
        dispatch_alert(
            MONITOR_NAME, "critical",
            f"LXC {vmid} restart FAILED",
            f"Auto-restart attempt failed: {output[:200]}",
        )
    return success


def get_lxc_summary(cfg: Optional[Dict] = None) -> Dict[str, Any]:
    """Get a summary of LXC status for dashboard/agent."""
    containers = check_lxc(cfg)
    critical_down = [c for c in containers if c["critical"] and not c["running"]]
    optional_down = [c for c in containers if c["optional"] and not c["running"]]

    return {
        "total": len(containers),
        "running": sum(1 for c in containers if c["running"]),
        "stopped": sum(1 for c in containers if not c["running"]),
        "critical_down": [
            {"vmid": c["vmid"], "name": c["name"]} for c in critical_down
        ],
        "optional_down": [
            {"vmid": c["vmid"], "name": c["name"]} for c in optional_down
        ],
        "health": "critical" if critical_down else (
            "warning" if optional_down else "ok"
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
