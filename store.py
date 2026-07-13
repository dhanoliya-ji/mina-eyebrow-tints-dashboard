"""
store.py
========
The storage layer of the dashboard. This module implements a hybrid database engine:
- If a valid `DATABASE_URL` is configured in `.env`, it connects to PostgreSQL.
- Otherwise, it falls back to a local SQLite database (`data/dashboard.db`).

Supports historical time-series database logging: every single refresh saves a new
record with a unique timestamp, preserving the full historical metrics logs.
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
    """Initialize database tables for PostgreSQL or SQLite, automatically migrating schemas."""
    conn, db_type = _get_connection()
    try:
        cursor = conn.cursor()
        
        if db_type == "postgres":
            # Check if source_snapshots table exists and inspect its primary key columns
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'source_snapshots'
                );
            """)
            exists = cursor.fetchone()[0]
            if exists:
                cursor.execute("""
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    WHERE i.indrelid = 'source_snapshots'::regclass AND i.indisprimary;
                """)
                pk_cols = [r[0] for r in cursor.fetchall()]
                # If last_synced is not in the primary key, drop table to migrate it
                if "last_synced" not in pk_cols:
                    print("[db] migrating PostgreSQL source_snapshots to time-series...")
                    cursor.execute("DROP TABLE IF EXISTS source_snapshots")
            
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
                    PRIMARY KEY (source_name, window_days, last_synced)
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
            # SQLite migration check
            cursor.execute("PRAGMA table_info(source_snapshots)")
            rows = cursor.fetchall()
            if rows:
                pk_cols = [r[1] for r in rows if r[5] > 0]
                if "last_synced" not in pk_cols:
                    print("[db] migrating SQLite source_snapshots to time-series...")
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
                    PRIMARY KEY (source_name, window_days, last_synced)
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
    Read the latest snapshots for a specific time window from the active database
    using a subquery to match the maximum last_synced timestamp.
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
        # Standard SQL query matching max(last_synced) for each source
        query = """
            SELECT s.source_name, s.data, s.last_synced, s.ok, s.live, s.note, s.error
            FROM source_snapshots s
            INNER JOIN (
                SELECT source_name, MAX(last_synced) as max_sync
                FROM source_snapshots
                WHERE window_days = {}
                GROUP BY source_name
            ) m ON s.source_name = m.source_name AND s.last_synced = m.max_sync
            WHERE s.window_days = {}
        """
        
        if db_type == "sqlite":
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query.format("?", "?"), (window_days, window_days))
            rows = cursor.fetchall()
        else:
            # PostgreSQL
            cursor = conn.cursor()
            cursor.execute(query.format("%s", "%s"), (window_days, window_days))
            db_rows = cursor.fetchall()
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
    Append a new historical record for this source snapshot to the database.
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
            cursor.execute("""
                INSERT INTO source_snapshots (source_name, window_days, data, last_synced, ok, live, note, error)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (name, window_days, raw_data, last_synced, ok, live, note, error))
        else:
            cursor.execute("""
                INSERT INTO source_snapshots (source_name, window_days, data, last_synced, ok, live, note, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, window_days, raw_data, last_synced, ok, live, note, error))

        conn.commit()
    except Exception as e:
        print(f"[db] error appending {name} snapshot to {db_type} for window_days {window_days}:", e)
    finally:
        conn.close()
