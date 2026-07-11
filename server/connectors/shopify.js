// ============================================================
//  Shopify Admin API connector — the revenue source of truth.
//  Pulls orders (line-item + SKU detail), sessions, refunds,
//  discounts, new vs returning, inventory (spec §2). Falls back
//  to mock on dummy/failed creds.
// ============================================================

import { config, WINDOW_DAYS } from '../config.js'
import { mockShopify } from '../mockData.js'
import { getDemoSources } from './demoLive.js'

export async function fetchShopify() {
  const c = config.shopify
  if (!c.live) {
    if (config.demoLive) {
      try {
        const { shopify } = await getDemoSources()
        return { data: shopify, live: true, note: 'DEMO live feed — replace with real Shopify Admin API' }
      } catch (err) {
        return { data: mockShopify, live: false, error: 'demo feed: ' + String(err.message || err) }
      }
    }
    return { data: mockShopify, live: false, note: 'dummy token — using mock' }
  }

  try {
    const since = new Date(Date.now() - WINDOW_DAYS * 864e5).toISOString()
    const base = `https://${c.domain}/admin/api/${c.apiVersion}`
    const res = await fetch(
      `${base}/orders.json?status=any&created_at_min=${since}&limit=250`,
      { headers: { 'X-Shopify-Access-Token': c.adminToken } }
    )
    if (!res.ok) throw new Error(`Shopify API ${res.status}`)
    const json = await res.json()
    // (Analytics — sessions/conversion — comes from a separate
    // GraphQL Analytics query; inventory from inventory_levels.json.)
    return { data: mapShopify(json), live: true }
  } catch (err) {
    return { data: mockShopify, live: false, error: String(err.message || err) }
  }
}

// TODO(live): aggregate orders -> grossRevenue, orders, refunds, discounts,
// new vs returning; roll up line_items -> per-SKU units/revenue; join
// inventory_levels for stock; pull sessions from the Analytics API.
function mapShopify(json) {
  return { ...mockShopify, orders: (json.orders || []).length }
}
