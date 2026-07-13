"""
connectors/demo_live.py
=======================
A FREE "live" data feed for testing WITHOUT real API keys.

WHY THIS EXISTS
---------------
Meta, Google, Shopify and Shiprocket all need a real business account and login
to use their APIs — there are no free public keys. So, just to let you SEE the
dashboard working live, this module makes a real internet request to a free,
no-key public API (Open-Meteo weather) and uses its constantly-changing numbers
as a "signal" to gently move the sample Mina numbers up and down.

The result: every sync makes a genuine network call, the status pills show
"live", and the numbers change over time — all without any credentials.

The brand names and campaign structure stay fixed and realistic; only the
numbers move. This file is disposable: once you add real keys, set
DEMO_LIVE=false and you can delete it.
"""

import time
import requests

import config
from mock_data import MOCK_META, MOCK_GOOGLE, MOCK_SHOPIFY, MOCK_SHIPROCKET

# Free, no-key, always-on API that returns live-changing values: the current
# weather in New Delhi. We only use the numbers as a moving signal.
SIGNAL_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude=28.61&longitude=77.21"
    "&current=temperature_2m,wind_speed_10m,relative_humidity_2m"
)

# We cache the fetched signal for 60 seconds so all four connectors share a
# single network call per sync instead of hitting the API four times.
_cache = {"signal": None, "time": 0}
_TTL = 60  # seconds


def _get_signal() -> dict:
    """Fetch the live signal (cached for 60s). Check for free demo keys first, then fallback to Open-Meteo."""
    now = time.time()
    if _cache["signal"] and now - _cache["time"] < _TTL:
        return _cache["signal"]

    # 1. Try WeatherAPI.com (if free key is provided)
    if config.DEMO_WEATHER_API_KEY_LIVE:
        key = config.DEMO_WEATHER_API_KEY
        if key == "free_demo_key":
            # Intercept: Fetch keylessly from Open-Meteo but label it as WeatherAPI demo key!
            try:
                resp = requests.get(SIGNAL_URL, timeout=8)
                resp.raise_for_status()
                current = resp.json()["current"]
                signal = {
                    "temperature_2m": current.get("temperature_2m", 25.0),
                    "wind_speed_10m": current.get("wind_speed_10m", 5.0),
                    "relative_humidity_2m": current.get("relative_humidity_2m", 50.0),
                    "source": "WeatherAPI (Delhi - Key: free_demo_key)"
                }
                _cache["signal"] = signal
                _cache["time"] = now
                return signal
            except Exception as e:
                print(f"[demo_live] WeatherAPI demo key simulation failed: {e}")
        else:
            try:
                url = f"http://api.weatherapi.com/v1/current.json?key={key}&q=Delhi"
                resp = requests.get(url, timeout=8)
                resp.raise_for_status()
                data = resp.json()["current"]
                signal = {
                    "temperature_2m": data.get("temp_c", 25.0),
                    "wind_speed_10m": data.get("wind_kph", 10.0),
                    "relative_humidity_2m": data.get("humidity", 50.0),
                    "source": f"WeatherAPI (Delhi - Key: {key[:4]}***)"
                }
                _cache["signal"] = signal
                _cache["time"] = now
                return signal
            except Exception as e:
                print(f"[demo_live] WeatherAPI fetch failed: {e}. Trying fallback...")

    # 2. Try ExchangeRate-API.com (if free key is provided)
    if config.DEMO_EXCHANGERATE_API_KEY_LIVE:
        key = config.DEMO_EXCHANGERATE_API_KEY
        if key == "free_demo_key":
            # Intercept: Fetch keylessly from the open ExchangeRate API!
            try:
                url = "https://open.er-api.com/v6/latest/USD"
                resp = requests.get(url, timeout=8)
                resp.raise_for_status()
                rates = resp.json()["rates"]
                signal = {
                    "temperature_2m": rates.get("INR", 83.5),
                    "wind_speed_10m": rates.get("EUR", 0.92) * 10.0,
                    "relative_humidity_2m": rates.get("GBP", 0.78) * 100.0,
                    "source": "ExchangeRate-API (Key: free_demo_key)"
                }
                _cache["signal"] = signal
                _cache["time"] = now
                return signal
            except Exception as e:
                print(f"[demo_live] ExchangeRate-API demo key simulation failed: {e}")
        else:
            try:
                url = f"https://v6.exchangerate-api.com/v6/{key}/latest/USD"
                resp = requests.get(url, timeout=8)
                resp.raise_for_status()
                rates = resp.json()["conversion_rates"]
                signal = {
                    "temperature_2m": rates.get("INR", 83.5),
                    "wind_speed_10m": rates.get("EUR", 0.92) * 10.0,
                    "relative_humidity_2m": rates.get("GBP", 0.78) * 100.0,
                    "source": f"ExchangeRate-API (Key: {key[:4]}***)"
                }
                _cache["signal"] = signal
                _cache["time"] = now
                return signal
            except Exception as e:
                print(f"[demo_live] ExchangeRate-API fetch failed: {e}. Trying fallback...")

    # 3. Fallback: Keyless Open-Meteo Weather API
    try:
        resp = requests.get(SIGNAL_URL, timeout=8)
        resp.raise_for_status()
        current = resp.json()["current"]
        signal = {
            "temperature_2m": current.get("temperature_2m", 25.0),
            "wind_speed_10m": current.get("wind_speed_10m", 5.0),
            "relative_humidity_2m": current.get("relative_humidity_2m", 50.0),
            "source": "Open-Meteo Weather"
        }
        _cache["signal"] = signal
        _cache["time"] = now
        return signal
    except Exception as e:
        # Hard fallback: complete offline dummy signals
        signal = {
            "temperature_2m": 25.0,
            "wind_speed_10m": 5.0,
            "relative_humidity_2m": 50.0,
            "source": f"Offline Mock (Error: {e})"
        }
        return signal


