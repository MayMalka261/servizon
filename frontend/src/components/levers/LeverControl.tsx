import { useEffect, useState } from 'react'
import { RotateCcw } from 'lucide-react'

import { BaselineTrack, InfoTooltip, Input, Slider } from '@/components/ui'
import { formatLeverValue } from '@/simulation/format'
import { ACCENTS } from '@/simulation/theme'
import { cn } from '@/lib/utils'
import type { LeverBounds, LeverDefinition } from '@/types/api'

interface Props {
  lever: LeverDefinition
  value: number
  baseline: number
  bounds: LeverBounds
  onChange: (value: number) => void
  onReset: () => void
  isMoved: boolean
}

/**
 * One operational lever.
 *
 * Two tracks, exactly as in the specification deck: the coloured one the user
 * drags, and a muted one beneath showing where the center actually sits today.
 * Seeing both at once is the difference between "60%" and "60%, up from 45%" —
 * only the second is a decision.
 */
export function LeverControl({
  lever,
  value,
  baseline,
  bounds,
  onChange,
  onReset,
  isMoved,
}: Props) {
  const accent = ACCENTS[lever.group]

  // The numeric field is free-text while focused so a partially typed number
  // is not clamped out from under the user mid-keystroke.
  const [draft, setDraft] = useState<string | null>(null)

  useEffect(() => {
    setDraft(null)
  }, [value])

  function commit(raw: string) {
    const parsed = Number(raw)
    setDraft(null)
    if (!Number.isFinite(parsed)) return
    onChange(Math.min(bounds.max, Math.max(bounds.min, parsed)))
  }

  return (
    <div
      className={cn(
        'rounded-xl border p-3 transition-colors',
        isMoved
          ? 'border-transparent'
          : 'border-[var(--color-line)] bg-white hover:border-[var(--color-line-strong)]',
      )}
      style={isMoved ? { backgroundColor: accent.soft } : undefined}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5">
          <span className="truncate text-sm font-medium text-[var(--color-ink)]">
            {lever.label}
          </span>
          <InfoTooltip content={lever.tooltip} />
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <Input
            value={draft ?? String(value)}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={(event) => commit(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') event.currentTarget.blur()
              if (event.key === 'Escape') setDraft(null)
            }}
            inputMode="decimal"
            aria-label={`ערך מספרי עבור ${lever.label}`}
            className="tnum h-7 w-16 px-2 text-center text-sm font-semibold"
          />
          <button
            type="button"
            onClick={onReset}
            disabled={!isMoved}
            aria-label={`איפוס ${lever.label} למצב הנוכחי`}
            title="איפוס למצב הנוכחי"
            className={cn(
              'rounded-md p-1 transition-colors',
              isMoved
                ? 'text-[var(--color-ink-soft)] hover:bg-white hover:text-[var(--color-ink)]'
                : 'cursor-not-allowed text-[var(--color-line-strong)]',
            )}
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="mt-2">
        <div className="flex items-center justify-between text-[11px] text-[var(--color-ink-muted)]">
          <span style={{ color: isMoved ? accent.color : undefined }} className="font-medium">
            תרחיש יעד
          </span>
          <span className="tnum">{formatLeverValue(value, lever.unit)}</span>
        </div>
        <Slider
          value={value}
          min={bounds.min}
          max={bounds.max}
          step={bounds.step}
          onValueChange={onChange}
          accent={accent.color}
          aria-label={lever.label}
        />
      </div>

      <div className="mt-1">
        <div className="flex items-center justify-between text-[11px] text-[var(--color-ink-muted)]">
          <span>מצב נוכחי</span>
          <span className="tnum">{formatLeverValue(baseline, lever.unit)}</span>
        </div>
        <BaselineTrack value={baseline} min={bounds.min} max={bounds.max} />
      </div>
    </div>
  )
}
