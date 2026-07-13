"""
metrics.py
==========
All the number-crunching. This is where raw platform data becomes the metrics
the dashboard shows. Every function takes one dictionary `d` holding the four
sources plus settings:

    d = {
        "meta": {...}, "google": {...},
        "shopify": {...}, "shiprocket": {...},
        "thresholds": {...}, "platformCredibility": {...},
    }

The golden rule of this file: REVENUE = reconciled "true" revenue from Shopify +
Shiprocket. Platform-reported revenue is only ever used for the comparison cards.
"""


def _div(a, b):
    """Safe division — returns 0 instead of crashing when dividing by zero."""
    return a / b if b else 0


def _sum(items, key):
    """Add up one field across a list of dicts (missing values count as 0)."""
    return sum(x.get(key, 0) or 0 for x in (items or []))


# ---------------------------------------------------------------------------
#  RECONCILIATION — the single source of truth
# ---------------------------------------------------------------------------
def reconcile(d: dict) -> dict:
    """
    True revenue = Shopify order revenue
                   - refunds
                   - cancelled order revenue   (Shiprocket)
                   - RTO order revenue          (Shiprocket, returned/never paid)

    'collectedFactor' is the fraction of gross revenue actually collected. We
    use it to estimate how much of each platform's reported sales were real.
    """
    shopify, shiprocket = d["shopify"], d["shiprocket"]
    gross = shopify["grossRevenue"]
    excluded = shopify["refunds"] + shiprocket["cancelledRevenue"] + shiprocket["rtoRevenue"]
    true_revenue = gross - excluded
    return {
        "gross": gross,
        "refunds": shopify["refunds"],
        "cancelled": shiprocket["cancelledRevenue"],
        "rto": shiprocket["rtoRevenue"],
        "trueRevenue": true_revenue,
        "collectedFactor": _div(true_revenue, gross),
        "deliveredRate": _div(shiprocket["delivered"], shiprocket["totalOrders"]),
    }


# ---------------------------------------------------------------------------
#  TOP-LINE KPIs (the 6 tiles at the top of the dashboard)
# ---------------------------------------------------------------------------
def topline(d: dict) -> dict:
    """
    Returns each KPI with: value, yesterday's value (prev), whether "up" is good,
    and how to format it. 'goodUp' lets the UI colour the delta correctly —
    revenue going up is green, but CAC (cost) going up is red.
    """
    rec = reconcile(d)
    ad_spend = _sum(d["meta"]["campaigns"], "spend") + _sum(d["google"]["campaigns"], "spend")
    orders = d["shopify"]["orders"]
    new_customers = d["shopify"]["newCustomers"]

    mer = _div(rec["trueRevenue"], ad_spend)          # Marketing Efficiency Ratio
    cac = _div(ad_spend, new_customers)               # Blended cost to acquire a customer
    aov = _div(rec["trueRevenue"], orders)            # Average order value

    # Live connectors (e.g. real Shopify) may not supply yesterday's figures.
    # Fall back to the current value so deltas render flat instead of crashing.
    p = d["shopify"].get("prev") or {}
    return {
        "trueRevenue": {"value": rec["trueRevenue"], "prev": p.get("trueRevenue", rec["trueRevenue"]), "goodUp": True, "fmt": "inr"},
        "adSpend":     {"value": ad_spend,           "prev": p.get("adSpend", ad_spend),               "goodUp": None, "fmt": "inr"},
        "mer":         {"value": mer,                "prev": p.get("mer", mer),                         "goodUp": True, "fmt": "x"},
        "cac":         {"value": cac,                "prev": p.get("cac", cac),                         "goodUp": False, "fmt": "inr"},
        "orders":      {"value": orders,             "prev": p.get("orders", orders),                   "goodUp": True, "fmt": "int"},
        "aov":         {"value": aov,                "prev": p.get("aov", aov),                         "goodUp": True, "fmt": "inr"},
    }


# ---------------------------------------------------------------------------
#  ATTRIBUTION — 1-day vs 7-day, platform-reported vs true (per platform)
# ---------------------------------------------------------------------------
def _build_attrib(name, spend, val_1d, val_7d, true_factor):
    """Assemble one platform's attribution card numbers."""
    true_rev = val_7d * true_factor            # reconciled + credibility-adjusted
    over_report = val_7d - true_rev            # how much the platform over-claims
    return {
        "name": name,
        "spend": spend,
        "roas1d": _div(val_1d, spend),
        "roas7d": _div(val_7d, spend),
        "trueRoas": _div(true_rev, spend),
        "reportedRev1d": val_1d,
        "reportedRev7d": val_7d,
        "trueRev": true_rev,
        "overReportAbs": over_report,
        "overReportPct": _div(over_report, true_rev),
    }


