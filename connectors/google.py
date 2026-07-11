"""
connectors/google.py
===================
Pulls advertising data from Google Ads (Search, Shopping, Performance Max).

Google is a little more involved than the others: you authenticate with a
long-lived "refresh token" which you exchange for a short-lived "access token"
on each call. That exchange is handled in _get_access_token() below.

Same three-step pattern as every connector: real key -> demo -> mock.
"""

import requests

import config
from mock_data import MOCK_GOOGLE
from connectors.demo_live import get_demo_sources


def fetch_google() -> dict:
    c = config.GOOGLE

    # ---- No real key yet -> demo feed or mock ---------------------------
    if not c["live"]:
        if config.DEMO_LIVE:
            try:
                demo = get_demo_sources()
                return {"data": demo["google"], "live": True,
                        "note": f"DEMO live via {demo['signal_source']} — replace with real Google Ads API"}
            except Exception as e:
                return {"data": MOCK_GOOGLE, "live": False, "error": f"demo feed: {e}"}
        return {"data": MOCK_GOOGLE, "live": False, "note": "dummy creds — using sample data"}

    # ---- Real credentials -> call the real API --------------------------
    try:
        access_token = _get_access_token(c)
        # GAQL (Google Ads Query Language) — like SQL for your ad account.
        query = f"""
            SELECT campaign.name, campaign.advertising_channel_type,
                   metrics.cost_micros, metrics.clicks, metrics.conversions,
                   metrics.conversions_value, metrics.search_impression_share
            FROM campaign
            WHERE segments.date DURING LAST_{config.WINDOW_DAYS}_DAYS
        """
        # =========================================================================
        #  REPLACE/INTEGRATE REAL GOOGLE ADS API KEYS HERE
        #  When you get your real Google Ads API keys, configure them in your .env:
        #    GOOGLE_ADS_DEVELOPER_TOKEN=your_dev_token
        #    GOOGLE_ADS_CLIENT_ID=your_oauth_client_id
        #    GOOGLE_ADS_CLIENT_SECRET=your_oauth_client_secret
        #    GOOGLE_ADS_REFRESH_TOKEN=your_oauth_refresh_token
        #    GOOGLE_ADS_CUSTOMER_ID=your_google_ads_customer_id
        #  This code block will automatically execute once they don't start with "DUMMY".
        # =========================================================================
        resp = requests.post(
            f"https://googleads.googleapis.com/v18/customers/{c['customer_id']}/googleAds:searchStream",
            headers={
                "Authorization": f"Bearer {access_token}",
                "developer-token": c["developer_token"],
                "login-customer-id": c["login_customer_id"],
                "Content-Type": "application/json",
            },
            json={"query": query},
            timeout=20,
        )
        resp.raise_for_status()
        return {"data": _map_google(resp.json()), "live": True}
    except Exception as e:
        return {"data": MOCK_GOOGLE, "live": False, "error": str(e)}


def _get_access_token(c: dict) -> str:
    """Exchange the refresh token for a short-lived access token."""
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": c["client_id"],
            "client_secret": c["client_secret"],
            "refresh_token": c["refresh_token"],
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _map_google(json_response: dict) -> dict:
    """
    =========================================================================
    REPLACE THIS MAPPING WITH REAL RESPONSE PARSING ONCE KEYS ARE ADDED
    =========================================================================
    Google Ads API return rows from the SearchStream are in GAQL structure.
    We convert the response into the unified campaign list used by the dashboard.
    
    Notes:
      - metrics.cost_micros is in millionths of currency unit, divide by 1,000,000 to get INR.
      - Segregate search terms by checking if campaign.name has "brand" or "brand terms".
      - Extract conversion values and map to 1d / 7d columns.
    """
    # Replace this placeholder return once you are ready to map raw Google Ads response:
    return {"campaigns": []}
