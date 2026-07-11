"""
mock_data.py
============
Realistic sample data for Mina Eyebrow Tints, written in the EXACT shape the
real platform APIs return. This is the fallback each connector serves when it
does not yet have a real API key.

Because the field names here match the live APIs, switching to real data later
is a drop-in change — the maths in metrics.py and rules.py never changes.

Money is in Indian Rupees (INR). A "campaign" contains "adsets" (Meta) or
"asset groups / ad groups" (Google) so we can drill down.
"""

# ---- Meta Ads (Marketing API) ---------------------------------------------
# Note the two attribution windows: value_1d_click (sales within 1 day of a
# click) and value_7d_click (within 7 days). Showing both is a core rule.
MOCK_META = {
    "campaigns": [
        {
            "id": "m-ret", "name": "Retargeting · Warm 30d", "channel": "meta",
            "type": "Advantage+",
            "spend": 18400, "impressions": 214000, "clicks": 5120, "purchases": 96,
            "value_1d_click": 61200, "value_7d_click": 118400,
            "purchases_1d_click": 52, "purchases_7d_click": 96,
            "adds_to_cart": 640, "checkouts_initiated": 240,
            "adsets": [
                {"id": "m-ret-a", "name": "Warm · Cart abandon", "spend": 9800, "clicks": 2700, "purchases": 58, "value_1d_click": 36000, "value_7d_click": 71000},
                {"id": "m-ret-b", "name": "Warm · Viewed product", "spend": 8600, "clicks": 2420, "purchases": 38, "value_1d_click": 25200, "value_7d_click": 47400},
            ],
        },
        {
            "id": "m-pros", "name": "Prospecting · Broad", "channel": "meta",
            "type": "Advantage+",
            "spend": 41200, "impressions": 1240000, "clicks": 14800, "purchases": 112,
            "value_1d_click": 38400, "value_7d_click": 172000,
            "purchases_1d_click": 34, "purchases_7d_click": 112,
            "adds_to_cart": 1180, "checkouts_initiated": 360,
            "adsets": [
                {"id": "m-pros-a", "name": "Broad · Video hooks", "spend": 24800, "clicks": 9100, "purchases": 71, "value_1d_click": 24000, "value_7d_click": 109000},
                {"id": "m-pros-b", "name": "Broad · Static UGC", "spend": 16400, "clicks": 5700, "purchases": 41, "value_1d_click": 14400, "value_7d_click": 63000},
            ],
        },
        {
            "id": "m-test", "name": "Creative testing · New UGC", "channel": "meta",
            "type": "ABO",
            "spend": 12600, "impressions": 388000, "clicks": 3900, "purchases": 14,
            "value_1d_click": 5400, "value_7d_click": 11800,
            "purchases_1d_click": 8, "purchases_7d_click": 14,
            "adds_to_cart": 210, "checkouts_initiated": 52,
            "adsets": [
                {"id": "m-test-a", "name": "Test · Founder story", "spend": 6400, "clicks": 2000, "purchases": 9, "value_1d_click": 3600, "value_7d_click": 7600},
                {"id": "m-test-b", "name": "Test · Before/after", "spend": 6200, "clicks": 1900, "purchases": 5, "value_1d_click": 1800, "value_7d_click": 4200},
            ],
        },
    ],
}