def attribution(d: dict) -> list:
    """
    For Meta and Google, show the immediate (1-day) and delayed (7-day) ROAS,
    then the platform-reported vs reconciled revenue and the over-report gap.

    true_factor = how much of the platform's revenue was actually collected
                  (collectedFactor) AND believable (platformCredibility). Meta
                  tends to over-claim more than Google brand search.
    """
    rec = reconcile(d)
    cred = d["platformCredibility"]

    meta_spend = _sum(d["meta"]["campaigns"], "spend")
    meta_1d = _sum(d["meta"]["campaigns"], "value_1d_click")
    meta_7d = _sum(d["meta"]["campaigns"], "value_7d_click")

    g_spend = _sum(d["google"]["campaigns"], "spend")
    g_1d = _sum(d["google"]["campaigns"], "conv_value_1d")
    g_7d = _sum(d["google"]["campaigns"], "conv_value_7d")

    return [
        _build_attrib("Meta Ads", meta_spend, meta_1d, meta_7d, rec["collectedFactor"] * cred["meta"]),
        _build_attrib("Google Ads", g_spend, g_1d, g_7d, rec["collectedFactor"] * cred["google"]),
    ]


# ---------------------------------------------------------------------------
#  SHOPIFY FUNNEL (sessions -> add to cart -> checkout -> orders)
# ---------------------------------------------------------------------------
def funnel(d: dict) -> list:
    s = d["shopify"]
    steps = [
        {"label": "Sessions", "count": s["sessions"]},
        {"label": "Add to cart", "count": s["addToCart"]},
        {"label": "Checkout", "count": s["checkouts"]},
        {"label": "Orders", "count": s["orders"]},
    ]
    top = steps[0]["count"]
    for i, st in enumerate(steps):
        st["pct"] = _div(st["count"], top)  # width of the bar (relative to sessions)
        # Drop-off rate from the previous step (e.g. what % of carts checked out).
        st["stepRate"] = None if i == 0 else _div(st["count"], steps[i - 1]["count"])
    return steps


# ---------------------------------------------------------------------------
#  SKU PERFORMANCE + stock-out forecast
# ---------------------------------------------------------------------------
def sku_performance(d: dict) -> list:
    out = []
    stock_out_days = d["thresholds"]["stockOutDays"]
    for s in d["shopify"]["skus"]:
        # Days of stock left = current inventory / how many sell per day.
        days_left = s["inventory"] / s["dailyVelocity"] if s["dailyVelocity"] else float("inf")
        out.append({**s, "daysToStockOut": days_left, "stockOut": days_left <= stock_out_days})
    # Show the biggest earners first.
    return sorted(out, key=lambda s: s["revenue"], reverse=True)


# ---------------------------------------------------------------------------
#  PER-CAMPAIGN numbers (feeds the recommendations table)
# ---------------------------------------------------------------------------
def _normalize_campaign(c, true_factor):
    true_rev = c["value7d"] * true_factor
    return {
        **c,
        "roas1d": _div(c["value1d"], c["spend"]),
        "roas7d": _div(c["value7d"], c["spend"]),
        "trueRoas": _div(true_rev, c["spend"]),
        "trueRev": true_rev,
        "cpa": _div(c["spend"], c["purchases"]),
    }


def campaign_rows(d: dict) -> list:
    """
    Flatten Meta + Google campaigns into one list with a common shape, each with
    1-day / 7-day / true ROAS, ready for the rules engine to label with an action.
    """
    rec = reconcile(d)
    meta_factor = rec["collectedFactor"] * d["platformCredibility"]["meta"]
    google_factor = rec["collectedFactor"] * d["platformCredibility"]["google"]
    rows = []

    for c in d["meta"]["campaigns"]:
        rows.append(_normalize_campaign({
            "id": c["id"], "name": c["name"], "channel": "Meta", "type": c["type"],
            "spend": c["spend"], "value1d": c["value_1d_click"], "value7d": c["value_7d_click"],
            "purchases": c["purchases"],
            "subs": [{
                "name": a["name"], "spend": a["spend"],
                "roas1d": _div(a["value_1d_click"], a["spend"]),
                "roas7d": _div(a["value_7d_click"], a["spend"]),
            } for a in c.get("adsets", [])],
        }, meta_factor))

    for c in d["google"]["campaigns"]:
        rows.append(_normalize_campaign({
            "id": c["id"], "name": c["name"], "channel": "Google", "type": c["type"],
            "spend": c["spend"], "value1d": c["conv_value_1d"], "value7d": c["conv_value_7d"],
            "purchases": c["conversions"],
            "subs": [{
                "name": a["name"], "spend": a["spend"],
                "roas1d": _div(a["conv_value_1d"], a["spend"]),
                "roas7d": _div(a["conv_value_7d"], a["spend"]),
            } for a in c.get("adsets", [])],
        }, google_factor))

    return rows
