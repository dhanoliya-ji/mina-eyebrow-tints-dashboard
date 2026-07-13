# Mina Eyebrow Tints · AI Automation Dashboard — Technical Documentation

A single command center that connects **Meta Ads, Google Ads, Shopify and Shiprocket**
for the D2C brand *Mina Eyebrow Tints* and turns four disconnected data sources into
one reconciled, plain-English, actionable daily briefing.

The entire backend — all four connectors, reconciliation, metrics, the AI rules
engine, the scheduler and the storage layer — is written in **Python (Flask)**. The
dashboard page is a single HTML file the backend serves directly. **No Node.js.** Run
everything with one command: `python app.py`.

> A browser can only run HTML/CSS/JavaScript, so the *page* is HTML+JS. But it is
> "thin": it only draws the numbers. Every calculation happens in Python and is shipped
> to the browser as finished JSON.

Two principles are baked into every number:

1. **Shopify + Shiprocket is the source of truth for revenue.** Platform-reported
   (Meta/Google) revenue is shown only for comparison. Real revenue is reconciled from
   Shopify orders minus refunds, cross-checked against Shiprocket delivery status to
   remove COD cancellations and RTO (return-to-origin) parcels.
2. **Attribution is always shown two ways side by side: 1-day and 7-day click.** A
   campaign is never judged on the 1-day number alone.

Currency **₹ INR**, timezone **IST**.

---

## Table of contents

