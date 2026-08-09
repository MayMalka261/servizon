/**
 * Thin wrappers over Radix primitives, styled for this application.
 *
 * Radix handles the keyboard and screen-reader behaviour; these add nothing
 * but appearance. Notably, Radix reads `dir` from the document, so sliders and
 * popovers orient correctly in RTL without per-component handling.
 */

import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'
import * as SliderPrimitive from '@radix-ui/react-slider'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import * as TabsPrimitive from '@radix-ui/react-tabs'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { Info, X } from 'lucide-react'

import { cn } from '@/lib/utils'

/* -------------------------------------------------------------------------- */
/* Input                                                                      */
/* -------------------------------------------------------------------------- */

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'h-10 w-full rounded-lg border border-[var(--color-line-strong)] bg-[var(--color-surface)] px-3 text-sm',
        'text-[var(--color-ink)] placeholder:text-[var(--color-ink-muted)]',
        'transition-colors focus:border-[var(--color-brand)] focus:outline-none',
        'disabled:cursor-not-allowed disabled:bg-[var(--color-surface-muted)]',
        className,
      )}
      {...props}
    />
  ),
)
Input.displayName = 'Input'

/* -------------------------------------------------------------------------- */
/* Select — native, because a native picker is better on touch and needs no    */
/* extra keyboard handling                                                     */
/* -------------------------------------------------------------------------- */

