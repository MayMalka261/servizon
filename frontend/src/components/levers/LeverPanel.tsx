import { useMemo } from 'react'
import { CalendarRange, RotateCcw, SlidersHorizontal } from 'lucide-react'

import { Button, Skeleton } from '@/components/ui'
import { LeverControl } from './LeverControl'
import { useLeverStore } from '@/stores/leverStore'
import { clampIsoDate, shiftIsoDate } from '@/lib/dateRange'
import { cn } from '@/lib/utils'
import { ACCENTS } from '@/simulation/theme'
import type { LeverBounds, LeverDefinition, LeverGroup, SimulationTab, Snapshot } from '@/types/api'

const GROUP_ORDER: LeverGroup[] = ['digital', 'workforce', 'ai', 'quality', 'targets']

const RANGE_PRESETS: { days: number; label: string }[] = [
  { days: 7, label: '7 ימים' },
  { days: 14, label: '14 יום' },
  { days: 30, label: '30 יום' },
]

interface Props {
  levers: LeverDefinition[] | undefined
  snapshot: Snapshot | undefined
  tab: SimulationTab
}

/**
 * The operational levers, grouped by family.
 *
 * Bounds come from the server — per-lever defaults, and per-center overrides
 * for anything whose scale depends on the center. Headcount has no meaningful
 * global range, so hardcoding one here would either cap a large center or let
 * a small one be dragged somewhere the model cannot evaluate.
 */
