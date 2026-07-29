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
import { formatNumber } from '@/simulation/format'
import { CHART_AXIS, CHART_GRID } from '@/simulation/theme'
import type { TrendPoint } from '@/types/api'

/**
 * Observed contact volume over the last four weeks, with the scenario's
 * projected daily volume drawn across it.
 *
 * The reference line is the point of the chart: it puts the simulated number
 * in the context of what the center has actually been handling, which is how
 * you tell an ambitious target from an unreachable one.
 */
export function TrendChart({
  trend,
  scenarioDaily,
  accent,
}: {
  trend: TrendPoint[]
  scenarioDaily: number | undefined
  accent: string
}) {
  if (trend.length === 0) {
    return (
      <ChartFrame title="מגמת נפח פניות">
        <EmptyChart />
      </ChartFrame>
    )
  }

  return (
    <ChartFrame
      title="מגמת נפח פניות"
      description="נפח יומי בפועל ב-28 הימים האחרונים, מול הנפח הצפוי בתרחיש."
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={trend} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={accent} stopOpacity={0.28} />
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
            width={44}
            tickFormatter={(value: number) => formatNumber(value)}
          />
          <Tooltip
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <ChartTooltipBox
                  label={String(label)}
                  rows={[
                    {
                      name: 'פניות בפועל',
                      value: formatNumber(Number(payload[0]?.value ?? 0)),
                      color: accent,
                    },
                  ]}
                />
              ) : null
            }
          />
          {scenarioDaily !== undefined ? (
            <ReferenceLine
              y={scenarioDaily}
              stroke="var(--color-brand)"
              strokeDasharray="5 4"
              strokeWidth={1.5}
              label={{
                value: `תרחיש: ${formatNumber(scenarioDaily)}`,
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
            fill="url(#trendFill)"
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

export function EmptyChart() {
  return (
    <div className="flex h-full items-center justify-center text-xs text-[var(--color-ink-muted)]">
      אין נתונים להצגה
    </div>
  )
}
