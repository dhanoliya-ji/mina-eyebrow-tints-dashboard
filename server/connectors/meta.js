// ============================================================
//  Meta Ads (Marketing API) connector.
//  Requests purchases + value under BOTH 1d_click and 7d_click
//  attribution windows (spec §2). Falls back to mock when the
//  access token is a dummy, or if the live call fails.
// ============================================================

import { config, WINDOW_DAYS } from '../config.js'
import { mockMeta } from '../mockData.js'
import { getDemoSources } from './demoLive.js'

export async function fetchMeta() {
  const c = config.meta
  if (!c.live) {
    // No real token yet. Use the live demo feed if enabled, else static mock.
    if (config.demoLive) {
      try {
        const { meta } = await getDemoSources()
        return { data: meta, live: true, note: 'DEMO live feed — replace with real Meta Marketing API' }
      } catch (err) {
        return { data: mockMeta, live: false, error: 'demo feed: ' + String(err.message || err) }
      }
    }
    return { data: mockMeta, live: false, note: 'dummy token — using mock' }
  }

  try {
    const base = `https://graph.facebook.com/${c.apiVersion}/${c.adAccountId}/insights`
    // Request BOTH attribution windows explicitly.
    const params = new URLSearchParams({
      level: 'campaign',
      date_preset: `last_${WINDOW_DAYS}d`,
      access_token: c.accessToken,
      action_attribution_windows: '1d_click,7d_click',
      fields: [
        'campaign_id', 'campaign_name', 'spend', 'impressions', 'clicks',
        'ctr', 'cpc', 'cpm', 'actions', 'action_values',
      ].join(','),
    })
    const res = await fetch(`${base}?${params}`)
    if (!res.ok) throw new Error(`Meta API ${res.status}`)
    const json = await res.json()
    return { data: mapMeta(json), live: true }
  } catch (err) {
    // Never silently show stale data as fresh — surface the error,
    // fall back to mock so the dashboard still renders.
    return { data: mockMeta, live: false, error: String(err.message || err) }
  }
}

// TODO(live): map Graph API `actions` / `action_values` arrays into the
// { value_1d_click, value_7d_click, purchases_1d_click, ... } shape that
// mockMeta uses. Kept isolated here so wiring real data is one function.
function mapMeta(json) {
  return { campaigns: (json.data || []).map(() => ({})) }
}
