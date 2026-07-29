/**
 * The live baseline and the scenario running against it.
 *
 * These are two separate subscriptions on purpose. `useSnapshot` polls the
 * server for reality; `useLeverStore` holds what the user is exploring. The
 * only place they meet is `syncBaseline`, which carries the user's edits
 * across a new baseline instead of discarding them.
 */

import { useEffect } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useShallow } from 'zustand/react/shallow'

import { queryKeys, REFRESH_INTERVAL_MS, SIMULATION_DEBOUNCE_MS } from '@/config/queryKeys'
import { fetchSnapshot } from '@/services/centersApi'
import { runSimulation } from '@/services/simulationApi'
import { selectMovedValues, useLeverStore } from '@/stores/leverStore'
import { useDebouncedValue } from './useDebouncedValue'
import type { SimulationRequest, SimulationTab } from '@/types/api'

export function useSnapshot(centerId: string | undefined) {
  const syncBaseline = useLeverStore((state) => state.syncBaseline)

  const query = useQuery({
    queryKey: queryKeys.snapshot(centerId ?? ''),
    queryFn: () => fetchSnapshot(centerId as string),
    enabled: Boolean(centerId),
    // Background refresh: no spinner, no unmount, no scenario reset.
    refetchInterval: REFRESH_INTERVAL_MS,
    refetchOnWindowFocus: false,
    placeholderData: keepPreviousData,
  })

  const snapshot = query.data

  useEffect(() => {
    if (snapshot) syncBaseline(snapshot.center_id, snapshot.lever_defaults)
  }, [snapshot, syncBaseline])

  return query
}

export function useSimulation(centerId: string | undefined, tab: SimulationTab) {
  // Only what the user moved — untouched levers must fall back to the precise
  // baseline on the server, not to their rounded display value.
  //
  // `useShallow` because the selector builds a new object every call; without
  // it, Zustand's reference equality re-renders on every store notification.
  const moved = useLeverStore(useShallow(selectMovedValues))
  const snapshotId = useLeverStore((state) => state.centerId)

  // Settle the drag before asking the server. The engine is authoritative
  // server-side, so there is exactly one implementation of the model.
  const settledValues = useDebouncedValue(moved, SIMULATION_DEBOUNCE_MS)

  const request: SimulationRequest = {
    center_id: centerId ?? '',
    tab,
    levers: settledValues,
  }

  return useQuery({
    queryKey: queryKeys.simulation(request),
    queryFn: () => runSimulation(request),
    enabled: Boolean(centerId) && Boolean(snapshotId),
    // Hold the previous result while the next is computed so KPI cards
    // animate from one value to the next instead of collapsing to a skeleton
    // on every slider movement.
    placeholderData: keepPreviousData,
    refetchOnWindowFocus: false,
    staleTime: 30_000,
  })
}
