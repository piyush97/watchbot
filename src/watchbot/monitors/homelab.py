"""Proxmox LXC monitoring via SSH — watchdog for container health."""

from __future__ import annotations

import logging
import re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from watchbot.core.alerts import dispatch_alert, render_alert_template
from watchbot.core.config import get_monitor_config
from watchbot.core.state import get_state, save_snapshot, set_state

logger = logging.getLogger(__name__)

MONITOR_NAME = "homelab"

# — SAFETY GUARD: Validate SSH config values to prevent injection ———


def _validate_ssh_config(host: str, user: str, port: int, key_path: str) -> None:
    """Validate SSH config values, raising ValueError on suspicious input.

    Guards against command injection via compromised config.yaml.
    """
    # Host must be IP or known domain — reject shell metacharacters
    if not re.match(r'^[a-zA-Z0-9._-]+$', host):
        raise ValueError(f"Invalid SSH host: {host!r}")
    # User must be alphanumeric
    if not re.match(r'^[a-zA-Z0-9._-]+$', user):
        raise ValueError(f"Invalid SSH user: {user!r}")
    # Port must be 1-65535
    if not (1 <= int(port) <= 65535):
        raise ValueError(f"Invalid SSH port: {port}")
    # Key path must be an absolute path under home or /etc/ssh
    resolved = Path(key_path).expanduser().resolve()
    allowed_prefixes = (
        Path.home() / ".ssh",
        Path("/etc/ssh"),
        Path("/etc/ssl"),
    )
    if not any(str(resolved).startswith(str(p)) for p in allowed_prefixes):
        raise ValueError(f"SSH key path outside allowed directories: {key_path}")


def _run_ssh(host: str, user: str, port: int, key_path: str, cmd: str,
             timeout: int = 15) -> Tuple[bool, str]:
    """Run a command via SSH using an argument list (no shell=True).

    Returns (success, output).
    """
    _validate_ssh_config(host, user, port, key_path)
    expanded_key = str(Path(key_path).expanduser())

    # Build argv — no shell=True, no string interpolation risk
    argv = [
        "ssh",
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        "-i", expanded_key,
        "-p", str(port),
        f"{user}@{host}",
        cmd,  # single command string — passed as one arg to ssh
    ]
    try:
        result = subprocess.run(
            argv, shell=False, capture_output=True, text=True,
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

    try:
        success, output = _run_ssh(host, user, port, key_path, "pct list")
    except ValueError as e:
        logger.warning("Invalid SSH config: %s", e)
        return []

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
