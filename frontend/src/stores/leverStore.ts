/**
 * Scenario state — the levers the user has moved.
 *
 * Deliberately kept OUT of the React Query cache. Query data is server-owned
 * and gets replaced wholesale every time the background refresh lands; if the
 * scenario lived there, a refresh arriving mid-analysis would wipe out the
 * user's work. Here it is client-owned and survives any number of refreshes.
 *
 * The store tracks which levers the user actually touched. When a new baseline
 * arrives, untouched levers follow it — they are meant to mirror reality — and
 * touched levers stay exactly where they were put. That is what makes a
 * refresh feel like the data updating rather than the tool resetting.
 */

import { create } from 'zustand'
import type { LeverId, SimulationTab } from '@/types/api'

type LeverValues = Partial<Record<LeverId, number>>
type TouchedMap = Partial<Record<LeverId, true>>

/** How much of the observed history the trend charts show. */
export type TrendWindow = 7 | 14 | 28

interface LeverState {
  centerId: string | null
  tab: SimulationTab
  /** Current position of every lever, in display units. */
  values: LeverValues
  /** The live baseline, i.e. where each lever sits for this center today. */
  defaults: LeverValues
  /** Levers the user has explicitly moved. */
  touched: TouchedMap
  /** Set when a refresh changed the baseline under an active scenario. */
  baselineMoved: boolean
  /** Window applied to every trend chart, independent of any one center. */
  trendWindow: TrendWindow

  syncBaseline: (centerId: string, defaults: LeverValues) => void
  setLever: (id: LeverId, value: number) => void
  resetLever: (id: LeverId) => void
  resetAll: () => void
  applyScenario: (levers: LeverValues) => void
  setTab: (tab: SimulationTab) => void
  setTrendWindow: (window: TrendWindow) => void
  acknowledgeBaselineMove: () => void
}

function shallowEqual(a: LeverValues, b: LeverValues): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]) as Set<LeverId>
  for (const key of keys) {
    if (a[key] !== b[key]) return false
  }
  return true
}

export const useLeverStore = create<LeverState>((set, get) => ({
  centerId: null,
  tab: 'phone_center',
  values: {},
  defaults: {},
  touched: {},
  baselineMoved: false,
  trendWindow: 28,

  syncBaseline: (centerId, defaults) => {
    const state = get()

    // A different center is a genuinely new scenario.
    if (state.centerId !== centerId) {
      set({
        centerId,
        values: { ...defaults },
        defaults: { ...defaults },
        touched: {},
        baselineMoved: false,
      })
      return
    }

    if (shallowEqual(state.defaults, defaults)) return

    // Same center, new baseline: carry the user's edits across it.
    const values: LeverValues = { ...defaults }
    for (const key of Object.keys(state.touched) as LeverId[]) {
      const held = state.values[key]
      if (held !== undefined) values[key] = held
    }

    set({
      defaults: { ...defaults },
      values,
      baselineMoved: Object.keys(state.touched).length > 0,
    })
  },

  setLever: (id, value) =>
    set((state) => ({
      values: { ...state.values, [id]: value },
      touched: { ...state.touched, [id]: true },
    })),

  resetLever: (id) =>
    set((state) => {
      const touched = { ...state.touched }
      delete touched[id]
      const values = { ...state.values }
      const fallback = state.defaults[id]
      if (fallback === undefined) delete values[id]
      else values[id] = fallback
      return { values, touched }
    }),

  resetAll: () =>
    set((state) => ({ values: { ...state.defaults }, touched: {}, baselineMoved: false })),

  applyScenario: (levers) =>
    set((state) => {
      const values = { ...state.defaults, ...levers }
      const touched: TouchedMap = {}
      for (const key of Object.keys(levers) as LeverId[]) {
        if (levers[key] !== state.defaults[key]) touched[key] = true
      }
      return { values, touched }
    }),

  setTab: (tab) => set({ tab }),

  setTrendWindow: (trendWindow) => set({ trendWindow }),

  acknowledgeBaselineMove: () => set({ baselineMoved: false }),
}))

/** Levers whose value differs from the live baseline. */
export function useMovedLevers(): LeverId[] {
  return useLeverStore((state) =>
    (Object.keys(state.touched) as LeverId[]).filter(
      (id) => state.values[id] !== state.defaults[id],
    ),
  )
}

/**
 * Only the levers the user actually moved.
 *
 * Sending the untouched ones back would hand the server their *rounded*
 * display values in place of the precise baseline, which makes the model
 * report a change nobody asked for. The server guards against this too, but
 * the request should say what it means.
 */
export function selectMovedValues(state: LeverState): LeverValues {
  const moved: LeverValues = {}
  for (const id of Object.keys(state.touched) as LeverId[]) {
    const value = state.values[id]
    if (value !== undefined && value !== state.defaults[id]) moved[id] = value
  }
  return moved
}

export function useHasScenario(): boolean {
  return useLeverStore((state) =>
    (Object.keys(state.touched) as LeverId[]).some(
      (id) => state.values[id] !== state.defaults[id],
    ),
  )
}
