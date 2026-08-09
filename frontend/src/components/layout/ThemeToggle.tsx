import { useEffect } from 'react'
import { Monitor, Moon, Sun } from 'lucide-react'

import { useThemeStore, type ThemePreference } from '@/stores/themeStore'
import { cn } from '@/lib/utils'

const OPTIONS: Array<{ value: ThemePreference; label: string; Icon: typeof Sun }> = [
  { value: 'light', label: 'בהיר', Icon: Sun },
  { value: 'dark', label: 'כהה', Icon: Moon },
  { value: 'system', label: 'לפי המערכת', Icon: Monitor },
]

/**
 * Three-way theme control.
 *
 * A segmented control rather than the usual sun/moon switch, because a binary
 * toggle cannot express "follow the machine" — and on managed workstations
 * that is the setting most people actually want.
 */
export function ThemeToggle() {
  const preference = useThemeStore((state) => state.preference)
  const setPreference = useThemeStore((state) => state.setPreference)
  const syncSystem = useThemeStore((state) => state.syncSystem)

  // Keep following the OS while the preference is "system" — a workstation
  // that switches to dark in the evening should take the app with it.
  useEffect(() => {
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    query.addEventListener('change', syncSystem)
    return () => query.removeEventListener('change', syncSystem)
  }, [syncSystem])

  return (
    <div
      role="radiogroup"
      aria-label="ערכת נושא"
      className="flex items-center gap-0.5 rounded-lg bg-white/5 p-0.5"
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = preference === value
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={label}
            title={label}
            onClick={() => setPreference(value)}
            className={cn(
              'rounded-md p-1.5 transition-colors duration-[var(--duration-fast)]',
              active ? 'bg-white/15 text-white' : 'text-white/50 hover:text-white/80',
            )}
          >
            <Icon className="h-3.5 w-3.5" />
          </button>
        )
      })}
    </div>
  )
}
