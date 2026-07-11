// ============================================================
// Rules engine (spec §5). Deterministic rules produce SIGNALS;
// a narrative layer turns them into plain-English sentences +
// per-campaign action labels. Every recommendation ties to a
// specific campaign/SKU and cites TRUE (reconciled) numbers.
//
// Takes the `d` data bundle (thresholds come from d.thresholds,
// so they are configurable from the backend without code changes).
// This is where a real LLM call would slot in: feed it the
// structured signals, get founder-friendly prose back.
// ============================================================

import {
  reconcile, topline, attribution, skuPerformance, campaignRows, div,
} from './metrics.js'

const inr = (n) => '₹' + Math.round(n).toLocaleString('en-IN')
const pct = (n) => Math.round(n * 100) + '%'
const x = (n) => n.toFixed(1) + '×'

// ---- Per-campaign action (§5 rules -> Scale / Cut / Hold / Keep) ----
export function campaignActions(d) {
  const T = d.thresholds
  return campaignRows(d).map((c) => {
    let action = 'keep'
    let label = 'Keep · monitor'
    let why = `1-day ${x(c.roas1d)}, 7-day ${x(c.roas7d)}, true ${x(c.trueRoas)}.`

    if (c.roas1d < T.weak1dRoas && c.roas7d >= T.strong7dRoas) {
      action = 'hold'
      label = "Hold — don't pause"
      why = `Weak on day 1 (${x(c.roas1d)}) but strong over 7 days (${x(c.roas7d)}). It converts on a delay — give it time.`
    } else if (c.roas1d < T.weak1dRoas && c.roas7d < T.breakevenRoas && c.spend > 8000) {
      action = 'cut'
      label = 'Cut / pause'
      why = `Weak on both windows (1d ${x(c.roas1d)}, 7d ${x(c.roas7d)}) on ${inr(c.spend)} spend. True ROAS ${x(c.trueRoas)} is below breakeven.`
    } else if (c.roas7d >= T.strong7dRoas && c.trueRoas >= T.breakevenRoas) {
      action = 'scale'
      label = `Scale +${Math.round(T.scaleStep * 100)}%`
      why = `7-day ${x(c.roas7d)} and true ${x(c.trueRoas)} are both healthy. Room to push ${inr(c.spend)} up ~${Math.round(T.scaleStep * 100)}%.`
    }

    return { ...c, action, label, why }
  })
}

