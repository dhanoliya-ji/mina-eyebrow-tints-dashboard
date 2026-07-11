"""
store.py
========
The storage layer of the dashboard. Instead of saving data to a JSON file,
this module implements a production-grade relational database (SQLite)
to store all synced metrics, status reports, and source configurations.

Database Schema:
- Table: `source_snapshots`
  - source_name (TEXT, PRIMARY KEY): e.g., 'meta', 'google', 'shopify', 'shiprocket'
  - data (TEXT): JSON-serialized platform data
  - last_synced (TEXT): ISO 8601 sync timestamp
  - ok (INTEGER): Boolean flag (1=Success, 0=Failed)
  - live (INTEGER): Boolean flag (1=Live API, 0=Mock/Demo)
  - note (TEXT): Notes or information messages
  - error (TEXT): Error messages if sync failed
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_FILE = os.path.join(DB_DIR, "dashboard.db")


def init_db() -> None:
    """Initialize the SQLite database and create necessary tables."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_snapshots (
                source_name TEXT PRIMARY KEY,
                data TEXT,
                last_synced TEXT,
                ok INTEGER,
                live INTEGER,
                note TEXT,
                error TEXT
            )
        """)
        conn.commit()
    except Exception as e:
        print("[store] database initialization failed:", e)
    finally:
        conn.close()


def get_snapshot() -> dict:
    """
    Read the latest snapshots from SQLite and format them in the structure
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
        cursor.execute("SELECT * FROM source_snapshots")
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
        print("[store] error loading snapshot from database:", e)

    return snapshot


def save_source(name: str, result: dict) -> None:
    """
    Save one source's freshly-pulled data and its status in the SQLite database
    using an upsert SQL statement (INSERT ON CONFLICT UPDATE).
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
            INSERT INTO source_snapshots (source_name, data, last_synced, ok, live, note, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_name) DO UPDATE SET
                data=excluded.data,
                last_synced=excluded.last_synced,
                ok=excluded.ok,
                live=excluded.live,
                note=excluded.note,
                error=excluded.error
        """, (name, raw_data, last_synced, ok, live, note, error))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[store] error writing {name} snapshot to database:", e)
