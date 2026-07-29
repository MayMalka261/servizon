import { useMemo, useState } from 'react'
import { SearchX, ServerCrash } from 'lucide-react'

import { CenterFilters } from '@/components/centers/CenterFilters'
import { CentersGrid } from '@/components/centers/CentersGrid'
import { Button, Card, Skeleton } from '@/components/ui'
import { useCenters } from '@/hooks/useCenters'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import type { CenterQuery } from '@/types/api'

export function CentersPage() {
  const [query, setQuery] = useState<CenterQuery>({})

  // Debounce only the free-text field; a dropdown change should apply at once.
  const debouncedSearch = useDebouncedValue(query.search ?? '', 250)
  const effectiveQuery = useMemo<CenterQuery>(
    () => ({ ...query, ...(debouncedSearch ? { search: debouncedSearch } : { search: undefined }) }),
    [query, debouncedSearch],
  )

  const { data: centers, isPending, isError, error, refetch } = useCenters(effectiveQuery)
  const { data: allCenters } = useCenters({})

  return (
    <main className="mx-auto max-w-[1800px] p-4 sm:p-6">
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-[var(--color-ink)]">מוקדי שירות</h1>
        <p className="mt-1 text-sm text-[var(--color-ink-muted)]">
          בחר מוקד כדי לפתוח את מרכז הסימולציה ולבחון תרחישי "מה אם" על נתוני האמת שלו.
        </p>
      </div>

      <div className="mb-5">
        <CenterFilters
          query={query}
          onChange={setQuery}
          resultCount={centers?.length ?? 0}
          totalCount={allCenters?.length ?? 0}
        />
      </div>

      {isError ? (
        <ErrorState message={(error as Error).message} onRetry={() => void refetch()} />
      ) : isPending ? (
        <LoadingState />
      ) : centers.length === 0 ? (
        <EmptyState onClear={() => setQuery({})} />
      ) : (
        <CentersGrid centers={centers} />
      )}
    </main>
  )
}

function LoadingState() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
      {Array.from({ length: 8 }, (_, index) => (
        <Skeleton key={index} className="h-52" />
      ))}
    </div>
  )
}

function EmptyState({ onClear }: { onClear: () => void }) {
  return (
    <Card className="flex flex-col items-center justify-center px-6 py-16 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-surface-sunken)]">
        <SearchX className="h-6 w-6 text-[var(--color-ink-muted)]" />
      </div>
      <h2 className="font-semibold text-[var(--color-ink)]">לא נמצאו מוקדים תואמים</h2>
      <p className="mt-1 max-w-sm text-sm text-[var(--color-ink-muted)]">
        נסה לשנות את מונחי החיפוש או להסיר חלק מהמסננים.
      </p>
      <Button variant="secondary" size="sm" className="mt-5" onClick={onClear}>
        ניקוי כל המסננים
      </Button>
    </Card>
  )
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Card className="flex flex-col items-center justify-center px-6 py-16 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-critical-soft)]">
        <ServerCrash className="h-6 w-6 text-[var(--color-critical)]" />
      </div>
      <h2 className="font-semibold text-[var(--color-ink)]">לא ניתן לטעון את רשימת המוקדים</h2>
      <p className="mt-1 max-w-sm text-sm text-[var(--color-ink-muted)]">{message}</p>
      <Button variant="primary" size="sm" className="mt-5" onClick={onRetry}>
        נסה שוב
      </Button>
    </Card>
  )
}