export function LeverPanel({ levers, snapshot, tab }: Props) {
  const values = useLeverStore((state) => state.values)
  const defaults = useLeverStore((state) => state.defaults)
  const touched = useLeverStore((state) => state.touched)
  const setLever = useLeverStore((state) => state.setLever)
  const resetLever = useLeverStore((state) => state.resetLever)
  const resetAll = useLeverStore((state) => state.resetAll)
  const trendRange = useLeverStore((state) => state.trendRange)
  const setTrendRange = useLeverStore((state) => state.setTrendRange)

  // The date input needs real bounds — the earliest and latest day the
  // center actually has history for — so the picker can't be aimed at a
  // range with nothing in it.
  const dateBounds = useMemo(() => {
    const points = snapshot?.trend[tab]?.volume
    if (!points || points.length === 0) return null
    return { min: points[0]!.date, max: points[points.length - 1]!.date }
  }, [snapshot, tab])

  const visible = useMemo(
    () => (levers ?? []).filter((lever) => lever.tabs.includes(tab)),
    [levers, tab],
  )

  const grouped = useMemo(() => {
    const map = new Map<LeverGroup, LeverDefinition[]>()
    for (const lever of visible) {
      const list = map.get(lever.group) ?? []
      list.push(lever)
      map.set(lever.group, list)
    }
    return map
  }, [visible])

  const movedCount = Object.keys(touched).filter(
    (id) => values[id as keyof typeof values] !== defaults[id as keyof typeof defaults],
  ).length

  if (!levers || !snapshot) {
    return (
      <div className="card p-4">
        <Skeleton className="mb-4 h-6 w-32" />
        {Array.from({ length: 6 }, (_, index) => (
          <Skeleton key={index} className="mb-2 h-24" />
        ))}
      </div>
    )
  }

  function boundsFor(lever: LeverDefinition): LeverBounds {
    return (
      snapshot?.lever_bounds[lever.id] ?? {
        min: lever.min,
        max: lever.max,
        step: lever.step,
      }
    )
  }

  return (
    <aside className="card flex min-h-0 flex-col overflow-hidden" aria-label="פילטרים">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-[var(--color-line)] px-4 py-3">
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4 text-[var(--color-ink-soft)]" />
          <h2 className="font-semibold text-[var(--color-ink)]">פילטרים</h2>
        </div>
        {movedCount > 0 ? (
          <Button variant="ghost" size="sm" onClick={resetAll}>
            <RotateCcw className="h-3.5 w-3.5" />
            איפוס ({movedCount})
          </Button>
        ) : null}
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto p-4">
        <section>
          <div className="mb-2 flex items-center gap-2">
            <CalendarRange className="h-3.5 w-3.5 text-[var(--color-ink-soft)]" aria-hidden />
            <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
              טווח תאריכים בגרפים
            </h3>
          </div>

          {dateBounds ? (
            <div className="space-y-2">
              <div className="grid grid-cols-4 gap-1 rounded-lg bg-[var(--color-surface-sunken)] p-1">
                {RANGE_PRESETS.map((preset) => {
                  const from = clampIsoDate(
                    shiftIsoDate(dateBounds.max, -(preset.days - 1)),
                    dateBounds.min,
                    dateBounds.max,
                  )
                  const isActive = trendRange.from === from && trendRange.to === dateBounds.max
                  return (
                    <button
                      key={preset.days}
                      type="button"
                      onClick={() => setTrendRange({ from, to: dateBounds.max })}
                      aria-pressed={isActive}
                      className={cn(
                        'rounded-md px-1.5 py-1.5 text-xs font-medium transition-colors',
                        isActive
                          ? 'bg-[var(--color-surface)] text-[var(--color-ink)] shadow-[var(--shadow-raised)]'
                          : 'text-[var(--color-ink-muted)] hover:text-[var(--color-ink-soft)]',
                      )}
                    >
                      {preset.label}
                    </button>
                  )
                })}
                <button
                  type="button"
                  onClick={() => setTrendRange({ from: null, to: null })}
                  aria-pressed={trendRange.from === null && trendRange.to === null}
                  className={cn(
                    'rounded-md px-1.5 py-1.5 text-xs font-medium transition-colors',
                    trendRange.from === null && trendRange.to === null
                      ? 'bg-[var(--color-surface)] text-[var(--color-ink)] shadow-[var(--shadow-raised)]'
                      : 'text-[var(--color-ink-muted)] hover:text-[var(--color-ink-soft)]',
                  )}
                >
                  הכל
                </button>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <label className="block">
                  <span className="mb-1 block text-[11px] text-[var(--color-ink-muted)]">מ-</span>
                  <input
                    type="date"
                    value={trendRange.from ?? dateBounds.min}
                    min={dateBounds.min}
                    max={trendRange.to ?? dateBounds.max}
                    onChange={(event) =>
                      setTrendRange({ ...trendRange, from: event.target.value || null })
                    }
                    className={cn(
                      'h-9 w-full rounded-lg border border-[var(--color-line-strong)] bg-[var(--color-surface)]',
                      'px-2 text-xs text-[var(--color-ink)] transition-colors',
                      'focus:border-[var(--color-brand)] focus:outline-none',
                    )}
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-[11px] text-[var(--color-ink-muted)]">עד</span>
                  <input
                    type="date"
                    value={trendRange.to ?? dateBounds.max}
                    min={trendRange.from ?? dateBounds.min}
                    max={dateBounds.max}
                    onChange={(event) =>
                      setTrendRange({ ...trendRange, to: event.target.value || null })
                    }
                    className={cn(
                      'h-9 w-full rounded-lg border border-[var(--color-line-strong)] bg-[var(--color-surface)]',
                      'px-2 text-xs text-[var(--color-ink)] transition-colors',
                      'focus:border-[var(--color-brand)] focus:outline-none',
                    )}
                  />
                </label>
              </div>
            </div>
          ) : (
            <Skeleton className="h-9 w-full" />
          )}
        </section>

        {GROUP_ORDER.map((group) => {
          const groupLevers = grouped.get(group)
          if (!groupLevers?.length) return null
          const accent = ACCENTS[group]

          return (
            <section key={group}>
              <div className="mb-2 flex items-center gap-2">
                <span
                  className="h-3 w-1 rounded-full"
                  style={{ backgroundColor: accent.color }}
                  aria-hidden
                />
                <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
                  {groupLevers[0]?.group_label}
                </h3>
              </div>

              <div className="space-y-2">
                {groupLevers.map((lever) => {
                  const bounds = boundsFor(lever)
                  const baseline = defaults[lever.id] ?? bounds.min
                  const value = values[lever.id] ?? baseline
                  return (
                    <LeverControl
                      key={lever.id}
                      lever={lever}
                      value={value}
                      baseline={baseline}
                      bounds={bounds}
                      isMoved={Boolean(touched[lever.id]) && value !== baseline}
                      onChange={(next) => setLever(lever.id, next)}
                      onReset={() => resetLever(lever.id)}
                    />
                  )
                })}
              </div>
            </section>
          )
        })}
      </div>

      <p className="shrink-0 border-t border-[var(--color-line)] px-4 py-2.5 text-[11px] leading-relaxed text-[var(--color-ink-muted)]">
        יש לגרור לצורך בדיקת ההשפעה. הסימולציה רצה על עותק זמני — נתוני המקור אינם משתנים.
      </p>
    </aside>
  )
}
