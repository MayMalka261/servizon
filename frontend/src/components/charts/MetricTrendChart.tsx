import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { ChartFrame, ChartTooltipBox } from './ChartFrame'
import { EmptyChart } from './TrendChart'
import { formatKpiValue } from '@/simulation/format'
import { CHART_AXIS, CHART_GRID } from '@/simulation/theme'
import type { KpiFormat, TrendPoint } from '@/types/api'

/**
 * Observed history for a rate or a duration, with the scenario drawn across it.
 *
 * Separate from `TrendChart`, which plots contact volume: these series are
 * percentages and seconds, so they need their own axis formatting rather than
 * a thousands separator.
 *
 * The dashed line is what the scenario predicts. Reading it against four weeks
 * of the centre's own history is what separates an ambitious target from an
 * unreachable one.
 */
export function MetricTrendChart({
  title,
  description,
  points,
  scenario,
  format,
  accent,
}: {
  title: string
  description?: string
  points: TrendPoint[]
  scenario: number | undefined
  format: KpiFormat
  accent: string
}) {
  if (points.length === 0) {
    return (
      <ChartFrame title={title} height={170}>
        <EmptyChart />
      </ChartFrame>
    )
  }

  const gradientId = `metricTrend-${title.replace(/\s/g, '')}`

  return (
    <ChartFrame title={title} description={description} height={170}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={accent} stopOpacity={0.26} />
              <stop offset="100%" stopColor={accent} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={CHART_GRID} vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: CHART_AXIS }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
            minTickGap={24}
          />
          <YAxis
            tick={{ fontSize: 10, fill: CHART_AXIS }}
            tickLine={false}
            axisLine={false}
            width={46}
            tickFormatter={(value: number) => formatKpiValue(value, format)}
          />
          <Tooltip
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <ChartTooltipBox
                  label={String(label)}
                  rows={[
                    {
                      name: 'בפועל',
                      value: formatKpiValue(Number(payload[0]?.value ?? 0), format),
                      color: accent,
                    },
                  ]}
                />
              ) : null
            }
          />
          {scenario !== undefined ? (
            <ReferenceLine
              y={scenario}
              stroke="var(--color-brand)"
              strokeDasharray="5 4"
              strokeWidth={1.5}
              label={{
                value: `תרחיש: ${formatKpiValue(scenario, format)}`,
                position: 'insideTopLeft',
                fill: 'var(--color-brand)',
                fontSize: 10,
              }}
            />
          ) : null}
          <Area
            type="monotone"
            dataKey="value"
            stroke={accent}
            strokeWidth={2}
            fill={`url(#${gradientId})`}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
