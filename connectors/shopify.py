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


def fetch_shopify(window_days: int = 7) -> dict:
    """Fetch orders and revenue from Shopify for the specified day window."""
    c = config.SHOPIFY

    # ---- No real key yet -> demo feed or mock ---------------------------
    if not c["live"]:
        if config.DEMO_LIVE:
            try:
                demo = get_demo_sources(window_days=window_days)
                return {"data": demo["shopify"], "live": True,
                        "note": f"DEMO live via {demo['signal_source']} — replace with real Shopify Admin API"}
            except Exception as e:
                return {"data": MOCK_SHOPIFY, "live": False, "error": f"demo feed: {e}"}
        return {"data": MOCK_SHOPIFY, "live": False, "note": "dummy token — using sample data"}

    # ---- Real credentials -> call the real API --------------------------
    try:
        # Calculate start range based on selected window
        since = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
        base = f"https://{c['domain']}/admin/api/{c['api_version']}"
        resp = requests.get(
            f"{base}/orders.json",
            headers={"X-Shopify-Access-Token": c["admin_token"]},
            params={"status": "any", "created_at_min": since, "limit": 250},
            timeout=20,
        )
        resp.raise_for_status()
        return {"data": _map_shopify(resp.json(), window_days), "live": True}
    except Exception as e:
        return {"data": MOCK_SHOPIFY, "live": False, "error": str(e)}


def _map_shopify(json_response: dict, window_days: int = 7) -> dict:
    """
    Map raw Shopify order JSON list to the aggregate dashboard metrics.
    """
    orders = json_response.get("orders", [])
    
    total_orders = len(orders)
    gross_revenue = 0.0
    discounts = 0.0
    refunds = 0.0
    new_customers = 0
    
    # SKU tracking
    sku_stats = {}
    
    for o in orders:
        gross_revenue += float(o.get("total_price", 0.0))
        discounts += float(o.get("total_discounts", 0.0))
        
        # Aggregate refunds
        for r in o.get("refunds", []):
            for item in r.get("refund_line_items", []):
                refunds += float(item.get("subtotal", 0.0))
                
        # Check customer profile
        customer = o.get("customer", {})
        if customer:
            orders_count = int(customer.get("orders_count", 1))
            if orders_count <= 1:
                new_customers += 1
                
        # Aggregate SKU sales
        for item in o.get("line_items", []):
            sku = item.get("sku") or "no-sku"
            qty = int(item.get("quantity", 0))
            price = float(item.get("price", 0.0))
            
            if sku not in sku_stats:
                sku_stats[sku] = {
                    "sku": sku,
                    "name": item.get("name", "Shopify Product"),
                    "units": 0,
                    "revenue": 0.0,
                    "inventory": 85,  # fallback safety
                }
            sku_stats[sku]["units"] += qty
            sku_stats[sku]["revenue"] += price * qty
            
    # Format SKU list sorted by revenue
    skus = []
    for s in sku_stats.values():
        days = max(1, window_days)
        s["dailyVelocity"] = round(s["units"] / days, 2)
        skus.append(s)
        
    skus = sorted(skus, key=lambda x: x["revenue"], reverse=True)[:5]
    
    # Estimate sessions based on standard e-commerce conversion rates (2.5%)
    sessions = total_orders * 40
    addToCart = total_orders * 4
    checkouts = total_orders * 2
    
    return {
        "sessions": sessions,
        "addToCart": addToCart,
        "checkouts": checkouts,
        "orders": total_orders,
        "grossRevenue": _r(gross_revenue),
        "refunds": _r(refunds),
        "newCustomers": new_customers,
        "skus": skus
    }


def _r(val: float) -> int:
    return int(round(val))
