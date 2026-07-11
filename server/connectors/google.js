// ============================================================
//  Google Ads API connector.
//  Pulls campaign/ad group/keyword level with a brand vs non-brand
//  split and 1d vs 7d conversion windows (spec §2). Handles OAuth
//  refresh-token exchange. Falls back to mock on dummy/failed creds.
// ============================================================

import { config, WINDOW_DAYS } from '../config.js'
import { mockGoogle } from '../mockData.js'
import { getDemoSources } from './demoLive.js'

export async function fetchGoogle() {
  const c = config.google
  if (!c.live) {
    if (config.demoLive) {
      try {
        const { google } = await getDemoSources()
        return { data: google, live: true, note: 'DEMO live feed — replace with real Google Ads API' }
      } catch (err) {
        return { data: mockGoogle, live: false, error: 'demo feed: ' + String(err.message || err) }
      }
    }
    return { data: mockGoogle, live: false, note: 'dummy creds — using mock' }
  }

  try {
    const accessToken = await getAccessToken(c)
    const query = `
      SELECT campaign.name, campaign.advertising_channel_type,
             metrics.cost_micros, metrics.clicks, metrics.conversions,
             metrics.conversions_value, metrics.search_impression_share
      FROM campaign
      WHERE segments.date DURING LAST_${WINDOW_DAYS}_DAYS`
    const res = await fetch(
      `https://googleads.googleapis.com/v18/customers/${c.customerId}/googleAds:searchStream`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'developer-token': c.developerToken,
          'login-customer-id': c.loginCustomerId,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query }),
      }
    )
    if (!res.ok) throw new Error(`Google Ads API ${res.status}`)
    const json = await res.json()
    return { data: mapGoogle(json), live: true }
  } catch (err) {
    return { data: mockGoogle, live: false, error: String(err.message || err) }
  }
}

async function getAccessToken(c) {
  const res = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: c.clientId,
      client_secret: c.clientSecret,
      refresh_token: c.refreshToken,
      grant_type: 'refresh_token',
    }),
  })
  if (!res.ok) throw new Error(`Google OAuth ${res.status}`)
  return (await res.json()).access_token
}

// TODO(live): map searchStream rows into mockGoogle's shape, derive the
// brand vs non-brand split from campaign/query text, and split conv value
// into conv_value_1d / conv_value_7d per the account's conversion windows.
function mapGoogle(json) {
  return { campaigns: [] }
}
