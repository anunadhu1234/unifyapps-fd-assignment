const integer = new Intl.NumberFormat('en-US')
const decimal = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

export function formatNumber(value: number): string {
  return Number.isInteger(value) ? integer.format(value) : decimal.format(value)
}

export function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') return formatNumber(value)
  return String(value)
}

export function isNumeric(value: unknown): boolean {
  return typeof value === 'number'
}

export function formatMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return ''
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
}

export function formatCost(usd: number | null | undefined): string {
  if (usd === null || usd === undefined) return 'n/a'
  if (usd === 0) return '$0.00 (free)'
  return usd < 0.01 ? `$${usd.toFixed(5)}` : `$${usd.toFixed(3)}`
}

export function relativeTime(iso: string): string {
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)}h ago`
  if (seconds < 7 * 86_400) return `${Math.floor(seconds / 86_400)}d ago`
  return new Date(iso).toLocaleDateString()
}

export function plural(n: number, word: string): string {
  return `${formatNumber(n)} ${word}${n === 1 ? '' : 's'}`
}

/** Rows as CSV text (used for "copy results"; the full download comes from the server). */
export function toCsv(columns: string[], rows: unknown[][]): string {
  const escape = (v: unknown) => {
    const s = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return [columns, ...rows].map((r) => r.map(escape).join(',')).join('\n')
}
