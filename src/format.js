// Display formatters (spec §3 rounding rules).
export const inr = (n) =>
  '₹' + Math.round(n).toLocaleString('en-IN')

export const inrShort = (n) => {
  const a = Math.abs(n)
  if (a >= 1e7) return '₹' + (n / 1e7).toFixed(1) + 'Cr'
  if (a >= 1e5) return '₹' + (n / 1e5).toFixed(1) + 'L'
  if (a >= 1e3) return '₹' + (n / 1e3).toFixed(1) + 'K'
  return '₹' + Math.round(n)
}

export const xRoas = (n) => n.toFixed(1) + '×'
export const pctWhole = (n) => Math.round(n * 100) + '%'
export const int = (n) => Math.round(n).toLocaleString('en-IN')

export function fmtValue(v, fmt) {
  if (fmt === 'inr') return inr(v)
  if (fmt === 'x') return xRoas(v)
  if (fmt === 'int') return int(v)
  return v
}

// "6:12 PM" style clock from ISO
export function clock(iso) {
  const d = new Date(iso)
  return d.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true })
}

// "how long ago"
export function ago(iso, now = new Date('2026-07-11T08:05:00+05:30')) {
  const mins = Math.round((now - new Date(iso)) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const h = Math.floor(mins / 60)
  return `${h}h ago`
}
