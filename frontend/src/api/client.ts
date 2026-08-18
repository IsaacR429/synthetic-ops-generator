import type {
  EnterpriseDetail,
  EnterpriseSummary,
  HealthResponse,
  ReplayRunResponse,
  RunEventQuery,
  RunEventsResponse,
  RunResponse,
  RunStatus,
  ScenarioCapabilities,
  ScenarioDetail,
  ScenarioSummary,
  StartRunRequest,
  StartRunResponse,
  StopRunResponse,
} from '../types/api'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function encodePathSegment(segment: string): string {
  return encodeURIComponent(segment)
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `/api${path}`
  const response = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`
    try {
      const errorJson = await response.json()
      if (errorJson && typeof errorJson.detail === 'string') {
        errorMessage = errorJson.detail
      }
    } catch {
      // Fallback to HTTP status message
    }
    throw new ApiError(response.status, errorMessage)
  }

  return response.json() as Promise<T>
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

export function listEnterprises(): Promise<EnterpriseSummary[]> {
  return request<EnterpriseSummary[]>('/enterprises')
}

export function getEnterprise(
  enterpriseId: string,
): Promise<EnterpriseDetail> {
  return request<EnterpriseDetail>(
    `/enterprises/${encodePathSegment(enterpriseId)}`,
  )
}

export function listScenarios(): Promise<ScenarioSummary[]> {
  return request<ScenarioSummary[]>('/scenarios')
}

export function getScenario(
  scenarioId: string,
): Promise<ScenarioDetail> {
  return request<ScenarioDetail>(
    `/scenarios/${encodePathSegment(scenarioId)}`,
  )
}

export function getScenarioCapabilities(
  scenarioId: string,
): Promise<ScenarioCapabilities> {
  return request<ScenarioCapabilities>(
    `/scenarios/${encodePathSegment(scenarioId)}/capabilities`,
  )
}

export function startRun(
  payload: StartRunRequest,
): Promise<StartRunResponse> {
  return request<StartRunResponse>('/runs', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listRuns(
  status?: RunStatus,
): Promise<RunResponse[]> {
  const path = status
    ? `/runs?status=${encodeURIComponent(status)}`
    : '/runs'

  return request<RunResponse[]>(path)
}

export function getRun(
  runId: string,
): Promise<RunResponse> {
  return request<RunResponse>(
    `/runs/${encodePathSegment(runId)}`,
  )
}

export function getRunEvents(
  runId: string,
  query?: RunEventQuery,
): Promise<RunEventsResponse> {
  const searchParams = new URLSearchParams()

  if (query?.source_domain) {
    searchParams.set(
      'source_domain',
      query.source_domain,
    )
  }

  if (query?.source_system) {
    searchParams.set(
      'source_system',
      query.source_system,
    )
  }

  if (query?.event_type) {
    searchParams.set(
      'event_type',
      query.event_type,
    )
  }

  if (query?.service) {
    searchParams.set(
      'service',
      query.service,
    )
  }

  if (query?.component) {
    searchParams.set(
      'component',
      query.component,
    )
  }

  if (
    query?.after_sequence_number !== undefined
  ) {
    searchParams.set(
      'after_sequence_number',
      String(query.after_sequence_number),
    )
  }

  if (query?.limit !== undefined) {
    searchParams.set(
      'limit',
      String(query.limit),
    )
  }

  const queryString = searchParams.toString()

  const path =
    `/runs/${encodePathSegment(runId)}/events` +
    (queryString ? `?${queryString}` : '')

  return request<RunEventsResponse>(path)
}

export function stopRun(
  runId: string,
): Promise<StopRunResponse> {
  return request<StopRunResponse>(
    `/runs/${encodePathSegment(runId)}/stop`,
    {
      method: 'POST',
    },
  )
}

export function replayRun(
  runId: string,
): Promise<ReplayRunResponse> {
  return request<ReplayRunResponse>(
    `/runs/${encodePathSegment(runId)}/replay`,
    {
      method: 'POST',
    },
  )
}
