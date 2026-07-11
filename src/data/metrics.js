// ============================================================
// Metric + reconciliation compute (spec §3).
// Every function takes a `d` data bundle:
//   { meta, google, shopify, shiprocket, thresholds, platformCredibility }
// so it runs identically on backend data or the mock fallback.
// Shopify + Shiprocket is the source of truth for revenue.
// ============================================================

const div = (a, b) => (b ? a / b : 0) // divide-by-zero guard

// ---- Reconciliation: the single source of truth ----
// True revenue = Shopify order revenue − refunds − cancellations − RTO
// (COD/RTO orders that were never delivered/collected are excluded).
export function reconcile(d) {
  const { shopify, shiprocket } = d
  const gross = shopify.grossRevenue
  const excluded =
    shopify.refunds + shiprocket.cancelledRevenue + shiprocket.rtoRevenue
  const trueRevenue = gross - excluded
  const collectedFactor = div(trueRevenue, gross)
  return {
    gross,
    refunds: shopify.refunds,
    cancelled: shiprocket.cancelledRevenue,
    rto: shiprocket.rtoRevenue,
    trueRevenue,
    collectedFactor,
    deliveredRate: div(shiprocket.delivered, shiprocket.totalOrders),
  }
}

// ---- Blended top-line metrics (KPI row) ----
export function topline(d) {
  const rec = reconcile(d)
  const adSpend = sum(d.meta.campaigns, 'spend') + sum(d.google.campaigns, 'spend')
  const orders = d.shopify.orders
  const newCustomers = d.shopify.newCustomers

  const mer = div(rec.trueRevenue, adSpend)
  const cac = div(adSpend, newCustomers)
  const aov = div(rec.trueRevenue, orders)

  const p = d.shopify.prev
  return {
    trueRevenue: { value: rec.trueRevenue, prev: p.trueRevenue, goodUp: true, fmt: 'inr' },
    adSpend: { value: adSpend, prev: p.adSpend, goodUp: null, fmt: 'inr' },
    mer: { value: mer, prev: p.mer, goodUp: true, fmt: 'x' },
    cac: { value: cac, prev: p.cac, goodUp: false, fmt: 'inr' },
    orders: { value: orders, prev: p.orders, goodUp: true, fmt: 'int' },
    aov: { value: aov, prev: p.aov, goodUp: true, fmt: 'inr' },
  }
}

// ---- Attribution comparison, per platform (spec §6.4) ----
export function attribution(d) {
  const rec = reconcile(d)
  const cred = d.platformCredibility

  const metaSpend = sum(d.meta.campaigns, 'spend')
  const metaVal1d = sum(d.meta.campaigns, 'value_1d_click')
  const metaVal7d = sum(d.meta.campaigns, 'value_7d_click')

  const gSpend = sum(d.google.campaigns, 'spend')
  const gVal1d = sum(d.google.campaigns, 'conv_value_1d')
  const gVal7d = sum(d.google.campaigns, 'conv_value_7d')

  return [
    buildAttrib('Meta Ads', metaSpend, metaVal1d, metaVal7d, rec.collectedFactor * cred.meta),
    buildAttrib('Google Ads', gSpend, gVal1d, gVal7d, rec.collectedFactor * cred.google),
  ]
}

function buildAttrib(name, spend, val1d, val7d, trueFactor) {
  const trueRev = val7d * trueFactor
  const overReport = val7d - trueRev
  return {
    name, spend,
    roas1d: div(val1d, spend),
    roas7d: div(val7d, spend),
    trueRoas: div(trueRev, spend),
    reportedRev7d: val7d,
    trueRev,
    overReportAbs: overReport,
    overReportPct: div(overReport, trueRev),
  }
}

// ---- Shopify funnel (spec §6.5) ----
export function funnel(d) {
  const s = d.shopify
  const steps = [
    { label: 'Sessions', count: s.sessions },
    { label: 'Add to cart', count: s.addToCart },
    { label: 'Checkout', count: s.checkouts },
    { label: 'Orders', count: s.orders },
  ]
  const top = steps[0].count
  return steps.map((st, i) => ({
    ...st,
    pct: div(st.count, top),
    stepRate: i === 0 ? null : div(st.count, steps[i - 1].count),
  }))
}

// ---- SKU performance + stock-out forecast (spec §6.6) ----
export function skuPerformance(d) {
  return d.shopify.skus
    .map((s) => {
      const daysToStockOut = s.dailyVelocity ? s.inventory / s.dailyVelocity : Infinity
      return { ...s, daysToStockOut, stockOut: daysToStockOut <= d.thresholds.stockOutDays }
    })
    .sort((a, b) => b.revenue - a.revenue)
}

// ---- Per-campaign compute for the recommendations table (spec §6.7) ----
export function campaignRows(d) {
  const rec = reconcile(d)
  const rows = []
  const metaFactor = rec.collectedFactor * d.platformCredibility.meta
  const googleFactor = rec.collectedFactor * d.platformCredibility.google

  for (const c of d.meta.campaigns) {
    rows.push(normalizeCampaign({
      id: c.id, name: c.name, channel: 'Meta', type: c.type,
      spend: c.spend, value1d: c.value_1d_click, value7d: c.value_7d_click,
      purchases: c.purchases,
      subs: (c.adsets || []).map((a) => ({
        name: a.name, spend: a.spend,
        roas1d: div(a.value_1d_click, a.spend), roas7d: div(a.value_7d_click, a.spend),
        purchases: a.purchases,
      })),
    }, metaFactor))
  }
  for (const c of d.google.campaigns) {
    rows.push(normalizeCampaign({
      id: c.id, name: c.name, channel: 'Google', type: c.type,
      spend: c.spend, value1d: c.conv_value_1d, value7d: c.conv_value_7d,
      purchases: c.conversions,
      subs: (c.adsets || []).map((a) => ({
        name: a.name, spend: a.spend,
        roas1d: div(a.conv_value_1d, a.spend), roas7d: div(a.conv_value_7d, a.spend),
        purchases: a.conversions,
      })),
    }, googleFactor))
  }
  return rows
}

function normalizeCampaign(c, trueFactor) {
  const trueRev = c.value7d * trueFactor
  return {
    ...c,
    roas1d: div(c.value1d, c.spend),
    roas7d: div(c.value7d, c.spend),
    trueRoas: div(trueRev, c.spend),
    trueRev,
    cpa: div(c.spend, c.purchases),
  }
}

function sum(arr, key) {
  return (arr || []).reduce((t, x) => t + (x[key] || 0), 0)
}

export { div }
