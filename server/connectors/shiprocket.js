// ============================================================
//  Shiprocket connector — per-order delivery status used ONLY to
//  reconcile which Shopify orders became real, collected revenue
//  (handles COD cancellations and RTO). Falls back to mock on
//  dummy/failed creds. Auth is an email/password -> token exchange.
// ============================================================

import { config } from '../config.js'
import { mockShiprocket } from '../mockData.js'
import { getDemoSources } from './demoLive.js'

let cachedToken = null
let tokenExpiry = 0

export async function fetchShiprocket() {
  const c = config.shiprocket
  if (!c.live) {
    if (config.demoLive) {
      try {
        const { shiprocket } = await getDemoSources()
        return { data: shiprocket, live: true, note: 'DEMO live feed — replace with real Shiprocket API' }
      } catch (err) {
        return { data: mockShiprocket, live: false, error: 'demo feed: ' + String(err.message || err) }
      }
    }
    return { data: mockShiprocket, live: false, note: 'dummy creds — using mock' }
  }

  try {
    const token = await getToken(c)
    const res = await fetch(
      'https://apiv2.shiprocket.in/v1/external/orders?per_page=250',
      { headers: { Authorization: `Bearer ${token}` } }
    )
    if (!res.ok) throw new Error(`Shiprocket API ${res.status}`)
    const json = await res.json()
    return { data: mapShiprocket(json), live: true }
  } catch (err) {
    return { data: mockShiprocket, live: false, error: String(err.message || err) }
  }
}

async function getToken(c) {
  if (cachedToken && Date.now() < tokenExpiry) return cachedToken
  const res = await fetch('https://apiv2.shiprocket.in/v1/external/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: c.email, password: c.password }),
  })
  if (!res.ok) throw new Error(`Shiprocket auth ${res.status}`)
  cachedToken = (await res.json()).token
  tokenExpiry = Date.now() + 9 * 864e5 // token valid ~10 days
  return cachedToken
}

// TODO(live): tally delivery statuses -> delivered/in_transit/cancelled/rto,
// and sum cancelledRevenue + rtoRevenue so reconciliation can exclude the
// revenue that was never collected.
function mapShiprocket(json) {
  return { ...mockShiprocket }
}
