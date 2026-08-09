/**
 * Light / dark preference.
 *
 * Kept in localStorage rather than in React state alone, because a manager who
 * set this once should not have to set it again after every refresh — and this
 * application reloads its data on a timer.
 *
 * The stored value is a *preference*, which may be "system". Only `resolve`
 * turns that into an actual theme, so following the OS remains live: a machine
 * that switches to dark at sunset takes the app with it.
 */

import { create } from 'zustand'

export type ThemePreference = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

const STORAGE_KEY = 'servizon.theme'

function systemTheme(): ResolvedTheme {
  if (typeof window === 'undefined') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function readStored(): ThemePreference {
  if (typeof window === 'undefined') return 'system'
  const stored = window.localStorage.getItem(STORAGE_KEY)
  return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system'
}

export function resolve(preference: ThemePreference): ResolvedTheme {
  return preference === 'system' ? systemTheme() : preference
}

/**
 * Write the theme to the document.
 *
 * The attribute goes on <html>, which is what the CSS selects on, and the
 * matching `color-scheme` makes the browser's own chrome — scrollbars, form
 * controls, the flash before first paint — follow along.
 */
export function applyTheme(theme: ResolvedTheme): void {
  document.documentElement.setAttribute('data-theme', theme)
}

interface ThemeState {
  preference: ThemePreference
  resolved: ResolvedTheme
  setPreference: (preference: ThemePreference) => void
  /** Called by the OS media-query listener when preference is "system". */
  syncSystem: () => void
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  preference: readStored(),
  resolved: resolve(readStored()),

  setPreference: (preference) => {
    const resolved = resolve(preference)
    window.localStorage.setItem(STORAGE_KEY, preference)
    applyTheme(resolved)
    set({ preference, resolved })
  },

  syncSystem: () => {
    if (get().preference !== 'system') return
    const resolved = systemTheme()
    applyTheme(resolved)
    set({ resolved })
  },
}))
