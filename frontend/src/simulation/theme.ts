/**
 * Which colour belongs to which lever family and status.
 *
 * The accent is not decoration: it tells the user at a glance whether they are
 * looking at a digital, workforce or AI scenario, and it carries through from
 * the lever panel to the KPI cards to the charts.
 */

import type { CenterStatus, LeverGroup, Severity, SimulationTab } from '@/types/api'

/**
 * Each tab's own colour, carried through its cards, sliders, charts and the
 * tab button itself.
 *
 * Two clearly separated hues rather than neighbouring blues: the tabs show
 * different metrics entirely, and the colour is the fastest signal of which
 * world you are looking at.
 */
export const TAB_ACCENT: Record<SimulationTab, string> = {
  digital_channels: 'var(--color-brand)',
  phone_center: 'var(--color-workforce)',
}

export interface Accent {
  /** CSS colour, for inline styles and chart props. */
  color: string
  soft: string
  /** Tailwind classes for the common card/panel treatment. */
  text: string
  bg: string
  border: string
}

export const ACCENTS: Record<LeverGroup, Accent> = {
  digital: {
    color: 'var(--color-digital)',
    soft: 'var(--color-digital-soft)',
    text: 'text-[var(--color-digital)]',
    bg: 'bg-[var(--color-digital-soft)]',
    border: 'border-[var(--color-digital)]',
  },
  workforce: {
    color: 'var(--color-workforce)',
    soft: 'var(--color-workforce-soft)',
    text: 'text-[var(--color-workforce)]',
    bg: 'bg-[var(--color-workforce-soft)]',
    border: 'border-[var(--color-workforce)]',
  },
  ai: {
    color: 'var(--color-ai)',
    soft: 'var(--color-ai-soft)',
    text: 'text-[var(--color-ai)]',
    bg: 'bg-[var(--color-ai-soft)]',
    border: 'border-[var(--color-ai)]',
  },
  quality: {
    color: 'var(--color-quality)',
    soft: 'var(--color-quality-soft)',
    text: 'text-[var(--color-quality)]',
    bg: 'bg-[var(--color-quality-soft)]',
    border: 'border-[var(--color-quality)]',
  },
  targets: {
    color: 'var(--color-brand)',
    soft: 'var(--color-brand-soft)',
    text: 'text-[var(--color-brand)]',
    bg: 'bg-[var(--color-brand-soft)]',
    border: 'border-[var(--color-brand)]',
  },
}

export const STATUS_STYLES: Record<CenterStatus, { dot: string; chip: string }> = {
  active: {
    dot: 'bg-[var(--color-positive)]',
    chip: 'bg-[var(--color-positive-soft)] text-[var(--color-positive)]',
  },
  strained: {
    dot: 'bg-[var(--color-warning)]',
    chip: 'bg-[var(--color-warning-soft)] text-[var(--color-warning)]',
  },
  critical: {
    dot: 'bg-[var(--color-critical)]',
    chip: 'bg-[var(--color-critical-soft)] text-[var(--color-critical)]',
  },
  offline: {
    dot: 'bg-[var(--color-neutral)]',
    chip: 'bg-[var(--color-neutral-soft)] text-[var(--color-neutral)]',
  },
}

export const SEVERITY_STYLES: Record<
  Severity,
  { bar: string; chip: string; label: string }
> = {
  critical: {
    bar: 'bg-[var(--color-critical)]',
    chip: 'bg-[var(--color-critical-soft)] text-[var(--color-critical)]',
    label: 'קריטי',
  },
  warning: {
    bar: 'bg-[var(--color-warning)]',
    chip: 'bg-[var(--color-warning-soft)] text-[var(--color-warning)]',
    label: 'לתשומת לב',
  },
  positive: {
    bar: 'bg-[var(--color-positive)]',
    chip: 'bg-[var(--color-positive-soft)] text-[var(--color-positive)]',
    label: 'שיפור',
  },
  info: {
    bar: 'bg-[var(--color-neutral)]',
    chip: 'bg-[var(--color-neutral-soft)] text-[var(--color-neutral)]',
    label: 'מידע',
  },
}

/** Chart series colours, in the order series should be assigned. */
export const CHART_SERIES = [
  'var(--color-digital)',
  'var(--color-ai)',
  'var(--color-brand)',
  'var(--color-workforce)',
] as const

export const CHART_GRID = 'var(--color-line)'
export const CHART_AXIS = 'var(--color-ink-muted)'
