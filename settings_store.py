"""
settings_store.py
=================
Holds the AI rule thresholds and per-platform "credibility" numbers in the active database.
Allows updates at runtime (PUT /api/settings) and persists them in PostgreSQL or SQLite.
"""

import json
import os
from store import _get_connection

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
    """Initialize settings table. Handled globally inside store.init_db(), but kept for safe imports."""
    pass


def get_settings() -> dict:
    """Return the current thresholds + credibility from the active database."""
    conn, db_type = _get_connection()
    
    try:
        cursor = conn.cursor()
        if db_type == "postgres":
            cursor.execute("SELECT value FROM settings WHERE key='config'")
        else:
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
        print(f"[db] error loading settings from {db_type}: {e}")

    return DEFAULTS


def update_settings(patch: dict) -> dict:
    """
    Merge a partial update into the settings and save to the active database.
    """
    current = get_settings()
    current["thresholds"].update(patch.get("thresholds", {}))
    current["platformCredibility"].update(patch.get("platformCredibility", {}))

    conn, db_type = _get_connection()
    try:
        cursor = conn.cursor()
        raw_val = json.dumps(current)
        
        if db_type == "postgres":
            cursor.execute("""
                INSERT INTO settings (key, value)
                VALUES ('config', %s)
                ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value
            """, (raw_val,))
        else:
            cursor.execute("""
                INSERT INTO settings (key, value)
                VALUES ('config', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """, (raw_val,))
            
        conn.commit()
    except Exception as e:
        print(f"[db] error writing settings to {db_type}: {e}")
    finally:
        conn.close()

    return current