# ---- Google Ads (Google Ads API) ------------------------------------------
# "brand": True marks campaigns that target the brand name ("mina ...").
MOCK_GOOGLE = {
    "campaigns": [
        {
            "id": "g-brand", "name": "Search · Brand", "channel": "google",
            "type": "Search", "brand": True,
            "spend": 4200, "clicks": 1980, "conversions": 78, "search_impression_share": 0.82,
            "conv_value_1d": 58000, "conv_value_7d": 71000,
            "adsets": [
                {"id": "g-brand-a", "name": '"mina eyebrow tint"', "spend": 2600, "clicks": 1240, "conversions": 52, "conv_value_1d": 39000, "conv_value_7d": 47000},
                {"id": "g-brand-b", "name": '"mina brow"', "spend": 1600, "clicks": 740, "conversions": 26, "conv_value_1d": 19000, "conv_value_7d": 24000},
            ],
        },
        {
            "id": "g-pmax", "name": "Performance Max · Catalog", "channel": "google",
            "type": "PMax", "brand": False,
            "spend": 22800, "clicks": 6100, "conversions": 84, "search_impression_share": None,
            "conv_value_1d": 41000, "conv_value_7d": 132000,
            "adsets": [
                {"id": "g-pmax-a", "name": "Asset group · Bestsellers", "spend": 13400, "clicks": 3600, "conversions": 54, "conv_value_1d": 27000, "conv_value_7d": 84000},
                {"id": "g-pmax-b", "name": "Asset group · New arrivals", "spend": 9400, "clicks": 2500, "conversions": 30, "conv_value_1d": 14000, "conv_value_7d": 48000},
            ],
        },
        {
            "id": "g-shop", "name": "Shopping · Non-brand", "channel": "google",
            "type": "Shopping", "brand": False,
            "spend": 15600, "clicks": 4200, "conversions": 22, "search_impression_share": 0.34,
            "conv_value_1d": 9800, "conv_value_7d": 21400,
            "adsets": [
                {"id": "g-shop-a", "name": '"eyebrow tint india"', "spend": 8600, "clicks": 2300, "conversions": 13, "conv_value_1d": 6000, "conv_value_7d": 12800},
                {"id": "g-shop-b", "name": '"brow color pen"', "spend": 7000, "clicks": 1900, "conversions": 9, "conv_value_1d": 3800, "conv_value_7d": 8600},
            ],
        },
    ],
}

# ---- Shopify (Admin API) ---------------------------------------------------
# grossRevenue is order revenue AFTER discounts but BEFORE reconciliation.
# "prev" holds yesterday's figures so we can show the up/down deltas on the KPIs.
MOCK_SHOPIFY = {
    "sessions": 14820,
    "addToCart": 2140,
    "checkouts": 1080,
    "orders": 612,
    "grossRevenue": 921000,
    "discounts": 58400,
    "refunds": 31200,
    "newCustomers": 430,
    "returningCustomers": 182,
    "prev": {"trueRevenue": 742000, "adSpend": 121400, "orders": 588, "aov": 1338, "mer": 6.1, "cac": 305},
    "skus": [
        {"sku": "MINA-BRN-01", "name": "Brown eyebrow tint", "units": 214, "revenue": 274000, "inventory": 96, "dailyVelocity": 31},
        {"sku": "MINA-BLK-01", "name": "Black eyebrow tint", "units": 168, "revenue": 218000, "inventory": 41, "dailyVelocity": 27},
        {"sku": "MINA-GRY-01", "name": "Grey-brown tint", "units": 121, "revenue": 152000, "inventory": 300, "dailyVelocity": 18},
        {"sku": "MINA-KIT-01", "name": "Starter kit (tint + brush)", "units": 88, "revenue": 158000, "inventory": 22, "dailyVelocity": 14},
        {"sku": "MINA-BRS-01", "name": "Precision brush", "units": 96, "revenue": 48000, "inventory": 640, "dailyVelocity": 12},
    ],
}

# ---- Shiprocket (API) ------------------------------------------------------
# Delivery status per order. Used ONLY to work out which orders became real,
# collected money. cancelledRevenue + rtoRevenue are subtracted from Shopify
# revenue to get "true" revenue (important for COD-heavy Indian D2C).
MOCK_SHIPROCKET = {
    "totalOrders": 612,
    "delivered": 388,
    "in_transit": 150,
    "cancelled": 34,      # cancelled before shipping
    "rto": 40,            # return to origin — shipped but came back, never paid
    "codShare": 0.61,     # 61% of orders are Cash on Delivery
    "cancelledRevenue": 44600,
    "rtoRevenue": 52800,
}
