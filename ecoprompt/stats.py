"""Anonymous usage analytics and the community impact counter.

Privacy: no prompt text, names, emails, IP addresses or user identifiers are
ever stored. Each event keeps only what kind of action happened, which AI app
and models were involved, and the estimated savings. Events older than
ECOPROMPT_RETENTION_DAYS (default 365) are deleted automatically.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path

_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    ts INTEGER NOT NULL,
    event TEXT NOT NULL,
    client TEXT,
    provider TEXT,
    current_model TEXT,
    recommended TEXT,
    complexity TEXT,
    region TEXT,
    outcome TEXT,
    energy_wh_saved REAL NOT NULL DEFAULT 0,
    water_ml_saved REAL NOT NULL DEFAULT 0,
    co2_g_saved REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS events_ts ON events (ts);
CREATE INDEX IF NOT EXISTS events_event ON events (event);
"""

# Events the public landing page may send to /track.
PAGE_EVENTS = {"page_view", "copy_url"}

_KNOWN_CLIENTS = (
    ("claude-code", "Claude Code"),
    ("claude code", "Claude Code"),
    ("claude", "Claude"),
    ("anthropic", "Claude"),
    ("chatgpt", "ChatGPT"),
    ("openai", "ChatGPT"),
    ("cursor", "Cursor"),
    ("vscode", "VS Code"),
    ("visual studio code", "VS Code"),
    ("copilot", "VS Code"),
    ("windsurf", "Windsurf"),
    ("gemini", "Gemini"),
    ("inspector", "MCP Inspector"),
)


def _db_path() -> Path:
    return Path(os.environ.get("ECOPROMPT_DB", Path(__file__).resolve().parent.parent / "ecoprompt.db"))


def _retention_seconds() -> int:
    return int(os.environ.get("ECOPROMPT_RETENTION_DAYS", "365")) * 86400


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.executescript(_SCHEMA)
    return conn


def normalize_client(raw: str | None) -> str:
    """Map a client name or User-Agent to a short app label, dropping anything identifying."""
    if not raw:
        return "Unknown"
    text = raw.lower()
    for needle, label in _KNOWN_CLIENTS:
        if needle in text:
            return label
    return "Other"


def record_event(
    event: str,
    *,
    client: str | None = None,
    provider: str | None = None,
    current_model: str | None = None,
    recommended: str | None = None,
    complexity: str | None = None,
    region: str | None = None,
    outcome: str | None = None,
    energy_wh_saved: float = 0.0,
    water_ml_saved: float = 0.0,
    co2_g_saved: float = 0.0,
) -> None:
    now = int(time.time())
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (now, event, client, provider, current_model, recommended, complexity, region, outcome,
             energy_wh_saved, water_ml_saved, co2_g_saved),
        )
        conn.execute("DELETE FROM events WHERE ts < ?", (now - _retention_seconds(),))


def totals() -> dict:
    """Public community counter."""
    with _lock, _connect() as conn:
        count, wh, ml, g = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(energy_wh_saved), 0), COALESCE(SUM(water_ml_saved), 0), "
            "COALESCE(SUM(co2_g_saved), 0) FROM events WHERE event = 'recommend_model'"
        ).fetchone()
    return {
        "recommendations": count,
        "energy_kwh_saved": round(wh / 1000, 4),
        "water_liters_saved": round(ml / 1000, 3),
        "co2_kg_saved": round(g / 1000, 4),
    }


def _breakdown(conn: sqlite3.Connection, column: str, where: str = "event = 'recommend_model'", limit: int = 10) -> list[dict]:
    rows = conn.execute(
        f"SELECT COALESCE({column}, 'Unknown') AS k, COUNT(*) FROM events WHERE {where} "
        f"GROUP BY k ORDER BY COUNT(*) DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [{"label": k, "count": n} for k, n in rows]


def analytics(days: int = 30) -> dict:
    """Private behaviour summary for the owner's dashboard."""
    since = int(time.time()) - days * 86400
    with _lock, _connect() as conn:
        by_event = dict(conn.execute("SELECT event, COUNT(*) FROM events GROUP BY event").fetchall())
        outcomes = dict(conn.execute(
            "SELECT outcome, COUNT(*) FROM events WHERE event = 'report_choice' GROUP BY outcome"
        ).fetchall())
        daily = conn.execute(
            "SELECT date(ts, 'unixepoch') AS d, "
            "SUM(event = 'recommend_model'), SUM(event = 'page_view'), SUM(event = 'report_choice' AND outcome = 'switched') "
            "FROM events WHERE ts >= ? GROUP BY d ORDER BY d",
            (since,),
        ).fetchall()
        result = {
            "community": None,
            "events": by_event,
            "funnel": {
                "page_views": by_event.get("page_view", 0),
                "copy_url_clicks": by_event.get("copy_url", 0),
                "recommendations": by_event.get("recommend_model", 0),
                "choices_reported": by_event.get("report_choice", 0),
            },
            "adoption": {
                "switched": outcomes.get("switched", 0),
                "kept_current": outcomes.get("kept", 0),
                "switch_rate_percent": round(100 * outcomes.get("switched", 0) / sum(outcomes.values()))
                if outcomes else None,
            },
            "by_app": _breakdown(conn, "client", "event != 'page_view' AND event != 'copy_url'"),
            "by_complexity": _breakdown(conn, "complexity"),
            "by_provider": _breakdown(conn, "provider"),
            "current_models": _breakdown(conn, "current_model"),
            "recommended_models": _breakdown(conn, "recommended"),
            "by_region": _breakdown(conn, "region"),
            "daily": [
                {"date": d, "recommendations": r or 0, "page_views": v or 0, "switches": s or 0} for d, r, v, s in daily
            ],
            "window_days": days,
        }
    result["community"] = totals()
    return result
