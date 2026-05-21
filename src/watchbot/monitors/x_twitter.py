"""X/Twitter monitoring — timeline, keyword search, DMs."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from watchbot.core.alerts import dispatch_alert, render_alert_template
from watchbot.core.config import get_monitor_config
from watchbot.core.state import get_state, save_snapshot, set_state

logger = logging.getLogger(__name__)

MONITOR_NAME = "twitter"


def _get_headers() -> Optional[Dict]:
    """Get X API headers from auth."""
    token = os.environ.get("X_API_TOKEN", "") or os.environ.get("TWITTER_API_TOKEN", "")
    if not token:
        # Try reading from auth.json
        try:
            from hermes_constants import get_hermes_home
            auth_path = get_hermes_home() / "auth.json"
            if auth_path.exists():
                with open(auth_path) as f:
                    auth = json.load(f)
                token = auth.get("twitter", {}).get("access_token", "")
        except Exception:
            pass
    if not token:
        return None

    return {
        "Authorization": f"Bearer {token}",
        "User-Agent": "watchbot-hermes/1.0",
    }


def get_timeline(user_id: str = None, max_results: int = 20,
                 cfg: Optional[Dict] = None) -> List[Dict]:
    """Fetch the home timeline.

    Uses the X API v2 via xurl CLI or direct API calls.
    """
    try:
        # Try using xurl CLI if available
        import subprocess
        result = subprocess.run(
            ["xurl", "timeline", "--limit", str(max_results)],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return json.loads(result.stdout) if result.stdout.strip() else []
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass

    return []


def search_keywords(keywords: List[str], cfg: Optional[Dict] = None) -> List[Dict]:
    """Search for keywords on X/Twitter.

    Returns recent matching tweets.
    """
    if not keywords:
        return []

    results = []
    try:
        import subprocess
        for kw in keywords:
            since_id = get_state(MONITOR_NAME, f"search_since_{kw}")
            cmd = ["xurl", "search", kw, "--limit", "5"]
            if since_id:
                cmd.extend(["--since-id", str(since_id)])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0 and result.stdout.strip():
                try:
                    tweets = json.loads(result.stdout)
                    if isinstance(tweets, list):
                        for t in tweets:
                            t["keyword"] = kw
                        results.extend(tweets)
                        if tweets:
                            set_state(MONITOR_NAME, f"search_since_{kw}",
                                     tweets[0].get("id", ""))
                except json.JSONDecodeError:
                    pass

        # Alert on keyword matches
        for tweet in results:
            msg = render_alert_template("twitter_keyword",
                keyword=tweet.get("keyword", "?"),
                user=tweet.get("author", {}).get("username", "?"),
                text=tweet.get("text", ""),
                url=tweet.get("url", ""),
                timestamp=datetime.now(timezone.utc).strftime("%H:%M UTC"),
            )
            dispatch_alert(MONITOR_NAME, "info",
                          f"Keyword: {tweet.get('keyword')}", msg)

    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("xurl CLI not available for keyword search")

    return results


def get_twitter_summary(cfg: Optional[Dict] = None) -> Dict[str, Any]:
    """Get a Twitter monitoring summary."""
    config = cfg or get_monitor_config(MONITOR_NAME)
    keywords = config.get("keywords", [])

    timeline = get_timeline(cfg=cfg)
    matches = search_keywords(keywords, cfg) if keywords else []

    save_snapshot(MONITOR_NAME, {
        "timeline_count": len(timeline),
        "keyword_matches": len(matches),
        "keywords": keywords,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "enabled": config.get("enabled", False),
        "timeline_tweets": len(timeline),
        "keyword_matches": len(matches),
        "keywords": keywords,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
