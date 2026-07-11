import React, { useState, useMemo } from 'react'
import { useDashboard } from './data/useDashboard.js'
import { topline, attribution, funnel, skuPerformance, reconcile } from './data/metrics.js'
import { briefing, campaignActions } from './data/rules.js'
import { inr, inrShort, xRoas, pctWhole, int, fmtValue, clock, ago } from './format.js'

/* ------------------------------------------------------------------ */
/*  Header                                                            */
/* ------------------------------------------------------------------ */
function Header({ theme, onToggleTheme, syncing, onRefresh, lastSync, rec, mode }) {
  const reconciled = rec.collectedFactor > 0
  return (
    <header className="header">
      <div className="header-left">
        <div className="brand-mark">m</div>
        <div>
          <div className="brand-name">Mina Eyebrow Tints · AI Automation Dashboard</div>
          <div className="brand-sub">
            minaeyebrowtints.in · {lastSync ? `data as of ${clock(lastSync)} IST` : 'loading…'}
          </div>
        </div>
      </div>
      <div className="header-right">
        <span className={`pill ${mode === 'live' ? 'pill-good' : 'pill-warn'}`}>
          <span className="dot" /> {mode === 'live' ? 'Backend live' : mode === 'offline' ? 'Offline · mock' : 'Connecting…'}
        </span>
        <span className={`pill ${reconciled ? 'pill-good' : 'pill-warn'}`}>
          <span className="dot" /> Reconciled · {pctWhole(rec.deliveredRate)} delivered
        </span>
        <button className="btn" onClick={onRefresh} disabled={syncing}>
          <span className={syncing ? 'spin' : ''}>↻</span>
          {syncing ? 'Syncing…' : 'Refresh'}
        </button>
        <button className="btn icon-btn" onClick={onToggleTheme} title="Toggle theme">
          {theme === 'dark' ? '☀' : '☾'}
        </button>
      </div>
    </header>
  )
}

