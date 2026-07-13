"""
connectors/meta.py
==================
Pulls advertising data from Meta Ads (Facebook/Instagram) using the Marketing API.

EVERY connector in this project follows the SAME three-step decision:
    1. If we have a REAL access token  -> call the real Meta API.
    2. Else if DEMO_LIVE is on          -> use the free live demo feed.
    3. Else                              -> use fixed sample (mock) data.
"""

import requests
import datetime

import config
from mock_data import MOCK_META
from connectors.demo_live import get_demo_sources


def fetch_meta(window_days: int = 7) -> dict:
    """Fetch ad insights from Meta Ads for the specified day window."""
    c = config.META

    # ---- Step 1: no real key yet -> demo feed or mock -------------------
    if not c["live"]:
        if config.DEMO_LIVE:
            try:
                demo = get_demo_sources(window_days=window_days)
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
        url = f"https://graph.facebook.com/{c['api_version']}/{c['ad_account_id']}/insights"
        
        # Calculate time range
        today = datetime.date.today()
        since = (today - datetime.timedelta(days=window_days)).isoformat()
        until = today.isoformat()
        time_range = f'{{"since":"{since}","until":"{until}"}}'
        
        params = {
            "level": "campaign",
            "time_range": time_range,
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
        return {"data": MOCK_META, "live": False, "error": str(e)}


def _map_meta(json_response: dict) -> dict:
    """
    Map raw Meta response JSON insights list to the unified campaign structure.
    Meta Ads API returns a list of insights dictionaries.
    """
    campaigns = []
    items = json_response.get("data", [])
    
    for item in items:
        campaign_id = item.get("campaign_id", "")
        campaign_name = item.get("campaign_name", "Unnamed Meta Campaign")
        spend = float(item.get("spend", 0.0))
        impressions = int(item.get("impressions", 0))
        clicks = int(item.get("clicks", 0))
        
        # Compute rates if they aren't explicitly in the response
        ctr = float(item.get("ctr", 0.0)) if item.get("ctr") else (clicks / impressions if impressions else 0.0)
        cpc = float(item.get("cpc", 0.0)) if item.get("cpc") else (spend / clicks if clicks else 0.0)
        cpm = float(item.get("cpm", 0.0)) if item.get("cpm") else (spend / impressions * 1000.0 if impressions else 0.0)
        
        purchases_1d = 0
        purchases_7d = 0
        value_1d = 0.0
        value_7d = 0.0
        adds_to_cart = 0
        checkouts_initiated = 0
        
        # Parse actions for purchase count, add to cart, and checkouts initiated
        actions = item.get("actions", [])
        if isinstance(actions, list):
            for act in actions:
                atype = act.get("action_type")
                if atype in ["offsite_conversion.fb_pixel_purchase", "purchase"]:
                    # Try reading 1d/7d attribution values or fall back to standard value
                    purchases_1d += int(act.get("1d_click", 0))
                    purchases_7d += int(act.get("7d_click", act.get("value", 0)))
                elif atype in ["offsite_conversion.fb_pixel_add_to_cart", "add_to_cart"]:
                    adds_to_cart += int(act.get("value", 0))
                elif atype in ["offsite_conversion.fb_pixel_initiate_checkout", "initiate_checkout"]:
                    checkouts_initiated += int(act.get("value", 0))
                    
        # Parse action values for purchase value
        action_values = item.get("action_values", [])
        if isinstance(action_values, list):
            for val in action_values:
                vtype = val.get("action_type")
                if vtype in ["offsite_conversion.fb_pixel_purchase", "purchase"]:
                    value_1d += float(val.get("1d_click", 0.0))
                    value_7d += float(val.get("7d_click", val.get("value", 0.0)))
                    
        campaigns.append({
            "id": campaign_id,
            "name": campaign_name,
            "channel": "meta",
            "type": "Advantage+",
            "spend": spend,
            "impressions": impressions,
            "clicks": clicks,
            "ctr": ctr,
            "cpc": cpc,
            "cpm": cpm,
            "purchases": purchases_7d,
            "value_1d_click": value_1d,
            "value_7d_click": value_7d,
            "purchases_1d_click": purchases_1d,
            "purchases_7d_click": purchases_7d,
            "adds_to_cart": adds_to_cart,
            "checkouts_initiated": checkouts_initiated,
            "adsets": [] # In simple insights pull, adsets are skipped unless queried separately
        })
        
    return {"campaigns": campaigns}
