import type { ReactNode } from 'react'

import { Card } from '@/components/ui'

/** Shared shell so every chart carries the same title/description treatment. */
export function ChartFrame({
  title,
  description,
  height = 200,
  children,
}: {
  title: string
  description?: string
  height?: number
  children: ReactNode
}) {
  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold text-[var(--color-ink)]">{title}</h3>
      {description ? (
        <p className="mt-0.5 text-[11px] leading-relaxed text-[var(--color-ink-muted)]">
          {description}
        </p>
      ) : null}
      {/* Recharts' ResponsiveContainer needs a definite height from its parent. */}
      <div className="mt-3" style={{ height }} dir="ltr">
        {children}
      </div>
    </Card>
  )
}

export function ChartTooltipBox({
  label,
  rows,
}: {
  label: string
  rows: Array<{ name: string; value: string; color?: string }>
}) {
  return (
    <div
      dir="rtl"
      className="rounded-lg border border-[var(--color-line)] bg-white px-3 py-2 shadow-[var(--shadow-raised)]"
    >
      <p className="mb-1 text-xs font-semibold text-[var(--color-ink)]">{label}</p>
      {rows.map((row) => (
        <div key={row.name} className="flex items-center gap-2 text-xs">
          {row.color ? (
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: row.color }}
              aria-hidden
            />
          ) : null}
          <span className="text-[var(--color-ink-muted)]">{row.name}</span>
          <span className="tnum ms-auto font-medium text-[var(--color-ink)]">{row.value}</span>
        </div>
      ))}
    </div>
  )
}
