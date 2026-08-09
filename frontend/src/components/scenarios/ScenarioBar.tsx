import { useState } from 'react'
import { Link } from 'react-router-dom'
import { BookmarkPlus, GitCompareArrows, Trash2 } from 'lucide-react'

import { Button, Dialog, DialogClose, DialogContent, DialogTrigger, Input } from '@/components/ui'
import { useCreateScenario, useDeleteScenario, useScenarios } from '@/hooks/useScenarios'
import { useHasScenario, useLeverStore } from '@/stores/leverStore'
import { cn } from '@/lib/utils'
import type { SimulationTab } from '@/types/api'

/**
 * Saved scenarios for this center.
 *
 * Scenarios persist server-side in a local database, so a comparison survives
 * a page reload and can be handed to somebody else at the same terminal.
 */
export function ScenarioBar({ centerId, tab }: { centerId: string; tab: SimulationTab }) {
  const { data: scenarios } = useScenarios(centerId)
  const create = useCreateScenario(centerId)
  const remove = useDeleteScenario(centerId)

  const values = useLeverStore((state) => state.values)
  const applyScenario = useLeverStore((state) => state.applyScenario)
  const hasScenario = useHasScenario()

  const [name, setName] = useState('')
  const [open, setOpen] = useState(false)

  const saved = scenarios ?? []

  function handleSave() {
    const trimmed = name.trim()
    if (!trimmed) return
    create.mutate(
      { center_id: centerId, name: trimmed, tab, levers: values },
      {
        onSuccess: () => {
          setName('')
          setOpen(false)
        },
      },
    )
  }

  return (
    <div className="card flex flex-wrap items-center gap-2 px-4 py-3">
      <span className="text-sm font-medium text-[var(--color-ink-soft)]">תרחישים שמורים:</span>

      {saved.length === 0 ? (
        <span className="text-sm text-[var(--color-ink-muted)]">
          אין תרחישים שמורים למוקד זה עדיין.
        </span>
      ) : (
        <div className="flex flex-wrap items-center gap-1.5">
          {saved.map((scenario) => (
            <div
              key={scenario.id}
              className={cn(
                'group flex items-center gap-1 rounded-lg border border-[var(--color-line-strong)]',
                'bg-[var(--color-surface)] ps-2 text-sm transition-colors hover:border-[var(--color-brand)]',
              )}
            >
              <button
                type="button"
                onClick={() => applyScenario(scenario.levers)}
                className="py-1.5 font-medium text-[var(--color-ink)]"
                title="טעינת התרחיש למנופים"
              >
                {scenario.name}
              </button>
              <button
                type="button"
                onClick={() => remove.mutate(scenario.id)}
                aria-label={`מחיקת ${scenario.name}`}
                className="rounded-e-lg p-1.5 text-[var(--color-ink-muted)] transition-colors hover:bg-[var(--color-negative-soft)] hover:text-[var(--color-negative)]"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="ms-auto flex items-center gap-2">
        {saved.length >= 2 ? (
          // A Link rather than a Button wrapping one: a button containing an
          // anchor is invalid and breaks keyboard navigation.
          <Link
            to={`/centers/${centerId}/compare`}
            className={cn(
              'inline-flex h-8 items-center gap-2 rounded-lg border border-[var(--color-line-strong)]',
              'bg-[var(--color-surface)] px-3 text-sm font-medium text-[var(--color-ink)] transition-colors',
              'hover:bg-[var(--color-surface-muted)]',
            )}
          >
            <GitCompareArrows className="h-3.5 w-3.5" />
            השוואת תרחישים
          </Link>
        ) : null}

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button variant="primary" size="sm" disabled={!hasScenario}>
              <BookmarkPlus className="h-3.5 w-3.5" />
              שמירת תרחיש
            </Button>
          </DialogTrigger>
          <DialogContent
            title="שמירת תרחיש"
            description="התרחיש נשמר עם ערכי המנופים הנוכחיים ויהיה זמין להשוואה."
          >
            <label className="block text-sm font-medium text-[var(--color-ink)]" htmlFor="scenario-name">
              שם התרחיש
            </label>
            <Input
              id="scenario-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && handleSave()}
              placeholder="לדוגמה: הגדלת אימוץ דיגיטלי ל-70%"
              className="mt-1.5"
              autoFocus
              maxLength={80}
            />
            {create.isError ? (
              <p className="mt-2 text-xs text-[var(--color-negative)]">
                {(create.error as Error).message}
              </p>
            ) : null}
            <div className="mt-5 flex justify-start gap-2">
              <Button variant="primary" onClick={handleSave} disabled={!name.trim() || create.isPending}>
                {create.isPending ? 'שומר…' : 'שמירה'}
              </Button>
              <DialogClose asChild>
                <Button variant="ghost">ביטול</Button>
              </DialogClose>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}
