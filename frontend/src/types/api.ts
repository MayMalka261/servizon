/**
 * The API contract, mirroring `backend/app/domain/models.py`.
 *
 * When one side changes the other must change with it. Everything the server
 * can label — status names, districts, KPI titles — arrives already labelled,
 * so this file carries no translation table that could drift out of step.
 */

export type CenterType =
  | 'technical_support'
  | 'personnel'
  | 'logistics'
  | 'medical'
  | 'general_inquiries'

export type District = 'north' | 'center' | 'south' | 'jerusalem' | 'hq'

export type CenterStatus = 'active' | 'strained' | 'critical' | 'offline'

export type CenterSize = 'small' | 'medium' | 'large'

export type ChannelKind = 'phone' | 'web' | 'whatsapp' | 'email' | 'forms' | 'chat'

export type SimulationTab = 'digital_channels' | 'phone_center'

export type LeverId =
  | 'digital_adoption'
  | 'agent_ai'
  | 'customer_ai'
  | 'workforce_capacity'
  | 'working_hours'
  | 'sla_target'
  | 'abandonment_target'
  | 'average_handle_time'
  | 'first_call_resolution'
  | 'queue_size'
  | 'self_service_rate'
  | 'automation_level'
  | 'knowledge_base_quality'

/**
 * Mirrors the backend enum, grouped the same way.
 *
 * The two tabs answer different questions, so they share only the outcomes a
 * caller feels either way — satisfaction and first-contact resolution.
 */
export type KpiId =
  // phone center: the queue
  | 'incoming_calls'
  | 'average_waiting_time'
  | 'abandonment_rate'
  | 'sla'
  | 'occupancy'
  | 'utilization'
  | 'queue_length'
  | 'required_agents'
  | 'aht'
  | 'agent_ai_usage'
  // digital channels: deflection
  | 'digital_contacts'
  | 'aht_digital'
  | 'containment_rate'
  | 'escalated_contacts'
  | 'digital_adoption'
  | 'self_service_rate'
  | 'automation_level'
  | 'customer_ai_usage'
  // cross-channel outcomes
  | 'customer_satisfaction'
  | 'fcr'

/** How to render a value. `percent` values arrive as fractions in [0, 1]. */
export type KpiFormat = 'number' | 'percent' | 'duration'

/** Whether a rising value is good, bad, or neither. See the backend enum. */
export type Direction = 'higher_is_better' | 'lower_is_better' | 'neutral'

export type Severity = 'positive' | 'info' | 'warning' | 'critical'

export type LeverGroup = 'digital' | 'workforce' | 'ai' | 'quality' | 'targets'

export interface ServiceCenter {
  id: string
  name: string
  center_type: CenterType
  center_type_label: string
  district: District
  district_label: string
  status: CenterStatus
  status_label: string
  size: CenterSize
  size_label: string
  headcount: number
  channels: ChannelKind[]
  working_hours_per_day: number
  daily_contacts: number
  sla_pct: number
  abandonment_pct: number
}

export interface BaselineMetrics {
  daily_contacts: number
  peak_hour_contacts: number
  aht_sec: number
  agents_scheduled: number
  shrinkage: number
  working_hours_per_day: number
  digital_adoption: number
  self_service_rate: number
  automation_level: number
  agent_ai_usage: number
  customer_ai_usage: number
  knowledge_base_quality: number
  fcr: number
  sla_target_sec: number
  abandonment_target: number
  queue_size: number
  patience_sec: number
}

export interface KpiValue {
  id: KpiId
  label: string
  value: number
  format: KpiFormat
  direction: Direction
}

export interface TrendPoint {
  /** ISO date (YYYY-MM-DD), for range filtering. */
  date: string
  label: string
  value: number
}

/** The observed history a tab charts, one series per metric. */
export interface TrendSeries {
  volume: TrendPoint[]
  abandonment: TrendPoint[]
  aht: TrendPoint[]
}

export interface LeverBounds {
  min: number
  max: number
  step: number
}

export interface Snapshot {
  id: string
  center_id: string
  captured_at: string
  baseline: BaselineMetrics
  kpis: KpiValue[]
  /**
   * Observed daily history per tab, split by channel so each chart compares
   * its own history against its own projection.
   */
  trend: Record<SimulationTab, TrendSeries>
  lever_defaults: Partial<Record<LeverId, number>>
  lever_bounds: Partial<Record<LeverId, LeverBounds>>
}

export interface LeverDefinition {
  id: LeverId
  label: string
  tooltip: string
  unit: string
  min: number
  max: number
  step: number
  tabs: SimulationTab[]
  group: LeverGroup
  group_label: string
  dynamic_bounds: boolean
  parent: LeverId | null
}

export interface SimulatedKpi {
  id: KpiId
  label: string
  format: KpiFormat
  direction: Direction
  current: number
  scenario: number
  difference: number
  percentage: number
  /** -1 down, 0 flat, +1 up. */
  trend: -1 | 0 | 1
  is_improvement: boolean
}

export interface Recommendation {
  id: string
  severity: Severity
  title: string
  body: string
}

export interface WaterfallStep {
  lever: LeverId
  label: string
  contribution: number
}

export interface SimulationResult {
  center_id: string
  snapshot_id: string
  tab: SimulationTab
  computed_at: string
  /** Echoed back after clamping, so the UI can correct an out-of-range slider. */
  levers: Partial<Record<LeverId, number>>
  kpis: SimulatedKpi[]
  recommendations: Recommendation[]
  waterfall: WaterfallStep[]
  /** True when the background refresh moved the baseline mid-scenario. */
  snapshot_changed: boolean
}

export interface SimulationRequest {
  center_id: string
  tab: SimulationTab
  levers: Partial<Record<LeverId, number>>
  snapshot_id?: string | null
  /** ISO date (YYYY-MM-DD). Narrows "current" to this window of history. */
  date_from?: string | null
  date_to?: string | null
}

export interface Scenario {
  id: string
  center_id: string
  name: string
  tab: SimulationTab
  levers: Partial<Record<LeverId, number>>
  notes: string | null
  created_at: string
  updated_at: string
}

export interface ScenarioCreate {
  center_id: string
  name: string
  tab: SimulationTab
  levers: Partial<Record<LeverId, number>>
  notes?: string | null
}

export interface CompareColumn {
  scenario_id: string
  name: string
  kpis: SimulatedKpi[]
}

export interface CompareResult {
  center_id: string
  snapshot_id: string
  columns: CompareColumn[]
  winners: Partial<Record<KpiId, string>>
}

export interface FilterOption {
  value: string
  label: string
}

export interface FilterOptions {
  center_type: FilterOption[]
  district: FilterOption[]
  status: FilterOption[]
  size: FilterOption[]
}

export interface CenterQuery {
  search?: string
  center_type?: CenterType
  district?: District
  status?: CenterStatus
  size?: CenterSize
}

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'starting'
  data_source: string
  centers_loaded: number
  last_refresh: string | null
  next_refresh: string | null
  refresh_minutes: number
}

export interface AppMetadata {
  tabs: FilterOption[]
  lever_groups: FilterOption[]
  kpis: Array<{
    id: KpiId
    label: string
    format: KpiFormat
    direction: Direction
    tabs: SimulationTab[]
    order: number
  }>
}
