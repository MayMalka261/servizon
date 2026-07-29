import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { queryKeys, REFRESH_INTERVAL_MS } from '@/config/queryKeys'
import {
  fetchCenter,
  fetchCenters,
  fetchFilterOptions,
  fetchHealth,
  fetchLevers,
} from '@/services/centersApi'
import type { CenterQuery } from '@/types/api'

export function useCenters(query: CenterQuery) {
  return useQuery({
    queryKey: queryKeys.centers(query),
    queryFn: () => fetchCenters(query),
    // Keeps the grid populated while a filter change is in flight, so the
    // list does not blank out on every keystroke.
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_INTERVAL_MS,
    refetchOnWindowFocus: false,
  })
}

export function useCenter(centerId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.center(centerId ?? ''),
    queryFn: () => fetchCenter(centerId as string),
    enabled: Boolean(centerId),
  })
}

export function useFilterOptions() {
  return useQuery({
    queryKey: queryKeys.filterOptions,
    queryFn: fetchFilterOptions,
    // Labels and enum values only change with a deployment.
    staleTime: Infinity,
  })
}

export function useLevers() {
  return useQuery({
    queryKey: queryKeys.levers,
    queryFn: fetchLevers,
    staleTime: Infinity,
  })
}

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: fetchHealth,
    refetchInterval: REFRESH_INTERVAL_MS,
    refetchOnWindowFocus: false,
  })
}
