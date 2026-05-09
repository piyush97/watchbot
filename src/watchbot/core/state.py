"""SQLite-backed state management for WatchBot.

Tracks alert state, monitor timestamps, dedup keys, and historical snapshots.
All state lives in ``$HERMES_HOME/watchbot/state.db``.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from hermes_constants import get_hermes_home
except ImportError:
    import os

    def get_hermes_home() -> Path:
        return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


logger = logging.getLogger(__name__)

STATE_DIR = get_hermes_home() / "watchbot"
STATE_DB = STATE_DIR / "state.db"

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Get a thread-local connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(STATE_DB))
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
        _init_schema(_local.conn)
    return _local.conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS monitor_state (
            monitor    TEXT NOT NULL,
            key        TEXT NOT NULL,
            value      TEXT,
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            PRIMARY KEY (monitor, key)
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      TEXT NOT NULL,
            severity    TEXT NOT NULL DEFAULT 'info',
            title       TEXT NOT NULL,
            message     TEXT,
            status      TEXT NOT NULL DEFAULT 'active',
            dismissed   INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
            resolved_at TEXT
        );
        CREATE TABLE IF NOT EXISTS snapshots (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            source     TEXT NOT NULL,
            data       TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        );
        CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
        CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at);
        CREATE INDEX IF NOT EXISTS idx_snapshots_source ON snapshots(source);
    """)


@contextmanager
def _tx():
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ── Monitor state ──────────────────────────────────────────────

def set_state(monitor: str, key: str, value: Any) -> None:
    """Persist a monitor's key/value state."""
    with _tx() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO monitor_state (monitor, key, value, updated_at)
               VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))""",
            (monitor, key, json.dumps(value) if not isinstance(value, str) else value),
        )


def get_state(monitor: str, key: str, default: Any = None) -> Any:
    """Read a monitor's state value."""
    with _tx() as conn:
        row = conn.execute(
            "SELECT value FROM monitor_state WHERE monitor = ? AND key = ?",
            (monitor, key),
        ).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return row["value"]


def get_all_state(monitor: str) -> Dict[str, Any]:
    """Get all state keys for a monitor."""
    with _tx() as conn:
        rows = conn.execute(
            "SELECT key, value FROM monitor_state WHERE monitor = ?", (monitor,)
        ).fetchall()
    result = {}
    for row in rows:
        try:
            result[row["key"]] = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            result[row["key"]] = row["value"]
    return result


# ── Alerts ─────────────────────────────────────────────────────

def create_alert(source: str, severity: str, title: str,
                 message: Optional[str] = None) -> int:
    """Create a new alert. Returns the alert ID."""
    with _tx() as conn:
        cur = conn.execute(
            """INSERT INTO alerts (source, severity, title, message)
               VALUES (?, ?, ?, ?)""",
            (source, severity, title, message),
        )
        return cur.lastrowid


def resolve_alert(alert_id: int) -> bool:
    """Mark an alert as resolved."""
    with _tx() as conn:
        cur = conn.execute(
            """UPDATE alerts SET status = 'resolved',
               resolved_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
               WHERE id = ? AND status = 'active'""",
            (alert_id,),
        )
        return cur.rowcount > 0


def get_active_alerts(source: Optional[str] = None,
                      severity: Optional[str] = None) -> List[Dict]:
    """Get all active (non-dismissed, non-resolved) alerts."""
    with _tx() as conn:
        query = "SELECT * FROM alerts WHERE dismissed = 0 AND status = 'active'"
        params: List[Any] = []
        if source:
            query += " AND source = ?"
            params.append(source)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        query += " ORDER BY created_at DESC LIMIT 100"
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def dismiss_alert(alert_id: int) -> bool:
    """Dismiss an alert (soft-delete)."""
    with _tx() as conn:
        cur = conn.execute(
            "UPDATE alerts SET dismissed = 1 WHERE id = ?", (alert_id,)
        )
        return cur.rowcount > 0


# ── Snapshots ──────────────────────────────────────────────────

def save_snapshot(source: str, data: Dict) -> int:
    """Save a monitor snapshot for historical tracking."""
    with _tx() as conn:
        cur = conn.execute(
            "INSERT INTO snapshots (source, data) VALUES (?, ?)",
            (source, json.dumps(data, default=str)),
        )
        return cur.lastrowid


def get_latest_snapshot(source: str) -> Optional[Dict]:
    """Get the most recent snapshot for a source."""
    with _tx() as conn:
        row = conn.execute(
            "SELECT data, created_at FROM snapshots WHERE source = ? ORDER BY id DESC LIMIT 1",
            (source,),
        ).fetchone()
    if row:
        return {"data": json.loads(row["data"]), "created_at": row["created_at"]}
    return None


def get_snapshot_history(source: str, limit: int = 50) -> List[Dict]:
    """Get recent snapshots for trend analysis."""
    with _tx() as conn:
        rows = conn.execute(
            "SELECT data, created_at FROM snapshots WHERE source = ? ORDER BY id DESC LIMIT ?",
            (source, limit),
        ).fetchall()
    return [{"data": json.loads(r["data"]), "created_at": r["created_at"]} for r in rows]
