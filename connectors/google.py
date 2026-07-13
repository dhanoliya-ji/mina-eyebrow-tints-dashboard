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
import datetime

import config
from mock_data import MOCK_GOOGLE
from connectors.demo_live import get_demo_sources


def fetch_google(window_days: int = 7) -> dict:
    """Fetch ad metrics from Google Ads for the specified day window."""
    c = config.GOOGLE

    # ---- No real key yet -> demo feed or mock ---------------------------
    if not c["live"]:
        if config.DEMO_LIVE:
            try:
                demo = get_demo_sources(window_days=window_days)
                return {"data": demo["google"], "live": True,
                        "note": f"DEMO live via {demo['signal_source']} — replace with real Google Ads API"}
            except Exception as e:
                return {"data": MOCK_GOOGLE, "live": False, "error": f"demo feed: {e}"}
        return {"data": MOCK_GOOGLE, "live": False, "note": "dummy creds — using sample data"}

    # ---- Real credentials -> call the real API --------------------------
    try:
        access_token = _get_access_token(c)
        
        # Calculate date range
        today = datetime.date.today()
        since = (today - datetime.timedelta(days=window_days)).isoformat()
        until = today.isoformat()
        
        # GAQL query using date range filter
        query = f"""
            SELECT campaign.id, campaign.name, campaign.advertising_channel_type,
                   metrics.cost_micros, metrics.clicks, metrics.conversions,
                   metrics.conversions_value, metrics.search_impression_share
             FROM campaign
             WHERE segments.date BETWEEN '{since}' AND '{until}'
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


def _map_google(json_response: list) -> dict:
    """
    Google Ads API return rows from the SearchStream are in GAQL structure.
    Convert the response into the unified campaign list used by the dashboard.
    """
    campaigns = []
    
    # Google Ads searchStream returns a list of result chunks
    for chunk in json_response:
        for row in chunk.get("results", []):
            camp = row.get("campaign", {})
            metrics = row.get("metrics", {})
            
            # Google Ads cost is in micros (millionths of currency unit). Divide by 1M.
            spend = float(metrics.get("costMicros", 0.0)) / 1000000.0
            clicks = int(metrics.get("clicks", 0))
            conversions = float(metrics.get("conversions", 0.0))
            conversions_value = float(metrics.get("conversionsValue", 0.0))
            
            # Impression share is sometimes a string percentage or double
            impr_share = metrics.get("searchImpressionShare")
            impr_share_val = None
            if impr_share:
                if isinstance(impr_share, str):
                    if "%" in impr_share:
                        try:
                            impr_share_val = float(impr_share.replace("%", "")) / 100.0
                        except ValueError:
                            pass
                else:
                    try:
                        impr_share_val = float(impr_share)
                    except (ValueError, TypeError):
                        pass
            
            name = camp.get("name", "Google Campaign")
            # Brand campaign separation: check if name contains 'brand' or 'mina'
            is_brand = "brand" in name.lower() or "mina" in name.lower()
            
            # Google doesn't segment conversions value by 1d vs 7d out of the box in this schema,
            # so we model the attribution delay in conversion value based on typical Google search behaviors.
            conv_value_1d = conversions_value * 0.78  # ~78% immediate
            conv_value_7d = conversions_value
            
            campaigns.append({
                "id": camp.get("id", "g-camp"),
                "name": name,
                "channel": "google",
                "type": camp.get("advertisingChannelType", "Search"),
                "brand": is_brand,
                "spend": spend,
                "clicks": clicks,
                "conversions": conversions,
                "search_impression_share": impr_share_val,
                "conv_value_1d": conv_value_1d,
                "conv_value_7d": conv_value_7d,
                "adsets": []  # Asset/ad groups can be queried separately
            })
            
    return {"campaigns": campaigns}
