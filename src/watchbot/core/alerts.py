"""Alert routing, deduplication, and rate-limiting for WatchBot."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ── Content sanitization ─────────────────────────────────────
# Guards against indirect prompt injection via external content
# (RSS feeds, tweets, etc.). Strips known prompt-injection patterns
# and wraps content in safe boundaries.

_INJECTION_PATTERNS = [
    re.compile(r'\b(?:ignore|disregard|forget)\s+(?:above|previous|all\s*(?:previous|the)?)\s*(?:instructions|prompts?|commands|directions|rules?)', re.I),
    re.compile(r'\b(?:new\s+)?(?:instruction|prompt|rule|directive)s?\s*[:\-]', re.I),
    re.compile(r'\b(?:you\s+are\s+(?:now|not\s+)|act\s+as|pretend\s+(?:to\s+be|that)|role.play\s*(?:\s*[:=]))', re.I),
    re.compile(r'\[?(?:END|START)\s*(?:OF|OF\s+INPUT|OF\s+OUTPUT)\]?', re.I),
    re.compile(r'<\|?[\w\s]+\|?>', re.I),  # special tokens like <|im_start|>, <s>
    re.compile(r'```[\s\S]*?```'),  # code blocks — strip entirely
]


def sanitize_external_content(text: str, max_length: int = 500) -> str:
    """Sanitize content from external sources (RSS, Twitter, etc.).

    - Strips known prompt-injection patterns
    - Strips code blocks
    - Truncates to max_length
    - Wraps in inert boundary markers so the agent sees it as data
    """
    if not text:
        return ""

    for pattern in _INJECTION_PATTERNS:
        text = pattern.sub("", text)

    # Strip excess whitespace from injection-pattern removal
    text = re.sub(r'\s+', ' ', text).strip()

    if len(text) > max_length:
        text = text[:max_length] + "…"

    return text

from watchbot.core.state import create_alert, get_active_alerts

logger = logging.getLogger(__name__)


# ── Rate limiting ──────────────────────────────────────────────

class AlertThrottle:
    """Rate-limits alerts per source+title to avoid spam."""

    def __init__(self, cooldown_seconds: int = 3600):
        self._cooldown = cooldown_seconds
        self._history: Dict[str, float] = {}

    def can_send(self, source: str, title: str) -> bool:
        key = f"{source}:{title}"
        last = self._history.get(key, 0.0)
        now = time.time()
        if now - last < self._cooldown:
            return False
        self._history[key] = now
        return True

    def reset(self, source: str, title: str) -> None:
        key = f"{source}:{title}"
        self._history.pop(key, None)


# Global throttle instance
_throttle = AlertThrottle()


# ── Severity triage ────────────────────────────────────────────

SEVERITY_ORDER = {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}

SEVERITY_EMOJI = {
    "debug": "🔍",
    "info": "ℹ️",
    "warning": "⚠️",
    "error": "🚨",
    "critical": "🔥",
}


def classify_severity(value: float, warn_at: float, crit_at: float) -> str:
    """Classify a numeric metric into a severity level."""
    if value >= crit_at:
        return "critical"
    if value >= warn_at:
        return "warning"
    if value >= warn_at * 0.8:
        return "info"
    return "debug"


# ── Template rendering ─────────────────────────────────────────

def render_alert_template(template_name: str, **kwargs) -> str:
    """Simple template rendering for alert messages.

    Automatically sanitizes external content fields (text, summary,
    message) to prevent indirect prompt injection.
    """
    # Sanitize any external content fields
    for field in ("text", "summary", "message", "title"):
        if field in kwargs and isinstance(kwargs[field], str):
            kwargs[field] = sanitize_external_content(kwargs[field])
    templates = {
        "lxc_down": (
            "{emoji} **LXC {vmid} — {name}** is DOWN\n"
            "Severity: {severity}\n"
            "Action: {action}\n"
            "Time: {timestamp}"
        ),
        "lxc_recovered": (
            "✅ **LXC {vmid} — {name}** recovered\n"
            "Downtime: {downtime}\n"
            "Time: {timestamp}"
        ),
        "system_high": (
            "{emoji} **System {metric}** at {value}%\n"
            "Threshold: {threshold}%\n"
            "Host: {host}\n"
            "Time: {timestamp}"
        ),
        "ha_sensor": (
            "🏠 **Home Assistant — {sensor}**\n"
            "Value: {value}\n"
            "Time: {timestamp}"
        ),
        "twitter_keyword": (
            "🐦 **Keyword match: {keyword}**\n"
            "[EXTERNAL_DATA] Tweet by @{user}: {text[:200]}\n"
            "URL: {url}\n"
            "Time: {timestamp}\n"
            "[/EXTERNAL_DATA]"
        ),
        "blog_post": (
            "📰 **New post: {title}**\n"
            "[EXTERNAL_DATA] Source: {feed}\n"
            "URL: {url}\n"
            "Time: {timestamp}\n"
            "[/EXTERNAL_DATA]"
        ),
        "docker_restart": (
            "🐳 **Docker container {name}** restarted\n"
            "Restart count: {restarts}\n"
            "Time: {timestamp}"
        ),
    }
    template = templates.get(template_name)
    if not template:
        return str(kwargs)
    kwargs.setdefault("emoji", SEVERITY_EMOJI.get(kwargs.get("severity", "info"), "ℹ️"))
    kwargs.setdefault("timestamp", datetime.now(timezone.utc).strftime("%H:%M:%S UTC"))
    return template.format(**kwargs)


# ── Delivery ───────────────────────────────────────────────────

def dispatch_alert(source: str, severity: str, title: str,
                   message: Optional[str] = None,
                   force: bool = False) -> Optional[int]:
    """Create an alert and route it to configured channels.

    Returns the alert ID, or None if rate-limited.
    """
    if not force and not _throttle.can_send(source, title):
        logger.debug("Alert throttled: %s / %s", source, title)
        return None

    alert_id = create_alert(source, severity, title, message)
    logger.info("Alert [%s/%s] %s: %s", severity, source, alert_id, title)
    return alert_id


# ── Alert summary ──────────────────────────────────────────────

def build_alert_summary(limit: int = 10) -> str:
    """Build a human-readable summary of all active alerts."""
    alerts = get_active_alerts()
    if not alerts:
        return "✅ No active alerts."

    lines = [f"📊 **{len(alerts)} active alert(s):**\n"]
    for a in alerts[:limit]:
        emoji = SEVERITY_EMOJI.get(a["severity"], "ℹ️")
        lines.append(
            f"  {emoji} **[{a['severity'].upper()}]** {a['title']}"
        )
        if a.get("message"):
            lines[-1] += f"\n     _{a['message'][:100]}_"
    if len(alerts) > limit:
        lines.append(f"  *...and {len(alerts) - limit} more*")
    return "\n".join(lines)
