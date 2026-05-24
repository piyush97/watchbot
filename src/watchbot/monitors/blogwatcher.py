"""Blog and RSS feed monitoring — blogwatcher integration."""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from watchbot.core.alerts import dispatch_alert, render_alert_template
from watchbot.core.config import get_monitor_config
from watchbot.core.state import get_state, save_snapshot, set_state

logger = logging.getLogger(__name__)

MONITOR_NAME = "blogs"


def check_feeds(cfg: Optional[Dict] = None) -> List[Dict]:
    """Check RSS/Atom feeds for new posts.

    Uses blogwatcher-cli if installed, otherwise falls back to
    direct feed parsing via feedparser.
    """
    config = cfg or get_monitor_config(MONITOR_NAME)
    feeds = config.get("feeds", [])

    if not feeds:
        return []

    new_posts = []

    # Try blogwatcher-cli first
    try:
        result = subprocess.run(
            ["blogwatcher-cli", "check", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            try:
                items = json.loads(result.stdout)
                if isinstance(items, list):
                    new_posts.extend(items)
            except json.JSONDecodeError:
                pass
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: direct feedparser
    if not new_posts:
        try:
            import feedparser
            for feed_url in feeds:
                last_seen = get_state(MONITOR_NAME, f"feed_{feed_url}_last")
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:
                    post_id = entry.get("id", entry.get("link", ""))
                    if last_seen and post_id <= last_seen:
                        continue
                    new_posts.append({
                        "title": entry.get("title", "Untitled"),
                        "url": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "summary": entry.get("summary", "")[:300],
                        "feed": feed_url,
                        "feed_title": feed.feed.get("title", feed_url),
                    })
                if feed.entries:
                    set_state(MONITOR_NAME, f"feed_{feed_url}_last",
                             feed.entries[0].get("id",
                                 feed.entries[0].get("link", "")))
        except ImportError:
            logger.warning("feedparser not installed, cannot parse feeds directly")
        except Exception as e:
            logger.warning("Feed parsing error: %s", e)

    # Alert on new posts
    for post in new_posts:
        msg = render_alert_template("blog_post",
            title=post.get("title", "?"),
            feed=post.get("feed_title", post.get("feed", "?")),
            url=post.get("url", ""),
            timestamp=datetime.now(timezone.utc).strftime("%H:%M UTC"),
        )
        dispatch_alert(MONITOR_NAME, "info",
                      f"New post: {post.get('title', '?')[:60]}", msg)

    return new_posts


def get_blog_summary(cfg: Optional[Dict] = None) -> Dict[str, Any]:
    """Get a blog monitoring summary."""
    config = cfg or get_monitor_config(MONITOR_NAME)
    feeds = config.get("feeds", [])
    new_posts = check_feeds(cfg)

    save_snapshot(MONITOR_NAME, {
        "feed_count": len(feeds),
        "new_posts": len(new_posts),
        "feeds": feeds,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "enabled": config.get("enabled", True),
        "feeds": feeds,
        "new_posts": len(new_posts),
        "latest_posts": [
            {"title": p["title"], "url": p["url"], "feed": p.get("feed_title", "")}
            for p in new_posts[:5]
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
