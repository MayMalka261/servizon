import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart as RechartsRadar,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'

import { ChartFrame, ChartTooltipBox } from './ChartFrame'
import { EmptyChart } from './TrendChart'
import { formatPercent } from '@/simulation/format'
import { CHART_AXIS, CHART_GRID } from '@/simulation/theme'
import type { KpiId, SimulatedKpi } from '@/types/api'

/** Metrics shown on the radar, all normalised to "higher is better". */
const AXES: Array<{ id: KpiId; label: string; invert?: boolean }> = [
  { id: 'sla', label: 'SLA' },
  { id: 'customer_satisfaction', label: 'שביעות רצון' },
  { id: 'fcr', label: 'פתרון ראשון' },
  { id: 'abandonment_rate', label: 'שימור פונים', invert: true },
  { id: 'occupancy', label: 'תפוסה' },
]

/**
 * Overall service profile, current against scenario.
 *
 * Abandonment is inverted so every axis points the same way — a shape that
 * grows outward is unambiguously better. Mixing directions on a radar makes
 * it unreadable.
 */
export function ServiceRadarChart({ kpis }: { kpis: SimulatedKpi[] }) {
  const byId = new Map(kpis.map((kpi) => [kpi.id, kpi]))

  const data = AXES.flatMap((axis) => {
    const kpi = byId.get(axis.id)
    if (!kpi || kpi.format !== 'percent') return []
    return [
      {
        axis: axis.label,
        current: (axis.invert ? 1 - kpi.current : kpi.current) * 100,
        scenario: (axis.invert ? 1 - kpi.scenario : kpi.scenario) * 100,
      },
    ]
  })

  if (data.length < 3) {
    return (
      <ChartFrame title="פרופיל שירות">
        <EmptyChart />
      </ChartFrame>
    )
  }

  return (
    <ChartFrame
      title="פרופיל שירות"
      description="כל הצירים מנורמלים כך שערך גבוה הוא טוב. שטח גדול יותר = שירות טוב יותר."
      height={230}
    >
      <ResponsiveContainer width="100%" height="100%">
        <RechartsRadar data={data} outerRadius="72%">
          <PolarGrid stroke={CHART_GRID} />
          <PolarAngleAxis dataKey="axis" tick={{ fontSize: 10, fill: CHART_AXIS }} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Tooltip
            content={({ active, payload }) =>
              active && payload?.length ? (
                <ChartTooltipBox
                  label={String(payload[0]?.payload?.axis ?? '')}
                  rows={payload.map((entry) => ({
                    name: entry.name === 'current' ? 'מצב נוכחי' : 'תרחיש',
                    value: formatPercent(Number(entry.value ?? 0) / 100),
                    color: String(entry.color),
                  }))}
                />
              ) : null
            }
          />
          <Radar
            name="current"
            dataKey="current"
            stroke="var(--color-ink-muted)"
            fill="var(--color-ink-muted)"
            fillOpacity={0.12}
            strokeWidth={1.5}
            isAnimationActive={false}
          />
          <Radar
            name="scenario"
            dataKey="scenario"
            stroke="var(--color-brand)"
            fill="var(--color-brand)"
            fillOpacity={0.22}
            strokeWidth={2}
            isAnimationActive={false}
          />
        </RechartsRadar>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
