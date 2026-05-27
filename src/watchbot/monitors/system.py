"""System health monitoring — disk, CPU, memory, network, temperature."""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from watchbot.core.alerts import (
    classify_severity,
    dispatch_alert,
    render_alert_template,
)
from watchbot.core.config import get_monitor_config
from watchbot.core.state import get_state, save_snapshot, set_state

logger = logging.getLogger(__name__)

MONITOR_NAME = "system"


def get_disk_usage(path: str = "/") -> Dict[str, Any]:
    """Get disk usage for a mount point."""
    try:
        usage = shutil.disk_usage(path)
        total = usage.total
        used = usage.used
        free = usage.free
        pct = (used / total) * 100 if total > 0 else 0
        return {
            "path": path,
            "total_gb": round(total / (1024**3), 1),
            "used_gb": round(used / (1024**3), 1),
            "free_gb": round(free / (1024**3), 1),
            "used_pct": round(pct, 1),
        }
    except OSError as e:
        logger.warning("Disk check error for %s: %s", path, e)
        return {"path": path, "error": str(e)}


def get_memory_usage() -> Dict[str, Any]:
    """Get memory usage from /proc/meminfo."""
    try:
        with open("/proc/meminfo") as f:
            meminfo = f.read()

        def _get_val(key: str) -> int:
            for line in meminfo.split("\n"):
                if line.startswith(key):
                    return int(line.split()[1]) * 1024  # Convert kB to bytes
            return 0

        total = _get_val("MemTotal")
        free = _get_val("MemFree")
        buffers = _get_val("Buffers")
        cached = _get_val("Cached")
        available = _get_val("MemAvailable")

        used = total - available if available > 0 else total - free - buffers - cached
        pct = (used / total) * 100 if total > 0 else 0

        return {
            "total_gb": round(total / (1024**3), 1),
            "used_gb": round(used / (1024**3), 1),
            "available_gb": round(available / (1024**3), 1),
            "used_pct": round(pct, 1),
        }
    except (OSError, ValueError, IndexError) as e:
        logger.warning("Memory check error: %s", e)
        return {"error": str(e)}


def get_cpu_usage() -> Dict[str, Any]:
    """Get CPU usage from /proc/stat (one-second delta)."""
    try:
        def _read_cpu():
            with open("/proc/stat") as f:
                for line in f:
                    if line.startswith("cpu "):
                        parts = [int(v) for v in line.strip().split()[1:]]
                        return sum(parts), parts[3]  # total, idle
            return 0, 0

        total1, idle1 = _read_cpu()
        import time
        time.sleep(0.5)
        total2, idle2 = _read_cpu()

        total_delta = total2 - total1
        idle_delta = idle2 - idle1
        pct = ((total_delta - idle_delta) / total_delta) * 100 if total_delta > 0 else 0

        # Get load average
        try:
            load1, load5, load15 = os.getloadavg()
        except OSError:
            load1 = load5 = load15 = 0.0

        return {
            "used_pct": round(pct, 1),
            "load_1min": load1,
            "load_5min": load5,
            "load_15min": load15,
        }
    except Exception as e:
        logger.warning("CPU check error: %s", e)
        return {"error": str(e)}


def get_temperature() -> Optional[float]:
    """Get CPU temperature from thermal zone or sensors."""
    thermal_zones = Path("/sys/class/thermal/")
    if thermal_zones.exists():
        for tz in sorted(thermal_zones.iterdir()):
            temp_file = tz / "temp"
            if temp_file.exists():
                try:
                    raw = int(temp_file.read_text().strip())
                    return round(raw / 1000, 1)  # Millidegrees → Celsius
                except (ValueError, OSError):
                    continue

    try:
        result = __import__("subprocess").run(
            ["sensors", "-u"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "temp1_input" in line:
                    return round(float(line.split(":")[1].strip()), 1)
    except Exception:
        pass

    return None


def check_all(cfg: Optional[Dict] = None) -> Dict[str, Any]:
    """Run all system health checks and alert on thresholds."""
    config = cfg or get_monitor_config(MONITOR_NAME)
    disk_threshold = config.get("disk_threshold_pct", 85)
    mem_threshold = config.get("mem_threshold_pct", 90)
    cpu_threshold = config.get("cpu_threshold_pct", 95)

    disk = get_disk_usage("/")
    memory = get_memory_usage()
    cpu = get_cpu_usage()
    temp = get_temperature()

    results = {
        "disk": disk,
        "memory": memory,
        "cpu": cpu,
        "temperature": temp,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Alert on thresholds
    if "used_pct" in disk:
        sev = classify_severity(disk["used_pct"], disk_threshold, disk_threshold + 10)
        if sev in ("warning", "critical"):
            msg = render_alert_template("system_high",
                metric="disk", value=disk["used_pct"],
                threshold=disk_threshold, host=os.uname().nodename,
            )
            dispatch_alert(MONITOR_NAME, sev,
                          f"Disk at {disk['used_pct']}%", msg)

    if "used_pct" in memory:
        sev = classify_severity(memory["used_pct"], mem_threshold, mem_threshold + 5)
        if sev in ("warning", "critical"):
            msg = render_alert_template("system_high",
                metric="memory", value=memory["used_pct"],
                threshold=mem_threshold, host=os.uname().nodename,
            )
            dispatch_alert(MONITOR_NAME, sev,
                          f"Memory at {memory['used_pct']}%", msg)

    if "used_pct" in cpu:
        sev = classify_severity(cpu["used_pct"], cpu_threshold, cpu_threshold + 3)
        if sev in ("warning", "critical"):
            msg = render_alert_template("system_high",
                metric="CPU", value=cpu["used_pct"],
                threshold=cpu_threshold, host=os.uname().nodename,
            )
            dispatch_alert(MONITOR_NAME, sev,
                          f"CPU at {cpu['used_pct']}%", msg)

    save_snapshot(MONITOR_NAME, results)
    return results


def get_system_summary(cfg: Optional[Dict] = None) -> Dict[str, Any]:
    """Get a health summary for dashboard/agent."""
    health = check_all(cfg)
    issues = []
    for component in ("disk", "memory", "cpu"):
        if "used_pct" in health.get(component, {}):
            pct = health[component]["used_pct"]
            if pct >= 90:
                issues.append({"component": component, "severity": "critical", "value": pct})
            elif pct >= 80:
                issues.append({"component": component, "severity": "warning", "value": pct})

    return {
        "disk": health.get("disk", {}),
        "memory": health.get("memory", {}),
        "cpu": health.get("cpu", {}),
        "temperature": health.get("temperature"),
        "issues": issues,
        "health": "critical" if any(i["severity"] == "critical" for i in issues) else (
            "warning" if issues else "ok"
        ),
        "timestamp": health.get("timestamp"),
    }
