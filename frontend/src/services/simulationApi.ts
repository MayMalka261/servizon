import { apiClient } from './apiClient'
import type {
  CompareResult,
  Scenario,
  ScenarioCreate,
  SimulationRequest,
  SimulationResult,
} from '@/types/api'

export async function runSimulation(request: SimulationRequest): Promise<SimulationResult> {
  const { data } = await apiClient.post<SimulationResult>('/simulate', request)
  return data
}

export async function fetchScenarios(centerId: string): Promise<Scenario[]> {
  const { data } = await apiClient.get<Scenario[]>('/scenarios', {
    params: { center_id: centerId },
  })
  return data
}

export async function createScenario(payload: ScenarioCreate): Promise<Scenario> {
  const { data } = await apiClient.post<Scenario>('/scenarios', payload)
  return data
}

export async function updateScenario(
  scenarioId: string,
  payload: Partial<Pick<ScenarioCreate, 'name' | 'levers' | 'notes'>>,
): Promise<Scenario> {
  const { data } = await apiClient.patch<Scenario>(`/scenarios/${scenarioId}`, payload)
  return data
}

export async function deleteScenario(scenarioId: string): Promise<void> {
  await apiClient.delete(`/scenarios/${scenarioId}`)
}

export async function compareScenarios(
  centerId: string,
  scenarioIds: string[],
): Promise<CompareResult> {
  const { data } = await apiClient.post<CompareResult>('/scenarios/compare', {
    center_id: centerId,
    scenario_ids: scenarioIds,
  })
  return data
}
