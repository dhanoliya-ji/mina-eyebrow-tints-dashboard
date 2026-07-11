"""
config.py
=========
The "settings brain" of the backend.

WHAT THIS FILE DOES
-------------------
1. Reads the .env file (your keys + options) into normal Python variables.
2. For each of the four data sources it decides ONE thing: do we have a REAL
   API key, or should we use test data?  A value is considered real only if it
   exists AND does not start with "DUMMY".

Everything else in the project asks THIS file "is Meta live?" instead of poking
at environment variables directly, so all the credential logic lives in one place.
"""

import os
from dotenv import load_dotenv

# Load the .env file sitting next to this script into os.environ.
# After this line, os.getenv("META_ACCESS_TOKEN") returns whatever is in .env.
load_dotenv()


def _is_real(value: str | None) -> bool:
    """A credential is 'real' only if it is present and not a DUMMY placeholder."""
    return bool(value) and not str(value).startswith("DUMMY")


# ---- General app settings -------------------------------------------------
PORT = int(os.getenv("PORT", "4000"))
SYNC_HOUR = int(os.getenv("SYNC_HOUR", "7"))
SYNC_MINUTE = int(os.getenv("SYNC_MINUTE", "30"))

# DEMO_LIVE=true means: for any source WITHOUT a real key, call a free public
# API (real network request, live-changing numbers) instead of fixed test data.
DEMO_LIVE = os.getenv("DEMO_LIVE", "false").lower() == "true"

# Free Demo API keys for live testing
DEMO_WEATHER_API_KEY = os.getenv("DEMO_WEATHER_API_KEY")
DEMO_WEATHER_API_KEY_LIVE = _is_real(DEMO_WEATHER_API_KEY)

DEMO_EXCHANGERATE_API_KEY = os.getenv("DEMO_EXCHANGERATE_API_KEY")
DEMO_EXCHANGERATE_API_KEY_LIVE = _is_real(DEMO_EXCHANGERATE_API_KEY)


# ---- Per-source credential blocks -----------------------------------------
# Each block is a small dictionary. The "live" key is True only when the real
# keys are present, which is how connectors decide to call the real API.

META = {
    "access_token": os.getenv("META_ACCESS_TOKEN"),
    "ad_account_id": os.getenv("META_AD_ACCOUNT_ID"),
    "api_version": os.getenv("META_API_VERSION", "v21.0"),
}
META["live"] = _is_real(META["access_token"]) and _is_real(META["ad_account_id"])

GOOGLE = {
    "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
    "client_id": os.getenv("GOOGLE_ADS_CLIENT_ID"),
    "client_secret": os.getenv("GOOGLE_ADS_CLIENT_SECRET"),
    "refresh_token": os.getenv("GOOGLE_ADS_REFRESH_TOKEN"),
    "customer_id": os.getenv("GOOGLE_ADS_CUSTOMER_ID"),
    "login_customer_id": os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID"),
}
GOOGLE["live"] = (
    _is_real(GOOGLE["developer_token"])
    and _is_real(GOOGLE["refresh_token"])
    and _is_real(GOOGLE["customer_id"])
)

SHOPIFY = {
    "domain": os.getenv("SHOPIFY_STORE_DOMAIN"),
    "admin_token": os.getenv("SHOPIFY_ADMIN_TOKEN"),
    "api_version": os.getenv("SHOPIFY_API_VERSION", "2025-01"),
}
SHOPIFY["live"] = _is_real(SHOPIFY["admin_token"]) and bool(SHOPIFY["domain"])

SHIPROCKET = {
    "email": os.getenv("SHIPROCKET_EMAIL"),
    "password": os.getenv("SHIPROCKET_PASSWORD"),
}
SHIPROCKET["live"] = _is_real(SHIPROCKET["email"]) and _is_real(SHIPROCKET["password"])


# The spec says: re-pull the last 7 days on every sync, because the ad
# platforms keep revising recent numbers.
WINDOW_DAYS = 7
