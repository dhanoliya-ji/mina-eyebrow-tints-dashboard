# Mina Eyebrow Tints · AI Automation Dashboard — Documentation (Python)

A single dashboard that connects **Meta Ads, Google Ads, Shopify and Shiprocket**
for the D2C beauty brand *Mina Eyebrow Tints* and turns them into a plain-English,
actionable morning briefing.

This is the **Python version**. The backend, all four connectors, reconciliation,
metrics, the AI rules engine and the scheduler are written in Python (Flask). The
dashboard page is a single HTML file that Python serves directly — **you never need
Node.js**. Run the whole thing with one command: `python app.py`.

> A browser can only run HTML/CSS/JavaScript, so the *page* is unavoidably HTML+JS.
> But it is "thin": it only draws the numbers. Every calculation happens in Python.

Two principles are baked into every number:

1. **Shopify + Shiprocket is the source of truth for revenue.** Platform-reported
   (Meta/Google) revenue is shown for comparison only. Real revenue is reconciled
   from Shopify orders minus refunds/cancellations, cross-checked against Shiprocket
   delivery status (handling COD cancellations and RTO — return to origin).
2. **Attribution is shown two ways side by side: 1-day and 7-day click.** A campaign
   is never judged on the 1-day number alone.

Currency **₹ INR**, timezone **IST**.

---

## Table of contents

