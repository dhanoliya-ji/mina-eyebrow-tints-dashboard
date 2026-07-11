"""
settings_store.py
=================
Holds the AI rule thresholds and per-platform "credibility" numbers in SQLite.
Allows updates at runtime (PUT /api/settings) and persists them in dashboard.db.
"""

import json
import os
import sqlite3

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_FILE = os.path.join(DB_DIR, "dashboard.db")

DEFAULTS = {
    "thresholds": {
        "weak1dRoas": 1.5,
        "strong7dRoas": 4.0,
        "breakevenRoas": 2.2,
        "scaleStep": 0.25,
        "overReportPct": 0.60,
        "stockOutDays": 7,
        "cpaSpikePct": 0.30,
    },
    "platformCredibility": {"meta": 0.62, "google": 0.84},
}


def init_settings_db() -> None:
    """Initialize the settings table in SQLite database."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()
    except Exception as e:
        print("[settings_store] settings table initialization failed:", e)
    finally:
        conn.close()


def get_settings() -> dict:
    """Return the current thresholds + credibility from SQLite database."""
    init_settings_db()
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key='config'")
        row = cursor.fetchone()
        conn.close()

        if row:
            loaded = json.loads(row[0])
            merged = json.loads(json.dumps(DEFAULTS))  # deep copy
            merged["thresholds"].update(loaded.get("thresholds", {}))
            merged["platformCredibility"].update(loaded.get("platformCredibility", {}))
            return merged
    except Exception as e:
        print("[settings_store] error loading settings from database:", e)

    return DEFAULTS


def update_settings(patch: dict) -> dict:
    """
    Merge a partial update into the settings and save to the SQLite database.
    """
    current = get_settings()
    current["thresholds"].update(patch.get("thresholds", {}))
    current["platformCredibility"].update(patch.get("platformCredibility", {}))

    init_settings_db()
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        raw_val = json.dumps(current)
        cursor.execute("""
            INSERT INTO settings (key, value)
            VALUES ('config', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (raw_val,))
        conn.commit()
        conn.close()
    except Exception as e:
        print("[settings_store] error writing settings to database:", e)

    return current
