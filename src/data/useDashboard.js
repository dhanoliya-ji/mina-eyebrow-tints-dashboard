// ============================================================
// Data provider. Fetches the reconciled payload from the backend
// (/api/dashboard). If the server is unreachable, falls back to the
// bundled mock so the dashboard always renders — with a visible
// "offline / mock" status instead of silently showing stale data.
// ============================================================

import { useState, useEffect, useCallback } from 'react'
import { mockBundle, mockSources } from './mock.js'

const API = import.meta.env.VITE_API_URL || 'http://localhost:4000'

const DISPLAY = { meta: 'Meta Ads', google: 'Google Ads', shopify: 'Shopify', shiprocket: 'Shiprocket' }

// Turn the backend's sources object into the array the UI renders.
function normalizeSources(obj) {
  return ['meta', 'google', 'shopify', 'shiprocket'].map((k) => {
    const s = obj?.[k] || {}
    return { source: DISPLAY[k], lastSynced: s.lastSynced, ok: s.ok !== false, live: !!s.live, error: s.error }
  })
}

export function useDashboard() {
  const [bundle, setBundle] = useState(mockBundle)
  const [sources, setSources] = useState(mockSources)
  const [mode, setMode] = useState('loading') // loading | live | offline
  const [syncing, setSyncing] = useState(false)

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/dashboard`)
      if (!res.ok) throw new Error(res.status)
      const d = await res.json()
      // Guard: only accept a payload that actually has the sources.
      if (!d.meta || !d.shopify) throw new Error('empty payload')
      setBundle({
        meta: d.meta, google: d.google, shopify: d.shopify, shiprocket: d.shiprocket,
        thresholds: d.thresholds, platformCredibility: d.platformCredibility,
      })
      setSources(normalizeSources(d.sources))
      setMode('live')
    } catch {
      setBundle(mockBundle)
      setSources(mockSources)
      setMode('offline')
    }
  }, [])

  useEffect(() => { load() }, [load])

  const refresh = useCallback(async () => {
    setSyncing(true)
    try {
      await fetch(`${API}/api/refresh`, { method: 'POST' })
      await load()
    } catch {
      /* stay on current data */
    } finally {
      setSyncing(false)
    }
  }, [load])

  return { bundle, sources, mode, syncing, refresh }
}
