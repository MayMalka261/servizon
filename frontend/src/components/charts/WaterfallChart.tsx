import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { ChartFrame, ChartTooltipBox } from './ChartFrame'
import { formatNumber } from '@/simulation/format'
import { CHART_AXIS, CHART_GRID } from '@/simulation/theme'
import type { WaterfallStep } from '@/types/api'

/**
 * How much of the change in contact volume each lever is responsible for.
 *
 * Each bar is that lever evaluated on its own against the baseline, so the
 * bars will not sum exactly to the combined result — interaction effects are
 * excluded, which is the standard simplification for an attribution chart.
 * The KPI cards remain the authoritative total, and the description says so.
 */
export function WaterfallChart({
  steps,
  hasScenario,
}: {
  steps: WaterfallStep[]
  hasScenario: boolean
}) {
  if (steps.length === 0) {
    return (
      <ChartFrame title="תרומת המנופים לשינוי" height={110}>
        <div className="flex h-full items-center justify-center px-4 text-center text-xs leading-relaxed text-[var(--color-ink-muted)]">
          {hasScenario
            ? // Distinguishing these two states matters: staffing and SLA
              // targets change service levels without touching demand, and
              // "no data" would read as a fault rather than a fact.
              'המנופים בתרחיש זה משפיעים על רמת השירות אך לא על נפח הפניות.'
            : 'הזז מנוף כדי לראות את חלקו בשינוי נפח הפניות.'}
        </div>
      </ChartFrame>
    )
  }

  const data = steps.map((step) => ({
    name: step.label,
    value: step.contribution,
  }))

  return (
    <ChartFrame
      title="תרומת המנופים לשינוי"
      description="השפעת כל מנוף בנפרד על נפח הפניות. הסכום המשולב מוצג בכרטיסי המדדים."
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 12, left: 4, bottom: 4 }}>
          <CartesianGrid stroke={CHART_GRID} horizontal={false} />
          <XAxis
            type="number"
            tick={{ fontSize: 10, fill: CHART_AXIS }}
            tickLine={false}
            axisLine={false}
            // Anchor at zero. Left to itself Recharts fits the domain to the
            // data, so a single moved lever produces an axis like -732…-728 —
            // five meaningless ticks around one bar, with no sense of scale.
            domain={([min, max]: readonly [number, number]) =>
              [Math.min(0, min), Math.max(0, max)] as [number, number]
            }
            tickFormatter={(value: number) => formatNumber(value)}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 10, fill: CHART_AXIS }}
            tickLine={false}
            axisLine={false}
            width={96}
          />
          <Tooltip
            cursor={{ fill: 'var(--color-surface-muted)' }}
            content={({ active, payload }) =>
              active && payload?.length ? (
                <ChartTooltipBox
                  label={String(payload[0]?.payload?.name ?? '')}
                  rows={[
                    {
                      name: 'שינוי בנפח',
                      value: `${Number(payload[0]?.value) > 0 ? '+' : '−'}${formatNumber(
                        Math.abs(Number(payload[0]?.value ?? 0)),
                      )}`,
                    },
                  ]}
                />
              ) : null
            }
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} isAnimationActive={false}>
            {data.map((entry) => (
              <Cell
                key={entry.name}
                // Volume down is the desirable direction for this metric.
                fill={entry.value < 0 ? 'var(--color-positive)' : 'var(--color-negative)'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}
