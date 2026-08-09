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

/**
 * One service metric: where it stands, where the scenario puts it, and by how
 * much it moved.
 *
 * The value is the largest thing on the card by a wide margin. A manager scans
 * a grid of these looking for the number that moved, so the figure has to win
 * against its own label — hence the display-scale type with tight tracking,
 * against a small uppercase-ish label above it.
 */
export function KpiCard({
  kpi,
  accent,
  index = 0,
}: {
  kpi: SimulatedKpi
  accent: string
  index?: number
}) {
  const tone = deltaTone(kpi.difference, kpi.direction, kpi.is_improvement)
  const hasChange = kpi.trend !== 0

  const Arrow = kpi.trend === 1 ? ArrowUp : kpi.trend === -1 ? ArrowDown : Minus

  // Progress bar is only meaningful for bounded metrics.
  const fraction = kpi.format === 'percent' ? Math.min(Math.max(kpi.scenario, 0), 1) : undefined

  return (
    <Card
      accent={accent}
      // The index staggers entry so a grid of twelve cascades in rather than
      // arriving as one slab.
      style={{ ['--i' as string]: index }}
      className="animate-rise group relative flex flex-col p-4"
    >
      {/* Accent wash behind the value, strongest at the top edge where the
          coloured rule is. Gives the card a light source instead of a flat
          fill, and ties it to the lever family that produced the number. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.055] transition-opacity duration-[var(--duration-base)] group-hover:opacity-[0.1]"
        style={{ background: `linear-gradient(to bottom, ${accent}, transparent 62%)` }}
      />

      <div className="relative">
        <p className="text-[13px] font-medium tracking-wide text-[var(--color-ink-soft)]">
          {kpi.label}
        </p>

        <p className="mt-2 text-[2.15rem] font-bold leading-[1.05] tracking-[-0.02em] text-[var(--color-ink)]">
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
            <span className="tnum">{hasChange ? formatDelta(kpi.difference, kpi.format) : '—'}</span>
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
              className="h-full rounded-full transition-[width] duration-500 ease-[var(--ease-out-soft)]"
              style={{
                width: `${fraction * 100}%`,
                backgroundColor: accent,
                boxShadow: `0 0 calc(10px * var(--glow-strength)) ${accent}`,
              }}
            />
          </div>
        ) : null}
      </div>
    </Card>
  )
}
