import { apiClient } from './apiClient'
import type {
  AppMetadata,
  CenterQuery,
  FilterOptions,
  HealthStatus,
  LeverDefinition,
  ServiceCenter,
  Snapshot,
} from '@/types/api'

/** Drops empty filters so the query string stays clean and cache keys stable. */
function toParams(query: CenterQuery): Record<string, string> {
  const params: Record<string, string> = {}
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') {
      params[key] = String(value)
    }
  }
  return params
}

export async function fetchCenters(query: CenterQuery = {}): Promise<ServiceCenter[]> {
  const { data } = await apiClient.get<ServiceCenter[]>('/centers', { params: toParams(query) })
  return data
}

export async function fetchCenter(centerId: string): Promise<ServiceCenter> {
  const { data } = await apiClient.get<ServiceCenter>(`/centers/${centerId}`)
  return data
}

export async function fetchSnapshot(centerId: string): Promise<Snapshot> {
  const { data } = await apiClient.get<Snapshot>(`/centers/${centerId}/snapshot`)
  return data
}

export async function fetchFilterOptions(): Promise<FilterOptions> {
  const { data } = await apiClient.get<FilterOptions>('/centers/filters')
  return data
}

export async function fetchLevers(): Promise<LeverDefinition[]> {
  const { data } = await apiClient.get<LeverDefinition[]>('/levers')
  return data
}

export async function fetchMetadata(): Promise<AppMetadata> {
  const { data } = await apiClient.get<AppMetadata>('/metadata')
  return data
}

export async function fetchHealth(): Promise<HealthStatus> {
  const { data } = await apiClient.get<HealthStatus>('/health')
  return data
}
