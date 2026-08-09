import { Link } from 'react-router-dom'
import { Activity, RefreshCw } from 'lucide-react'

import { useHealth } from '@/hooks/useCenters'
import { formatTime } from '@/simulation/format'
import { ThemeToggle } from './ThemeToggle'
import { cn } from '@/lib/utils'

/**
 * The dark command bar carried across every screen in the specification deck.
 *
 * The freshness indicator is not decoration: this tool reads live operational
 * data, and a manager needs to know at a glance whether the numbers in front
 * of them are three minutes old or thirty.
 */
export function AppHeader() {
  const { data: health } = useHealth()

  const state = health?.status ?? 'starting'
  const tone =
    state === 'ok'
      ? 'bg-[var(--color-positive)]'
      : state === 'degraded'
        ? 'bg-[var(--color-warning)]'
        : 'bg-[var(--color-neutral)]'

  return (
    <header className="glass-bar sticky top-0 z-40 border-b border-white/10">
      {/* Hairline of accent along the bottom edge — reads as a status strip on
          a command bar, and stops the header floating free of the page. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-l from-transparent via-[var(--color-brand)]/45 to-transparent"
      />
      <div className="mx-auto flex h-16 max-w-[1800px] items-center justify-between gap-4 px-4 sm:px-6">
        <Link to="/" className="group flex items-center gap-3 min-w-0">
          <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--color-brand)] shadow-[0_0_20px_-4px_var(--color-brand)] transition-transform duration-[var(--duration-base)] ease-[var(--ease-out-soft)] group-hover:scale-105">
            <Activity className="h-5 w-5 text-white" strokeWidth={2.5} />
          </div>
          <div className="min-w-0">
            <div className="flex items-baseline gap-2">
              <span className="ltr text-lg font-bold leading-none text-white">Servizon</span>
              <span className="hidden text-sm text-white/60 sm:inline">אופק שירות</span>
            </div>
            <p className="mt-0.5 hidden truncate text-xs text-white/50 md:block">
              כלי הדמיה ותמיכה בקבלת החלטות למרכזי שירות
            </p>
          </div>
        </Link>

        <div className="flex items-center gap-3">
          {health?.last_refresh ? (
            <div className="hidden items-center gap-2 rounded-lg bg-white/5 px-3 py-1.5 text-xs text-white/70 sm:flex">
              <RefreshCw className="h-3.5 w-3.5" />
              <span>
                עודכן {formatTime(health.last_refresh)} · רענון כל {health.refresh_minutes} דק'
              </span>
            </div>
          ) : null}

          <div
            className="flex items-center gap-2 rounded-lg bg-white/5 px-3 py-1.5"
            title={`מקור נתונים: ${health?.data_source ?? '—'}`}
          >
            {/* The ring pulses only while data is actually flowing, so it
                reads as a heartbeat rather than as decoration. */}
            <span className={cn('relative h-2 w-2 rounded-full', tone, state === 'ok' && 'pulse-ring')} />
            <span className="text-xs font-medium text-white/80">
              {health?.centers_loaded ?? 0} מוקדים
            </span>
          </div>

          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
