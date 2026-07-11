// ============================================================
//  Storage layer (spec §4.2). A JSON file stands in for Postgres
//  for now — same read/write contract, so swapping to a real DB
//  is isolated to this file. Holds the latest synced snapshot per
//  source plus its sync status (last synced, ok, error).
// ============================================================

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const DATA_DIR = join(__dirname, 'data')
const SNAPSHOT = join(DATA_DIR, 'snapshot.json')

let snapshot = {
  meta: null,
  google: null,
  shopify: null,
  shiprocket: null,
  sources: {}, // { meta: { lastSynced, ok, live, error } , ... }
}

// Load any persisted snapshot on boot.
if (existsSync(SNAPSHOT)) {
  try {
    snapshot = JSON.parse(readFileSync(SNAPSHOT, 'utf8'))
  } catch {
    /* corrupt file — start fresh */
  }
}

export function getSnapshot() {
  return snapshot
}

export function saveSource(name, result) {
  snapshot[name] = result.data
  snapshot.sources[name] = {
    lastSynced: new Date().toISOString(),
    ok: result.live !== false ? true : !result.error, // mock is "ok", failed live is not
    live: result.live === true,
    note: result.note || null,
    error: result.error || null,
  }
  persist()
}

function persist() {
  try {
    if (!existsSync(DATA_DIR)) mkdirSync(DATA_DIR, { recursive: true })
    writeFileSync(SNAPSHOT, JSON.stringify(snapshot, null, 2))
  } catch (err) {
    console.error('[store] failed to persist snapshot:', err.message)
  }
}
