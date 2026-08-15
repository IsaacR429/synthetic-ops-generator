export type Industry = 'banking' | 'insurance' | 'retail'

export type Environment =
  | 'development'
  | 'staging'
  | 'production'

export type OperationalState =
  | 'initialized'
  | 'observing'
  | 'perturbed'
  | 'recovering'
  | 'completed'

export type RunStatus =
  | 'running'
  | 'completed'
  | 'failed'
  | 'stopped'

export type RunExecutionMode =
  | 'standard'
  | 'historical'

export type SourceDomain =
  | 'metric'
  | 'incident'
  | 'deployment'
  | 'change'

export type TargetScope =
  | 'business_stream'
  | 'service'
  | 'component'

export interface EnterpriseSummary {
  enterprise_id: string
  name: string
  industry: Industry
}

export interface ComponentSummary {
  component_id: string
  name: string
}

export interface ServiceSummary {
  service_id: string
  name: string
  components: ComponentSummary[]
}

export interface BusinessStreamSummary {
  stream_id: string
  name: string
  services: ServiceSummary[]
}

export interface EnterpriseDetail extends EnterpriseSummary {
  description: string
  business_streams: BusinessStreamSummary[]
}

export interface ScenarioSummary {
  scenario_id: string
  name: string
  description: string
  enterprise_id: string
}

export interface ScenarioTarget {
  enterprise_id: string
  target_scope: TargetScope
  business_stream_id: string
  service_id: string | null
  component_id: string | null
}

export interface ScenarioBehaviour {
  behaviour_id: string
  profile_id: string
  source_domain: SourceDomain
}

export interface ScenarioDetail extends ScenarioSummary {
  target: ScenarioTarget
  behaviours: ScenarioBehaviour[]
}

export interface HistoricalExecutionConfiguration {
  degradation_samples: number
  plateau_samples: number
  recovery_samples: number
}

export interface HistoricalExecutionCapability {
  supported: boolean
  unavailable_reason: string | null
  configuration: HistoricalExecutionConfiguration | null
}

export interface ScenarioCapabilities {
  scenario_id: string
  execution_modes: RunExecutionMode[]
  historical: HistoricalExecutionCapability
}

export interface StartRunRequest {
  scenario_id: string
  random_seed?: number
  execution_mode?: RunExecutionMode
  historical?: HistoricalExecutionConfiguration | null
}

export interface StartRunResponse {
  scenario_id: string
  run_id: string
  change_id: string

  status: RunStatus
  execution_mode: RunExecutionMode

  historical_configuration:
    | HistoricalExecutionConfiguration
    | null
}

export interface RunResponse {
  run_id: string
  scenario_id: string
  change_id: string

  status: RunStatus
  execution_mode: RunExecutionMode

  started_at: string
  completed_at: string | null

  current_state: OperationalState

  event_count: number
  validation_passed: boolean | null

  random_seed: number
  event_interval_seconds: number

  error_message: string | null

  historical_configuration:
    | HistoricalExecutionConfiguration
    | null
}

export interface StopRunResponse {
  run_id: string
  scenario_id: string

  status: RunStatus

  event_count: number
}

export interface ReplayRunResponse {
  run_id: string
  scenario_id: string

  replayed_event_count: number
}

export interface GeneratedEvent {
  event_id: string
  event_type: string
  schema_version: string

  event_time: string

  source_system: string

  scenario_id: string
  run_id: string

  chg_id: string | null

  business_stream: string | null
  service: string | null
  component: string | null
  environment: Environment | null

  sequence_number: number

  synthetic: boolean

  data: Record<string, unknown>
}

export interface RunEventsResponse {
  run_id: string
  retained_event_count: number

  events: GeneratedEvent[]
}

export interface HealthResponse {
  status: string
}
