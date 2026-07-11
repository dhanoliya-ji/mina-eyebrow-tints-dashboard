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

import config
from mock_data import MOCK_SHIPROCKET
from connectors.demo_live import get_demo_sources

# Cache the login token so we don't authenticate on every sync.
_token_cache = {"token": None, "expires": 0}


def fetch_shiprocket() -> dict:
    c = config.SHIPROCKET

    # ---- No real key yet -> demo feed or mock ---------------------------
    if not c["live"]:
        if config.DEMO_LIVE:
            try:
                demo = get_demo_sources()
                return {"data": demo["shiprocket"], "live": True,
                        "note": f"DEMO live via {demo['signal_source']} — replace with real Shiprocket API"}
            except Exception as e:
                return {"data": MOCK_SHIPROCKET, "live": False, "error": f"demo feed: {e}"}
        return {"data": MOCK_SHIPROCKET, "live": False, "note": "dummy creds — using sample data"}

    # ---- Real credentials -> call the real API --------------------------
    try:
        token = _get_token(c)
        resp = requests.get(
            "https://apiv2.shiprocket.in/v1/external/orders",
            headers={"Authorization": f"Bearer {token}"},
            params={"per_page": 250},
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
    =========================================================================
    REPLACE THIS MAPPING WITH REAL RESPONSE PARSING ONCE KEYS ARE ADDED
    =========================================================================
    Map raw Shiprocket order lists to delivery status counters:
      - Iterate over orders in json_response.
      - Count statuses: "delivered", "in_transit", "canceled", "rto" (returned).
      - Sum up orders that were cancelled before shipping to 'cancelledRevenue'.
      - Sum up orders that were shipped but returned to origin as 'rtoRevenue'.
      - These values will be subtracted from Shopify revenue to find reconciled "true" revenue.
    """
    # Replace this simple mock fallback with actual parsed values:
    return {**MOCK_SHIPROCKET}
