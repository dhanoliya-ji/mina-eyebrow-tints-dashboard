"""
sync.py
=======
The "ingestion" step. It pulls data from all four sources and saves each result
to the store.

Two important behaviours the spec requires:
  - PARTIAL-FAILURE SAFE: if one source fails, the others still update. Each
    source records its own success/failure independently.
  - RUNS ON A SCHEDULE: once when the server starts, then every day at the time
    set in .env (SYNC_HOUR / SYNC_MINUTE). You can also trigger it manually with
    the "Refresh" button (POST /api/refresh).
"""

import threading
import time
from datetime import datetime, timedelta

import config
from store import save_source
from connectors.meta import fetch_meta
from connectors.google import fetch_google
from connectors.shopify import fetch_shopify
from connectors.shiprocket import fetch_shiprocket

# Map each source name to the function that fetches it.
_CONNECTORS = {
    "meta": fetch_meta,
    "google": fetch_google,
    "shopify": fetch_shopify,
    "shiprocket": fetch_shiprocket,
}

# A simple lock so two syncs can't run at the same time (e.g. the daily job
# firing while you also click Refresh).
_lock = threading.Lock()
_is_syncing = False


def is_syncing() -> bool:
    return _is_syncing


def run_sync() -> dict:
    """Pull every source once and store the results. Returns a small summary."""
    global _is_syncing
    if not _lock.acquire(blocking=False):
        return {"skipped": True, "reason": "a sync is already running"}

    _is_syncing = True
    started = time.time()
    print("[sync] starting 7-day pull for all sources...")
    failures = 0

    try:
        for name, fetch in _CONNECTORS.items():
            try:
                result = fetch()               # call the connector
                save_source(name, result)      # store its data + status
                tag = "LIVE" if result.get("live") else ("MOCK(err)" if result.get("error") else "MOCK")
                extra = f" - {result['error']}" if result.get("error") else ""
                print(f"[sync]   {name:<11} {tag}{extra}")
            except Exception as e:
                # This should rarely happen (connectors handle their own errors),
                # but if it does, one broken source must not stop the others.
                failures += 1
                print(f"[sync]   {name:<11} HARD FAIL - {e}")
    finally:
        _is_syncing = False
        _lock.release()

    print(f"[sync] done in {int((time.time() - started) * 1000)}ms ({failures} hard failures)")
    return {"ok": True, "failures": failures}


# ---------------------------------------------------------------------------
#  Daily scheduler
# ---------------------------------------------------------------------------
def _seconds_until(hour: int, minute: int) -> float:
    """How many seconds from now until the next HH:MM (today or tomorrow)."""
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)  # already passed today -> schedule tomorrow
    return (target - now).total_seconds()


def _scheduler_loop():
    """Background loop: sleep until the scheduled time, sync, repeat forever."""
    while True:
        wait = _seconds_until(config.SYNC_HOUR, config.SYNC_MINUTE)
        print(f"[sync] next scheduled sync in {int(wait / 3600)}h "
              f"{int((wait % 3600) / 60)}m ({config.SYNC_HOUR:02d}:{config.SYNC_MINUTE:02d})")
        time.sleep(wait)
        run_sync()


def start_scheduler():
    """Start the daily scheduler on a background thread (does not block the web server)."""
    thread = threading.Thread(target=_scheduler_loop, daemon=True)
    thread.start()
