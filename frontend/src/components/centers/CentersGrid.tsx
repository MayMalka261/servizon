import { useEffect, useRef, useState } from 'react'
import { useWindowVirtualizer } from '@tanstack/react-virtual'

import { CenterCard } from './CenterCard'
import type { ServiceCenter } from '@/types/api'

const CARD_HEIGHT = 208
const GAP = 16

/** Column count per breakpoint, matching the grid classes below. */
function columnsFor(width: number): number {
  if (width >= 1536) return 4
  if (width >= 1024) return 3
  if (width >= 640) return 2
  return 1
}

/**
 * Virtualized grid of service centers.
 *
 * The seed carries twenty centers, but the deployment target has dozens and
 * the design has to survive hundreds without the browser laying out every card
 * on every filter keystroke. Rows are virtualized against the window scroll,
 * so the page keeps a single natural scrollbar rather than a nested one.
 */
export function CentersGrid({ centers }: { centers: ServiceCenter[] }) {
  const listRef = useRef<HTMLDivElement>(null)
  const [columns, setColumns] = useState(() =>
    columnsFor(typeof window === 'undefined' ? 1280 : window.innerWidth),
  )

  useEffect(() => {
    function measure() {
      setColumns(columnsFor(window.innerWidth))
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [])

  const rowCount = Math.ceil(centers.length / columns)

  const virtualizer = useWindowVirtualizer({
    count: rowCount,
    estimateSize: () => CARD_HEIGHT + GAP,
    overscan: 3,
    scrollMargin: listRef.current?.offsetTop ?? 0,
  })

  return (
    <div ref={listRef} className="relative">
      <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
        {virtualizer.getVirtualItems().map((row) => {
          const start = row.index * columns
          const slice = centers.slice(start, start + columns)

          return (
            <div
              key={row.key}
              data-index={row.index}
              ref={virtualizer.measureElement}
              className="absolute inset-x-0 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4"
              style={{
                transform: `translateY(${row.start - virtualizer.options.scrollMargin}px)`,
                paddingBottom: GAP,
              }}
            >
              {/* Stagger within the row, not across the whole list: rows mount
                  as they scroll into view, and a global index would give the
                  hundredth card a four-second delay. */}
              {slice.map((center, column) => (
                <CenterCard key={center.id} center={center} index={column} />
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}