1. [Quick start](#1-quick-start)
2. [How it all fits together](#2-how-it-all-fits-together)
3. [Every file explained](#3-every-file-explained)
4. [The data flow, step by step](#4-the-data-flow-step-by-step)
5. [Metric & reconciliation definitions](#5-metric--reconciliation-definitions)
6. [The AI rules engine](#6-the-ai-rules-engine)
7. [Data modes: mock, demo-live, real](#7-data-modes-mock-demo-live-real)
8. [Going live with real API keys](#8-going-live-with-real-api-keys)
9. [API reference](#9-api-reference)
10. [Configuration reference](#10-configuration-reference)
11. [Troubleshooting](#11-troubleshooting)
12. [What's built vs. what remains](#12-whats-built-vs-what-remains)

---

## 1. Quick start

You need **Python 3.10+** (developed on 3.11). You do **not** need Node.js.

```bash
# 1. install the three Python libraries (one time)
pip install -r requirements.txt

# 2. run the whole app
python app.py
```

Then open **http://localhost:4000**.

Out of the box `DEMO_LIVE=true` in `.env`, so the dashboard runs **live** against a
free public API (no keys needed) — every source pill reads "live" and the numbers
move over time. To add real keys later, see §8.

---

## 2. How it all fits together

The product spec calls for a six-stage pipeline. Here is where each stage lives, all
in Python except the browser page:

```
   .env  ─────►  config.py          decide: real key or test data? (per source)
                    │
                    ▼
              connectors/*.py        (1) INGESTION — call each real API, OR the
                    │                    free demo feed, OR fixed sample data
                    ▼
              sync.py                orchestrates all 4; runs on startup + daily
                    │                    + on the Refresh button; failure-safe
                    ▼
              store.py               (2) STORAGE — data/snapshot.json (DB stand-in)
                    │
                    ▼
   app.py ──► build_payload()        (3) RECONCILE + (4) METRICS + (5) AI, using
                    │                    metrics.py and rules.py
                    ▼
   GET /api/dashboard  ──────────►   (6) DELIVERY — one JSON blob of finished numbers
                    │
                    ▼  (browser fetches it)
   static/index.html + style.css     draws the 7 screens (no calculations here)
```

**Key idea:** unlike a typical setup where the browser does some maths, here
**Python computes everything** — reconciliation, every metric, the AI briefing — and
sends the finished numbers. The web page is a pure renderer. That keeps all the
"business logic" in one language you're comfortable with.

---

## 3. Every file explained

| File | What it is | What it does |
|------|-----------|--------------|
| **app.py** | the program you run | Starts the web server, defines the `/api/*` routes, builds the finished payload, kicks off the first sync + the daily scheduler. **Start reading here.** |
| **config.py** | settings brain | Reads `.env`; for each source decides "real key or test data?" (a value counts as real only if present and not starting with `DUMMY`). |
| **mock_data.py** | sample data | Realistic Mina numbers in the *exact shape* the real APIs return — the fallback when there's no key. |
| **connectors/meta.py** | Meta Ads | Calls the Meta Marketing API (both 1d & 7d windows) or falls back. |
| **connectors/google.py** | Google Ads | OAuth token exchange + GAQL query, or falls back. |
| **connectors/shopify.py** | Shopify | Pulls orders for the rolling window, or falls back. |
| **connectors/shiprocket.py** | Shiprocket | Email/password login → delivery statuses, or falls back. |
| **connectors/demo_live.py** | free live feed | Real call to a free weather API; uses its live values to move the sample numbers so the dashboard runs "live" without keys. **Delete once real keys exist.** |
| **sync.py** | ingestion + scheduler | Pulls all four in turn (one failing never stops the others); schedules the daily sync on a background thread. |
| **store.py** | storage layer | Saves the latest data + per-source status to `data/snapshot.json`. Swap this one file for a real database later. |
| **settings_store.py** | thresholds | The AI thresholds + platform credibility; editable at runtime via the API, saved to `data/settings.json`. |
| **metrics.py** | the maths | Reconciliation and every metric (MER, CAC, AOV, ROAS, attribution, funnel, SKUs). Pure functions. |
| **rules.py** | the AI layer | Rules decide Scale/Cut/Hold and build the six-part morning briefing. Where a real LLM would plug in. |
| **static/index.html** | the dashboard page | Vanilla JavaScript that fetches `/api/dashboard` and draws the 7 screens. |
| **static/style.css** | the look | The calm, premium design system (light + dark). |
| **.env** | your settings | Port, schedule, `DEMO_LIVE`, and the API keys. Git-ignored. |
| **requirements.txt** | dependencies | Flask, requests, python-dotenv. |

> The `server/` and `src/` folders are the **old Node.js version**. They are not used
> by the Python app and can be deleted.

---

## 4. The data flow, step by step

1. **You run `python app.py`.** It prints which sources have real keys, then calls
   `run_sync()` once so there's data to show, then starts the daily scheduler, then
   starts the web server.
2. **`sync.py` pulls each source.** For each one it calls the connector, which returns
   `{data, live, note/error}`, and hands it to `store.py` to save with a timestamp.
3. **You open the page.** `static/index.html` calls `GET /api/dashboard`.
4. **`app.py` builds the payload.** It reads the stored data, bundles it with the
   settings, and runs it through `metrics.py` (reconciliation → KPIs → attribution →
   funnel → SKUs) and `rules.py` (campaign actions + briefing). It returns one JSON.
5. **The page draws it.** Formatting (₹, ×, %) happens in the browser; all the numbers
   were already computed by Python.
6. **Refresh / daily sync** re-runs step 2 and the page re-fetches.

---

## 5. Metric & reconciliation definitions

All in `metrics.py`. Every function takes one bundle
`d = {meta, google, shopify, shiprocket, thresholds, platformCredibility}` and every
division is divide-by-zero guarded (`_div`).

**Reconciliation — the source of truth (`reconcile`)**
```
true revenue    = Shopify gross order revenue
                  − refunds
                  − Shiprocket cancelled revenue
                  − Shiprocket RTO revenue        (returned, never collected)

collectedFactor = true revenue / gross revenue   (the share actually collected)
```
COD/RTO orders never delivered are excluded — vital for Indian D2C.

**Top-line KPIs (`topline`)**
| Metric | Formula |
|--------|---------|
| MER (Marketing Efficiency Ratio) | true revenue ÷ total ad spend |
| Blended CAC | total ad spend ÷ new customers |
| AOV | true revenue ÷ orders |
| CPC / CPM / CPA / CTR | spend÷clicks / spend÷(impr/1000) / spend÷purchases / clicks÷impr |

**Attribution & over-report (`attribution`)** — per platform:
```
trueFactor  = collectedFactor × platformCredibility[channel]
trueRevenue = reported7dValue × trueFactor
overReport  = reported7dValue − trueRevenue        (shown in ₹ and %)
```
`platformCredibility` = the share of a platform's reported sales that survives
cross-checking against real Shopify orders (ad platforms over-claim via duplicate /
view-through attribution). Meta over-claims most (0.62); Google brand search is
closest to true (0.84). It's a configurable setting, not a hard-coded constant.

---

## 6. The AI rules engine

In `rules.py`, a **hybrid**: fixed rules produce the signal; a sentence layer makes it
readable. **This is exactly where a real AI model (LLM) plugs in** — feed it the
signals and ask for the prose. Every recommendation names a campaign/SKU, quotes the
numbers, and always uses **true (reconciled)** revenue.

**Per-campaign action (`campaign_actions`)**
| Rule | Action |
|------|--------|
| 1-day ROAS `< weak1dRoas` **and** 7-day ROAS `≥ strong7dRoas` | **Hold — don't pause** (converts on a delay) |
| weak on **both** windows **and** meaningful spend | **Cut / pause** |
| 7-day ROAS `≥ strong7dRoas` **and** true ROAS `≥ breakevenRoas` | **Scale +X%** |
| otherwise | **Keep · monitor** |

The **"weak 1-day / strong 7-day → don't pause"** rule is the flagship — it stops the
founder from killing a campaign that simply converts slowly.

**The morning briefing (`briefing`)** answers the six spec questions, each tied to real
numbers: what changed, what improved, what got worse, what's stuck (near stock-outs +
"hold" campaigns), what to escalate (big over-report, budget bleeding), and a ranked
"do today" list.

---

## 7. Data modes: mock, demo-live, real

Each source picks its mode **independently**, decided top-down inside every connector:

```
IF the source has a real key in .env    → REAL API
ELSE IF DEMO_LIVE=true                   → FREE LIVE DEMO FEED (real network call)
ELSE                                     → FIXED SAMPLE (mock) DATA
```

| Mode | Network? | Numbers | Chip | When |
|------|----------|---------|------|------|
| Real | the platform API | your real account | `live` | real key present |
| Demo-live | Open-Meteo (free) | Mina names, live-moving numbers | `live` | `DEMO_LIVE=true`, no key |
| Mock | none | fixed sample | `mock` | `DEMO_LIVE=false`, no key |

You can mix modes (e.g. Shopify real, others demo) and each chip is labelled honestly.

---

## 8. Going live with real API keys

Switch sources on **one at a time** — no code change flips a source to real, only
credentials (plus the per-source mapping).

**Step 1 — get the credentials**
| Source | Needs | Where |
|--------|-------|-------|
| Meta Ads | access token, ad-account id | developers.facebook.com → Marketing API |
| Google Ads | developer token, OAuth client id/secret, refresh token, customer ids | Google Ads API Center + OAuth playground |
| Shopify | Admin API token, store domain | Shopify admin → Apps → develop apps |
| Shiprocket | account email + password | your Shiprocket account |

**Step 2 — put them in `.env`.** Replace the matching `DUMMY_*` values. As soon as a
value no longer starts with `DUMMY`, that source's `live` flag becomes true and the
connector calls the **real API** on the next sync. Restart `python app.py` (`.env` is
read at startup).

**Step 3 — fill in the mapping.** Each connector has a `_map_xxx()` function marked
`TODO`. That's the one place you translate the raw API response into our field shape
(the same shape `mock_data.py` uses). Everything downstream already works against that
shape, so this is the only code you write per platform.

**Step 4 — turn off the demo feed.** Once all four are real, set `DEMO_LIVE=false` and
delete `connectors/demo_live.py`.

**Step 5 (optional) — swap storage for a database.** Replace the JSON file in
`store.py` with PostgreSQL. Only `get_snapshot` / `save_source` change.

---

## 9. API reference

Base URL `http://localhost:4000`.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | the dashboard web page |
| `GET` | `/api/dashboard` | the finished payload: sources, reconciliation, kpis, attribution, funnel, skus, campaigns, briefing |
| `POST` | `/api/refresh` | re-sync all sources now (the Refresh button) |
| `GET` | `/api/health` | is it running + which sources have real keys |
| `GET` | `/api/settings` | current thresholds + platform credibility |
| `PUT` | `/api/settings` | update thresholds without code, e.g. `{"thresholds":{"stockOutDays":10}}` |

---

## 10. Configuration reference

### `.env`
| Key | Meaning |
|-----|---------|
| `PORT` | web server port (default 4000) |
| `SYNC_HOUR`, `SYNC_MINUTE` | when the daily auto-sync runs (default 07:30) |
| `DEMO_LIVE` | `true` = free live demo for un-keyed sources; `false` = fixed sample |
| `META_*` | Meta access token, ad-account id, API version |
| `GOOGLE_ADS_*` | developer token, OAuth details, customer ids |
| `SHOPIFY_*` | store domain, Admin token, API version |
| `SHIPROCKET_*` | account email + password |

### Thresholds (`settings_store.py`, editable via `PUT /api/settings`)
| Threshold | Default | Effect |
|-----------|---------|--------|
| `weak1dRoas` | 1.5 | below this on 1-day = weak immediate |
| `strong7dRoas` | 4.0 | at/above this on 7-day = delayed winner |
| `breakevenRoas` | 2.2 | true ROAS below this = losing money |
| `scaleStep` | 0.25 | suggested scale-up (+25%) |
| `overReportPct` | 0.60 | over-report above this = escalate |
| `stockOutDays` | 7 | flag SKUs running out within N days |
| `cpaSpikePct` | 0.30 | flag CAC/CPA up more than this vs yesterday |
| `platformCredibility.meta` | 0.62 | share of Meta's reported value that is real |
| `platformCredibility.google` | 0.84 | share of Google's reported value that is real |

---

## 11. Troubleshooting

**`OSError: [Errno 98]` / "address already in use" (port 4000)** — an old server is
running. On Windows, stop it:
```powershell
Get-NetTCPConnection -LocalPort 4000 -State Listen | %{ Stop-Process -Id $_.OwningProcess -Force }
```

**`ModuleNotFoundError: No module named 'flask'`** — run `pip install -r requirements.txt`.

**Page says "Could not reach the backend"** — `python app.py` isn't running, or it's on
a different port. Start it and refresh.

**All chips say "mock" even with `DEMO_LIVE=true`** — restart `python app.py`; `.env`
is read only at startup.

**Numbers don't change on Refresh** — the demo feed caches the live signal for 60
seconds and the weather API updates slowly, so rapid refreshes can look identical. This
is the cache, not a bug.

**A source shows "sync failed"** — the real API call errored (bad/expired key, rate
limit). The connector fell back to sample data and recorded the error; check the
terminal log for the reason.

**You see a `₹` error only in a terminal `print`** — that's the Windows console's
default encoding, not the app. The web page and the JSON API handle ₹ correctly. (To
print ₹ in your own scripts, set `PYTHONUTF8=1`.)

---

## 12. What's built vs. what remains

**Built and working now (all Python):**
- Full 7-screen dashboard, light/dark, mobile-responsive, served by Flask.
- Ingestion orchestrator, storage layer, daily scheduler, manual refresh,
  configurable thresholds, per-source status, failure-safe syncing.
- Reconciliation → true revenue → all metrics → both attribution windows →
  over-report → AI rules → morning briefing, all computed (not hard-coded).
- Genuinely **live** end-to-end via the free demo feed (no keys required).
- Real API endpoints + auth scaffolded in all four connectors.

**Remaining for full production:**
- Fill in each connector's `_map_xxx()` with real field mapping (needs real keys).
- Swap the JSON storage for a database (only `store.py` changes).
- Replace the templated briefing with a real LLM call (the signals are ready).
- Add the daily push delivery (email / WhatsApp).

---

*Mock and demo data use the exact field names of the live APIs, so switching to real
data is a drop-in change. See §8 to go live.*