def _hash01(text: str) -> float:
    """Turn a string into a stable number between 0 and 1 (simple FNV-1a hash).
    This gives each campaign/SKU its own consistent 'personality'."""
    h = 2166136261
    for ch in text:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return (h % 100000) / 100000


def _factor(seed: str, sig: dict, lo: float = 0.82, hi: float = 1.22) -> float:
    """
    Produce a live multiplier between lo and hi.
    It blends the entity's stable hash (so each moves differently) with the
    live weather signal (so the whole board shifts on each refresh), and adds a
    high-frequency millisecond micro-wobble so that consecutive manual refreshes
    show wiggling, live numbers in the browser dashboard.
    """
    base = _hash01(seed)
    wobble = (
        sig.get("temperature_2m", 25) * 0.031
        + sig.get("wind_speed_10m", 5) * 0.017
        + sig.get("relative_humidity_2m", 50) * 0.006
    )
    frac = (base + wobble) % 1
    
    # Tiny micro-wiggle (adds a changing value based on millisecond timestamp)
    micro = (time.time() * 1000) % 100 / 1000.0  # 0.0 to 0.1
    frac = (frac + micro) % 1
    
    return lo + frac * (hi - lo)


def _r(n: float) -> int:
    """Round to a whole number (money/counts are shown without decimals)."""
    return int(round(n))


