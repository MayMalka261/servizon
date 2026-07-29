/**
 * Value formatting.
 *
 * All of it lives here because the same number appears on a KPI card, in a
 * chart tooltip and in a comparison table, and the three must agree. A metric
 * that reads 92% in one place and 91.6% in another destroys confidence in the
 * whole tool.
 */

import type { Direction, KpiFormat } from '@/types/api'

const HEBREW_LOCALE = 'he-IL'

const integerFormatter = new Intl.NumberFormat(HEBREW_LOCALE, { maximumFractionDigits: 0 })
const decimalFormatter = new Intl.NumberFormat(HEBREW_LOCALE, {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

/** Seconds as mm:ss, matching the deck. Values above an hour show h:mm:ss. */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(secs)}` : `${pad(minutes)}:${pad(secs)}`
}

/** Percent values arrive from the API as fractions in [0, 1]. */
export function formatPercent(fraction: number, decimals = 1): string {
  const value = fraction * 100
  // Whole numbers read better without a trailing .0 on a large KPI card.
  if (Math.abs(value - Math.round(value)) < 0.05) return `${Math.round(value)}%`
  return `${value.toFixed(decimals)}%`
}

export function formatNumber(value: number): string {
  return Math.abs(value) >= 100 || Number.isInteger(value)
    ? integerFormatter.format(Math.round(value))
    : decimalFormatter.format(value)
}

export function formatKpiValue(value: number, format: KpiFormat): string {
  switch (format) {
    case 'duration':
      return formatDuration(value)
    case 'percent':
      return formatPercent(value)
    case 'number':
      return formatNumber(value)
  }
}

/**
 * The delta beneath a KPI value.
 *
 * Percentage metrics are reported in percentage points, not as a percentage of
 * a percentage: "SLA rose 4 points" is what an operations officer means, and
 * "SLA rose 4.7%" from 85 to 89 is a different and confusing claim.
 */
export function formatDelta(difference: number, format: KpiFormat): string {
  const magnitude = Math.abs(difference)
  switch (format) {
    case 'duration':
      return formatDuration(magnitude)
    case 'percent':
      return `${(magnitude * 100).toFixed(1).replace(/\.0$/, '')} נק'`
    case 'number':
      return formatNumber(magnitude)
  }
}

export function formatSignedPercent(percentage: number): string {
  const rounded = Math.abs(percentage) < 0.05 ? 0 : percentage
  const sign = rounded > 0 ? '+' : rounded < 0 ? '−' : ''
  return `${sign}${Math.abs(rounded).toFixed(1).replace(/\.0$/, '')}%`
}

/** A lever's own value, in its display unit. */
export function formatLeverValue(value: number, unit: string): string {
  if (unit === '%') return `${formatNumber(value)}%`
  if (unit === "שנ'") return formatDuration(value)
  return `${formatNumber(value)} ${unit}`.trim()
}

export type DeltaTone = 'positive' | 'negative' | 'neutral'

/** Which colour a delta badge should take. */
export function deltaTone(
  difference: number,
  direction: Direction,
  isImprovement: boolean,
): DeltaTone {
  if (Math.abs(difference) < 1e-9) return 'neutral'
  if (direction === 'neutral') return 'neutral'
  return isImprovement ? 'positive' : 'negative'
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso)
  return new Intl.DateTimeFormat(HEBREW_LOCALE, {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function formatTime(iso: string): string {
  return new Intl.DateTimeFormat(HEBREW_LOCALE, {
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso))
}