export function Select({
  value,
  onChange,
  options,
  placeholder,
  className,
  'aria-label': ariaLabel,
}: {
  value: string
  onChange: (value: string) => void
  options: Array<{ value: string; label: string }>
  placeholder: string
  className?: string
  'aria-label'?: string
}) {
  return (
    <select
      aria-label={ariaLabel ?? placeholder}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className={cn(
        'h-10 w-full appearance-none rounded-lg border border-[var(--color-line-strong)] bg-[var(--color-surface)]',
        'px-3 pe-8 text-sm text-[var(--color-ink)] transition-colors',
        'focus:border-[var(--color-brand)] focus:outline-none',
        // Chevron drawn as a background image so it sits on the correct side
        // in RTL without an absolutely positioned icon.
        "bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2216%22 height=%2216%22 fill=%22none%22 stroke=%22%237b8fa1%22 stroke-width=%222%22><path d=%22M4 6l4 4 4-4%22/></svg>')]",
        'bg-[length:16px] bg-no-repeat bg-[position:left_0.65rem_center]',
        className,
      )}
    >
      <option value="">{placeholder}</option>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

/* -------------------------------------------------------------------------- */
/* Slider                                                                     */
/* -------------------------------------------------------------------------- */

export function Slider({
  value,
  min,
  max,
  step,
  onValueChange,
  onValueCommit,
  accent,
  disabled,
  'aria-label': ariaLabel,
}: {
  value: number
  min: number
  max: number
  step: number
  onValueChange: (value: number) => void
  onValueCommit?: (value: number) => void
  accent: string
  disabled?: boolean
  'aria-label': string
}) {
  return (
    <SliderPrimitive.Root
      className="relative flex h-5 w-full touch-none select-none items-center"
      value={[value]}
      min={min}
      max={max}
      step={step}
      disabled={disabled}
      aria-label={ariaLabel}
      onValueChange={([next]) => next !== undefined && onValueChange(next)}
      onValueCommit={([next]) => next !== undefined && onValueCommit?.(next)}
    >
      <SliderPrimitive.Track className="relative h-1.5 w-full grow rounded-full bg-[var(--color-surface-sunken)]">
        <SliderPrimitive.Range
          className="absolute h-full rounded-full"
          style={{ backgroundColor: accent }}
        />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb
        className={cn(
          'block h-4 w-4 rounded-full border-2 bg-[var(--color-surface)] shadow-sm transition-transform',
          'hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
          'disabled:pointer-events-none',
        )}
        style={{ borderColor: accent }}
      />
    </SliderPrimitive.Root>
  )
}

/** Static bar showing where the center sits today, beneath the live slider. */
export function BaselineTrack({ value, min, max }: { value: number; min: number; max: number }) {
  const span = max - min
  const percent = span > 0 ? ((value - min) / span) * 100 : 0
  return (
    <div className="relative flex h-5 w-full items-center" aria-hidden>
      <div className="relative h-1.5 w-full rounded-full bg-[var(--color-surface-sunken)]">
        <div
          className="absolute h-full rounded-full bg-[var(--color-line-strong)]"
          style={{ width: `${percent}%` }}
        />
      </div>
      <div
        className="absolute h-3.5 w-3.5 rounded-full border-2 border-[var(--color-ink-muted)] bg-[var(--color-surface)]"
        style={{ insetInlineStart: `calc(${percent}% - 7px)` }}
      />
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Tooltip                                                                    */
/* -------------------------------------------------------------------------- */

export function TooltipProvider({ children }: { children: ReactNode }) {
  return (
    <TooltipPrimitive.Provider delayDuration={200} skipDelayDuration={400}>
      {children}
    </TooltipPrimitive.Provider>
  )
}

export function InfoTooltip({ content }: { content: string }) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>
        <button
          type="button"
          className="text-[var(--color-ink-muted)] transition-colors hover:text-[var(--color-ink-soft)]"
          aria-label="הסבר על המנוף"
        >
          <Info className="h-3.5 w-3.5" />
        </button>
      </TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side="top"
          align="center"
          sideOffset={6}
          collisionPadding={12}
          className={cn(
            'z-50 max-w-72 rounded-lg bg-[var(--color-header)] px-3 py-2',
            'text-xs leading-relaxed text-white shadow-[var(--shadow-overlay)]',
            'data-[state=delayed-open]:animate-in data-[state=delayed-open]:fade-in-0',
          )}
        >
          {content}
          <TooltipPrimitive.Arrow className="fill-[var(--color-header)]" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  )
}

/* -------------------------------------------------------------------------- */
/* Tabs                                                                       */
/* -------------------------------------------------------------------------- */

export const Tabs = TabsPrimitive.Root

export function TabsList({ children }: { children: ReactNode }) {
  return (
    <TabsPrimitive.List className="inline-flex items-center gap-1 rounded-xl bg-[var(--color-surface-sunken)] p-1">
      {children}
    </TabsPrimitive.List>
  )
}

export function TabsTrigger({ value, children }: { value: string; children: ReactNode }) {
  return (
    <TabsPrimitive.Trigger
      value={value}
      className={cn(
        'inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium',
        'transition-all duration-[var(--duration-base)] ease-[var(--ease-out-soft)]',
        'text-[var(--color-ink-soft)] hover:text-[var(--color-ink)]',
        'data-[state=active]:bg-[var(--color-surface)] data-[state=active]:text-[var(--color-brand)]',
        'data-[state=active]:shadow-[var(--shadow-raised)]',
      )}
    >
      {children}
    </TabsPrimitive.Trigger>
  )
}

/* -------------------------------------------------------------------------- */
/* Dialog                                                                     */
/* -------------------------------------------------------------------------- */

export const Dialog = DialogPrimitive.Root
export const DialogTrigger = DialogPrimitive.Trigger
export const DialogClose = DialogPrimitive.Close

export function DialogContent({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[var(--color-header)]/40 backdrop-blur-[2px]" />
      <DialogPrimitive.Content
        dir="rtl"
        className={cn(
          'fixed start-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-md -translate-y-1/2',
          'translate-x-1/2 rounded-2xl bg-[var(--color-surface)] p-6 shadow-[var(--shadow-overlay)]',
        )}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <DialogPrimitive.Title className="text-lg font-semibold text-[var(--color-ink)]">
              {title}
            </DialogPrimitive.Title>
            {description ? (
              <DialogPrimitive.Description className="mt-1 text-sm text-[var(--color-ink-muted)]">
                {description}
              </DialogPrimitive.Description>
            ) : null}
          </div>
          <DialogPrimitive.Close
            className="rounded-lg p-1 text-[var(--color-ink-muted)] transition-colors hover:bg-[var(--color-surface-sunken)]"
            aria-label="סגירה"
          >
            <X className="h-4 w-4" />
          </DialogPrimitive.Close>
        </div>
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
}

/* -------------------------------------------------------------------------- */
/* Small display helpers                                                      */
/* -------------------------------------------------------------------------- */

export function Badge({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium',
        className,
      )}
    >
      {children}
    </span>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('animate-pulse rounded-lg bg-[var(--color-surface-sunken)]', className)}
      aria-hidden
    />
  )
}
