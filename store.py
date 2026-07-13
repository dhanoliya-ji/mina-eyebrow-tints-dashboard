"""
store.py
========
The storage layer of the dashboard. This module implements a hybrid database engine:
- If a valid `DATABASE_URL` is configured in `.env`, it connects to PostgreSQL.
- Otherwise, it falls back to a local SQLite database (`data/dashboard.db`).

Both database engines support composite key storage `(source_name, window_days)`.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_FILE = os.path.join(DB_DIR, "dashboard.db")


def _get_connection():
    """
    Connect to PostgreSQL if DATABASE_URL is set and not a DUMMY/placeholder.
    Otherwise, fall back to SQLite.
    Returns: (connection, db_type_string)
    """
    db_url = os.environ.get("DATABASE_URL")
    if db_url and not db_url.startswith("DUMMY") and not db_url.startswith("DUMMY_"):
        try:
            import psycopg2
            conn = psycopg2.connect(db_url)
            return conn, "postgres"
        except Exception as e:
            print(f"[db] PostgreSQL connection failed: {e}. Falling back to SQLite...")
            
    # SQLite Fallback
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    return conn, "sqlite"


def init_db() -> None:
    """Initialize database tables for PostgreSQL or SQLite."""
    conn, db_type = _get_connection()
    try:
        cursor = conn.cursor()
        
        if db_type == "postgres":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS source_snapshots (
                    source_name VARCHAR(50),
                    window_days INTEGER,
                    data TEXT,
                    last_synced VARCHAR(50),
                    ok INTEGER,
                    live INTEGER,
                    note TEXT,
                    error TEXT,
                    PRIMARY KEY (source_name, window_days)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key VARCHAR(50) PRIMARY KEY,
                    value TEXT
                )
            """)
            print("[db] PostgreSQL database tables initialized successfully.")
        else:
            # SQLite specific schema & migration
            cursor.execute("PRAGMA table_info(source_snapshots)")
            cols = [r[1] for r in cursor.fetchall()]
            if cols and "window_days" not in cols:
                print("[db] migrating SQLite source_snapshots table...")
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
        conn.commit()
    except Exception as e:
        print(f"[db] table initialization failed on {db_type}:", e)
    finally:
        conn.close()


def get_snapshot(window_days: int = 7) -> dict:
    """
    Read the snapshots for a specific time window from the active database
    and format them in the structure expected by the rest of the application.
    """
    init_db()
    snapshot = {
        "meta": None,
        "google": None,
        "shopify": None,
        "shiprocket": None,
        "sources": {},
    }

    conn, db_type = _get_connection()
    try:
        # For SQLite, we can configure row_factory to get dictionaries
        if db_type == "sqlite":
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM source_snapshots WHERE window_days = ?", (window_days,))
            rows = cursor.fetchall()
        else:
            # PostgreSQL connection
            cursor = conn.cursor()
            cursor.execute("SELECT source_name, data, last_synced, ok, live, note, error FROM source_snapshots WHERE window_days = %s", (window_days,))
            db_rows = cursor.fetchall()
            # Map Postgres tuples to dictionary-like objects
            rows = []
            for r in db_rows:
                rows.append({
                    "source_name": r[0],
                    "data": r[1],
                    "last_synced": r[2],
                    "ok": r[3],
                    "live": r[4],
                    "note": r[5],
                    "error": r[6],
                })

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
        print(f"[db] error loading snapshot from {db_type} for window_days {window_days}:", e)
    finally:
        conn.close()

    return snapshot


def save_source(name: str, result: dict, window_days: int = 7) -> None:
    """
    Save one source's freshly-pulled data and its status in the active database.
    """
    init_db()
    conn, db_type = _get_connection()
    try:
        cursor = conn.cursor()

        raw_data = json.dumps(result["data"])
        last_synced = datetime.now(timezone.utc).isoformat()
        ok = 1 if result.get("error") is None else 0
        live = 1 if result.get("live") is True else 0
        note = result.get("note")
        error = result.get("error")

        if db_type == "postgres":
            # PostgreSQL upsert (INSERT ON CONFLICT)
            cursor.execute("""
                INSERT INTO source_snapshots (source_name, window_days, data, last_synced, ok, live, note, error)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(source_name, window_days) DO UPDATE SET
                    data=EXCLUDED.data,
                    last_synced=EXCLUDED.last_synced,
                    ok=EXCLUDED.ok,
                    live=EXCLUDED.live,
                    note=EXCLUDED.note,
                    error=EXCLUDED.error
            """, (name, window_days, raw_data, last_synced, ok, live, note, error))
        else:
            # SQLite upsert
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
    except Exception as e:
        print(f"[db] error writing {name} snapshot to {db_type} for window_days {window_days}:", e)
    finally:
        conn.close()
