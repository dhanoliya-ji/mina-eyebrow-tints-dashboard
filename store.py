"""
store.py
========
The storage layer of the dashboard. Instead of saving data to a JSON file,
this module implements a production-grade relational database (SQLite)
to store all synced metrics, status reports, and source configurations by time window.

Database Schema:
- Table: `source_snapshots`
  - source_name (TEXT): e.g., 'meta', 'google', 'shopify', 'shiprocket'
  - window_days (INTEGER): time window length in days (e.g. 1, 7, 30)
  - data (TEXT): JSON-serialized platform data
  - last_synced (TEXT): ISO 8601 sync timestamp
  - ok (INTEGER): Boolean flag (1=Success, 0=Failed)
  - live (INTEGER): Boolean flag (1=Live API, 0=Mock/Demo)
  - note (TEXT): Notes or information messages
  - error (TEXT): Error messages if sync failed
  - PRIMARY KEY (source_name, window_days)
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_FILE = os.path.join(DB_DIR, "dashboard.db")


def init_db() -> None:
    """Initialize the SQLite database and create necessary tables with composite primary key."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        
        # Auto-migration: check if table lacks the window_days column
        cursor.execute("PRAGMA table_info(source_snapshots)")
        cols = [r[1] for r in cursor.fetchall()]
        if cols and "window_days" not in cols:
            print("[store] migrating database table source_snapshots...")
            cursor.execute("DROP TABLE IF EXISTS source_snapshots")
            
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_snapshots (
                source_name TEXT,
                window_days INTEGER,
                data TEXT,
                last_synced TEXT,
                ok INTEGER,
                live INTEGER,
                note TEXT,
                error TEXT,
                PRIMARY KEY (source_name, window_days)
            )
        """)
        conn.commit()
    except Exception as e:
        print("[store] database initialization failed:", e)
    finally:
        conn.close()


def get_snapshot(window_days: int = 7) -> dict:
    """
    Read the snapshots for a specific time window from SQLite and format them in the structure
    expected by the rest of the application.
    """
    init_db()
    snapshot = {
        "meta": None,
        "google": None,
        "shopify": None,
        "shiprocket": None,
        "sources": {},
    }

    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM source_snapshots WHERE window_days = ?", (window_days,))
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            name = row["source_name"]
            raw_data = row["data"]
            
            # Map database columns to the memory structure
            snapshot[name] = json.loads(raw_data) if raw_data else None
            snapshot["sources"][name] = {
                "lastSynced": row["last_synced"],
                "ok": bool(row["ok"]),
                "live": bool(row["live"]),
                "note": row["note"],
                "error": row["error"],
            }
    except Exception as e:
        print(f"[store] error loading snapshot from database for window_days {window_days}:", e)

    return snapshot


def save_source(name: str, result: dict, window_days: int = 7) -> None:
    """
    Save one source's freshly-pulled data and its status in the SQLite database
    using a composite upsert SQL statement (INSERT ON CONFLICT(source_name, window_days) UPDATE).
    """
    init_db()
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        raw_data = json.dumps(result["data"])
        last_synced = datetime.now(timezone.utc).isoformat()
        ok = 1 if result.get("error") is None else 0
        live = 1 if result.get("live") is True else 0
        note = result.get("note")
        error = result.get("error")

        cursor.execute("""
            INSERT INTO source_snapshots (source_name, window_days, data, last_synced, ok, live, note, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_name, window_days) DO UPDATE SET
                data=excluded.data,
                last_synced=excluded.last_synced,
                ok=excluded.ok,
                live=excluded.live,
                note=excluded.note,
                error=excluded.error
        """, (name, window_days, raw_data, last_synced, ok, live, note, error))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[store] error writing {name} snapshot to database for window_days {window_days}:", e)
