"""
app.py  —  START HERE
=====================
This is the program you run:  python app.py

It does three jobs:
  1. Serves the dashboard web page (static/index.html) at http://localhost:4000
  2. Serves the data the page needs at /api/dashboard (fully computed here in
     Python — reconciliation, metrics, and the AI briefing).
  3. Runs the data sync: once on startup, then every day at the scheduled time,
     and on demand when you click "Refresh".

The web page itself is "thin": it just draws whatever numbers this file sends.
All the thinking happens in Python (metrics.py + rules.py).
"""

from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory

import config
from store import get_snapshot
from settings_store import get_settings, update_settings
from sync import run_sync, is_syncing, start_scheduler
import metrics
import rules

# Flask serves files from the "static" folder. static_url_path="" means
# static/index.html is available at "/" (the root URL).
app = Flask(__name__, static_folder="static", static_url_path="")

# Nice display names for the four sources, in display order.
SOURCE_LABELS = {"meta": "Meta Ads", "google": "Google Ads",
                 "shopify": "Shopify", "shiprocket": "Shiprocket"}


# ---------------------------------------------------------------------------
#  Build the complete payload the dashboard renders
# ---------------------------------------------------------------------------
def build_payload() -> dict:
    """
    Take the latest stored source data, run ALL the maths + AI rules, and return
    one big dictionary the web page can draw directly.
    """
    snap = get_snapshot()
    settings = get_settings()

    # The data bundle every metrics/rules function expects.
    bundle = {
        "meta": snap["meta"],
        "google": snap["google"],
        "shopify": snap["shopify"],
        "shiprocket": snap["shiprocket"],
        "thresholds": settings["thresholds"],
        "platformCredibility": settings["platformCredibility"],
    }

    # If a sync hasn't populated data yet, tell the page to wait.
    if not bundle["meta"] or not bundle["shopify"]:
        return {"ready": False}

    # Turn the per-source status dict into an ordered list for the UI chips.
    sources = []
    any_live = False
    for key, label in SOURCE_LABELS.items():
        s = snap["sources"].get(key, {})
        any_live = any_live or s.get("live", False)
        sources.append({
            "source": label,
            "lastSynced": s.get("lastSynced"),
            "ok": s.get("ok", True),
            "live": s.get("live", False),
            "note": s.get("note"),
            "error": s.get("error"),
        })

    rec = metrics.reconcile(bundle)

    # Everything below is computed once, here, and shipped to the browser.
    return {
        "ready": True,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "mode": "live" if any_live else "mock",
        "sources": sources,
        "reconciliation": rec,
        "kpis": metrics.topline(bundle),
        "attribution": metrics.attribution(bundle),
        "funnel": metrics.funnel(bundle),
        "skus": metrics.sku_performance(bundle),
        "campaigns": rules.campaign_actions(bundle),
        "briefing": rules.briefing(bundle),
        "thresholds": settings["thresholds"],
    }


# ---------------------------------------------------------------------------
#  Web routes
# ---------------------------------------------------------------------------
@app.route("/")
def home():
    """Serve the dashboard web page."""
    return send_from_directory("static", "index.html")


@app.route("/api/dashboard")
def api_dashboard():
    """The single endpoint the page fetches — fully computed numbers + briefing."""
    return jsonify(build_payload())


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """The header 'Refresh' button — pull all sources again right now."""
    result = run_sync()
    return jsonify(result)


@app.route("/api/health")
def api_health():
    """Quick status check: is it running, and which sources have real keys?"""
    return jsonify({
        "ok": True,
        "syncing": is_syncing(),
        "live": {"meta": config.META["live"], "google": config.GOOGLE["live"],
                 "shopify": config.SHOPIFY["live"], "shiprocket": config.SHIPROCKET["live"]},
    })


@app.route("/api/settings", methods=["GET", "PUT"])
def api_settings():
    """Read (GET) or change (PUT) the AI thresholds without touching code."""
    if request.method == "PUT":
        return jsonify(update_settings(request.get_json(force=True) or {}))
    return jsonify(get_settings())


# ---------------------------------------------------------------------------
#  Start-up
# ---------------------------------------------------------------------------
def main():
    # Initialize the SQLite database tables
    from store import init_db
    from settings_store import init_settings_db
    init_db()
    init_settings_db()

    live = [name for name, cfg in
            {"meta": config.META, "google": config.GOOGLE,
             "shopify": config.SHOPIFY, "shiprocket": config.SHIPROCKET}.items()
            if cfg["live"]]
    print("[server] starting Mina Eyebrow Tints · AI Automation Dashboard")
    print("[server] live sources:", ", ".join(live) if live else
          "none (all using dummy keys - demo/mock data)")

    run_sync()          # pull data once so the page has something to show
    start_scheduler()   # schedule the daily automatic sync

    print(f"[server] open http://localhost:{config.PORT}")
    # debug=False and use_reloader=False so the sync doesn't run twice.
    app.run(host="0.0.0.0", port=config.PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
