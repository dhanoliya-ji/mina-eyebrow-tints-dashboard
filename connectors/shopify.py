"""
connectors/shopify.py
====================
Pulls store data from Shopify using the Admin API. Shopify is the REVENUE
SOURCE OF TRUTH — orders here (minus refunds/cancellations, cross-checked with
Shiprocket delivery) are what "true revenue" is built from.

Same three-step pattern: real key -> demo -> mock.
"""

import requests
from datetime import datetime, timedelta, timezone

import config
from mock_data import MOCK_SHOPIFY
from connectors.demo_live import get_demo_sources


def fetch_shopify() -> dict:
    c = config.SHOPIFY

    # ---- No real key yet -> demo feed or mock ---------------------------
    if not c["live"]:
        if config.DEMO_LIVE:
            try:
                demo = get_demo_sources()
                return {"data": demo["shopify"], "live": True,
                        "note": f"DEMO live via {demo['signal_source']} — replace with real Shopify Admin API"}
            except Exception as e:
                return {"data": MOCK_SHOPIFY, "live": False, "error": f"demo feed: {e}"}
        return {"data": MOCK_SHOPIFY, "live": False, "note": "dummy token — using sample data"}

    # ---- Real credentials -> call the real API --------------------------
    try:
        # Only pull orders from the last 7 days (the rolling window).
        since = (datetime.now(timezone.utc) - timedelta(days=config.WINDOW_DAYS)).isoformat()
        base = f"https://{c['domain']}/admin/api/{c['api_version']}"
        resp = requests.get(
            f"{base}/orders.json",
            headers={"X-Shopify-Access-Token": c["admin_token"]},
            params={"status": "any", "created_at_min": since, "limit": 250},
            timeout=20,
        )
        resp.raise_for_status()
        return {"data": _map_shopify(resp.json()), "live": True}
    except Exception as e:
        return {"data": MOCK_SHOPIFY, "live": False, "error": str(e)}


def _map_shopify(json_response: dict) -> dict:
    """
    =========================================================================
    REPLACE THIS MAPPING WITH REAL RESPONSE PARSING ONCE KEYS ARE ADDED
    =========================================================================
    Map raw Shopify order JSON lists into the aggregate KPIs:
      - orders: count of orders (e.g. len(json_response["orders"]))
      - grossRevenue: sum of order total prices
      - discounts: sum of discount allocations
      - refunds: sum of refund amounts
      - new/returning customer split: inspect 'customer.orders_count'
      - SKUs: aggregate from 'line_items' and query inventory API
    """
    orders = json_response.get("orders", [])
    # Replace this simple mock fallback with actual parsed values:
    return {**MOCK_SHOPIFY, "orders": len(orders)}
