"""
connectors/meta.py
==================
Pulls advertising data from Meta Ads (Facebook/Instagram) using the Marketing API.

EVERY connector in this project follows the SAME three-step decision:
    1. If we have a REAL access token  -> call the real Meta API.
    2. Else if DEMO_LIVE is on          -> use the free live demo feed.
    3. Else                              -> use fixed sample (mock) data.

It always returns a dictionary shaped like:
    {"data": <the campaigns>, "live": True/False, "note"/"error": "..."}
so the rest of the program treats real and test data identically.
"""

import requests

import config
from mock_data import MOCK_META
from connectors.demo_live import get_demo_sources


def fetch_meta() -> dict:
    c = config.META

    # ---- Step 1: no real key yet -> demo feed or mock -------------------
    if not c["live"]:
        if config.DEMO_LIVE:
            try:
                demo = get_demo_sources()
                return {"data": demo["meta"], "live": True,
                        "note": f"DEMO live via {demo['signal_source']} — replace with real Meta Marketing API"}
            except Exception as e:
                return {"data": MOCK_META, "live": False, "error": f"demo feed: {e}"}
        return {"data": MOCK_META, "live": False, "note": "dummy token — using sample data"}

    # ---- Step 2: we DO have real credentials -> call the real API -------
    # =========================================================================
    #  REPLACE/INTEGRATE REAL META API KEYS HERE
    #  When you get your real Meta API keys, configure them in your .env:
    #    META_ACCESS_TOKEN=your_actual_facebook_marketing_api_token
    #    META_AD_ACCOUNT_ID=act_your_account_id
    #  This code block will automatically execute once they don't start with "DUMMY".
    # =========================================================================
    try:
        url = (f"https://graph.facebook.com/{c['api_version']}"
               f"/{c['ad_account_id']}/insights")
        params = {
            "level": "campaign",
            "date_preset": f"last_{config.WINDOW_DAYS}d",
            "access_token": c["access_token"],
            # Ask Meta for BOTH attribution windows explicitly — this is central
            # to the product (1-day = immediate intent, 7-day = delayed impact).
            "action_attribution_windows": "1d_click,7d_click",
            "fields": "campaign_id,campaign_name,spend,impressions,clicks,ctr,cpc,cpm,actions,action_values",
        }
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        return {"data": _map_meta(resp.json()), "live": True}
    except Exception as e:
        # Never crash the dashboard: log the error, fall back to sample data.
        return {"data": MOCK_META, "live": False, "error": str(e)}


def _map_meta(json_response: dict) -> dict:
    """
    =========================================================================
    REPLACE THIS MAPPING WITH REAL RESPONSE PARSING ONCE KEYS ARE ADDED
    =========================================================================
    Meta Ads API returns a list of insights dictionaries. You need to parse
    the 'actions' list to retrieve purchase counts, and the 'action_values'
    list to retrieve purchase values for both '1d_click' and '7d_click'.
    
    Structure of Meta API return item:
      {
        "campaign_id": "...",
        "campaign_name": "...",
        "spend": 1200.0,
        "actions": [
          {"action_type": "purchase", "1d_click": 5, "7d_click": 8}
        ],
        "action_values": [
          {"action_type": "purchase", "1d_click": 2500.0, "7d_click": 4000.0}
        ]
      }
    """
    # Replace this placeholder return once you are ready to map raw Meta response:
    return {"campaigns": []}
