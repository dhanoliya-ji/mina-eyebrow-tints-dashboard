"""
connectors/shiprocket.py
=======================
Pulls per-order delivery status from Shiprocket. This is used ONLY to work out
which Shopify orders actually became collected money — it catches COD orders
that were cancelled and RTO (return to origin) parcels that came back unpaid.
That is essential in India where a large share of orders are Cash on Delivery.

Shiprocket logs you in with your email + password and gives back a token that
is valid for about 10 days, which we cache so we don't log in on every call.

Same three-step pattern: real key -> demo -> mock.
"""

import time
import requests
from datetime import datetime, timedelta, timezone

import config
from mock_data import MOCK_SHIPROCKET
from connectors.demo_live import get_demo_sources

# Cache the login token so we don't authenticate on every sync.
_token_cache = {"token": None, "expires": 0}


def fetch_shiprocket(window_days: int = 7) -> dict:
    """Fetch shipments from Shiprocket for the specified day window."""
    c = config.SHIPROCKET

    # ---- No real key yet -> demo feed or mock ---------------------------
    if not c["live"]:
        if config.DEMO_LIVE:
            try:
                demo = get_demo_sources(window_days=window_days)
                return {"data": demo["shiprocket"], "live": True,
                        "note": f"DEMO live via {demo['signal_source']} — replace with real Shiprocket API"}
            except Exception as e:
                return {"data": MOCK_SHIPROCKET, "live": False, "error": f"demo feed: {e}"}
        return {"data": MOCK_SHIPROCKET, "live": False, "note": "dummy creds — using sample data"}

    # ---- Real credentials -> call the real API --------------------------
    try:
        token = _get_token(c)
        
        # Calculate date range
        today = datetime.now(timezone.utc)
        since = (today - timedelta(days=window_days)).strftime("%Y-%m-%d")
        until = today.strftime("%Y-%m-%d")
        
        resp = requests.get(
            "https://apiv2.shiprocket.in/v1/external/orders",
            headers={"Authorization": f"Bearer {token}"},
            params={"per_page": 250, "from": since, "to": until},
            timeout=20,
        )
        resp.raise_for_status()
        return {"data": _map_shiprocket(resp.json()), "live": True}
    except Exception as e:
        return {"data": MOCK_SHIPROCKET, "live": False, "error": str(e)}


def _get_token(c: dict) -> str:
    """Log in (or reuse the cached token) and return a bearer token."""
    if _token_cache["token"] and time.time() < _token_cache["expires"]:
        return _token_cache["token"]
    resp = requests.post(
        "https://apiv2.shiprocket.in/v1/external/auth/login",
        json={"email": c["email"], "password": c["password"]},
        timeout=20,
    )
    resp.raise_for_status()
    _token_cache["token"] = resp.json()["token"]
    _token_cache["expires"] = time.time() + 9 * 24 * 3600  # ~9 days
    return _token_cache["token"]


def _map_shiprocket(json_response: dict) -> dict:
    """
    Map raw Shiprocket order lists to delivery status counters.
    """
    orders = json_response.get("data", [])
    
    delivered = 0
    in_transit = 0
    cancelled = 0
    rto = 0
    
    cancelled_revenue = 0.0
    rto_revenue = 0.0
    
    for order in orders:
        status = order.get("status", "").lower()
        # Shiprocket order total price
        total_price = float(order.get("total", 0.0))
        
        if "delivered" in status:
            delivered += 1
        elif "cancelled" in status or "canceled" in status:
            cancelled += 1
            cancelled_revenue += total_price
        elif "rto" in status or "return" in status:
            rto += 1
            rto_revenue += total_price
        else:
            in_transit += 1
            
    return {
        "totalOrders": len(orders),
        "delivered": delivered,
        "in_transit": in_transit,
        "cancelled": cancelled,
        "rto": rto,
        "cancelledRevenue": int(round(cancelled_revenue)),
        "rtoRevenue": int(round(rto_revenue))
    }