// ---- Master signal builder feeding the 6-question briefing ----
export function briefing(d) {
  const T = d.thresholds
  const rec = reconcile(d)
  const kpi = topline(d)
  const attrib = attribution(d)
  const skus = skuPerformance(d)
  const camps = campaignActions(d)

  const improved = []
  const worse = []
  const stuck = []
  const escalate = []
  const todo = []

  if (kpi.mer.value >= kpi.mer.prev) {
    improved.push({ text: `Blended MER rose to <strong>${x(kpi.mer.value)}</strong> (from ${x(kpi.mer.prev)}) — you're keeping ${inr(rec.trueRevenue)} of true revenue against ${inr(kpi.adSpend.value)} spend.` })
  } else {
    worse.push({ text: `MER slipped to <strong>${x(kpi.mer.value)}</strong> from ${x(kpi.mer.prev)}.` })
  }

  const cacDelta = div(kpi.cac.value - kpi.cac.prev, kpi.cac.prev)
  if (kpi.cac.value <= kpi.cac.prev) {
    improved.push({ text: `Blended CAC fell to <strong>${inr(kpi.cac.value)}</strong> from ${inr(kpi.cac.prev)} per new customer.` })
  } else if (cacDelta > T.cpaSpikePct) {
    worse.push({ text: `Blended CAC spiked <strong>+${pct(cacDelta)}</strong> to ${inr(kpi.cac.value)} — up sharply vs yesterday.` })
  } else {
    worse.push({ text: `Blended CAC crept up to <strong>${inr(kpi.cac.value)}</strong> from ${inr(kpi.cac.prev)}.` })
  }

  const scalers = camps.filter((c) => c.action === 'scale').sort((a, b) => b.roas7d - a.roas7d)
  if (scalers[0]) improved.push({ text: `<strong>${scalers[0].name}</strong> (${scalers[0].channel}) is your strongest — 7-day ${x(scalers[0].roas7d)}, true ${x(scalers[0].trueRoas)}.` })

  const cutters = camps.filter((c) => c.action === 'cut').sort((a, b) => a.trueRoas - b.trueRoas)
  if (cutters[0]) worse.push({ text: `<strong>${cutters[0].name}</strong> (${cutters[0].channel}) is weak on both windows — true ROAS only ${x(cutters[0].trueRoas)} on ${inr(cutters[0].spend)}.` })

  for (const s of skus) {
    if (s.stockOut) stuck.push({ text: `<strong>${s.name}</strong> (${s.sku}) runs out in ~<strong>${Math.round(s.daysToStockOut)} days</strong> at ${s.dailyVelocity}/day — restock or pause its ads before you pay for out-of-stock clicks.` })
  }
  const holds = camps.filter((c) => c.action === 'hold')
  for (const h of holds) stuck.push({ text: `<strong>${h.name}</strong> looks flat on day 1 (${x(h.roas1d)}) but is not stuck — it's converting late (7-day ${x(h.roas7d)}). Do not pause.` })

  for (const a of attrib) {
    if (a.overReportPct > T.overReportPct) escalate.push({ text: `<strong>${a.name}</strong> over-reports revenue by <strong>${inr(a.overReportAbs)} (+${pct(a.overReportPct)})</strong> vs reconciled Shopify. Its ${x(a.roas7d)} platform ROAS is misleading — true ROAS is ${x(a.trueRoas)}. Judge budget on the true number.` })
  }
  for (const c of cutters) {
    if (c.trueRoas < T.breakevenRoas && c.spend > 12000) escalate.push({ text: `Budget bleeding on <strong>${c.name}</strong>: ${inr(c.spend)} spent at true ROAS ${x(c.trueRoas)}, below breakeven ${x(T.breakevenRoas)}.` })
  }

  if (cutters[0]) todo.push(`Pause or cut <strong>${cutters[0].name}</strong> — true ROAS ${x(cutters[0].trueRoas)} on ${inr(cutters[0].spend)}.`)
  if (scalers[0]) todo.push(`Scale <strong>${scalers[0].name}</strong> +${Math.round(T.scaleStep * 100)}% — 7-day ${x(scalers[0].roas7d)} has headroom.`)
  const soonestStock = skus.filter((s) => s.stockOut).sort((a, b) => a.daysToStockOut - b.daysToStockOut)[0]
  if (soonestStock) todo.push(`Restock <strong>${soonestStock.name}</strong> — ~${Math.round(soonestStock.daysToStockOut)} days of cover left.`)
  const worstOver = [...attrib].sort((a, b) => b.overReportPct - a.overReportPct)[0]
  if (worstOver && worstOver.overReportPct > T.overReportPct) todo.push(`Re-check <strong>${worstOver.name}</strong> budgets against true ROAS ${x(worstOver.trueRoas)}, not its reported ${x(worstOver.roas7d)}.`)
  if (holds[0]) todo.push(`Leave <strong>${holds[0].name}</strong> running — it converts late; pausing now loses booked 7-day sales.`)

  const changed = `Yesterday you spent <strong>${inr(kpi.adSpend.value)}</strong> and collected <strong>${inr(rec.trueRevenue)}</strong> in true revenue across ${kpi.orders.value} orders (MER ${x(kpi.mer.value)}). ${escalate.length} item${escalate.length === 1 ? '' : 's'} need${escalate.length === 1 ? 's' : ''} your attention.`

  return { changed, improved, worse, stuck, escalate, todo }
}
