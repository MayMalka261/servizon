import { Search, X } from 'lucide-react'

import { Button, Input, Select } from '@/components/ui'
import { useFilterOptions } from '@/hooks/useCenters'
import type { CenterQuery } from '@/types/api'

interface Props {
  query: CenterQuery
  onChange: (next: CenterQuery) => void
  resultCount: number
  totalCount: number
}

export function CenterFilters({ query, onChange, resultCount, totalCount }: Props) {
  const { data: options } = useFilterOptions()

  const activeCount = Object.values(query).filter(Boolean).length
  const hasFilters = activeCount > 0

  function update<K extends keyof CenterQuery>(key: K, value: string) {
    const next = { ...query }
    if (value) next[key] = value as CenterQuery[K]
    else delete next[key]
    onChange(next)
  }

  return (
    <div className="card p-4">
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-5">
        <div className="relative lg:col-span-1">
          <Search className="pointer-events-none absolute inset-y-0 start-3 my-auto h-4 w-4 text-[var(--color-ink-muted)]" />
          <Input
            value={query.search ?? ''}
            onChange={(event) => update('search', event.target.value)}
            placeholder="חיפוש לפי שם או מזהה"
            className="ps-9"
            aria-label="חיפוש מוקד"
          />
        </div>

        <Select
          value={query.center_type ?? ''}
          onChange={(value) => update('center_type', value)}
          options={options?.center_type ?? []}
          placeholder="כל סוגי המוקדים"
          aria-label="סינון לפי סוג מוקד"
        />
        <Select
          value={query.district ?? ''}
          onChange={(value) => update('district', value)}
          options={options?.district ?? []}
          placeholder="כל המחוזות"
          aria-label="סינון לפי מחוז"
        />
        <Select
          value={query.status ?? ''}
          onChange={(value) => update('status', value)}
          options={options?.status ?? []}
          placeholder="כל הסטטוסים"
          aria-label="סינון לפי סטטוס"
        />
        <Select
          value={query.size ?? ''}
          onChange={(value) => update('size', value)}
          options={options?.size ?? []}
          placeholder="כל הגדלים"
          aria-label="סינון לפי גודל מוקד"
        />
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-[var(--color-line)] pt-3">
        <p className="text-sm text-[var(--color-ink-muted)]">
          {hasFilters ? (
            <>
              מוצגים <span className="font-semibold text-[var(--color-ink)]">{resultCount}</span> מתוך{' '}
              {totalCount} מוקדים
            </>
          ) : (
            <>
              <span className="font-semibold text-[var(--color-ink)]">{totalCount}</span> מוקדי שירות
            </>
          )}
        </p>
        {hasFilters ? (
          <Button variant="ghost" size="sm" onClick={() => onChange({})}>
            <X className="h-3.5 w-3.5" />
            ניקוי סינון
          </Button>
        ) : null}
      </div>
    </div>
  )
}
