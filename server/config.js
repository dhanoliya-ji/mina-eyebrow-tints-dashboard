// ============================================================
//  Central config. Reads .env and decides, per source, whether
//  we have REAL credentials or should fall back to mock data.
//  A value that is missing or starts with "DUMMY" => not live.
// ============================================================

import 'dotenv/config'

const real = (v) => Boolean(v) && !String(v).startsWith('DUMMY')

export const config = {
  port: Number(process.env.PORT) || 4000,
  syncCron: process.env.SYNC_CRON || '30 7 * * *',
  tz: process.env.TZ || 'Asia/Kolkata',

  // DEMO_LIVE=true routes any source that lacks real credentials through
  // the free public demo feed (real network calls, live-changing numbers)
  // instead of static mock. Set to false once real keys are in place.
  demoLive: process.env.DEMO_LIVE === 'true',

  meta: {
    accessToken: process.env.META_ACCESS_TOKEN,
    adAccountId: process.env.META_AD_ACCOUNT_ID,
    apiVersion: process.env.META_API_VERSION || 'v21.0',
    get live() {
      return real(this.accessToken) && real(this.adAccountId)
    },
  },

  google: {
    developerToken: process.env.GOOGLE_ADS_DEVELOPER_TOKEN,
    clientId: process.env.GOOGLE_ADS_CLIENT_ID,
    clientSecret: process.env.GOOGLE_ADS_CLIENT_SECRET,
    refreshToken: process.env.GOOGLE_ADS_REFRESH_TOKEN,
    customerId: process.env.GOOGLE_ADS_CUSTOMER_ID,
    loginCustomerId: process.env.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
    get live() {
      return (
        real(this.developerToken) &&
        real(this.refreshToken) &&
        real(this.customerId)
      )
    },
  },

  shopify: {
    domain: process.env.SHOPIFY_STORE_DOMAIN,
    adminToken: process.env.SHOPIFY_ADMIN_TOKEN,
    apiVersion: process.env.SHOPIFY_API_VERSION || '2025-01',
    get live() {
      return real(this.adminToken) && Boolean(this.domain)
    },
  },

  shiprocket: {
    email: process.env.SHIPROCKET_EMAIL,
    password: process.env.SHIPROCKET_PASSWORD,
    get live() {
      return real(this.email) && real(this.password)
    },
  },
}

// Rolling window the spec requires: re-pull the last 7 days each sync.
export const WINDOW_DAYS = 7
