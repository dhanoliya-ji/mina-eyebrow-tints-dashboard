// ============================================================
//  DEMO LIVE FEED  — for testing the live pipeline WITHOUT real
//  platform credentials.
//
//  WHY THIS EXISTS: Meta Ads, Google Ads, Shopify Admin and
//  Shiprocket all require a real business account + OAuth — there
//  are no free public keys. So for live testing we make a REAL
//  network call to a free, no-key public API (Open-Meteo) and use
//  its live, constantly-changing values to modulate the baseline
//  Mina numbers. Every sync genuinely hits the internet, so the
//  status pills read "live" and the numbers move on each refresh.
//
//  >>> REPLACE ME: When you have real keys, set DEMO_LIVE=false in
//  .env and fill in the mapXxx() functions in each real connector
//  (meta.js / google.js / shopify.js / shiprocket.js). This whole
//  file can then be deleted. Nothing else depends on it.
// ============================================================

import { mockMeta, mockGoogle, mockShopify, mockShiprocket } from '../mockData.js'

// Free, no-key, always-on, live-changing signal: current weather in
// New Delhi. We only use it as a moving "market signal" to make the
// demo numbers live — the values themselves are not meaningful.
const SIGNAL_URL =
  'https://api.open-meteo.com/v1/forecast?latitude=28.61&longitude=77.21' +
  '&current=temperature_2m,wind_speed_10m,relative_humidity_2m'

let cache = null
let cacheTime = 0
const TTL = 60_000 // share one fetch across all four connectors per minute

async function getSignal() {
  if (cache && Date.now() - cacheTime < TTL) return cache
  const res = await fetch(SIGNAL_URL)
  if (!res.ok) throw new Error(`demo signal ${res.status}`)
  const json = await res.json()
  cache = json.current // { temperature_2m, wind_speed_10m, relative_humidity_2m, time }
  cacheTime = Date.now()
  return cache
}

// deterministic 0..1 hash of a string (FNV-1a)
function hash(str) {
  let h = 2166136261
  for (let i = 0; i < str.length; i++) h = Math.imul(h ^ str.charCodeAt(i), 16777619)
  return ((h >>> 0) % 100000) / 100000
}

// A live, seed-specific multiplier. Blends a stable per-entity hash
// with the live weather signal so each entity moves differently and
// the whole board shifts on every refresh.
function factor(seed, sig, min = 0.82, max = 1.22) {
  const s = hash(seed)
  const wobble =
    (sig.temperature_2m || 25) * 0.031 +
    (sig.wind_speed_10m || 5) * 0.017 +
    (sig.relative_humidity_2m || 50) * 0.006
  const frac = (s + wobble) % 1
  return min + frac * (max - min)
}

const r0 = (n) => Math.round(n)

// ---- Build all four live-modulated source shapes from one signal ----
export async function getDemoSources() {
  const sig = await getSignal()

  // Meta: modulate spend and value independently so ROAS actually moves.
  const meta = {
    campaigns: mockMeta.campaigns.map((c) => {
      const fs = factor(c.id + 's', sig)
      const fv = factor(c.id + 'v', sig, 0.7, 1.35)
      return {
        ...c,
        spend: r0(c.spend * fs),
        impressions: r0(c.impressions * fs),
        clicks: r0(c.clicks * fs),
        purchases: r0(c.purchases * fv),
        value_1d_click: r0(c.value_1d_click * fv),
        value_7d_click: r0(c.value_7d_click * fv),
        adsets: (c.adsets || []).map((a) => {
          const afs = factor(a.id + 's', sig)
          const afv = factor(a.id + 'v', sig, 0.7, 1.35)
          return {
            ...a,
            spend: r0(a.spend * afs),
            value_1d_click: r0(a.value_1d_click * afv),
            value_7d_click: r0(a.value_7d_click * afv),
          }
        }),
      }
    }),
  }

  const google = {
    campaigns: mockGoogle.campaigns.map((c) => {
      const fs = factor(c.id + 's', sig)
      const fv = factor(c.id + 'v', sig, 0.7, 1.35)
      return {
        ...c,
        spend: r0(c.spend * fs),
        clicks: r0(c.clicks * fs),
        conversions: r0(c.conversions * fv),
        conv_value_1d: r0(c.conv_value_1d * fv),
        conv_value_7d: r0(c.conv_value_7d * fv),
        adsets: (c.adsets || []).map((a) => {
          const afs = factor(a.id + 's', sig)
          const afv = factor(a.id + 'v', sig, 0.7, 1.35)
          return {
            ...a,
            spend: r0(a.spend * afs),
            conv_value_1d: r0(a.conv_value_1d * afv),
            conv_value_7d: r0(a.conv_value_7d * afv),
          }
        }),
      }
    }),
  }

  // Shopify: one global demand factor + live per-SKU inventory so the
  // stock-out warning can genuinely flip between refreshes.
  const demand = factor('shopify-demand', sig, 0.8, 1.25)
  const shopify = {
    ...mockShopify,
    sessions: r0(mockShopify.sessions * demand),
    addToCart: r0(mockShopify.addToCart * demand),
    checkouts: r0(mockShopify.checkouts * demand),
    orders: r0(mockShopify.orders * demand),
    grossRevenue: r0(mockShopify.grossRevenue * demand),
    refunds: r0(mockShopify.refunds * factor('refunds', sig)),
    newCustomers: r0(mockShopify.newCustomers * demand),
    skus: mockShopify.skus.map((s) => ({
      ...s,
      units: r0(s.units * factor(s.sku + 'u', sig)),
      revenue: r0(s.revenue * factor(s.sku + 'r', sig)),
      inventory: r0(s.inventory * factor(s.sku + 'inv', sig, 0.5, 1.4)),
      dailyVelocity: Math.max(1, r0(s.dailyVelocity * demand)),
    })),
  }

  // Shiprocket: modulate collected/lost revenue so reconciliation moves.
  const shiprocket = {
    ...mockShiprocket,
    totalOrders: shopify.orders,
    delivered: r0(mockShiprocket.delivered * demand),
    in_transit: r0(mockShiprocket.in_transit * demand),
    cancelled: r0(mockShiprocket.cancelled * factor('cancel', sig)),
    rto: r0(mockShiprocket.rto * factor('rto', sig)),
    cancelledRevenue: r0(mockShiprocket.cancelledRevenue * factor('cancelRev', sig, 0.6, 1.5)),
    rtoRevenue: r0(mockShiprocket.rtoRevenue * factor('rtoRev', sig, 0.6, 1.5)),
  }

  return { meta, google, shopify, shiprocket, signal: sig }
}