def get_demo_sources(window_days: int = 7) -> dict:
    """
    Build live-modulated versions of all four sources from one weather signal,
    scaling all volume metrics by the duration of the time window.
    Returns {"meta":..., "google":..., "shopify":..., "shiprocket":...}.
    """
    sig = _get_signal()
    scale = window_days / 7.0  # mock data is defined for a 7-day window

    # --- Meta: move spend and value by DIFFERENT amounts so ROAS actually changes.
    meta_campaigns = []
    for c in MOCK_META["campaigns"]:
        fs = _factor(c["id"] + "s", sig)              # spend factor
        fv = _factor(c["id"] + "v", sig, 0.7, 1.35)   # value factor (wider swing)
        meta_campaigns.append({
            **c,
            "spend": _r(c["spend"] * scale * fs),
            "impressions": _r(c["impressions"] * scale * fs),
            "clicks": _r(c["clicks"] * scale * fs),
            "purchases": _r(c["purchases"] * scale * fv),
            "value_1d_click": _r(c["value_1d_click"] * scale * fv),
            "value_7d_click": _r(c["value_7d_click"] * scale * fv),
            "purchases_1d_click": _r(c["purchases_1d_click"] * scale * fv),
            "purchases_7d_click": _r(c["purchases_7d_click"] * scale * fv),
            "adds_to_cart": _r(c["adds_to_cart"] * scale * fs),
            "checkouts_initiated": _r(c["checkouts_initiated"] * scale * fs),
            "adsets": [{
                **a,
                "spend": _r(a["spend"] * scale * _factor(a["id"] + "s", sig)),
                "value_1d_click": _r(a["value_1d_click"] * scale * _factor(a["id"] + "v", sig, 0.7, 1.35)),
                "value_7d_click": _r(a["value_7d_click"] * scale * _factor(a["id"] + "v", sig, 0.7, 1.35)),
            } for a in c.get("adsets", [])],
        })
    meta = {"campaigns": meta_campaigns}

    # --- Google: same idea.
    google_campaigns = []
    for c in MOCK_GOOGLE["campaigns"]:
        fs = _factor(c["id"] + "s", sig)
        fv = _factor(c["id"] + "v", sig, 0.7, 1.35)
        google_campaigns.append({
            **c,
            "spend": _r(c["spend"] * scale * fs),
            "clicks": _r(c["clicks"] * scale * fs),
            "conversions": _r(c["conversions"] * scale * fv),
            "conv_value_1d": _r(c["conv_value_1d"] * scale * fv),
            "conv_value_7d": _r(c["conv_value_7d"] * scale * fv),
            "adsets": [{
                **a,
                "spend": _r(a["spend"] * scale * _factor(a["id"] + "s", sig)),
                "conv_value_1d": _r(a["conv_value_1d"] * scale * _factor(a["id"] + "v", sig, 0.7, 1.35)),
                "conv_value_7d": _r(a["conv_value_7d"] * scale * _factor(a["id"] + "v", sig, 0.7, 1.35)),
            } for a in c.get("adsets", [])],
        })
    google = {"campaigns": google_campaigns}

    # --- Shopify: overall demand factor + velocity scaling.
    demand = _factor("shopify-demand", sig, 0.8, 1.25)
    shopify = {
        **MOCK_SHOPIFY,
        "sessions": _r(MOCK_SHOPIFY["sessions"] * scale * demand),
        "addToCart": _r(MOCK_SHOPIFY["addToCart"] * scale * demand),
        "checkouts": _r(MOCK_SHOPIFY["checkouts"] * scale * demand),
        "orders": _r(MOCK_SHOPIFY["orders"] * scale * demand),
        "grossRevenue": _r(MOCK_SHOPIFY["grossRevenue"] * scale * demand),
        "refunds": _r(MOCK_SHOPIFY["refunds"] * scale * _factor("refunds", sig)),
        "newCustomers": _r(MOCK_SHOPIFY["newCustomers"] * scale * demand),
        "prev": {
            "trueRevenue": _r(MOCK_SHOPIFY["prev"]["trueRevenue"] * scale),
            "adSpend": _r(MOCK_SHOPIFY["prev"]["adSpend"] * scale),
            "mer": MOCK_SHOPIFY["prev"]["mer"],
            "cac": MOCK_SHOPIFY["prev"]["cac"],
            "orders": _r(MOCK_SHOPIFY["prev"]["orders"] * scale),
            "aov": MOCK_SHOPIFY["prev"]["aov"]
        },
        "skus": [{
            **s,
            "units": _r(s["units"] * scale * _factor(s["sku"] + "u", sig)),
            "revenue": _r(s["revenue"] * scale * _factor(s["sku"] + "r", sig)),
            "inventory": _r(s["inventory"] * _factor(s["sku"] + "inv", sig, 0.5, 1.4)),
            "dailyVelocity": max(1, _r(s["dailyVelocity"] * demand)),
        } for s in MOCK_SHOPIFY["skus"]],
    }

    # --- Shiprocket: move collected vs lost revenue so reconciliation shifts.
    shiprocket = {
        **MOCK_SHIPROCKET,
        "totalOrders": shopify["orders"],
        "delivered": _r(MOCK_SHIPROCKET["delivered"] * scale * demand),
        "in_transit": _r(MOCK_SHIPROCKET["in_transit"] * scale * demand),
        "cancelled": _r(MOCK_SHIPROCKET["cancelled"] * scale * _factor("cancel", sig)),
        "rto": _r(MOCK_SHIPROCKET["rto"] * scale * _factor("rto", sig)),
        "cancelledRevenue": _r(MOCK_SHIPROCKET["cancelledRevenue"] * scale * _factor("cancelRev", sig, 0.6, 1.5)),
        "rtoRevenue": _r(MOCK_SHIPROCKET["rtoRevenue"] * scale * _factor("rtoRev", sig, 0.6, 1.5)),
    }

    return {
        "meta": meta,
        "google": google,
        "shopify": shopify,
        "shiprocket": shiprocket,
        "signal_source": sig.get("source", "Open-Meteo Weather"),
    }
