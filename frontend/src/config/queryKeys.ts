import type { CenterQuery, SimulationRequest } from '@/types/api'

/**
 * Every React Query key in one place.
 *
 * Keys built inline drift: two call sites spell the same query slightly
 * differently and the cache silently splits in two.
 */
export const queryKeys = {
  health: ['health'] as const,
  metadata: ['metadata'] as const,
  levers: ['levers'] as const,
  filterOptions: ['filter-options'] as const,

  centers: (query: CenterQuery) => ['centers', query] as const,
  center: (centerId: string) => ['center', centerId] as const,
  snapshot: (centerId: string) => ['snapshot', centerId] as const,

  simulation: (request: SimulationRequest) =>
    ['simulation', request.center_id, request.tab, request.levers] as const,

  scenarios: (centerId: string) => ['scenarios', centerId] as const,
  comparison: (centerId: string, scenarioIds: string[]) =>
    ['comparison', centerId, [...scenarioIds].sort()] as const,
} as const

/** How often the client re-reads live data. Matches the server's cadence. */
export const REFRESH_INTERVAL_MS = 3 * 60 * 1000

/**
 * Slider settle time before a request goes out.
 *
 * The engine is authoritative on the server, so dragging fires a round trip.
 * On a local network that is a few milliseconds; the debounce exists to avoid
 * queueing sixty requests during a single drag, not to hide latency.
 */
export const SIMULATION_DEBOUNCE_MS = 120