1. [Quick start](#1-quick-start)
2. [Architecture overview](#2-architecture-overview)
3. [Every file explained](#3-every-file-explained)
4. [The data flow, step by step](#4-the-data-flow-step-by-step)
5. [Storage layer & database schema](#5-storage-layer--database-schema)
6. [Metric & reconciliation definitions](#6-metric--reconciliation-definitions)
7. [The AI rules engine](#7-the-ai-rules-engine)
8. [Data modes: mock, demo-live, real](#8-data-modes-mock-demo-live-real)
9. [Going live with real API keys](#9-going-live-with-real-api-keys)
10. [API reference](#10-api-reference)
11. [Configuration reference](#11-configuration-reference)
12. [Troubleshooting](#12-troubleshooting)
13. [What's built vs. what remains](#13-whats-built-vs-what-remains)

---

## 1. Quick start

You need **Python 3.10+** (developed on 3.11). You do **not** need Node.js.

```bash
# 1. install the Python libraries (one time)
pip install -r requirements.txt

# 2. run the whole app
python app.py
```

Then open **http://localhost:4000**.

Out of the box the app runs with `DEMO_LIVE=true` and no real API keys, so it starts in
**demo-live mode** — every source pulls from a free public API (no keys needed) and the
numbers move over time. Storage defaults to a local **SQLite** file until you point
`DATABASE_URL` at a real PostgreSQL server. To go fully live, see §9.

---

## 2. Architecture overview

The pipeline is a six-stage flow. Every stage is Python except the browser page:

```
   .env  ─────►  config.py          decide per source: real key or test data?
                    │
                    ▼
              connectors/*.py        (1) INGESTION — call each real API, OR the
                    │                    free demo feed, OR fixed sample data
                    ▼
              sync.py                orchestrates all 4; runs on startup + daily
                    │                    + on the Refresh button; failure-safe
                    ▼
              store.py               (2) STORAGE — PostgreSQL (time-series),
                    │                    automatic SQLite fallback
                    ▼
   app.py ──► build_payload()        (3) RECONCILE + (4) METRICS + (5) AI, using
                    │                    metrics.py and rules.py
                    ▼
   GET /api/dashboard  ──────────►   (6) DELIVERY — one JSON blob of finished numbers
                    │
                    ▼  (browser fetches it)
   static/index.html + style.css     renders the dashboard (no calculations here)
```

**Key idea:** all business logic lives in Python. Reconciliation, every metric and the
AI briefing are computed server-side; the web page is a pure renderer that only formats
values (₹, ×, %).

---

## 3. Every file explained

| File | What it is | What it does |
|------|-----------|--------------|
| **app.py** | the program you run | Starts the web server, defines the `/api/*` routes, builds the finished payload, initializes the database, runs the first sync + the daily scheduler. **Start reading here.** |
| **config.py** | credential brain | Reads `.env`; for each source decides "real key or test data?" (a value counts as real only if present and not starting with `DUMMY`). |
| **mock_data.py** | sample data | Realistic Mina numbers in the *exact shape* the real APIs return — the fallback when there is no key. |
| **connectors/meta.py** | Meta Ads | Calls the Meta Marketing API requesting **both** 1d and 7d click attribution, maps the response, or falls back. |
| **connectors/google.py** | Google Ads | OAuth refresh-token → access-token exchange, GAQL query, maps the response, or falls back. |
| **connectors/shopify.py** | Shopify | Pulls orders for the rolling window, aggregates revenue/refunds/SKUs, or falls back. |
| **connectors/shiprocket.py** | Shiprocket | Email/password login → order delivery statuses (cancelled/RTO), or falls back. |
| **connectors/demo_live.py** | free live feed | Real call to a free public API (Open-Meteo); uses live values to move the sample numbers so the dashboard runs "live" without real keys. **Delete once all real keys exist.** |
| **sync.py** | ingestion + scheduler | Pulls all four sources in turn (one failing never stops the others), pre-warms the 1d/7d/30d windows, and schedules the daily sync on a background thread. |
| **store.py** | storage layer | Hybrid database engine: connects to PostgreSQL if `DATABASE_URL` is set, otherwise falls back to SQLite. Time-series: each sync **appends** a new row. |
| **settings_store.py** | thresholds | The AI thresholds + platform-credibility numbers, stored in the database `settings` table, editable at runtime via the API. |
| **metrics.py** | the maths | Reconciliation and every metric (MER, CAC, AOV, ROAS, attribution, funnel, SKUs). Pure functions, divide-by-zero guarded. |
| **rules.py** | the AI layer | Rules decide Scale/Cut/Hold/Keep per campaign and build the six-part daily briefing. Where a real LLM would plug in. |
| **static/index.html** | the dashboard page | Vanilla JavaScript that fetches `/api/dashboard` and renders every section. |
| **static/style.css** | the look | The design system (light + dark, responsive). |
| **.env** | your settings | Port, schedule, `DEMO_LIVE`, `DATABASE_URL`, and the API keys. Git-ignored. |
| **.env.example** | template | Copy to `.env` and fill in. |
| **requirements.txt** | dependencies | Flask, requests, python-dotenv, psycopg2. |

---

## 4. The data flow, step by step

1. **You run `python app.py`.** It initializes the database tables, prints which
   sources have real keys, pre-warms the 1d/7d/30d windows via `run_all_windows()`,
   starts the daily scheduler, then starts the web server.
2. **`sync.py` pulls each source.** For each one it calls the connector, which returns
   `{data, live, note/error}`, and hands it to `store.save_source()`, which **appends**
   a timestamped row to the database.
3. **You open the page.** `static/index.html` calls `GET /api/dashboard?window_days=7`.
4. **`app.py` builds the payload.** `store.get_snapshot()` reads the newest row per
   source for that window, bundles it with the settings, and runs it through
   `metrics.py` (reconciliation → KPIs → attribution → funnel → SKUs) and `rules.py`
   (campaign actions + briefing). It returns one JSON object.
5. **The page renders it.** Formatting happens in the browser; every number was already
   computed by Python.
6. **Refresh / daily sync** re-runs step 2 (appending new rows) and the page re-fetches.

---

## 5. Storage layer & database schema

`store.py` implements a **hybrid database engine** with automatic fallback:

- If `DATABASE_URL` is set in `.env` and does **not** start with `DUMMY`, it connects to
  **PostgreSQL** (via `psycopg2`).
- Otherwise, or if the Postgres connection fails, it falls back to a local **SQLite**
  file at `data/dashboard.db`. This means the app runs with zero database setup in
  development and uses Postgres in production — no code change, only `.env`.

### Time-series (append-only) design

Storage is **append-only**, not upsert. Every sync inserts a new row, giving a full
historical audit log of how each source's numbers were reported over time — which is
exactly the over-reporting problem the product exists to surface.

`source_snapshots` table:

| Column | Type | Notes |
|--------|------|-------|
| `source_name` | text | `meta` / `google` / `shopify` / `shiprocket` |
| `window_days` | int | 1, 7 or 30 |
| `data` | text | the source payload as JSON |
| `last_synced` | text | ISO-8601 UTC timestamp |
| `ok`, `live` | int | status flags (0/1) |
| `note`, `error` | text | human-readable status / error message |
| **Primary key** | | `(source_name, window_days, last_synced)` |

`get_snapshot(window_days)` reads back only the **latest** row per source using an inner
join on `MAX(last_synced)` grouped by `source_name`.

`settings` table: a single row `key='config'` holding the thresholds + platform
credibility as JSON, upserted on `PUT /api/settings`.

Both tables are created (and migrated to the time-series schema if an older layout is
detected) automatically on startup by `store.init_db()`.

---

## 6. Metric & reconciliation definitions

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
COD/RTO orders that never delivered are excluded — vital for Indian D2C.

**Top-line KPIs (`topline`)**
| Metric | Formula |
|--------|---------|
| MER (Marketing Efficiency Ratio) | true revenue ÷ total ad spend |
| Blended CAC | total ad spend ÷ new customers |
| AOV | true revenue ÷ orders |

Each KPI ships with a `prev` (yesterday's value) so the UI can render up/down deltas.
When a live source does not supply yesterday's figures, `prev` falls back to the current
value so deltas render flat instead of erroring.

**Attribution & over-report (`attribution`)** — per platform:
```
trueFactor  = collectedFactor × platformCredibility[channel]
trueRevenue = reported 7d value × trueFactor
overReport  = reported 7d value − trueRevenue        (shown in ₹ and %)
```
`platformCredibility` is the share of a platform's reported sales that survives
cross-checking against real Shopify orders (ad platforms over-claim via duplicate and
view-through attribution). It is a **configurable, tunable assumption** — not a learned
value — with sensible defaults (Meta 0.62, Google 0.84). A production roadmap item is to
derive it automatically from the historical platform-vs-actual gap now that every sync
is stored.

**True ROAS** (revenue-on-reconciled-revenue) is computed per campaign and shown in the
campaign table, where the AI actions are judged on it rather than on platform ROAS.

---

## 7. The AI rules engine

In `rules.py`, a **transparent, deterministic rules engine**: fixed thresholds produce
the signal; a sentence layer makes it readable. This is *AI-assisted* decision-making —
explainable and auditable, with no hallucination — and it is exactly where a real LLM
would plug in to generate the natural-language prose from the same signals. Every
recommendation names a campaign/SKU, quotes the numbers, and always uses **true
(reconciled)** revenue.

**Per-campaign action (`campaign_actions`)**
| Rule | Action |
|------|--------|
| 1-day ROAS `< weak1dRoas` **and** 7-day ROAS `≥ strong7dRoas` | **Hold — don't pause** (converts on a delay) |
| weak on **both** windows **and** meaningful spend | **Cut / pause** |
| 7-day ROAS `≥ strong7dRoas` **and** true ROAS `≥ breakevenRoas` | **Scale +X%** |
| otherwise | **Keep · monitor** |

The **"weak 1-day / strong 7-day → don't pause"** rule is the flagship — it stops a slow-
converting campaign from being killed prematurely.

**The daily briefing (`briefing`)** answers the six questions, each tied to real
numbers: what changed, what improved, what got worse, what is stuck (near stock-outs +
"hold" campaigns), what to escalate (large over-report, budget bleeding), and a ranked
"do today" list.

---

## 8. Data modes: mock, demo-live, real

Each source picks its mode **independently**, decided top-down inside every connector:

```
IF the source has a real key in .env    → REAL API
ELSE IF DEMO_LIVE=true                   → FREE LIVE DEMO FEED (real network call)
ELSE                                     → FIXED SAMPLE (mock) DATA
```

| Mode | Network? | Numbers | Flag | When |
|------|----------|---------|------|------|
| Real | the platform API | your real account | `live` | real key present |
| Demo-live | Open-Meteo (free) | Mina names, live-moving numbers | `live` | `DEMO_LIVE=true`, no key |
| Mock | none | fixed sample | `mock` | `DEMO_LIVE=false`, no key |

You can mix modes (e.g. Shopify real, others demo) and each source is flagged honestly
in the payload's `sources` array.

**Every connector fails safe.** If a real API call errors (bad key, rate limit,
unexpected schema), the connector returns sample data with an `error` note instead of
crashing — the dashboard stays up and the error is visible per source.

---

## 9. Going live with real API keys

Switch sources on **one at a time**. **No Python code change is needed to go live** —
only `.env`. Each connector already contains the real API integration and auto-switches
the moment its credential no longer starts with `DUMMY`.

**Step 1 — get the credentials**
| Source | Needs | Where |
|--------|-------|-------|
| Meta Ads | access token, ad-account id (`act_…`) | developers.facebook.com → Marketing API |
| Google Ads | developer token, OAuth client id/secret, refresh token, customer ids | Google Ads API Center + OAuth playground |
| Shopify | Admin API token (`read_orders`), store domain | Shopify admin → Apps → develop apps |
| Shiprocket | account email + password | your Shiprocket account |

**Step 2 — put them in `.env`.** Replace the matching `DUMMY_*` values. No quotes, no
spaces around `=`, and don't leave the word `DUMMY` in a real value. As soon as a value
is real, that source's `live` flag becomes true.

**Step 3 — turn off the demo feed.** Set `DEMO_LIVE=false` so any source *without* a real
key cleanly uses sample data instead of the demo feed.

**Step 4 — point at PostgreSQL** (optional but recommended for production). Set
`DATABASE_URL=postgresql://user:pass@host:5432/dbname`. Without it the app uses SQLite.

**Step 5 — restart** `python app.py` (`.env` is read only at startup).

**Verify the field mapping.** The connectors' real-API code is written but each real
account can name fields slightly differently. If a live source comes back empty or with
an `error` note, adjust that connector's `_map_*()` function to match the actual
response. This is the only code you may need to touch, and the fail-safe design means a
mismatch degrades to sample data rather than breaking the dashboard.

---

## 10. API reference

Base URL `http://localhost:4000`.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | the dashboard web page |
| `GET` | `/api/dashboard?window_days=N` | the finished payload: sources, reconciliation, kpis, attribution, funnel, skus, campaigns, briefing (`N` = 1/7/30) |
| `POST` | `/api/refresh` | re-sync all sources now for a window (the Refresh button); body `{"window_days": N}` |
| `GET` | `/api/health` | is it running + which sources have real keys |
| `GET` | `/api/settings` | current thresholds + platform credibility |
| `PUT` | `/api/settings` | update thresholds without code, e.g. `{"thresholds":{"stockOutDays":10}}` |

---

## 11. Configuration reference

### `.env`
| Key | Meaning |
|-----|---------|
| `PORT` | web server port (default 4000) |
| `SYNC_HOUR`, `SYNC_MINUTE` | when the daily auto-sync runs (config default 07:30; `.env.example` ships 01:01) |
| `DEMO_LIVE` | `true` = free live demo for un-keyed sources; `false` = fixed sample |
| `DATABASE_URL` | PostgreSQL connection string; if unset or `DUMMY_…`, the app uses SQLite |
| `META_*` | Meta access token, ad-account id, API version |
| `GOOGLE_ADS_*` | developer token, OAuth details, customer ids |
| `SHOPIFY_*` | store domain, Admin token, API version |
| `SHIPROCKET_*` | account email + password |

### Thresholds (`settings_store.py`, editable via `PUT /api/settings`, stored in DB)
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

## 12. Troubleshooting

**Rows appear in SQLite but not PostgreSQL** — your `DATABASE_URL` is missing or still
starts with `DUMMY`, so `store.py` fell back to SQLite (`data/dashboard.db`). Set a real
`DATABASE_URL` and restart.

**`[db] PostgreSQL connection failed … Falling back to SQLite`** — Postgres isn't
reachable at the URL. Check the server is running and the host/port/credentials are
correct; try `127.0.0.1` instead of `localhost`.

**Port 4000 already in use** — an old server is running. On Windows:
```powershell
Get-NetTCPConnection -LocalPort 4000 -State Listen | %{ Stop-Process -Id $_.OwningProcess -Force }
```

**`ModuleNotFoundError`** — run `pip install -r requirements.txt`.

**Page says "Could not reach the backend"** — `python app.py` isn't running, or it's on
a different port. Start it and refresh.

**All sources say "mock" even with `DEMO_LIVE=true`** — restart `python app.py`; `.env`
is read only at startup.

**A source shows an error note** — the real API call errored (bad/expired key, rate
limit, or a field-mapping mismatch). The connector fell back to sample data and recorded
the reason; check the terminal log and that connector's `_map_*()`.

**A `₹` error appears only in a terminal `print`** — that's the Windows console's default
encoding, not the app. The web page and JSON API handle ₹ correctly. Set `PYTHONUTF8=1`
to print ₹ in your own scripts.

---

## 13. What's built vs. what remains

**Built and working now (all Python):**
- Full dashboard, light/dark, responsive, served by Flask.
- Ingestion orchestrator, hybrid PostgreSQL/SQLite storage with time-series audit
  history, daily scheduler, manual refresh, per-source status, failure-safe syncing.
- Reconciliation → true revenue → all metrics → both attribution windows →
  over-report → AI rules → daily briefing, all computed (not hard-coded).
- Genuinely **live** end-to-end via the free demo feed (no keys required).
- Real API calls + auth implemented in all four connectors, with fail-safe fallback.

**Remaining for full production:**
- Verify each connector's `_map_*()` against real live account responses (needs keys).
- Expand Meta ad-set/ad/creative and Google search-term/brand-split breakdowns.
- Replace the Shopify session/funnel estimate with the Analytics API / GA data.
- Replace the templated briefing with a real LLM call (the signals are ready).
- Add daily push delivery (email / WhatsApp).

---

*Mock and demo data use the exact field names of the live APIs, so switching to real
data is a drop-in change. See §9 to go live.*
