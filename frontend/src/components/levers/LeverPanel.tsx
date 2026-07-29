import { useMemo } from 'react'
import { RotateCcw, SlidersHorizontal } from 'lucide-react'

import { Button, Skeleton } from '@/components/ui'
import { LeverControl } from './LeverControl'
import { useLeverStore } from '@/stores/leverStore'
import { ACCENTS } from '@/simulation/theme'
import type { LeverBounds, LeverDefinition, LeverGroup, SimulationTab, Snapshot } from '@/types/api'

const GROUP_ORDER: LeverGroup[] = ['digital', 'workforce', 'ai', 'targets']

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
    <aside className="card flex flex-col overflow-hidden" aria-label="מנופים תפעוליים">
      <div className="flex items-center justify-between gap-2 border-b border-[var(--color-line)] px-4 py-3">
        <div className="flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4 text-[var(--color-ink-soft)]" />
          <h2 className="font-semibold text-[var(--color-ink)]">מנוף תפעולי</h2>
        </div>
        {movedCount > 0 ? (
          <Button variant="ghost" size="sm" onClick={resetAll}>
            <RotateCcw className="h-3.5 w-3.5" />
            איפוס ({movedCount})
          </Button>
        ) : null}
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto p-4">
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

      <p className="border-t border-[var(--color-line)] px-4 py-2.5 text-[11px] leading-relaxed text-[var(--color-ink-muted)]">
        יש לגרור לצורך בדיקת ההשפעה. הסימולציה רצה על עותק זמני — נתוני המקור אינם משתנים.
      </p>
    </aside>
  )
}
