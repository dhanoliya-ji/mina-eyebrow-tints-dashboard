"""
preflight.py — run BEFORE showing the dashboard after adding real keys.

    python preflight.py

It re-reads .env, then calls each connector once and prints a clean
LIVE / MOCK / ERROR status per source so you know exactly what will show
on screen. No mistakes in front of anyone.
"""
import importlib
import config
importlib.reload(config)  # ensure freshest .env

from connectors.meta import fetch_meta
from connectors.google import fetch_google
from connectors.shopify import fetch_shopify
from connectors.shiprocket import fetch_shiprocket

print("\n  Credential flags (from .env):")
print(f"    Meta       live={config.META['live']}")
print(f"    Google     live={config.GOOGLE['live']}")
print(f"    Shopify    live={config.SHOPIFY['live']}")
print(f"    Shiprocket live={config.SHIPROCKET['live']}")
print(f"    DEMO_LIVE={config.DEMO_LIVE}\n")

checks = [
    ("Meta",       fetch_meta),
    ("Google",     fetch_google),
    ("Shopify",    fetch_shopify),
    ("Shiprocket", fetch_shiprocket),
]

print("  Live fetch results:")
for name, fn in checks:
    try:
        r = fn(window_days=7)
        if r.get("error"):
            print(f"    [ERROR] {name:11} -> {r['error']}")
        elif r.get("live"):
            note = r.get("note", "")
            tag = "DEMO" if note.startswith("DEMO") else "REAL API"
            print(f"    [ OK  ] {name:11} -> LIVE ({tag}) {note}")
        else:
            print(f"    [MOCK ] {name:11} -> sample data ({r.get('note','')})")
    except Exception as e:
        print(f"    [CRASH] {name:11} -> {e}")
print()
