"""Anonymous community impact counter.

Privacy: only the complexity level, the two model ids and the estimated
savings are stored. Prompt text, names, IPs and any user identifiers never are.
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path

_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendations (
    ts INTEGER NOT NULL,
    complexity INTEGER NOT NULL,
    recommended TEXT NOT NULL,
    baseline TEXT NOT NULL,
    energy_wh_saved REAL NOT NULL,
    water_ml_saved REAL NOT NULL,
    co2_g_saved REAL NOT NULL
)
"""


def _db_path() -> Path:
    return Path(os.environ.get("ECOPROMPT_DB", Path(__file__).resolve().parent.parent / "ecoprompt.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.execute(_SCHEMA)
    return conn


def record(complexity: int, recommended: str, baseline: str, energy_wh: float, water_ml: float, co2_g: float) -> None:
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO recommendations VALUES (?, ?, ?, ?, ?, ?, ?)",
            (int(time.time()), complexity, recommended, baseline, energy_wh, water_ml, co2_g),
        )


def totals() -> dict:
    with _lock, _connect() as conn:
        count, wh, ml, g = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(energy_wh_saved), 0), COALESCE(SUM(water_ml_saved), 0), "
            "COALESCE(SUM(co2_g_saved), 0) FROM recommendations"
        ).fetchone()
    return {
        "recommendations": count,
        "energy_kwh_saved": round(wh / 1000, 4),
        "water_liters_saved": round(ml / 1000, 3),
        "co2_kg_saved": round(g / 1000, 4),
    }
