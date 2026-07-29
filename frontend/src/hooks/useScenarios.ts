import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '@/config/queryKeys'
import {
  compareScenarios,
  createScenario,
  deleteScenario,
  fetchScenarios,
  updateScenario,
} from '@/services/simulationApi'
import type { ScenarioCreate } from '@/types/api'

export function useScenarios(centerId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.scenarios(centerId ?? ''),
    queryFn: () => fetchScenarios(centerId as string),
    enabled: Boolean(centerId),
  })
}

export function useCreateScenario(centerId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ScenarioCreate) => createScenario(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.scenarios(centerId ?? '') })
    },
  })
}

export function useUpdateScenario(centerId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => updateScenario(id, { name }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.scenarios(centerId ?? '') })
    },
  })
}

export function useDeleteScenario(centerId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (scenarioId: string) => deleteScenario(scenarioId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.scenarios(centerId ?? '') })
    },
  })
}

export function useComparison(centerId: string | undefined, scenarioIds: string[]) {
  return useQuery({
    queryKey: queryKeys.comparison(centerId ?? '', scenarioIds),
    queryFn: () => compareScenarios(centerId as string, scenarioIds),
    enabled: Boolean(centerId) && scenarioIds.length > 0,
  })
}
