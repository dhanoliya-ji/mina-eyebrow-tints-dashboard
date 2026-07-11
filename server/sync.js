// ============================================================
//  Ingestion orchestrator (spec §4.1). Pulls all four sources for
//  the rolling 7-day window, in parallel, with PARTIAL-FAILURE
//  handling: one source failing never blocks the others, and each
//  source records its own last-synced / ok / error in the store.
// ============================================================

import { fetchMeta } from './connectors/meta.js'
import { fetchGoogle } from './connectors/google.js'
import { fetchShopify } from './connectors/shopify.js'
import { fetchShiprocket } from './connectors/shiprocket.js'
import { saveSource } from './store.js'

const CONNECTORS = {
  meta: fetchMeta,
  google: fetchGoogle,
  shopify: fetchShopify,
  shiprocket: fetchShiprocket,
}

let syncing = false

export function isSyncing() {
  return syncing
}

export async function runSync() {
  if (syncing) return { skipped: true }
  syncing = true
  const started = Date.now()
  console.log('[sync] starting 7-day pull for all sources…')

  const results = await Promise.allSettled(
    Object.entries(CONNECTORS).map(async ([name, fn]) => {
      const result = await fn()
      saveSource(name, result)
      const tag = result.live ? 'LIVE' : result.error ? 'MOCK(err)' : 'MOCK'
      console.log(`[sync]   ${name.padEnd(11)} ${tag}${result.error ? ' — ' + result.error : ''}`)
      return name
    })
  )

  syncing = false
  const failed = results.filter((r) => r.status === 'rejected').length
  console.log(`[sync] done in ${Date.now() - started}ms (${failed} hard failures)`)
  return { ok: true, failed }
}
