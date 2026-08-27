import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { ChartFrame, ChartTooltipBox } from './ChartFrame'
import { EmptyChart } from './TrendChart'
import { formatKpiValue } from '@/simulation/format'
import { CHART_AXIS, CHART_GRID } from '@/simulation/theme'
import type { KpiId, SimulatedKpi, SimulationTab } from '@/types/api'

/** Percentage metrics only — mixing seconds and counts on one axis is noise. */
const SHOWN: Record<SimulationTab, KpiId[]> = {
  phone_center: ['sla', 'abandonment_rate', 'fcr'],
  digital_channels: ['customer_satisfaction', 'fcr'],
}

export function BarComparison({
  kpis,
  tab,
  accent,
}: {
  kpis: SimulatedKpi[]
  tab: SimulationTab
  accent: string
}) {
  const data = kpis
    .filter((kpi) => SHOWN[tab].includes(kpi.id) && kpi.format === 'percent')
    .map((kpi) => ({
      name: kpi.label,
      current: Number((kpi.current * 100).toFixed(1)),
      scenario: Number((kpi.scenario * 100).toFixed(1)),
    }))

  if (data.length === 0) {
    return (
      <ChartFrame title="מצב נוכחי מול תרחיש">
        <EmptyChart />
      </ChartFrame>
    )
  }

  return (
    <ChartFrame
      title="מצב נוכחי מול תרחיש"
      description="השוואה ישירה של מדדי האחוזים."
      height={220}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }} barGap={2}>
          <CartesianGrid stroke={CHART_GRID} vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 9, fill: CHART_AXIS }}
            tickLine={false}
            axisLine={false}
            interval={0}
          />
          <YAxis
            tick={{ fontSize: 10, fill: CHART_AXIS }}
            tickLine={false}
            axisLine={false}
            width={34}
            domain={[0, 100]}
            tickFormatter={(value: number) => `${value}%`}
          />
          <Tooltip
            cursor={{ fill: 'var(--color-surface-muted)' }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <ChartTooltipBox
                  label={String(label)}
                  rows={payload.map((entry) => ({
                    name: entry.dataKey === 'current' ? 'מצב נוכחי' : 'תרחיש',
                    value: formatKpiValue(Number(entry.value ?? 0) / 100, 'percent'),
                    color: String(entry.color),
                  }))}
                />
              ) : null
            }
          />
          <Legend
            verticalAlign="top"
            height={24}
            formatter={(value) => (
              <span className="text-[11px] text-[var(--color-ink-soft)]">
                {value === 'current' ? 'מצב נוכחי' : 'תרחיש'}
              </span>
            )}
          />
          <Bar
            dataKey="current"
            fill="var(--color-line-strong)"
            radius={[3, 3, 0, 0]}
            isAnimationActive={false}
          />
          <Bar dataKey="scenario" fill={accent} radius={[3, 3, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
