// ============================================================
//  Rule thresholds + attribution credibility (spec §5 — must be
//  configurable without code changes). Served to the frontend and
//  editable via PUT /api/settings. Persisted alongside the snapshot.
// ============================================================

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const DATA_DIR = join(__dirname, 'data')
const FILE = join(DATA_DIR, 'settings.json')

const DEFAULTS = {
  thresholds: {
    weak1dRoas: 1.5,
    strong7dRoas: 4.0,
    breakevenRoas: 2.2,
    scaleStep: 0.25,
    overReportPct: 0.6,
    stockOutDays: 7,
    cpaSpikePct: 0.3,
  },
  // Share of platform-reported 7-day value that survives cross-checking
  // against reconciled Shopify orders (duplicate / view-through inflation).
  platformCredibility: { meta: 0.62, google: 0.84 },
}

let settings = structuredClone(DEFAULTS)
if (existsSync(FILE)) {
  try {
    settings = { ...settings, ...JSON.parse(readFileSync(FILE, 'utf8')) }
  } catch {
    /* ignore corrupt file */
  }
}

export function getSettings() {
  return settings
}

export function updateSettings(patch) {
  settings = {
    thresholds: { ...settings.thresholds, ...(patch.thresholds || {}) },
    platformCredibility: { ...settings.platformCredibility, ...(patch.platformCredibility || {}) },
  }
  try {
    if (!existsSync(DATA_DIR)) mkdirSync(DATA_DIR, { recursive: true })
    writeFileSync(FILE, JSON.stringify(settings, null, 2))
  } catch (err) {
    console.error('[settings] persist failed:', err.message)
  }
  return settings
}
