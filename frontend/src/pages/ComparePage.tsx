import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowRight, Check, Trophy } from 'lucide-react'

import { Card, Skeleton } from '@/components/ui'
import { useCenter } from '@/hooks/useCenters'
import { useComparison, useScenarios } from '@/hooks/useScenarios'
import { deltaTone, formatKpiValue, formatSignedPercent } from '@/simulation/format'
import { cn } from '@/lib/utils'
import type { SimulatedKpi } from '@/types/api'

const MAX_COLUMNS = 3

const TONE_TEXT = {
  positive: 'text-[var(--color-positive)]',
  negative: 'text-[var(--color-negative)]',
  neutral: 'text-[var(--color-ink-muted)]',
} as const

/**
 * Side-by-side comparison of saved scenarios.
 *
 * All columns are evaluated server-side against a single snapshot in one
 * request. Fetching them separately could straddle a background refresh and
 * quietly compare scenarios built on different baselines — which would look
 * fine and be wrong.
 */
export function ComparePage() {
  const { centerId } = useParams<{ centerId: string }>()
  const { data: center } = useCenter(centerId)
  const { data: scenarios } = useScenarios(centerId)

  const [selected, setSelected] = useState<string[]>([])

  // Preselect the first few once the list arrives, so the page is useful
  // immediately instead of showing an empty table.
  useEffect(() => {
    if (scenarios && scenarios.length > 0 && selected.length === 0) {
      setSelected(scenarios.slice(0, MAX_COLUMNS).map((scenario) => scenario.id))
    }
  }, [scenarios, selected.length])

  const { data: comparison, isPending } = useComparison(centerId, selected)

  function toggle(id: string) {
    setSelected((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id)
      if (current.length >= MAX_COLUMNS) return current
      return [...current, id]
    })
  }

  const kpiRows = comparison?.columns[0]?.kpis ?? []

  return (
    <main className="mx-auto max-w-[1400px] space-y-4 p-4 sm:p-6">
      <div className="card p-4">
        <Link
          to={`/centers/${centerId}`}
          className="mb-2 inline-flex items-center gap-1 text-xs text-[var(--color-ink-muted)] transition-colors hover:text-[var(--color-brand)]"
        >
          <ArrowRight className="h-3 w-3" />
          חזרה למרכז הסימולציה
        </Link>
        <h1 className="text-xl font-bold text-[var(--color-ink)]">השוואת תרחישים</h1>
        <p className="mt-1 text-sm text-[var(--color-ink-muted)]">
          {center?.name ?? '—'} · עד {MAX_COLUMNS} תרחישים במקביל, כולם מחושבים מול אותו בסיס נתונים.
        </p>
      </div>

      <Card className="p-4">
        <h2 className="mb-3 text-sm font-semibold text-[var(--color-ink)]">בחירת תרחישים</h2>
        {!scenarios?.length ? (
          <p className="text-sm text-[var(--color-ink-muted)]">
            אין תרחישים שמורים למוקד זה. חזור למרכז הסימולציה, הגדר תרחיש ושמור אותו.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {scenarios.map((scenario) => {
              const active = selected.includes(scenario.id)
              const full = !active && selected.length >= MAX_COLUMNS
              return (
                <button
                  key={scenario.id}
                  type="button"
                  onClick={() => toggle(scenario.id)}
                  disabled={full}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm transition-colors',
                    active
                      ? 'border-[var(--color-brand)] bg-[var(--color-brand-soft)] font-medium text-[var(--color-brand-strong)]'
                      : 'border-[var(--color-line-strong)] bg-[var(--color-surface)] text-[var(--color-ink)] hover:bg-[var(--color-surface-muted)]',
                    full && 'cursor-not-allowed opacity-40',
                  )}
                >
                  {active ? <Check className="h-3.5 w-3.5" /> : null}
                  {scenario.name}
                </button>
              )
            })}
          </div>
        )}
      </Card>

      {selected.length === 0 ? null : isPending || !comparison ? (
        <Skeleton className="h-96" />
      ) : (
        <Card className="overflow-hidden">
          {/* Wide tables scroll inside their own container so the page body
              never scrolls sideways. */}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <caption className="sr-only">
                השוואת מדדי שירות בין המצב הנוכחי לתרחישים שנבחרו
              </caption>
              <thead>
                <tr className="border-b border-[var(--color-line)] bg-[var(--color-surface-muted)]">
                  <th scope="col" className="p-3 text-start font-semibold text-[var(--color-ink)]">
                    מדד
                  </th>
                  <th scope="col" className="p-3 text-center font-semibold text-[var(--color-ink-soft)]">
                    מצב נוכחי
                  </th>
                  {comparison.columns.map((column) => (
                    <th
                      key={column.scenario_id}
                      scope="col"
                      className="p-3 text-center font-semibold text-[var(--color-ink)]"
                    >
                      {column.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {kpiRows.map((row, rowIndex) => {
                  const winner = comparison.winners[row.id]
                  return (
                    <tr
                      key={row.id}
                      className={cn(
                        'border-b border-[var(--color-line)] last:border-0',
                        rowIndex % 2 === 1 && 'bg-[var(--color-surface-muted)]/50',
                      )}
                    >
                      <th scope="row" className="p-3 text-start font-medium text-[var(--color-ink)]">
                        {row.label}
                      </th>
                      <td className="tnum p-3 text-center text-[var(--color-ink-soft)]">
                        {formatKpiValue(row.current, row.format)}
                      </td>
                      {comparison.columns.map((column) => {
                        const cell = column.kpis.find((kpi) => kpi.id === row.id)
                        if (!cell) return <td key={column.scenario_id} className="p-3 text-center">—</td>
                        return (
                          <ScenarioCell
                            key={column.scenario_id}
                            kpi={cell}
                            isWinner={winner === column.scenario_id && cell.trend !== 0}
                          />
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <p className="border-t border-[var(--color-line)] px-4 py-2.5 text-[11px] text-[var(--color-ink-muted)]">
            <Trophy className="me-1 inline h-3 w-3 text-[var(--color-brand)]" />
            הסמל מציין את התרחיש המוביל בכל מדד, בהתאם לכיוון הרצוי שלו. תפוסה וניצולת אינן
            מסומנות — להן טווח תקין, לא כיוון עדיף.
          </p>
        </Card>
      )}
    </main>
  )
}

function ScenarioCell({ kpi, isWinner }: { kpi: SimulatedKpi; isWinner: boolean }) {
  const tone = deltaTone(kpi.difference, kpi.direction, kpi.is_improvement)

  return (
    <td
      className={cn(
        'p-3 text-center',
        isWinner && 'bg-[var(--color-brand-soft)]',
      )}
    >
      <div className="flex items-center justify-center gap-1.5">
        {isWinner ? <Trophy className="h-3 w-3 text-[var(--color-brand)]" /> : null}
        <span className="tnum font-semibold text-[var(--color-ink)]">
          {formatKpiValue(kpi.scenario, kpi.format)}
        </span>
      </div>
      {kpi.trend !== 0 ? (
        <span className={cn('tnum text-xs', TONE_TEXT[tone])}>
          {formatSignedPercent(kpi.percentage)}
        </span>
      ) : (
        <span className="text-xs text-[var(--color-ink-muted)]">ללא שינוי</span>
      )}
    </td>
  )
}
