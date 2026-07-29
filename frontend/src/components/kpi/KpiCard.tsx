import { ArrowDown, ArrowUp, Minus } from 'lucide-react'

import { Card } from '@/components/ui'
import { AnimatedValue } from './AnimatedValue'
import { deltaTone, formatDelta, formatKpiValue, formatSignedPercent } from '@/simulation/format'
import { cn } from '@/lib/utils'
import type { SimulatedKpi } from '@/types/api'

const TONE_CLASSES = {
  positive: 'text-[var(--color-positive)] bg-[var(--color-positive-soft)]',
  negative: 'text-[var(--color-negative)] bg-[var(--color-negative-soft)]',
  neutral: 'text-[var(--color-neutral)] bg-[var(--color-neutral-soft)]',
} as const

export function KpiCard({ kpi, accent }: { kpi: SimulatedKpi; accent: string }) {
  const tone = deltaTone(kpi.difference, kpi.direction, kpi.is_improvement)
  const hasChange = kpi.trend !== 0

  const Arrow = kpi.trend === 1 ? ArrowUp : kpi.trend === -1 ? ArrowDown : Minus

  // Progress bar is only meaningful for bounded metrics.
  const fraction =
    kpi.format === 'percent' ? Math.min(Math.max(kpi.scenario, 0), 1) : undefined

  return (
    <Card accent={accent} className="flex flex-col p-4">
      <p className="text-sm text-[var(--color-ink-soft)]">{kpi.label}</p>

      <p className="mt-2 text-3xl font-bold leading-none text-[var(--color-ink)]">
        <AnimatedValue value={kpi.scenario} format={kpi.format} />
      </p>

      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
        <span
          className={cn(
            'inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-semibold',
            TONE_CLASSES[tone],
          )}
        >
          <Arrow className="h-3 w-3" />
          <span className="tnum">
            {hasChange ? formatDelta(kpi.difference, kpi.format) : '—'}
          </span>
        </span>
        {hasChange ? (
          <span className="tnum text-xs text-[var(--color-ink-muted)]">
            {formatSignedPercent(kpi.percentage)}
          </span>
        ) : null}
      </div>

      <p className="mt-1.5 text-[11px] text-[var(--color-ink-muted)]">
        מצב נוכחי:{' '}
        <span className="tnum font-medium text-[var(--color-ink-soft)]">
          {formatKpiValue(kpi.current, kpi.format)}
        </span>
      </p>

      {fraction !== undefined ? (
        <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-[var(--color-surface-sunken)]">
          <div
            className="h-full rounded-full transition-[width] duration-500 ease-out"
            style={{ width: `${fraction * 100}%`, backgroundColor: accent }}
          />
        </div>
      ) : null}
    </Card>
  )
}
