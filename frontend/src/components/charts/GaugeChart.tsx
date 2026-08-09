import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts'

import { ChartFrame } from './ChartFrame'
import { formatPercent } from '@/simulation/format'
import type { SimulatedKpi } from '@/types/api'

/**
 * SLA attainment as a half gauge, with the current state marked on the arc.
 *
 * A single number cannot show distance-to-target; an arc can, and the tick
 * showing where the center is today makes the gap the subject of the chart.
 */
export function GaugeChart({
  kpi,
  title,
  target = 0.9,
}: {
  kpi: SimulatedKpi | undefined
  title: string
  target?: number
}) {
  if (!kpi) {
    return (
      <ChartFrame title={title} height={170}>
        <div className="flex h-full items-center justify-center text-xs text-[var(--color-ink-muted)]">
          אין נתונים להצגה
        </div>
      </ChartFrame>
    )
  }

  const value = Math.min(Math.max(kpi.scenario, 0), 1)
  const colour =
    value >= target
      ? 'var(--color-positive)'
      : value >= target - 0.1
        ? 'var(--color-warning)'
        : 'var(--color-critical)'

  const data = [
    { name: 'attained', value },
    { name: 'gap', value: Math.max(1 - value, 0) },
  ]

  return (
    <ChartFrame
      title={title}
      description={`יעד ${formatPercent(target, 0)} · מצב נוכחי ${formatPercent(kpi.current)}`}
      height={170}
    >
      <div className="relative h-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              // Half gauge, opening upward.
              startAngle={180}
              endAngle={0}
              cx="50%"
              cy="85%"
              innerRadius="72%"
              outerRadius="100%"
              stroke="none"
              isAnimationActive={false}
            >
              <Cell fill={colour} />
              <Cell fill="var(--color-surface-sunken)" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>

        <div
          dir="rtl"
          className="pointer-events-none absolute inset-x-0 bottom-1 flex flex-col items-center"
        >
          <span className="tnum text-2xl font-bold" style={{ color: colour }}>
            {formatPercent(value)}
          </span>
          <span className="text-[11px] text-[var(--color-ink-muted)]">
            {value >= target ? 'עומד ביעד' : `חסר ${formatPercent(target - value)} ליעד`}
          </span>
        </div>
      </div>
    </ChartFrame>
  )
}