/* ------------------------------------------------------------------ */
/*  Source sync strip                                                 */
/* ------------------------------------------------------------------ */
function SourceStrip({ sources }) {
  return (
    <div className="src-strip">
      {sources.map((s) => (
        <span key={s.source} className="src-chip">
          <span className="dot" style={{ color: s.ok ? 'var(--good-fg)' : 'var(--bad-fg)' }} />
          {s.source} · {s.ok ? `${s.live ? 'live' : 'mock'} · synced ${s.lastSynced ? ago(s.lastSynced) : '—'}` : 'sync failed'}
        </span>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Toolbar (date range + channel filter)                            */
/* ------------------------------------------------------------------ */
function Toolbar({ range, setRange, channel, setChannel }) {
  return (
    <div className="toolbar">
      <span className="toolbar-label">Range</span>
      <div className="seg">
        {['Today', '7 days', '30 days'].map((r) => (
          <button key={r} className={range === r ? 'active' : ''} onClick={() => setRange(r)}>{r}</button>
        ))}
      </div>
      <span className="toolbar-label" style={{ marginLeft: 8 }}>Channel</span>
      <div className="seg">
        {['All', 'Meta', 'Google'].map((c) => (
          <button key={c} className={channel === c ? 'active' : ''} onClick={() => setChannel(c)}>{c}</button>
        ))}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  KPI row                                                           */
/* ------------------------------------------------------------------ */
function Delta({ value, prev, goodUp, fmt }) {
  if (prev == null) return null
  const diff = value - prev
  const pct = prev ? diff / prev : 0
  const flat = Math.abs(pct) < 0.005
  const up = diff > 0
  let cls = 'delta-flat'
  if (!flat && goodUp !== null) cls = up === goodUp ? 'up-good' : 'up-bad'
  const arrow = flat ? '→' : up ? '▲' : '▼'
  const shown = fmt === 'x' ? xRoas(Math.abs(diff)) : fmt === 'int' ? int(Math.abs(diff)) : inrShort(Math.abs(diff))
  return (
    <span className={`kpi-delta ${cls} num`}>
      {arrow} {shown} <span style={{ color: 'var(--text-faint)', fontWeight: 400 }}>({pctWhole(Math.abs(pct))})</span>
    </span>
  )
}

function KpiRow({ bundle }) {
  const t = topline(bundle)
  const tiles = [
    { key: 'trueRevenue', label: 'Shopify revenue (true)', ...t.trueRevenue },
    { key: 'adSpend', label: 'Total ad spend', ...t.adSpend },
    { key: 'mer', label: 'MER (blended)', ...t.mer },
    { key: 'cac', label: 'Blended CAC', ...t.cac },
    { key: 'orders', label: 'Orders', ...t.orders },
    { key: 'aov', label: 'AOV', ...t.aov },
  ]
  return (
    <div className="kpi-grid">
      {tiles.map((tile) => (
        <div className="kpi" key={tile.key}>
          <div className="kpi-label">{tile.label}</div>
          <div className="kpi-value num">{fmtValue(tile.value, tile.fmt)}</div>
          <Delta value={tile.value} prev={tile.prev} goodUp={tile.goodUp} fmt={tile.fmt} />
        </div>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  AI briefing — the hero card                                       */
/* ------------------------------------------------------------------ */
function BriefRow({ kicker, cls, items }) {
  if (!items || items.length === 0) return null
  return (
    <div className={`brief-row ${cls}`}>
      <div>
        <div className="brief-kicker">{kicker}</div>
        {items.map((it, i) => (
          <div className="brief-text" key={i} dangerouslySetInnerHTML={{ __html: it.text }} style={{ marginTop: i ? 6 : 0 }} />
        ))}
      </div>
    </div>
  )
}

function Briefing({ bundle }) {
  const b = useMemo(() => briefing(bundle), [bundle])
  return (
    <div className="card" style={{ marginTop: 12 }}>
      <div className="card-head">
        <div className="card-title">Today's briefing</div>
        <span className="pill pill-neutral">AI · reconciled revenue</span>
      </div>
      <div className="brief-text" style={{ marginBottom: 14, color: 'var(--text-muted)' }}
        dangerouslySetInnerHTML={{ __html: b.changed }} />

      {b.escalate.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <BriefRow kicker="Escalate" cls="brief-escalate" items={b.escalate} />
        </div>
      )}

      <div className="briefing-grid">
        <BriefRow kicker="Improved" cls="brief-good" items={b.improved} />
        <BriefRow kicker="Got worse" cls="brief-bad" items={b.worse} />
        <BriefRow kicker="Stuck / watch" cls="brief-warn" items={b.stuck} />
        <div className="brief-row brief-do">
          <div style={{ width: '100%' }}>
            <div className="brief-kicker">Do today</div>
            <div className="todo-list">
              {b.todo.map((t, i) => (
                <div className="todo" key={i}>
                  <span className="todo-rank num">{i + 1}</span>
                  <span className="brief-text" dangerouslySetInnerHTML={{ __html: t }} />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Attribution comparison (Meta + Google)                            */
/* ------------------------------------------------------------------ */
function AttribCard({ a }) {
  return (
    <div className="card">
      <div className="card-head">
        <div className="card-title">{a.name} · attribution</div>
        <span className="card-sub">spend {inr(a.spend)}</span>
      </div>
      <div className="roas-row">
        <div className="roas-box">
          <div className="lbl">1-day click ROAS</div>
          <div className="val num">{xRoas(a.roas1d)}</div>
          <div className="card-sub">immediate intent</div>
        </div>
        <div className="roas-box">
          <div className="lbl">7-day click ROAS</div>
          <div className="val num">{xRoas(a.roas7d)}</div>
          <div className="card-sub">delayed impact</div>
        </div>
      </div>
      <div className="reconcile-line">
        <span className="rl-label">Platform-reported revenue (7d)</span>
        <span className="rl-val num">{inr(a.reportedRev7d)}</span>
      </div>
      <div className="reconcile-line">
        <span className="rl-label">Shopify actual (true, reconciled)</span>
        <span className="rl-val num">{inr(a.trueRev)}</span>
      </div>
      <div className="reconcile-line">
        <span className="rl-label">Over-report</span>
        <span className="rl-val num" style={{ color: 'var(--bad-fg)' }}>
          +{inr(a.overReportAbs)} ({pctWhole(a.overReportPct)})
        </span>
      </div>
      <div className="footnote">True ROAS on collected revenue: <strong>{xRoas(a.trueRoas)}</strong>. Judge budget on this, not the platform number.</div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Shopify funnel                                                    */
/* ------------------------------------------------------------------ */
function Funnel({ bundle }) {
  const steps = funnel(bundle)
  return (
    <div className="card">
      <div className="card-head">
        <div className="card-title">Shopify funnel</div>
        <span className="card-sub">last 7 days</span>
      </div>
      <div className="funnel">
        {steps.map((s) => (
          <div className="funnel-step" key={s.label}>
            <div className="funnel-meta">
              <span className="fs-label">{s.label}
                {s.stepRate != null && <span className="fs-rate num">{pctWhole(s.stepRate)} of prev</span>}
              </span>
              <span className="fs-count num">{int(s.count)}</span>
            </div>
            <div className="funnel-track">
              <div className="funnel-fill" style={{ width: `${Math.max(s.pct * 100, 2)}%` }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  SKU performance                                                   */
/* ------------------------------------------------------------------ */
function Skus({ bundle }) {
  const skus = skuPerformance(bundle)
  return (
    <div className="card">
      <div className="card-head">
        <div className="card-title">SKU performance</div>
        <span className="card-sub">stock-out forecast at current velocity</span>
      </div>
      <table className="tbl">
        <thead>
          <tr>
            <th>Product</th>
            <th className="r">Units</th>
            <th className="r">Revenue</th>
            <th className="r hide-sm">Stock</th>
            <th className="r">Cover</th>
          </tr>
        </thead>
        <tbody>
          {skus.map((s) => (
            <tr key={s.sku}>
              <td>
                <div className="sku-name">{s.name}</div>
                <div className="sku-sub num">{s.sku}</div>
              </td>
              <td className="r num">{int(s.units)}</td>
              <td className="r num">{inr(s.revenue)}</td>
              <td className="r num hide-sm">{int(s.inventory)}</td>
              <td className="r">
                {s.stockOut ? (
                  <span className="warn-tag">⚠ {Math.round(s.daysToStockOut)}d left</span>
                ) : (
                  <span className="num" style={{ color: 'var(--text-muted)' }}>{Math.round(s.daysToStockOut)}d</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Campaigns · AI recommended action (with drill-down)              */
/* ------------------------------------------------------------------ */
const ACTION_CLASS = { scale: 'act-scale', cut: 'act-cut', hold: 'act-hold', keep: 'act-keep' }

function Campaigns({ bundle, channel }) {
  const [open, setOpen] = useState(null)
  const rows = useMemo(() => campaignActions(bundle), [bundle])
  const filtered = channel === 'All' ? rows : rows.filter((r) => r.channel === channel)

  return (
    <div className="card">
      <div className="card-head">
        <div className="card-title">Campaigns · AI recommended action</div>
        <span className="card-sub">tap a row to drill into ad sets</span>
      </div>
      <table className="tbl">
        <thead>
          <tr>
            <th>Campaign</th>
            <th className="r hide-sm">Spend</th>
            <th className="r">1d ROAS</th>
            <th className="r">7d ROAS</th>
            <th className="r hide-sm">True ROAS</th>
            <th className="r">Action</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((c) => (
            <React.Fragment key={c.id}>
              <tr className="clickable" onClick={() => setOpen(open === c.id ? null : c.id)}>
                <td>
                  <div className="sku-name">{c.name}</div>
                  <div className="sku-sub">{c.channel} · {c.type}</div>
                </td>
                <td className="r num hide-sm">{inr(c.spend)}</td>
                <td className="r num">{xRoas(c.roas1d)}</td>
                <td className="r num">{xRoas(c.roas7d)}</td>
                <td className="r num hide-sm">{xRoas(c.trueRoas)}</td>
                <td className="r">
                  <span className={`action-pill ${ACTION_CLASS[c.action]}`}>{c.label}</span>
                </td>
              </tr>
              {open === c.id && (
                <tr className="expand-row">
                  <td colSpan={6}>
                    <div style={{ padding: '4px 10px 10px' }}>
                      <div className="footnote" style={{ marginBottom: 8 }}>{c.why}</div>
                      <table className="subtbl">
                        <thead>
                          <tr>
                            <th>Ad set</th>
                            <th className="r">Spend</th>
                            <th className="r">1d ROAS</th>
                            <th className="r">7d ROAS</th>
                          </tr>
                        </thead>
                        <tbody>
                          {c.subs.map((s, i) => (
                            <tr key={i}>
                              <td>{s.name}</td>
                              <td className="r num">{inr(s.spend)}</td>
                              <td className="r num">{xRoas(s.roas1d)}</td>
                              <td className="r num">{xRoas(s.roas7d)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  App                                                               */
/* ------------------------------------------------------------------ */
export default function App() {
  const [theme, setTheme] = useState('light')
  const [range, setRange] = useState('7 days')
  const [channel, setChannel] = useState('All')
  const { bundle, sources, mode, syncing, refresh } = useDashboard()

  React.useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const rec = useMemo(() => reconcile(bundle), [bundle])
  const attrib = useMemo(() => attribution(bundle), [bundle])
  const lastSync = sources.find((s) => s.source === 'Shopify')?.lastSynced

  return (
    <div className="app">
      <Header
        theme={theme}
        onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        syncing={syncing}
        onRefresh={refresh}
        lastSync={lastSync}
        rec={rec}
        mode={mode}
      />
      <SourceStrip sources={sources} />
      <Toolbar range={range} setRange={setRange} channel={channel} setChannel={setChannel} />

      <KpiRow bundle={bundle} />
      <Briefing bundle={bundle} />

      <div className="section-title">Attribution · 1-day vs 7-day, platform vs true</div>
      <div className="attrib-grid">
        {attrib
          .filter((a) => channel === 'All' || a.name.startsWith(channel))
          .map((a) => <AttribCard key={a.name} a={a} />)}
      </div>

      <div className="section-title">Store performance</div>
      <div className="grid-2">
        <Funnel bundle={bundle} />
        <Skus bundle={bundle} />
      </div>

      <div className="section-title">Recommendations</div>
      <Campaigns bundle={bundle} channel={channel} />

      <div className="footnote" style={{ marginTop: 24, textAlign: 'center' }}>
        Revenue everywhere is reconciled true revenue (Shopify orders − refunds − cancellations − RTO, cross-checked with Shiprocket).
        Platform revenue appears only in the attribution cards.
        {mode === 'offline' && ' Backend unreachable — showing bundled mock data.'}
      </div>
    </div>
  )
}
