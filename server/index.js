// ============================================================
//  Mina Eyebrow Tints · AI Automation Dashboard — API server (spec §4.6 delivery).
//  Serves the reconciled dashboard payload to the frontend,
//  runs the daily scheduled sync, and exposes manual refresh +
//  editable thresholds.
// ============================================================

import express from 'express'
import cors from 'cors'
import cron from 'node-cron'
import { config } from './config.js'
import { runSync, isSyncing } from './sync.js'
import { getSnapshot } from './store.js'
import { getSettings, updateSettings } from './settings.js'

const app = express()
app.use(cors())
app.use(express.json())

// ---- Health ----
app.get('/api/health', (_req, res) => {
  res.json({
    ok: true,
    syncing: isSyncing(),
    live: {
      meta: config.meta.live,
      google: config.google.live,
      shopify: config.shopify.live,
      shiprocket: config.shiprocket.live,
    },
  })
})

// ---- The single payload the dashboard renders from ----
// Same four source shapes as the frontend mock, plus per-source
// sync status and the configurable settings.
app.get('/api/dashboard', (_req, res) => {
  const snap = getSnapshot()
  const s = getSettings()
  res.json({
    meta: snap.meta,
    google: snap.google,
    shopify: snap.shopify,
    shiprocket: snap.shiprocket,
    sources: snap.sources,
    thresholds: s.thresholds,
    platformCredibility: s.platformCredibility,
  })
})

// ---- Manual refresh (the header "Refresh" button) ----
app.post('/api/refresh', async (_req, res) => {
  const result = await runSync()
  res.json(result)
})

// ---- Read / edit thresholds without code changes (spec §5) ----
app.get('/api/settings', (_req, res) => res.json(getSettings()))
app.put('/api/settings', (req, res) => res.json(updateSettings(req.body || {})))

// ---- Boot: initial sync, then schedule the daily pull ----
app.listen(config.port, async () => {
  console.log(`[server] listening on http://localhost:${config.port}`)
  console.log('[server] live sources:',
    Object.entries({
      meta: config.meta.live, google: config.google.live,
      shopify: config.shopify.live, shiprocket: config.shiprocket.live,
    }).filter(([, v]) => v).map(([k]) => k).join(', ') || 'none (all mock — using dummy keys)')

  await runSync() // pull once on startup

  cron.schedule(config.syncCron, () => {
    console.log('[cron] scheduled daily sync firing')
    runSync()
  }, { timezone: config.tz })
  console.log(`[server] daily sync scheduled: "${config.syncCron}" (${config.tz})`)
})
